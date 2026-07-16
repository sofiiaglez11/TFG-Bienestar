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

from services.auth import verify_password, create_token, hash_password


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

##################################################################
# ESTRUTURAS DE DATOS PARA SOLICITAR DATOS AL CLIENTE
##################################################################
class ChatRequest(BaseModel):
    message: str

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str


##################################################################
# ENDPOINTS
##################################################################


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
 

@app.post("/api/login")
async def login(request: LoginRequest):
    user = await db_service.get_user_by_email(request.email)
    if not user or not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    
    token = create_token(str(user["_id"]), user["email"])
    return {"token": token, "user": {"email": user["email"], "name": user["name"]}}




@app.post("/api/register")
async def register(request: RegisterRequest):
    existing = await db_service.get_user_by_email(request.email)
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una cuenta con ese email")
    
    hashed = hash_password(request.password)
    user = await db_service.create_user(request.email, request.name, hashed)
    return {"message": "Usuario creado correctamente", "user_id": user["_id"]}


@app.post("/api/chat/reset")
async def reset_chat():
    ai_chatbot.clear_history()
    return {"message": "Conversación reiniciada"}