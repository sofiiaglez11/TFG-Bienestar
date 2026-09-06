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

    def __init__(self, academic_agent, wellbeing_agent, general_agent, advisor_agent, orchestrator, mcp_client, db_service, analytics_service=None):
        self.academic_agent = academic_agent
        self.wellbeing_agent = wellbeing_agent
        self.general_agent = general_agent
        self.advisor_agent = advisor_agent
        self.orchestrator = orchestrator
        self.mcp_client = mcp_client
        self.db_service = db_service
        self.analytics_service = analytics_service
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

    # async def _advisor_node(self, state: GraphState) -> Dict[str, Any]:
    #     user_id = state.get("user_id", "")
    #     response_text = state.get("response_text", "")
    #     history_msgs = state.get("history_msgs", [])
    #     tools_raw = state.get("tools_raw", [])
    #     advisor_trigger = state.get("advisor_trigger", "")

    #     read_only_tools = [
    #         t for t in tools_raw
    #         if t["name"].startswith("get_") or t["name"].startswith("wb_get_") or t["name"].startswith("list_")
    #     ]

    #     self.advisor_agent.set_config(read_only_tools)
    #     self.advisor_agent.load_history(history_msgs)

    #     async def intercepted_tool_executor(name: str, arguments: dict):
    #         if name != "get_agent_capabilities":
    #             arguments["user_id"] = user_id
    #         return await self.mcp_client.call_tool(name, arguments)

    #     # Obtener el resumen estadístico del usuario en el backend si el servicio está disponible
    #     analytics_text = ""
    #     if self.analytics_service:
    #         try:
    #             analytics_data = await self.analytics_service.get_user_analytics(user_id, days=7)
    #             analytics_text = analytics_data.get("formatted_text", "")
    #         except Exception as e:
    #             print(f"[LANGGRAPH ADVISOR NODE] Error al obtener analítica: {e}", file=sys.stderr)

    #     prompt_advisor = (
    #         f"El agente principal ha generado la siguiente respuesta al usuario:\n"
    #         f"\"\"\"\n{response_text}\n\"\"\"\n\n"
    #         f"DATOS Y ESTADÍSTICAS DEL USUARIO (ÚLTIMOS 7 DÍAS):\n"
    #         f"{analytics_text}\n\n"
    #         f"MOTIVO DEL DISPARADOR: {advisor_trigger}\n\n"
    #         f"INSTRUCCIONES PARA EL CONSEJO:\n"
    #         f"1. Analiza los datos estadísticos reales presentados arriba (especialmente asignaturas desatendidas, baja concentración, duración corta por sesión, estudio nocturno de madrugada o síntomas de fatiga/mal descanso).\n"
    #         f"2. Si identificas algún punto crítico o patrón que mejorar, redacta una recomendación HIPER-PERSONALIZADA y ESPECIALIZADA. "
    #         f"CITA DATOS CONCRETOS Y ESPECÍFICOS DE LAS ESTADÍSTICAS DEL USUARIO (por ejemplo: nombra la asignatura concreta, las horas semanales dedicadas, la duración media por sesión o la nota media de concentración de esa asignatura).\n"
    #         f"3. Si los datos son equilibrados y no hay patrones preocupantes, puedes ofrecer un consejo breve de refuerzo positivo o responder 'NO_ADVICE'.\n"
    #         f"4. Redacta únicamente el texto de la recomendación de forma fluida y empática, introduciéndola con una frase de transición natural (ej: 'Por cierto, he estado revisando tus métricas y...', 'Un pequeño consejo sobre tu progreso:...').\n"
    #         f"5. NUNCA utilices separadores como '---' ni etiquetas div u HTML."
    #     )

    #     result = await self.advisor_agent.run_agentic_conversation(
    #         user_message=prompt_advisor,
    #         tool_executor=intercepted_tool_executor
    #     )

    #     advice_text = (result.text or "").strip()
    #     if advice_text and "NO_ADVICE" not in advice_text:
    #         updated_response = f"{response_text}\n\n{advice_text}"
    #         print(f"[LANGGRAPH ADVISOR NODE] Recomendación añadida (Trigger: {advisor_trigger}).", file=sys.stderr)
    #         return {"response_text": updated_response}

    #     print(f"[LANGGRAPH ADVISOR NODE] Sin recomendación (NO_ADVICE). Trigger: {advisor_trigger}.", file=sys.stderr)
    #     return {"response_text": response_text}


    async def _advisor_node(self, state: GraphState) -> Dict[str, Any]:
        user_id = state.get("user_id", "")
        response_text = state.get("response_text", "")
        history_msgs = state.get("history_msgs", [])
        # tools_raw = state.get("tools_raw", [])
        advisor_trigger = state.get("advisor_trigger", "")

        # read_only_tools = [
        #     t for t in tools_raw
        #     if t["name"].startswith("get_") or t["name"].startswith("wb_get_") or t["name"].startswith("list_")
        # ]

        self.advisor_agent.set_config([])
        self.advisor_agent.load_history(history_msgs)

        async def intercepted_tool_executor(name: str, arguments: dict):
            if name != "get_agent_capabilities":
                arguments["user_id"] = user_id
            return await self.mcp_client.call_tool(name, arguments)

        # Obtener analytics detalladas usando los tres métodos separados
        academic_text = ""
        wellbeing_text = ""
        patterns_text = ""

        if self.analytics_service:
            try:
                academic_data = await self.analytics_service.get_academic_analytics(user_id, days=7)
                wellbeing_data = await self.analytics_service.get_wellbeing_analytics(user_id, days=7)
                patterns_data = await self.analytics_service.get_patterns(user_id, days=7)

                # Formateamos cada sección por separado para que el LLM pueda razonar sobre cada una
                academic_text = self._format_academic(academic_data)
                wellbeing_text = self._format_wellbeing(wellbeing_data)
                patterns_text = self._format_patterns(patterns_data)

            except Exception as e:
                print(f"[LANGGRAPH ADVISOR NODE] Error al obtener analítica: {e}", file=sys.stderr)

        prompt_advisor = (
            f"El agente principal ha generado la siguiente respuesta al usuario:\n"
            f"\"\"\"\n{response_text}\n\"\"\"\n\n"
            f"MOTIVO DEL DISPARADOR: {advisor_trigger}\n\n"
            f"=== DATOS ACADÉMICOS (últimos 7 días) ===\n"
            f"{academic_text}\n\n"
            f"=== BIENESTAR (últimos 7 días) ===\n"
            f"{wellbeing_text}\n\n"
            f"=== PATRONES DETECTADOS ===\n"
            f"{patterns_text}\n\n"
            f"INSTRUCCIONES:\n"
            f"1. Analiza los datos de arriba buscando patrones concretos:\n"
            f"   - Asignaturas con pocas horas o baja concentración\n"
            f"   - Días de la semana con peor rendimiento o peor descanso\n"
            f"   - Sesiones nocturnas tardías\n"
            f"   - Desequilibrio entre asignaturas (una muy desatendida vs otra con muchas horas)\n"
            f"   - Relación entre mal descanso y baja concentración al día siguiente\n"
            f"2. Si encuentras un patrón relevante, redacta UNA recomendación concreta y empática.\n"
            f"   CITA DATOS ESPECÍFICOS: nombra la asignatura, el día, las horas concretas.\n"
            f"   Ejemplo correcto: 'He visto que los martes dedicas solo 20 min a Física y tu estado de ánimo ese día es de 2/5...'\n"
            f"   Ejemplo incorrecto: 'Deberías descansar más y estudiar mejor...'\n"
            f"3. Introduce la recomendación con una frase natural como:\n"
            f"   'Por cierto, revisando tus datos de esta semana...' o 'Un pequeño apunte sobre tu progreso:...'\n"
            f"4. Si los datos son equilibrados y no hay nada destacable, responde exactamente: NO_ADVICE\n"
            f"5. NUNCA uses separadores como '---', HTML ni markdown excesivo."
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

        print(f"[LANGGRAPH ADVISOR NODE] Sin recomendación. Trigger: {advisor_trigger}.", file=sys.stderr)
        return {"response_text": response_text}


    # Helpers de formateo dentro de LangGraphService

    def _format_academic(self, academic_data: list) -> str:
        if not academic_data:
            return "Sin datos académicos esta semana."
        lines = []
        for s in academic_data:
            lines.append(f"📚 {s['name']}:")
            lines.append(f"  - Horas totales: {s['total_hours_week']}h")
            lines.append(f"  - Duración media por sesión: {s['avg_session_duration_minutes']} min")
            if s.get("avg_concentration") is not None:
                lines.append(f"  - Concentración media: {s['avg_concentration']}/5")
            lines.append(f"  - Tareas completadas: {s['tasks_completed']} / pendientes: {s['tasks_pending']}")
            if s.get("grade") is not None:
                lines.append(f"  - Nota registrada: {s['grade']}/10")
            if s.get("sessions"):
                lines.append(f"  - Sesiones ({len(s['sessions'])}):")
                for sess in s["sessions"]:
                    conc = f", concentración {sess['concentration']}/5" if sess.get("concentration") else ""
                    lines.append(f"    · {sess['weekday']} {sess['date']}: {sess['duration_minutes']} min{conc}")
        return "\n".join(lines)


    def _format_wellbeing(self, wellbeing_data: dict) -> str:
        if not wellbeing_data:
            return "Sin datos de bienestar esta semana."
        lines = []
        lines.append(f"Sueño medio: {wellbeing_data.get('avg_sleep_hours', 'N/D')}h")
        if wellbeing_data.get("worst_day"):
            lines.append(f"Día con peor estado de ánimo: {wellbeing_data['worst_day']}")
        by_day = wellbeing_data.get("reports_by_weekday", {})
        if by_day:
            lines.append("Por día de la semana:")
            for day, vals in by_day.items():
                lines.append(f"  - {day}: sueño {vals['sleep']}h, ánimo {vals['mood']}/5, energía {vals['energy']}/5")
        return "\n".join(lines)


    def _format_patterns(self, patterns_data: dict) -> str:
        if not patterns_data:
            return "Sin patrones detectados."
        lines = []
        if patterns_data.get("most_productive_weekday"):
            lines.append(f"Día más productivo: {patterns_data['most_productive_weekday']}")
        if patterns_data.get("least_productive_weekday"):
            lines.append(f"Día menos productivo: {patterns_data['least_productive_weekday']}")
        hours = patterns_data.get("hours_by_weekday", {})
        if hours:
            lines.append("Horas por día:")
            for day, h in hours.items():
                lines.append(f"  - {day}: {h}h")
        late = patterns_data.get("late_night_sessions", [])
        if late:
            lines.append(f"Sesiones nocturnas (después de las 23h): {len(late)}")
            for s in late[:3]:
                lines.append(f"  - {s}")
        return "\n".join(lines)

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

