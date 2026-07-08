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
    # Al arrancar la API, encendemos el "USB" del servidor MCP una sola vez
    await mcp_client.connect()
    await db_service.ensure_indexes()  # Aseguramos que los índices estén creados al iniciar la app

    yield
    # Al apagar la API, desconectamos el proceso de fondo de forma segura
    await mcp_client.disconnect()
    db_service.client.close()



app = FastAPI(title="TFG Bienestar", lifespan=lifespan)
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Permitir solicitudes desde el frontend
    allow_methods=["*"], # Permitir todos los métodos HTTP
    allow_headers=["*"], # Permitir todos los encabezados
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

        # Obtenemos la lista de herramientas disponibles en el MCP
        # las pasamos a la configuración del agente para que pueda usarlas
        # sin formato (raw) para que el traductor de cada proveedor las adapte a su SDK
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
        

        result = await ai_chatbot.run_agentic_conversation(
            user_message=request.message,
            tool_executor=mcp_client.call_tool
        )
        return {"response": result.text}

    except Exception as e:
        print(f"Error crítico en handle_chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
 

@app.post("/api/chat/reset")
async def reset_chat():
    ai_chatbot.clear_history()
    return {"message": "Conversación reiniciada"}