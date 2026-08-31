import sys
from typing import TypedDict, Optional, List, Dict, Any
from langgraph.graph import StateGraph, START, END

class GraphState(TypedDict):
    user_id: str
    user_message: str
    history_msgs: List[Dict[str, Any]]
    message_with_context: str
    tools_raw: List[Dict[str, Any]]
    active_domain: str
    in_study_report_flow: bool
    response_text: str

class LangGraphService:
    def __init__(self, academic_agent, wellbeing_agent, general_agent, orchestrator, mcp_client, db_service):
        self.academic_agent = academic_agent
        self.wellbeing_agent = wellbeing_agent
        self.general_agent = general_agent
        self.orchestrator = orchestrator
        self.mcp_client = mcp_client
        self.db_service = db_service
        # Cache en RAM: evita consultar MongoDB en cada mensaje.
        # Si el servidor se reinicia, se recarga desde MongoDB en el primer acceso.
        self._study_flow_cache: Dict[str, bool] = {}

        # Construir el grafo (sin checkpointer: el historial lo gestiona MongoDB)
        self.workflow = self._build_graph()
        self.app = self.workflow.compile()

    def _build_graph(self) -> StateGraph:
        builder = StateGraph(GraphState)

        # Nodos
        builder.add_node("router", self._router_node)
        builder.add_node("academic", self._academic_node)
        builder.add_node("bienestar", self._bienestar_node)
        builder.add_node("general", self._general_node)

        # Transición inicial
        builder.add_edge(START, "router")

        # Transición condicional desde el router
        builder.add_conditional_edges(
            "router",
            self._select_agent_path,
            {
                "BIENESTAR": "bienestar",
                "ACADEMICO": "academic",
                "GENERAL": "general"
            }
        )

        # Transiciones de salida a END
        builder.add_edge("academic", END)
        builder.add_edge("bienestar", END)
        builder.add_edge("general", END)

        return builder

    async def _get_study_flow_state(self, user_id: str) -> bool:
        """Lectura desde cache RAM; consulta MongoDB solo si no está cacheado (p.ej. tras reinicio)."""
        if user_id not in self._study_flow_cache:
            self._study_flow_cache[user_id] = await self.db_service.get_study_flow_state(user_id)
        return self._study_flow_cache[user_id]

    async def _set_study_flow_state(self, user_id: str, state: bool) -> None:
        """Actualiza cache en RAM y persiste en MongoDB."""
        self._study_flow_cache[user_id] = state          # inmediato, sin I/O
        await self.db_service.set_study_flow_state(user_id, state)  # persistencia

    async def _router_node(self, state: GraphState) -> Dict[str, Any]:
        user_id = state.get("user_id", "")
        message = state.get("user_message", "")
        history_msgs = state.get("history_msgs", [])

        # Si estamos en flujo de informe de estudio para este usuario, bloquear en BIENESTAR
        in_flow = await self._get_study_flow_state(user_id)
        if in_flow:
            print(f"[LANGGRAPH ROUTER] Estado in_study_report_flow=True para user_id={user_id}. Forzando BIENESTAR.", file=sys.stderr)
            return {"active_domain": "BIENESTAR", "in_study_report_flow": True}

        # De lo contrario, clasificar intención con el orquestador
        domain = await self.orchestrator.route_intent(message, history_msgs)
        print(f"[LANGGRAPH ROUTER] Dominio clasificado: {domain}", file=sys.stderr)
        return {"active_domain": domain, "in_study_report_flow": False}

    def _select_agent_path(self, state: GraphState) -> str:
        return state.get("active_domain", "ACADEMICO")

    async def _academic_node(self, state: GraphState) -> Dict[str, Any]:
        user_id = state.get("user_id", "")
        message_with_context = state.get("message_with_context", "")
        history_msgs = state.get("history_msgs", [])

        tools_raw = state.get("tools_raw", [])
        filtered_tools = [t for t in tools_raw if not t["name"].startswith("wb_") and t["name"] != "get_agent_capabilities"]
        
        self.academic_agent.set_config(filtered_tools)
        self.academic_agent.load_history(history_msgs)

        async def intercepted_tool_executor(name: str, arguments: dict):
            if name != "get_agent_capabilities":
                arguments["user_id"] = user_id
            
            res = await self.mcp_client.call_tool(name, arguments)
            
            # Si el agente académico registró una sesión de estudio (de cualquier forma),
            # activar el flujo del informe de sesión para que lo recoja el agente de bienestar.
            SESSION_TOOLS = {"stop_timer", "log_time_entry", "log_study_hours"}
            if name in SESSION_TOOLS:
                print(f"[LANGGRAPH ACADEMIC NODE] {name} detectado. Activando in_study_report_flow = True", file=sys.stderr)
                await self._set_study_flow_state(user_id, True)

            return res

        result = await self.academic_agent.run_agentic_conversation(
            user_message=message_with_context,
            tool_executor=intercepted_tool_executor
        )

        return {"response_text": result.text}

    async def _bienestar_node(self, state: GraphState) -> Dict[str, Any]:
        user_id = state.get("user_id", "")
        message_with_context = state.get("message_with_context", "")
        history_msgs = state.get("history_msgs", [])

        tools_raw = state.get("tools_raw", [])
        filtered_tools = [t for t in tools_raw if t["name"].startswith("wb_")]
        
        self.wellbeing_agent.set_config(filtered_tools)
        self.wellbeing_agent.load_history(history_msgs)

        async def intercepted_tool_executor(name: str, arguments: dict):
            if name != "get_agent_capabilities":
                arguments["user_id"] = user_id
            
            res = await self.mcp_client.call_tool(name, arguments)
            
            # Si el agente de bienestar guardó el informe de estudio, desactivar el flujo
            if name == "wb_add_study_report":
                print(f"[LANGGRAPH BIENESTAR NODE] wb_add_study_report ejecutado. Restableciendo in_study_report_flow = False", file=sys.stderr)
                await self._set_study_flow_state(user_id, False)

            return res

        result = await self.wellbeing_agent.run_agentic_conversation(
            user_message=message_with_context,
            tool_executor=intercepted_tool_executor
        )

        return {"response_text": result.text}

    async def _general_node(self, state: GraphState) -> Dict[str, Any]:
        user_id = state.get("user_id", "")
        message_with_context = state.get("message_with_context", "")
        history_msgs = state.get("history_msgs", [])

        tools_raw = state.get("tools_raw", [])
        filtered_tools = [t for t in tools_raw if t["name"] == "get_agent_capabilities"]
        
        self.general_agent.set_config(filtered_tools)
        self.general_agent.load_history(history_msgs)

        async def intercepted_tool_executor(name: str, arguments: dict):
            if name != "get_agent_capabilities":
                arguments["user_id"] = user_id
            return await self.mcp_client.call_tool(name, arguments)

        result = await self.general_agent.run_agentic_conversation(
            user_message=message_with_context,
            tool_executor=intercepted_tool_executor
        )

        return {"response_text": result.text}

    async def run(self, user_id: str, user_message: str, message_with_context: str, history_msgs: list, tools_raw: list) -> dict:
        inputs = {
            "user_id": user_id,
            "user_message": user_message,
            "message_with_context": message_with_context,
            "history_msgs": history_msgs,
            "tools_raw": tools_raw,
            "in_study_report_flow": await self._get_study_flow_state(user_id)
        }

        final_state = await self.app.ainvoke(inputs)

        return {
            "response": final_state.get("response_text", ""),
            "agent_used": final_state.get("active_domain", "ACADEMICO")
        }
