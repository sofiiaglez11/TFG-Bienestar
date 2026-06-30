import os
from google import genai
from google.genai import types 
from dotenv import load_dotenv

from services.base_bot import BaseChatbotService
from services.base_bot import StandardResponse, FunctionCall

load_dotenv()

class GeminiService(BaseChatbotService):
    def __init__(self):
        super().__init__()
        self.client = genai.Client()
        self.model = "gemini-2.5-flash"

    def set_config(self, config):
        config.system_instruction = (
        "Eres una IA experta en bienestar laboral y gestión del tiempo. "
        "Tu objetivo es ayudar al usuario a gestionar su fatiga y mejorar su día. "
        "Tienes acceso a herramientas de Clockify mediante el protocolo MCP para consultar "
        "proyectos o espacios de trabajo reales si el usuario te lo pide. Responde siempre en español."
        )
        self.config = config

    def append_user_message(self, user_message: str):
        self.history.append({"role": "user", "parts": [{"text": user_message}]})

    async def call_model(self):
        return await self.client.aio.models.generate_content(
            model=self.model,
            contents=self.history,
            config=self.config
        )

    def append_model_message(self, response):
        if response.candidates:
            parts = response.candidates[0].content.parts
            text_parts = [p for p in parts if hasattr(p, 'text') and p.text]
            if text_parts:
                self.history.append({"role": "model", "parts": [{"text": p.text} for p in text_parts]})

    def get_standard_response(self, response) -> StandardResponse:
        function_calls = []
        if hasattr(response, 'function_calls') and response.function_calls:
            for fc in response.function_calls:
                function_calls.append(FunctionCall(fc.name, fc.args))
        return StandardResponse(text=response.text, function_calls=function_calls)