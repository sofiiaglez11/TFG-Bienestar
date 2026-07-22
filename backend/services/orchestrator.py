import json
from services.openai_service import OpenAIService
from services.gemini_service import GeminiService

class AgentOrchestrator:
    def __init__(self, provider: str = "openai"):
        if provider == "gemini":
            self.classifier = GeminiService()
        else:
            self.classifier = OpenAIService()

    async def route_intent(self, user_message: str) -> str:
        """
        Analiza el mensaje del usuario y decide qué agente debe responder.
        Devuelve: 'ACADEMICO', 'BIENESTAR' o 'GENERAL'
        """
        prompt = f"""
        Eres el enrutador principal de un sistema de tutoría académica y bienestar.
        Tu ÚNICA función es clasificar la intención del mensaje del usuario en una de estas 3 categorías:

        1. ACADEMICO: Si habla de asignaturas, tareas, exámenes, notas, registrar tiempo de estudio, Clockify, entregas o calendario.
        2. BIENESTAR: Si habla de su estado físico o mental (sueño, cansancio, estrés, fatiga, pausas, hábitos de descanso, cómo se siente).
        3. GENERAL: Si es un saludo ('hola', 'qué tal'), una pregunta sobre qué puedes hacer, o una despedida.

        Mensaje del usuario: "{user_message}"

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