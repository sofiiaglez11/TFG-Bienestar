import sys
import re
import asyncio
from datetime import datetime, timezone
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
    event_type: Optional[str]
    proactive_prompt: Optional[str]

class LangGraphService:
    ADVISOR_EVERY_N_MESSAGES = 40

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
        builder.add_node("onboarding", self._onboarding_node)
        builder.add_node("login_greeting", self._login_greeting_node)

        # Transición inicial condicional: evalúa si es mensaje normal o saludo proactivo
        builder.add_conditional_edges(
            START,
            self._select_start_path,
            {
                "USER_MESSAGE": "router",
                "ONBOARDING": "onboarding",
                "LOGIN_GREETING": "login_greeting"
            }
        )

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
        builder.add_edge("onboarding", END)
        builder.add_edge("login_greeting", END)

        return builder

    def _select_start_path(self, state: GraphState) -> str:
        return state.get("event_type") or "USER_MESSAGE"

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

    async def _onboarding_node(self, state: GraphState) -> Dict[str, Any]:
        user_id = state.get("user_id", "")
        proactive_prompt = state.get("proactive_prompt", "")
        
        self.general_agent.set_config([])
        result = await self.general_agent.run_agentic_conversation(
            user_message=proactive_prompt,
            tool_executor=None
        )
        return {
            "response_text": result.text,
            "active_domain": "GENERAL",
            "run_advisor": False
        }

    async def _login_greeting_node(self, state: GraphState) -> Dict[str, Any]:
        user_id = state.get("user_id", "")
        proactive_prompt = state.get("proactive_prompt", "")

        self.wellbeing_agent.set_config([])
        result = await self.wellbeing_agent.run_agentic_conversation(
            user_message=proactive_prompt,
            tool_executor=None
        )
        return {
            "response_text": result.text,
            "active_domain": "BIENESTAR",
            "run_advisor": False
        }

    async def _advisor_node(self, state: GraphState) -> Dict[str, Any]:
        user_id = state.get("user_id", "")
        response_text = state.get("response_text", "")
        history_msgs = state.get("history_msgs", [])
        advisor_trigger = state.get("advisor_trigger", "")

        self.advisor_agent.set_config([])
        self.advisor_agent.load_history(history_msgs)

        async def intercepted_tool_executor(name: str, arguments: dict):
            if name != "get_agent_capabilities":
                arguments["user_id"] = user_id
            return await self.mcp_client.call_tool(name, arguments)

        # Extraer sugerencias/recomendaciones previas dadas por el asistente en esta sesión
        past_advice_text = self._extract_past_advice(history_msgs)

        # Comprobar si se ha hablado de tareas en la sesión actual
        tasks_discussed = self._were_tasks_discussed(history_msgs)
        tasks_status_note = (
            "SÍ (ya se ha mencionado el tema de tareas en la sesión)."
            if tasks_discussed else
            "NO (¡IMPORTANTE: Si no se ha hablado de tareas hoy y el estudiante tiene tareas pendientes o activas, pregúntale amigablemente cómo las lleva o si quiere ponerse con alguna de ellas!)."
        )
        academic_text = ""
        wellbeing_text = ""
        patterns_text = ""

        if self.analytics_service:
            try:
                academic_data = await self.analytics_service.get_academic_analytics(user_id, days=7)
                wellbeing_data = await self.analytics_service.get_wellbeing_analytics(user_id, days=7)
                patterns_data = await self.analytics_service.get_patterns(user_id, days=7)

                academic_text = self._format_academic(academic_data)
                wellbeing_text = self._format_wellbeing(wellbeing_data)
                patterns_text = self._format_patterns(patterns_data)

            except Exception as e:
                print(f"[LANGGRAPH ADVISOR NODE] Error al obtener analítica: {e}", file=sys.stderr)

        prompt_advisor = (
            f"El agente principal ha generado la siguiente respuesta al usuario:\n"
            f"\"\"\"\n{response_text}\n\"\"\"\n\n"
            f"Cuando generes la respuesta, no incluyas la respuesta del agente principal, solo da la recomendación.\n\n"
            f"MOTIVO DEL DISPARADOR: {advisor_trigger}\n\n"
            f"=== SEGUIMIENTO DE TAREAS HOY ===\n"
            f"¿Se ha hablado de tareas en esta conversación hoy?: {tasks_status_note}\n\n"
            f"=== CONSEJOS / RECOMENDACIONES DADAS ANTERIORMENTE AL USUARIO EN ESTA SESIÓN ===\n"
            f"{past_advice_text}\n\n"
            f"=== DATOS ACADÉMICOS (últimos 7 días) ===\n"
            f"{academic_text}\n\n"
            f"=== BIENESTAR (últimos 7 días) ===\n"
            f"{wellbeing_text}\n\n"
            f"=== PATRONES DETECTADOS ===\n"
            f"{patterns_text}\n\n"
            f"INSTRUCCIONES:\n"
            f"1. Analiza los datos de arriba buscando patrones concretos:\n"
            f"   - Si NO se ha hablado de tareas hoy y hay tareas pendientes o activas, hazle una pregunta amigable sobre su avance o estado.\n"
            f"   - Asignaturas con pocas horas o baja concentración\n"
            f"   - Días de la semana con peor rendimiento o peor descanso\n"
            f"   - Sesiones nocturnas tardías\n"
            f"   - Desequilibrio entre asignaturas (una muy desatendida vs otra con muchas horas)\n"
            f"   - Relación entre mal descanso y baja concentración al día siguiente\n"
            f"2. REGLA ESTRICTA DE NO REPETICIÓN:\n"
            f"   - Revisa la lista de 'CONSEJOS / RECOMENDACIONES DADAS ANTERIORMENTE' arriba.\n"
            f"   - Si el consejo o patrón que vas a sugerir ES EL MISMO o MUY SIMILAR a uno que ya le diste anteriormente:\n"
            f"     a) Si no hay novedad sustancial, responde exactamente: NO_ADVICE (no repitas el mismo consejo).\n"
            f"     b) Si la situación es urgente y exige volver a mencionarlo, NO des la explicación larga; RESÚMELA AL MÁXIMO en 1 sola frase corta usando una muletilla como 'Como te comenté antes...' o 'Como pequeña sugerencia rápida...'.\n"
            f"3. Si encuentras un patrón NUEVO y relevante, redacta UNA recomendación concreta y empática citando datos específicos (asignatura, día, horas).\n"
            f"4. Introduce la recomendación con una frase natural como:\n"
            f"   'Por cierto, revisando tus datos de esta semana...' o 'Un pequeño apunte sobre tu progreso:...'\n"
            f"5. Si los datos son equilibrados y no hay nada destacable, responde exactamente: NO_ADVICE\n"
            f"6. NUNCA uses separadores como '---', HTML ni markdown excesivo."
        )


        result = await self.advisor_agent.run_agentic_conversation(
            user_message=prompt_advisor,
            tool_executor=intercepted_tool_executor
        )

        advice_text = (result.text or "").strip()
        if advice_text and "NO_ADVICE" not in advice_text:
            updated_response = f"{response_text}\n\n{advice_text}"
            active_dom = state.get("active_domain", "ACADEMICO")

            print(f"[LANGGRAPH ADVISOR NODE] Recomendación añadida (Trigger: {advisor_trigger}).", file=sys.stderr)
            return {
                "response_text": updated_response,
                "active_domain": f"{active_dom}+ASESOR"
            }

        print(f"[LANGGRAPH ADVISOR NODE] Sin recomendación. Trigger: {advisor_trigger}.", file=sys.stderr)
        return {"response_text": response_text}

    # Helpers de extracción de contexto de la sesión
    TASK_TOOLS = {"get_tasks", "add_task", "edit_task", "complete_task", "mark_task_active", "delete_task", "set_task_hierarchy", "start_timer", "stop_timer"}

    def _extract_past_advice(self, history_msgs: List[Dict[str, Any]]) -> str:
        """Extrae de forma limpia los consejos o recomendaciones previas generadas por el asesor en la sesión."""
        past_advice = []
        for msg in history_msgs:
            if msg.get("role") != "assistant":
                continue
            agent_used = msg.get("agent_used", "")
            content = str(msg.get("content", "")).strip()
            if not content:
                continue

            # Si la respuesta fue generada o enriquecida por el Asesor
            if agent_used and ("ASESOR" in agent_used or "ADVISOR" in agent_used):
                parts = content.split("\n\n")
                advice_part = parts[-1] if len(parts) > 1 else content
                past_advice.append(advice_part)

        recent = past_advice[-5:]
        if not recent:
            return "Ninguno todavía en esta sesión."
        return "\n".join([f"• \"{adv}\"" for adv in recent])

    def _were_tasks_discussed(self, history_msgs: List[Dict[str, Any]]) -> bool:
        """Comprueba si se han ejecutado herramientas relativas a tareas o cronómetros en la sesión."""
        for msg in history_msgs:
            tool_calls = msg.get("tool_calls", [])
            for call in tool_calls:
                name = call.get("name", "") if isinstance(call, dict) else str(call)
                if any(tk in name for tk in ["task", "timer"]):
                    return True
            content = str(msg.get("content", ""))
            if any(tool_name in content for tool_name in self.TASK_TOOLS):
                return True
        return False

    # Helpers de formateo dentro de LangGraphService

    def _format_academic(self, academic_data: list) -> str:
        if not academic_data:
            return "Sin datos académicos esta semana."
        lines = []
        for s in academic_data:
            lines.append(f"ASIGNATURA: {s['name']}:")
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

        plan = patterns_data.get("study_plan_progress", {})
        if plan and plan.get("has_active_plan"):
            lines.append(f"\n PLAN DE ESTUDIO ACTIVO ('{plan.get('plan_title')}'):")
            lines.append(f"  - Progreso global: {plan.get('overall_progress_pct')}% ({plan.get('total_actual_hours')}h estudiadas / {plan.get('total_planned_hours')}h planificadas)")
            for subj, pdata in plan.get("progress_by_subject", {}).items():
                lines.append(f"  - {subj}: {pdata['actual_hours']}h reales / {pdata['planned_hours']}h planificadas ({pdata['progress_pct']}%)")

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
            "periodic_trigger": is_periodic_turn,
            "event_type": "USER_MESSAGE",
            "proactive_prompt": None
        }

        final_state = await self.app.ainvoke(inputs)

        return {
            "response": final_state.get("response_text", ""),
            "agent_used": final_state.get("active_domain", "ACADEMICO")
        }

    async def run_proactive_greeting(self, user_id: str, is_force_onboarding: bool = False) -> dict:
        """
        Ejecuta el saludo proactivo a través del grafo de LangGraph:
        - Si es nuevo usuario: ejecuta onboarding_node (GENERAL) explicando capacidades.
        - Si es usuario recurrente: ejecuta login_greeting_node (BIENESTAR) con repaso breve de sesión,
          plan de estudio activo y chequeo de horas de sueño diario.
        """
        user = await self.db_service.get_user_by_id(user_id)
        user_name = (user.get("name") if user else None) or "estudiante"

        history_msgs = await self.db_service.get_history(user_id=user_id, limit=5)
        subjects = await self.db_service.get_subjects_by_user(user_id)

        is_new_user = is_force_onboarding or (len(history_msgs) == 0 and len(subjects) == 0)

        if is_new_user:
            event_type = "ONBOARDING"
            proactive_prompt = (
                f"El usuario {user_name} acaba de registrarse e ingresar por primera vez a la plataforma.\n"
                "Dale una cálida, entusiasta y cercana bienvenida llamándole por su nombre.\n"
                "Explícale de manera clara, amigable y bien estructurada (usa viñetas o puntos breves) "
                "las funcionalidades principales con las que este chat le ayudará en su día a día como estudiante:\n"
                "• **Gestión de Asignaturas y Tareas**: Organización de materias, tareas pendientes, fechas límite de entregas y exámenes.\n"
                "• **Temporizador y Registro de Estudio**: Medición del tiempo real de estudio con cronómetro en directo e integración con Clockify.\n"
                "• **Planes de Estudio Personalizados**: Creación y seguimiento de planificaciones semanales adaptadas a sus objetivos y ritmo.\n"
                "• **Cuidado de tu Bienestar**: Registro de horas de sueño, descansos, niveles de estrés y fatiga tras cada sesión para mantener un equilibrio saludable.\n"
                "• **Métricas y Consejos Inteligentes**: Análisis de rendimiento y recomendaciones proactivas para optimizar su estudio sin agotarse.\n\n"
                "Termina el mensaje con una llamada a la acción clara e interactiva para empezar, sugiriendo registrar sus asignaturas actuales. Por ejemplo:\n"
                "'Para empezar a organizarnos, ¿qué te parece si registramos tus asignaturas? Cuéntame qué asignaturas estás cursando este cuatrimestre y las configuramos juntos.'\n\n"
                "REGLA ESTRICTA: En este primer saludo de onboarding NO le preguntes cuántas horas ha dormido hoy ni le pidas informe de bienestar todavía; el foco absoluto es presentarle la plataforma e invitarle a registrar sus asignaturas."
            )
        else:
            event_type = "LOGIN_GREETING"
            
            try:
                from zoneinfo import ZoneInfo
                today_str = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d")
            except Exception:
                today_str = datetime.now().strftime("%Y-%m-%d")

            has_today_sleep = False
            latest_wellbeing = None
            try:
                has_today_sleep = await self.db_service.has_wellbeing_report_for_date(user_id, today_str)
                latest_wellbeing = await self.db_service.get_latest_wellbeing_report(user_id)
            except Exception as e:
                print(f"[LANGGRAPH GREETING] Error comprobando bienestar: {e}", file=sys.stderr)

            session_parts = []
            try:
                study_reports = await self.db_service.get_study_reports_by_user(user_id, limit=1)
                if study_reports and len(study_reports) > 0:
                    sr = study_reports[0]
                    subj = sr.get("subject_name") or "una sesión de estudio"
                    quality = sr.get("study_quality")
                    goals = sr.get("goals_achieved")
                    quality_str = f"calidad {quality}/5" if quality else ""
                    goals_str = "habiendo cumplido tus objetivos" if goals is True else ("con objetivos pendientes" if goals is False else "")
                    details = [p for p in [quality_str, goals_str] if p]
                    details_text = f" ({', '.join(details)})" if details else ""
                    session_parts.append(f"Última sesión de estudio registrada: en {subj}{details_text}.")
            except Exception as e:
                print(f"[LANGGRAPH GREETING] Error obteniendo study_reports: {e}", file=sys.stderr)

            if not session_parts and self.analytics_service:
                try:
                    cs = await self.analytics_service._get_user_clockify_service(user_id)
                    if cs:
                        latest_entry = await asyncio.to_thread(cs.get_latest_time_entry)
                        if latest_entry:
                            desc = latest_entry.get("description") or "Estudio"
                            dur_str = latest_entry.get("timeInterval", {}).get("duration", "")
                            dur_mins = self.analytics_service._parse_iso_duration_minutes(dur_str) if dur_str else 0
                            dur_text = f"{int(dur_mins // 60)}h {int(dur_mins % 60)}m" if dur_mins >= 60 else f"{int(dur_mins)} minutos"
                            session_parts.append(f"Última sesión registrada en Clockify: '{desc}' ({dur_text}).")
                except Exception as e:
                    print(f"[LANGGRAPH GREETING] Error Clockify latest entry: {e}", file=sys.stderr)

            session_summary = " ".join(session_parts)

            login_prompt = (
                f"El usuario {user_name} acaba de iniciar sesión en la plataforma.\n"
                "Instrucciones para el saludo:\n"
                "1. Salúdale de forma cálida, cercana y motivadora por su nombre.\n"
            )

            if session_summary:
                login_prompt += (
                    f"2. Haz un repaso MUY BREVE (máximo 1 o 2 frases) de su última sesión o actividad reciente:\n"
                    f"   {session_summary}\n"
                )
            else:
                login_prompt += "2. Dale la bienvenida de vuelta a su espacio de estudio.\n"

            if not has_today_sleep:
                login_prompt += (
                    f"3. Hoy ({today_str}) AÚN NO ha registrado sus horas de sueño ni su reporte de bienestar diario. "
                    "Aprovecha este saludo para preguntarle de forma natural y empática cómo ha descansado esta noche, "
                    "cuántas horas ha dormido y cómo se siente de ánimos para empezar el día, para así dejar listo su informe de bienestar.\n"
                )
            else:
                sleep_hrs = latest_wellbeing.get('sleep_hours', 'N/A') if latest_wellbeing else 'N/A'
                login_prompt += (
                    f"3. Hoy ({today_str}) YA ha registrado sus horas de sueño ({sleep_hrs}h). "
                    "NO le vuelvas a preguntar por el sueño. En su lugar, pregúntale qué tiene planificado estudiar hoy o cómo le gustaría enfocar la jornada.\n"
                )

            # 4. Plan de estudio activo y tareas específicas para hoy
            today_plan_tasks = []
            plan_title = None
            try:
                active_plan = await self.db_service.get_active_study_plan(user_id)
                if active_plan:
                    plan_title = active_plan.get("title", "Plan Activo")
                    items = active_plan.get("items", [])

                    try:
                        from zoneinfo import ZoneInfo
                        now_dt = datetime.now(ZoneInfo("Europe/Madrid"))
                    except Exception:
                        now_dt = datetime.now()

                    dias_semana = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
                    dias_semana_raw = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
                    weekday_name = dias_semana[now_dt.weekday()]
                    weekday_raw = dias_semana_raw[now_dt.weekday()]
                    today_date_str = now_dt.strftime("%Y-%m-%d")

                    for it in items:
                        it_day = (it.get("day") or "").lower().strip()
                        it_due = (it.get("due_date") or "").strip()
                        if it_day in (weekday_name, weekday_raw) or it_due == today_date_str:
                            s_name = it.get("subject_name") or "Estudio"
                            hrs = it.get("planned_hours", 0)
                            desc = it.get("description") or it.get("task", "")
                            hrs_str = f"{hrs}h" if hrs else ""
                            desc_str = f" - {desc}" if desc else ""
                            today_plan_tasks.append(f"• {s_name} ({hrs_str}{desc_str})")
            except Exception as e:
                print(f"[LANGGRAPH GREETING] Error obteniendo tareas del plan de hoy: {e}", file=sys.stderr)

            if today_plan_tasks:
                login_prompt += (
                    f"\n4. SEGUIMIENTO DEL PLAN DE ESTUDIO PARA HOY ('{plan_title}'):\n"
                    f"Hoy el usuario tiene programadas en su planificación:\n"
                    f"{chr(10).join(today_plan_tasks)}\n"
                    "Menciónale de forma concreta y motivadora lo que tiene previsto estudiar hoy y "
                    "pregúntale directamente si quiere que pongamos en marcha el temporizador para comenzar con alguna de esas tareas.\n"
                )
            elif plan_title:
                login_prompt += (
                    f"\n4. PLAN DE ESTUDIO ACTIVO ('{plan_title}'):\n"
                    "Tiene un plan activo, aunque hoy no tiene tareas específicas marcadas. "
                    "Pregúntale amigablemente qué le gustaría avanzar hoy.\n"
                )

            login_prompt += "\nSé conciso, empático y natural. No uses listas innecesariamente largas."
            proactive_prompt = login_prompt

        inputs = {
            "user_id": user_id,
            "user_message": "",
            "message_with_context": "",
            "history_msgs": history_msgs,
            "tools_raw": [],
            "in_study_report_flow": False,
            "run_advisor": False,
            "advisor_trigger": "",
            "periodic_trigger": False,
            "event_type": event_type,
            "proactive_prompt": proactive_prompt
        }

        final_state = await self.app.ainvoke(inputs)

        return {
            "response": final_state.get("response_text", ""),
            "agent_used": final_state.get("active_domain", "GENERAL" if is_new_user else "BIENESTAR")
        }

