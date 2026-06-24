import os
import json
from openai import AsyncOpenAI  # ⚡ Versión asíncrona para no bloquear FastAPI
from dotenv import load_dotenv
from services.base_bot import BaseChatbotService

load_dotenv()

class OpenAIService(BaseChatbotService):
    def __init__(self):
        # Inicializa el cliente asíncrono con tu OPENAI_API_KEY del .env
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # Usamos gpt-4o-mini: es ultra rápido, baratísimo y buenísimo con herramientas
        self.model = "gpt-4o-mini" 

    async def chat_with_mcp_async(self, user_message: str, config):
        """
        Procesa el mensaje del usuario con OpenAI y traduce la configuración 
        de herramientas de Gemini/FastAPI al formato JSON Schema de OpenAI.
        """
        try:
            openai_tools = []
            
            # TRADUCCIÓN DE HERRAMIENTAS: 
            # Convertimos el formato de tools que armó FastAPI al formato que entiende OpenAI
            if hasattr(config, 'tools') and config.tools:
                for tool in config.tools[0].function_declarations:
                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters
                        }
                    })

            # Configuramos las instrucciones de sistema enfocadas en el bienestar laboral
            system_instruction = (
                "Eres una IA experta en bienestar laboral y gestión del tiempo. "
                "Tu objetivo es ayudar al usuario a gestionar su fatiga y mejorar su día. "
                "Tienes acceso a herramientas de Clockify mediante el protocolo MCP para consultar "
                "proyectos, registrar tiempos o ver espacios de trabajo reales. Responde siempre en español."
            )

            # Montamos el histórico de mensajes
            messages = [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_message}
            ]

            # Preparamos los argumentos de la llamada a la API
            kwargs = {"model": self.model, "messages": messages}
            if openai_tools:
                kwargs["tools"] = openai_tools

            # Invocación asíncrona
            response = await self.client.chat.completions.create(**kwargs)
            choice = response.choices[0].message

            # ADAPTADOR DE RESPUESTA HOMOGÉNEA:
            # Creamos un objeto "espejo" idéntico al que devuelve Gemini 
            # para que tu main.py no tenga que cambiar su forma de leer los datos (.text y .function_calls)
            class StandardResponse:
                def __init__(self, text, function_calls=None):
                    self.text = text
                    self.function_calls = function_calls

            # Si OpenAI ha decidido invocar herramientas, traducimos sus tool_calls
            standard_calls = []
            if choice.tool_calls:
                for call in choice.tool_calls:
                    class FunctionCallMock:
                        def __init__(self, name, args):
                            self.name = name
                            self.args = args
                    
                    # OpenAI devuelve los argumentos como un string JSON, lo parseamos a un diccionario de Python
                    arguments_dict = json.loads(call.function.arguments)
                    standard_calls.append(FunctionCallMock(call.function.name, arguments_dict))

            return StandardResponse(text=choice.content, function_calls=standard_calls)

        except Exception as e:
            print(f"Error en OpenAIService MCP: {str(e)}")
            raise e