import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class OpenAIService:
    def __init__(self):
        self.client = OpenAI() # reads the OPENAI_API_KEY from .env automatically
        self.model = "gpt-4o-mini" 

    def chat_with_context(self, user_message, clokify_data):

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "Eres una IA experta en bienestar laboral y gestión del tiempo. "
                            "Tu objetivo es ayudar al usuario a gestionar su fatiga y mejorar su día. "
                            f"Aquí tienes los datos reales actuales de su Clockify: {clokify_data}. "
                            "Usa estos datos para responder a sus preguntas de forma empática, clara y concisa."
                        )
                    },
                    {
                        "role": "user", 
                        "content": user_message
                    }
                ]
            )
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Error al conectar con la IA de OpenAI: {str(e)}"