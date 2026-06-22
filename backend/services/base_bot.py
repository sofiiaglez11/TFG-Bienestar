from abc import ABC, abstractmethod

class BaseChatbotService(ABC):

    @abstractmethod
    async def chat_with_mcp_async(self, user_message: str, config: any):
        """
        Método obligatorio para procesar mensajes y herramientas MCP.
        Cada proveedor de IA mapeará el config a sus propios tipos de herramientas.
        """
        pass