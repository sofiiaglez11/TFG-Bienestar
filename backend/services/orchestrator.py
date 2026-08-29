import json
from services.openai_service import OpenAIService
from services.gemini_service import GeminiService

class AgentOrchestrator:
    def __init__(self, provider: str = "openai"):
        if provider == "gemini":
            self.classifier = GeminiService()
        else:
            self.classifier = OpenAIService()

    async def route_intent(self, user_message: str, history_msgs: list[dict] = None) -> str:
        """
        Analiza el mensaje del usuario y decide qué agente debe responder.
        Devuelve: 'ACADEMICO', 'BIENESTAR' o 'GENERAL'
        """
        history_str = ""
        if history_msgs:
            history_str = "Historial reciente de la conversación:\n"
            for msg in history_msgs:
                role_label = "Usuario" if msg.get("role") == "user" else "Asistente"
                history_str += f"- {role_label}: {msg.get('content')}\n"
            history_str += "\n"

        prompt = f"""
        Eres el enrutador principal de un sistema de tutoría académica y bienestar.
        Tu ÚNICA función es clasificar la intención del mensaje del usuario en una de estas 3 categorías:

        1. ACADEMICO: Si habla de asignaturas, tareas, exámenes, notas, registrar o consultar tiempo de estudio, iniciar/parar/detener el cronómetro o timer, Clockify, entregas o calendario.
           TAMBIÉN incluye respuestas afirmativas o de confirmación ("sí", "no", "vale", "hazlo", "confirmo", "adelante", "cancela") cuando el mensaje anterior del asistente trataba de tareas, asignaturas o tiempos (por ejemplo, al pedir confirmación para borrar o archivar algo).
           Ejemplos ACADEMICO: "para el cronómetro", "detén el timer", "cuánto tiempo llevo estudiando", "inicia el cronómetro de X", "sí" (tras pedir confirmación de borrado/archivado).
        2. BIENESTAR: Si habla de su estado físico o mental (sueño, cansancio, estrés, fatiga, hábitos de descanso, cómo se siente emocionalmente) o responde a preguntas sobre su estado de ánimo/descanso.
           TAMBIÉN es BIENESTAR si la conversación reciente trata sobre evaluar o recoger el informe de una sesión de estudio que se acaba de parar (preguntas sobre calidad de la sesión, objetivos conseguidos, distracciones, descansos o cómo le fue), INCLUSO si la respuesta del usuario menciona asignaturas, tareas, exámenes o el TFG. Toda la recopilación del informe de sesión pertenece a BIENESTAR.
           IMPORTANTE: preguntas para iniciar o parar el cronómetro son ACADEMICO, pero la entrevista conversacional sobre CÓMO FUE la sesión de estudio (objetivos, distracciones, concentración) es SIEMPRE BIENESTAR.
        3. GENERAL: Si es un saludo aislado ('hola', 'qué tal'), una pregunta sobre qué puedes hacer, o una despedida sin contexto previo de tareas u operaciones académicas.

        {history_str} Último mensaje del usuario (a clasificar, utilizando el historial superior como contexto de ser necesario): "{user_message}"

        Responde ÚNICAMENTE con un JSON con el siguiente formato, sin bloques de código ni texto adicional:
        {{"domain": "ACADEMICO" | "BIENESTAR" | "GENERAL"}}
        """
        
        # Guarda el historial limpio para la clasificación
        self.classifier.clear_history()
        self.classifier.append_user_message(prompt)
        response = await self.classifier.call_model()
        
        # Extrae el texto del modelo
        std_resp = self.classifier.get_standard_response(response)
        
        try:
            # Limpia posibles formatos markdown tipo ```json
            clean_text = std_resp.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            return data.get("domain", "ACADEMICO")
        except Exception:
            # Si falla la extracción, por defecto deriva al agente académico
            return "ACADEMICO"