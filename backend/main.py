import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from google.genai import types

# Importamos tus servicios
from services.openai import OpenAIService
from services.gemini import GeminiService
from mcp_local.client import MCPClientService

from services.base_bot import StandardResponse, FunctionCall

from fastapi.middleware.cors import CORSMiddleware

from services.database import DatabaseService

# Servicios de MCP y de la Base de DAtos
db_service = DatabaseService()
mcp_client = MCPClientService()

ACTIVE_MODEL = "openai" 
# ACTIVE_MODEL = "gemini"

if ACTIVE_MODEL == "gemini":
    ai_chatbot = GeminiService()
elif ACTIVE_MODEL == "openai":
    ai_chatbot = OpenAIService()


# FastAPI lifespan: Manages startup and shutdown of the app
@asynccontextmanager
async def lifespan(app: FastAPI):
    #Al arrancar la API, encendemos el "USB" del servidor MCP una sola vez
    await mcp_client.connect()
    yield
    # Al apagar la API, desconectamos el proceso de fondo de forma segura
    await mcp_client.disconnect()
    db_service.client.close()



app = FastAPI(title="TFG Bienestar (Agentic App)", lifespan=lifespan)
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)



class ChatRequest(BaseModel):
    message: str


@app.get("/api/test-db")
async def test_db():
    # Intenta insertar y luego borrar un documento de prueba
    result = await db_service.users.insert_one({"test": "conexion ok"})
    await db_service.users.delete_one({"_id": result.inserted_id})
    return {"message": "Conexión a MongoDB funcionando"}

@app.post("/api/chat")
async def handle_chat(request: ChatRequest):
    try:
        mcp_tools = mcp_client.tools
        
        # NOTE hay que mapear las herramientas a declaraciones de Gemini (esquemas de texto)
        # gemini_declarations = []
        # for tool in mcp_tools:
        #     gemini_declarations.append(
        #         types.FunctionDeclaration(
        #             name=tool.name,
        #             description=tool.description or f"Ejecutar {tool.name}",
        #             parameters=tool.inputSchema
        #         )
        #     )
        
        # tool_config = types.Tool(function_declarations=gemini_declarations)
        # mcp_config = types.GenerateContentConfig(tools=[tool_config])

        # ai_chatbot.set_config(mcp_config)  # Configuramos el chatbot con las herramientas MCP


        mcp_tools = mcp_client.tools
        tools_raw = [
            {
                "name": tool.name,
                "description": tool.description or f"Ejecutar {tool.name}",
                "parameters": tool.inputSchema
            }
            for tool in mcp_tools
        ]

        ai_chatbot.set_config(tools_raw)
        
        # Primer paso del agente: Consultamos a Gemini
        # (Usa el método asíncrono con client.aio que configuramos en tu gemini.py)
        response = await ai_chatbot.chat_with_mcp_async(
            user_message=request.message
        )
        
       # El bucle agéntico: Si el LLM solicita ejecutar una o varias herramientas
        # if hasattr(response, 'function_calls') and response.function_calls:
        if response.function_calls:

            # Creamos una lista por si el LLM decide encadenar varias llamadas consecutivas
            resultados_herramientas = []
            
            for function_call in response.function_calls:
                tool_name = function_call.name
                tool_args = function_call.args
                
                print(f"[Agente] Solicitando herramienta del MCP: {tool_name} con argumentos: {tool_args}")
                
                # Invocamos al cliente MCP aislado para ejecutar la tarea en tu server.py (Clockify)
                tool_result = await mcp_client.call_tool(tool_name, tool_args)
                
                # Almacenamos el resultado formateado
                resultados_herramientas.append(f"Resultado de ejecutar {tool_name}: {tool_result}")
            
            # Unimos todos los resultados obtenidos del servidor MCP en un único mensaje de contexto
            contexto_final = "\n".join(resultados_herramientas)
            
            # Devolvemos el resultado al LLM activo para que redacte el texto empático final en español
            final_response = await ai_chatbot.chat_with_mcp_async(
                user_message=f"Aquí tienes los datos que me pediste del sistema:\n{contexto_final}\n\nPor favor, responde ahora al usuario en base a estos datos."
            )
            
            # Retornamos la respuesta redactada (manejando tanto el objeto adaptado como texto plano)
            texto_respuesta = final_response.text

            
            return {"response": texto_respuesta}
        

        texto_directo = response.text

        return {"response": texto_directo}

    except Exception as e:
        print(f"Error crítico en handle_chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
 

@app.post("/api/chat/reset")
async def reset_chat():
    ai_chatbot.clear_history()
    return {"message": "Conversación reiniciada"}