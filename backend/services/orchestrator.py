import json
from services.openai_service import OpenAIService
from services.gemini_service import GeminiService

VALID_DOMAINS = {"ACADEMICO", "BIENESTAR", "GENERAL", "PLANIFICADOR"}


class AgentOrchestrator:
    def __init__(self, provider: str = "openai"):
        if provider == "gemini":
            self.classifier = GeminiService()
        else:
            self.classifier = OpenAIService()

    async def route_intent(self, user_message: str, history_msgs: list[dict] = None) -> str:
        """
        Analiza el mensaje del usuario y decide qué agente debe responder.
        Devuelve: 'ACADEMICO', 'BIENESTAR', 'GENERAL' o 'PLANIFICADOR'
        """
        history_str = ""
        last_agent = ""
        if history_msgs:
            history_str = "Historial reciente de la conversación (entre corchetes, el agente que escribió cada respuesta):\n"
            for msg in history_msgs:
                if msg.get("role") == "user":
                    role_label = "Usuario"
                else:
                    agent = (msg.get("agent_used") or "").replace("+ASESOR", "")
                    role_label = f"Asistente[{agent}]" if agent else "Asistente"
                    last_agent = agent or last_agent
                history_str += f"- {role_label}: {msg.get('content')}\n"
            history_str += "\n"

        last_agent_hint = (
            f"El agente que escribió el ÚLTIMO mensaje del asistente fue: {last_agent}.\n"
            if last_agent else ""
        )

        prompt = f"""
        Eres el enrutador principal de un sistema de tutoría académica y bienestar.
        Tu ÚNICA función es clasificar la intención del mensaje del usuario en una de estas 4 categorías:

        1. ACADEMICO: Gestión del día a día académico: asignaturas, TAREAS INDIVIDUALES (añadir, completar, borrar, ver,
           cambiar la fecha/prioridad/etiquetas de UNA tarea concreta), exámenes, notas, registrar o consultar tiempo
           de estudio, iniciar/parar el cronómetro o timer, Clockify, y CONSULTAR el plan de estudio activo
           (ver qué tiene programado), sin modificarlo.
           Ejemplos ACADEMICO: "para el cronómetro", "añade la tarea X", "marca esta tarea como completada",
           "mueve la fecha de la tarea X al viernes", "¿qué tareas tengo?", "¿cuánto tiempo llevo estudiando?",
           "¿cuál es mi plan?", "¿qué me toca estudiar hoy según mi plan?".

        2. BIENESTAR: Estado físico o mental (sueño, cansancio, estrés, fatiga, hábitos de descanso, estado de ánimo).
           TAMBIÉN es BIENESTAR si el asistente preguntó por cómo le fue la sesión de estudio (informe post-sesión),
           incluso si el usuario menciona asignaturas al responder.
           EXCEPCIÓN CRÍTICA: Si el usuario pide EXPLÍCITAMENTE una acción académica ("muéstrame mis tareas",
           "añade esta tarea") ignorando la pregunta de bienestar, clasifica SIEMPRE como ACADEMICO.

        3. GENERAL: Saludo aislado ("hola", "qué tal"), pregunta sobre qué puede hacer el sistema, o despedida
           sin contexto previo de tareas u operaciones académicas.

        4. PLANIFICADOR: SOLO cuando el usuario pide EXPLÍCITAMENTE crear, modificar o reorganizar su PLAN DE ESTUDIO
           EN CONJUNTO (varias actividades, la semana, el plan entero), no una tarea suelta. Señales claras:
           - Quiere cambiar las HORAS de estudio del plan ("quiero dedicar 5 horas al día", "aumenta las horas").
           - Quiere reorganizar/reagendar actividades del plan ("reorganiza mi plan", "cambia las fechas del plan",
             "replanifica la semana", "tengo muchas tareas vencidas, reorganízame la semana", "tengo retrasos, ajusta el plan").
           - Quiere CREAR un plan de estudio nuevo ("hazme un plan para el TFG", "crea un plan de estudio").
           - Pregunta por tendencias para decidir el plan ("¿qué día me conviene estudiar más?", "¿cuántas horas debería dedicar a X en mi plan?").
           NO uses PLANIFICADOR para:
           - Consultar el plan activo → ACADEMICO.
           - Añadir, completar o modificar UNA tarea concreta (incluida su fecha) → ACADEMICO.
           - Ajustes de tiempo de estudio (cronómetro/Clockify) → ACADEMICO.

        REGLA DE CONFIRMACIONES CORTAS ("sí", "vale", "hazlo", "ok", "venga", "adelante"):
        Enruta SIEMPRE al MISMO agente que emitió la última propuesta del asistente.
        - Si la última propuesta vino de PLANIFICADOR, o proponía reorganizar/crear/ajustar el PLAN → PLANIFICADOR.
        - Si proponía algo sobre tareas, asignaturas, tiempos o el cronómetro (incluido un borrado) → ACADEMICO.
        - Si era una pregunta de informe de sesión o de bienestar → BIENESTAR.
        Una invitación del asistente a "reorganizar el plan" tras un saludo o un aviso de retrasos cuenta como propuesta de PLANIFICADOR.

        {last_agent_hint}{history_str}Último mensaje del usuario (a clasificar, utilizando el historial superior como contexto): "{user_message}"

        Responde ÚNICAMENTE con un JSON con el siguiente formato, sin bloques de código ni texto adicional:
        {{"domain": "ACADEMICO" | "BIENESTAR" | "GENERAL" | "PLANIFICADOR"}}
        """

        self.classifier.clear_history()
        self.classifier.append_user_message(prompt)
        response = await self.classifier.call_model()

        std_resp = self.classifier.get_standard_response(response)

        try:
            clean_text = std_resp.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            domain = data.get("domain", "ACADEMICO")
            if domain not in VALID_DOMAINS:
                return "ACADEMICO"
            return domain
        except Exception:
            return "ACADEMICO"