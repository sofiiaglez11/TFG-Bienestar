import sys
import re
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
    run_advisor: bool
    advisor_trigger: str
    periodic_trigger: bool
    response_text: str

class LangGraphService:
    ADVISOR_EVERY_N_MESSAGES = 5

    def __init__(self, academic_agent, wellbeing_agent, general_agent, advisor_agent, orchestrator, mcp_client, db_service):
        self.academic_agent = academic_agent
        self.wellbeing_agent = wellbeing_agent
        self.general_agent = general_agent
        self.advisor_agent = advisor_agent
        self.orchestrator = orchestrator
        self.mcp_client = mcp_client
        self.db_service = db_service
        # Cache en RAM: evita consultar MongoDB en cada mensaje.
        self._study_flow_cache: Dict[str, bool] = {}
        # Contador de mensajes por usuario para evaluación periódica del asesor
        self._user_message_counts: Dict[str, int] = {}

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
        builder.add_node("advisor", self._advisor_node)

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

        # Transiciones hacia el asesor o END
        builder.add_conditional_edges(
            "academic",
            self._check_advisor_path,
            {"advisor": "advisor", END: END}
        )
        builder.add_conditional_edges(
            "bienestar",
            self._check_advisor_path,
            {"advisor": "advisor", END: END}
        )
        builder.add_conditional_edges(
            "general",
            self._check_advisor_path,
            {"advisor": "advisor", END: END}
        )

        builder.add_edge("advisor", END)

        return builder

    async def _get_study_flow_state(self, user_id: str) -> bool:
        """Lectura desde cache RAM; consulta MongoDB solo si no está cacheado (p.ej. tras reinicio)."""
        if user_id not in self._study_flow_cache:
            self._study_flow_cache[user_id] = await self.db_service.get_study_flow_state(user_id)
        return self._study_flow_cache[user_id]

    async def _set_study_flow_state(self, user_id: str, state: bool, session_entry_id: str = None) -> None:
        """Actualiza cache en RAM y persiste en MongoDB."""
        self._study_flow_cache[user_id] = state          # inmediato, sin I/O
        await self.db_service.set_study_flow_state(user_id, state, session_entry_id=session_entry_id)  # persistencia

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

    def _check_advisor_path(self, state: GraphState) -> str:
        if state.get("run_advisor", False):
            return "advisor"
        return END

    async def _academic_node(self, state: GraphState) -> Dict[str, Any]:
        user_id = state.get("user_id", "")
        message_with_context = state.get("message_with_context", "")
        history_msgs = state.get("history_msgs", [])
        periodic_trigger = state.get("periodic_trigger", False)

        tools_raw = state.get("tools_raw", [])
        filtered_tools = [t for t in tools_raw if not t["name"].startswith("wb_") and t["name"] != "get_agent_capabilities"]
        
        self.academic_agent.set_config(filtered_tools)
        self.academic_agent.load_history(history_msgs)

        session_registered = False

        async def intercepted_tool_executor(name: str, arguments: dict):
            nonlocal session_registered
            if name != "get_agent_capabilities":
                arguments["user_id"] = user_id
            
            res = await self.mcp_client.call_tool(name, arguments)
            
            SESSION_TOOLS = {"stop_timer", "log_time_entry", "log_study_hours"}
            if name in SESSION_TOOLS:
                session_registered = True
                session_entry_id = None
                match = re.search(r"clockify_time_entry_id=([\w-]+)", str(res))
                if match:
                    session_entry_id = match.group(1)
                print(f"[LANGGRAPH ACADEMIC NODE] {name} detectado. ID sesión: {session_entry_id}. Activando in_study_report_flow = True", file=sys.stderr)
                await self._set_study_flow_state(user_id, True, session_entry_id=session_entry_id)

            return res

        result = await self.academic_agent.run_agentic_conversation(
            user_message=message_with_context,
            tool_executor=intercepted_tool_executor
        )

        run_adv = session_registered or periodic_trigger
        trigger_reason = "session_registered" if session_registered else ("periodic_counter" if periodic_trigger else "")

        return {
            "response_text": result.text,
            "run_advisor": run_adv,
            "advisor_trigger": trigger_reason
        }

    async def _bienestar_node(self, state: GraphState) -> Dict[str, Any]:
        user_id = state.get("user_id", "")
        message_with_context = state.get("message_with_context", "")
        history_msgs = state.get("history_msgs", [])
        in_study_report_flow = state.get("in_study_report_flow", False)
        periodic_trigger = state.get("periodic_trigger", False)

        tools_raw = state.get("tools_raw", [])
        filtered_tools = [t for t in tools_raw if t["name"].startswith("wb_")]
        
        self.wellbeing_agent.set_config(filtered_tools)
        self.wellbeing_agent.load_history(history_msgs)

        report_added = False

        async def intercepted_tool_executor(name: str, arguments: dict):
            nonlocal report_added
            if name != "get_agent_capabilities":
                arguments["user_id"] = user_id
            
            res = await self.mcp_client.call_tool(name, arguments)
            
            if name in {"wb_add_study_report", "wb_add_wellbeing_report"}:
                report_added = True
                if name == "wb_add_study_report":
                    print(f"[LANGGRAPH BIENESTAR NODE] wb_add_study_report ejecutado. Restableciendo in_study_report_flow = False", file=sys.stderr)
                    await self._set_study_flow_state(user_id, False)

            return res

        session_entry_id = await self.db_service.get_pending_session_entry_id(user_id)
        if session_entry_id:
            message_with_context = message_with_context + f"\n[DATOS_SESION: clockify_time_entry_id={session_entry_id}]"

        result = await self.wellbeing_agent.run_agentic_conversation(
            user_message=message_with_context,
            tool_executor=intercepted_tool_executor
        )

        if report_added:
            run_adv = True
            trigger_reason = "report_added"
        elif periodic_trigger:
            run_adv = True
            trigger_reason = "periodic_counter"
        else:
            run_adv = not in_study_report_flow
            trigger_reason = "wellbeing_signal" if run_adv else ""

        return {
            "response_text": result.text,
            "run_advisor": run_adv,
            "advisor_trigger": trigger_reason
        }

    async def _general_node(self, state: GraphState) -> Dict[str, Any]:
        user_id = state.get("user_id", "")
        message_with_context = state.get("message_with_context", "")
        history_msgs = state.get("history_msgs", [])
        periodic_trigger = state.get("periodic_trigger", False)

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

        return {
            "response_text": result.text,
            "run_advisor": periodic_trigger,
            "advisor_trigger": "periodic_counter" if periodic_trigger else ""
        }

    async def _advisor_node(self, state: GraphState) -> Dict[str, Any]:
        user_id = state.get("user_id", "")
        response_text = state.get("response_text", "")
        history_msgs = state.get("history_msgs", [])
        tools_raw = state.get("tools_raw", [])
        advisor_trigger = state.get("advisor_trigger", "")

        read_only_tools = [
            t for t in tools_raw
            if t["name"].startswith("get_") or t["name"].startswith("wb_get_") or t["name"].startswith("list_")
        ]

        self.advisor_agent.set_config(read_only_tools)
        self.advisor_agent.load_history(history_msgs)

        async def intercepted_tool_executor(name: str, arguments: dict):
            if name != "get_agent_capabilities":
                arguments["user_id"] = user_id
            return await self.mcp_client.call_tool(name, arguments)

        trigger_instruction = ""
        if advisor_trigger == "report_added":
            trigger_instruction = (
                "El usuario acaba de registrar un nuevo informe de estudio o bienestar. "
                "Usa tus herramientas (list_subjects, get_time_summary, get_time_entries, wb_get_study_reports, wb_get_wellbeing_report, wb_get_wellbeing_trends) "
                "para analizar si hay un desequilibrio de estudio entre asignaturas, sesiones en la madrugada, o si el último informe muestra fatiga o mal descanso.\n"
            )
        elif advisor_trigger == "periodic_counter":
            trigger_instruction = (
                "Se ha alcanzado la revisión periódica del progreso del usuario. "
                "Ejecuta tus herramientas de lectura (list_subjects, get_time_summary, get_time_entries, wb_get_study_reports, wb_get_wellbeing_trends) "
                "para detectar si alguna asignatura activa está abandonada (0 horas), si estudia a altas horas de la madrugada, si las sesiones son muy dispersas o si arrastra fatiga acumulada.\n"
            )
        elif advisor_trigger == "session_registered":
            trigger_instruction = (
                "El usuario acaba de registrar/finalizar una sesión de estudio. "
                "Consulta get_time_entries y list_subjects para verificar el horario de la sesión (ej. si fue de madrugada) y la distribución del tiempo por asignatura, evaluando si es conveniente ofrecer una recomendación.\n"
            )
        else:
            trigger_instruction = (
                "Consulta los datos de asignaturas y tiempos (list_subjects, get_time_summary, get_time_entries) e informes de bienestar (wb_get_wellbeing_trends) "
                "para verificar si hay desequilibrios entre asignaturas, estudio nocturno o signos de estrés.\n"
            )

        prompt_advisor = (
            f"El agente principal ha generado la siguiente respuesta al usuario:\n"
            f"\"\"\"\n{response_text}\n\"\"\"\n\n"
            f"{trigger_instruction}"
            f"Analiza si con los datos recopilados del usuario y la respuesta dada es conveniente ofrecer una recomendación adicional. "
            f"Si decides hacer una sugerencia, redacta únicamente el texto de la recomendación de forma fluida y natural, "
            f"introduciéndola con una frase de transición adecuada (ej: 'Por cierto, te sugiero...', 'Como consejo rápido...', 'Un pequeño consejo:...'). "
            f"NUNCA utilices separadores como '---' ni etiquetas div. "
            # f"Si no procede o no hay patrones preocupantes en sus datos, responde exactamente 'NO_ADVICE'."
        )

        result = await self.advisor_agent.run_agentic_conversation(
            user_message=prompt_advisor,
            tool_executor=intercepted_tool_executor
        )

        advice_text = (result.text or "").strip()
        if advice_text and "NO_ADVICE" not in advice_text:
            updated_response = f"{response_text}\n\n{advice_text}"
            print(f"[LANGGRAPH ADVISOR NODE] Recomendación añadida (Trigger: {advisor_trigger}).", file=sys.stderr)
            return {"response_text": updated_response}

        print(f"[LANGGRAPH ADVISOR NODE] Sin recomendación (NO_ADVICE). Trigger: {advisor_trigger}.", file=sys.stderr)
        return {"response_text": response_text}

    async def run(self, user_id: str, user_message: str, message_with_context: str, history_msgs: list, tools_raw: list) -> dict:
        # Incrementar contador de mensajes del usuario
        current_count = self._user_message_counts.get(user_id, 0) + 1
        self._user_message_counts[user_id] = current_count
        is_periodic_turn = (current_count % self.ADVISOR_EVERY_N_MESSAGES == 0)

        if is_periodic_turn:
            print(f"[LANGGRAPH SERVICE] Turno periódico alcanzado para {user_id} (mensaje #{current_count}). Activando periodic_trigger.", file=sys.stderr)

        inputs = {
            "user_id": user_id,
            "user_message": user_message,
            "message_with_context": message_with_context,
            "history_msgs": history_msgs,
            "tools_raw": tools_raw,
            "in_study_report_flow": await self._get_study_flow_state(user_id),
            "run_advisor": False,
            "advisor_trigger": "",
            "periodic_trigger": is_periodic_turn
        }

        final_state = await self.app.ainvoke(inputs)

        return {
            "response": final_state.get("response_text", ""),
            "agent_used": final_state.get("active_domain", "ACADEMICO")
        }

