# base_bot.py
from abc import ABC, abstractmethod


class StandardResponse:
    """
    Formato estándar de respuesta que deben devolver todos los proveedores de IA,
    para que main.py pueda leer .text y .function_calls sin importar qué LLM se use.
    """
    def __init__(self, text: str, function_calls: list = None):
        self.text = text
        self.function_calls = function_calls or []


class FunctionCall:
    """Representa una llamada a herramienta solicitada por el modelo."""
    def __init__(self, name: str, args: dict):
        self.name = name
        self.args = args


class BaseChatbotService(ABC):

    def __init__(self):
        self.history = []
        self.config = None
        self.model = None

    
    def set_config(self, config):
        self.config = {
            "tools": self.translate_tools_to_specific_format(config),
            "system_instruction": (
                "Eres una IA experta en bienestar laboral y gestión del tiempo. "
                "Tu objetivo es ayudar al usuario a gestionar su fatiga y mejorar su día. "
                "Tienes acceso a herramientas de Clockify mediante el protocolo MCP para consultar "
                "proyectos, registrar tiempos o ver espacios de trabajo reales. Responde siempre en español."
            )
        }

    @abstractmethod
    def translate_tools_to_specific_format(self, config):
        pass


    @abstractmethod
    def append_user_message(self, user_message: str):
        pass

    @abstractmethod
    def append_model_message(self, response):
        pass

    @abstractmethod
    async def call_model(self):
        pass

    @abstractmethod
    def get_standard_response(self, response) -> StandardResponse:
        pass

    async def chat_with_mcp_async(self, user_message: str):
        try:
            self.append_user_message(user_message)
            response = await self.call_model()
            self.append_model_message(response)
            return self.get_standard_response(response)
        except Exception as e:
            print(f"Error en chat_with_mcp_async: {str(e)}")
            raise e

    def clear_history(self):
        self.history = []