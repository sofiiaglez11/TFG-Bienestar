import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from google.genai import types


from services.openai_service import OpenAIService
from services.gemini_service import GeminiService
from mcp_local.client import MCPClientService

from services.base_chatbot_service import StandardResponse, FunctionCall

from fastapi.middleware.cors import CORSMiddleware

from services.database_service import DatabaseService

from services.auth import verify_password, create_token, hash_password

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from services.auth import SECRET_KEY, ALGORITHM



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

# ESQUEMA DE SEGURIDAD
security = HTTPBearer()

async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Coge el token de la cabecera, 
    verifica que sea válido y devuelve el ID del usuario.
    """
    token = credentials.credentials
    try:
        # Intentamos descifrar el token con nuestra clave secreta
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token inválido: falta el usuario")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El token ha caducado. Vuelve a iniciar sesión.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido o corrupto.")


 
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
async def handle_chat(request: ChatRequest, user_id: str = Depends(get_current_user_id)):
    try:

        # Obtenemos la lista de herramientas disponibles en el MCP
        # y ocultamos el campo "user_id" para que la IA no se lo invente.
        tools_raw = []
        for tool in mcp_client.tools:
            schema = dict(tool.inputSchema) if tool.inputSchema else {}
            if "properties" in schema and "user_id" in schema["properties"]:
                props = dict(schema["properties"])
                del props["user_id"]
                schema["properties"] = props
                
                if "required" in schema and "user_id" in schema["required"]:
                    reqs = list(schema["required"])
                    reqs.remove("user_id")
                    schema["required"] = reqs
                    
            tools_raw.append({
                "name": tool.name,
                "description": tool.description or f"Ejecutar {tool.name}",
                "parameters": schema
            })

        ai_chatbot.set_config(tools_raw)

        #NOTE: PARA DEPURACIÓN
        print(f"Mensaje recibido del usuario con ID: {user_id}")

        async def custom_tool_executor(name: str, arguments: dict):
            # Inyectamos el user_id del token en los argumentos de la herramienta
            if name != "get_agent_capabilities":
                arguments["user_id"] = user_id
            return await mcp_client.call_tool(name, arguments)

        result = await ai_chatbot.run_agentic_conversation(
            user_message=request.message,
            tool_executor=custom_tool_executor
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