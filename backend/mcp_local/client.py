import os
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp import ClientSession
from contextlib import AsyncExitStack
import sys

# PARA QUE NO IMPORTE DESDE DONDE SE LANCE LA APLICACIÓN
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SERVER_SCRIPT_PATH = os.path.join(_THIS_DIR, "server.py")
 
class MCPClientService:
    def __init__(self):
        self.session = None
        self._exit_stack = None
        self.tools = []
 
    async def connect(self):
        """Inicializa el servidor MCP de forma limpia sin argumentos extra"""
        
        # Copiamos el entorno actual
        current_env = os.environ.copy()
        
        # NOTE para que FastMCP que no sature la consola con logs interactivos
        current_env["MCP_LOG_LEVEL"] = "WARNING" 
 
        server_params = StdioServerParameters(
            command="python3",
            args=[_SERVER_SCRIPT_PATH], 
            env=current_env,
            stderr=sys.stderr  
        )      
        
        self._exit_stack = AsyncExitStack()
        
        #  Dejamos el stdio_client limpio de argumentos no permitidos
        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        
        # Inicializamos la sesión del protocolo de manera segura
        self.session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()
        
        # Cacheamos las herramientas disponibles
        await self.refresh_tools()
        print("[MCP] Conexión con Servidor MCP establecida con éxito.")
 
    async def refresh_tools(self):
        if self.session:
            response = await self.session.list_tools()
            self.tools = response.tools
            return self.tools
        return []
 
    async def call_tool(self, tool_name: str, arguments: dict):
        if not self.session:
            raise RuntimeError("El cliente MCP no está conectado.")
        response = await self.session.call_tool(tool_name, arguments)
        return response.content
 
    async def disconnect(self):
        if self._exit_stack:
            await self._exit_stack.aclose()
            print("Conexión con Servidor MCP cerrada.")

