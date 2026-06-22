import os
from google import genai
from google.genai import types 
from dotenv import load_dotenv

from services.base_bot import BaseChatbotService

load_dotenv()

class GeminiService (BaseChatbotService):
    def __init__(self):
        self.client = genai.Client() # loads GEMINI_API_KEY from .env automatically
        self.model = "gemini-2.5-flash" 

    async def chat_with_mcp_async(self, user_message: str, config: types.GenerateContentConfig):
        """
        Async method to handle chat interactions with Gemini, specifically designed to work with the MCP protocol.
        It takes the user's message and a configuration object that includes the tools (functions) available from 
        the MCP client. The method processes the message, incorporates the tool configurations, and returns the response from   
        Gemini, which may include function calls if the model decides to use any of the tools.
        """
        try:
        
            # NOTE Añadimos la instrucción de sistema directamente a la configuración que viene de main.py
            config.system_instruction = (
                "Eres una IA experta en bienestar laboral y gestión del tiempo. "
                "Tu objetivo es ayudar al usuario a gestionar su fatiga y mejorar su día. "
                "Tienes acceso a herramientas de Clockify mediante el protocolo MCP para consultar "
                "proyectos o espacios de trabajo reales si el usuario te lo pide. Responde siempre en español."
            )

            # NOTE Usamos 'client.aio' en lugar de 'client' para que sea 100% asíncrono
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=user_message,
                config=config
            )
            
            # NOTE Devolvemos el objeto 'response' completo porque main.py necesita comprobar si viene una llamada a función 
            return response
            
        except Exception as e:
            print(f"Error en GeminiService MCP: {str(e)}")
            raise e