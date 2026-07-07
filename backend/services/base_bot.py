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
                "Cuando el usuario mencione que tiene ciertas asignaturas (por ejemplo: 'tengo Matemáticas, "
                "Física e Historia'), interpreta que quiere registrarlas en el sistema. Pregúntale si quiere "
                "añadirlas y, si confirma, usa add_multiple_subjects para crearlas todas de una vez. "
                "Nunca guardes asignaturas solo como contexto de conversación sin confirmar con el usuario."
                # "Si el usuario te pide ayuda o no sabe qué hacer, tienes un método llamado get_agent_capabilities que "
                # "informa de todas las herramientas disponibles y cómo usarlas. "

                "Cuando el usuario pregunte qué puedes hacer o pida ayuda, usa get_agent_capabilities "
"para obtener la lista de herramientas disponibles e intéprpretala de forma amigable "
"para el usuario, sin mencionar nombres técnicos. Por ejemplo, si hay una tool llamada "
"add_subject, dile 'Puedo registrar tus asignaturas'. Si hay get_subjects, dile "
"'Puedo mostrarte tus asignaturas actuales'. Usa un tono cercano y natural."
            )
        }

    @abstractmethod
    def translate_tools_to_specific_format(self, config):
        '''Traduce la lista de herramientas a un formato específico para cada proveedor de IA.'''
        pass


    @abstractmethod
    def append_user_message(self, user_message: str):
        '''Agrega el mensaje del usuario al historial de conversación.'''
        pass

    @abstractmethod
    def append_model_message(self, response):
        '''Agrega el mensaje del modelo al historial de conversación.'''
        pass

    @abstractmethod
    def append_tool_results(self, function_calls: list, results: list):
        '''
        Añade al historial los resultados de las tools ejecutadas, usando el formato
        NATIVO que cada proveedor necesita para continuar la conversación:
        - OpenAI: mensajes {"role": "tool", "tool_call_id": ..., "content": ...}
        - Gemini: Content(role="user", parts=[Part.from_function_response(...)])
        function_calls: lista de FunctionCall, en el mismo orden en que se pidieron.
        results: lista de resultados (mismo orden), ya convertidos a string/dict.
        '''
        pass
 


    @abstractmethod
    async def call_model(self):
        '''Llama al modelo de IA con el historial de conversación y devuelve la respuesta.'''
        pass

    @abstractmethod
    def get_standard_response(self, response) -> StandardResponse:
        '''Convierte la respuesta del modelo a un formato estándar que pueda ser leído por main.py.'''
        pass

    async def chat_with_mcp_async(self, user_message: str):
        '''Permite al usuario enviar un mensaje a la IA y obtener una respuesta, manejando el historial de conversación y las llamadas a herramientas.'''
        try:
            self.append_user_message(user_message)
            response = await self.call_model()
            self.append_model_message(response)
            return self.get_standard_response(response)
        except Exception as e:
            print(f"Error en chat_with_mcp_async: {str(e)}")
            raise e
        

    
    async def run_agentic_conversation(self, user_message: str, tool_executor, max_turns: int = 5) -> StandardResponse:
        '''
        Bucle agéntico genérico, independiente del proveedor de IA.
        Usa FunctionCall/StandardResponse y delega el formateo específico a
          append_model_message/append_tool_results.
 
        tool_executor: función async (nombre: str, args: dict) -> resultado
                       p.ej. mcp_client.call_tool
        max_turns: límite de "rondas" de tool-calling encadenadas (evita bucles infinitos
                   si el modelo insiste en llamar tools sin parar, p.ej. get_agent_capabilities).
        '''
        standard = await self.chat_with_mcp_async(user_message)
 
        turns = 0
        while standard.function_calls and turns < max_turns:
            results = []
            for fc in standard.function_calls:
                print(f"[Agente] Ejecutando herramienta: {fc.name} con argumentos: {fc.args}")
                resultado = await tool_executor(fc.name, fc.args)
                results.append(str(resultado))
 
            # Cada proveedor sabe cómo insertar esto en SU propio formato de historial
            self.append_tool_results(standard.function_calls, results)
 
            response = await self.call_model()
            self.append_model_message(response)
            standard = self.get_standard_response(response)
            turns += 1
 
        if not standard.text:
            # Para evitar enviar al endpoint una respuesta vacía, devolvemos este mensaje
            # genérico"
            standard.text = (
                "Lo siento, no he podido generar una respuesta esta vez. "
                "¿Puedes reformular tu mensaje?"
            )
 
        return standard
 

    def clear_history(self):
        '''Limpia el historial de conversación.'''
        self.history = []