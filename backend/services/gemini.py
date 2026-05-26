import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

class GeminiService:
    def __init__(self):
        self.client = genai.Client() # loads GEMINI_API_KEY from .env automatically
        self.model = "gemini-2.5-flash" 

    def chat_with_context(self, user_message: str, clockify_data: list) -> str:
        """
        Sends the user message to Gemini along with Clockify data as context.
        """
        try:
            config = {
                "system_instruction": (
                    "Eres una IA experta en bienestar laboral y gestión del tiempo. "
                    "Tu objetivo es ayudar al usuario a gestionar su fatiga y mejorar su día. "
                    f"Aquí tienes los datos reales actuales de su Clockify: {clockify_data}. "
                    "Usa estos datos para responder a sus preguntas de forma empática, clara y concisa "
                    "siempre en español."
                )
            }
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_message,
                config=config
            )
            return response.text
            
        except Exception as e:
            return f"Error connecting to Gemini API: {str(e)}"