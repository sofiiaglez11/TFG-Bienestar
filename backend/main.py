import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from google.genai import types


from services.openai_service import OpenAIService
from services.gemini_service import GeminiService
from services.orchestrator import AgentOrchestrator
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

orchestrator = AgentOrchestrator(provider=ACTIVE_MODEL)

if ACTIVE_MODEL == "gemini":
    academic_agent = GeminiService()
    wellbeing_agent = GeminiService()
    general_agent = GeminiService()
elif ACTIVE_MODEL == "openai":
    academic_agent = OpenAIService()
    wellbeing_agent = OpenAIService()
    general_agent = OpenAIService()

ACADEMIC_PROMPT = (
    "Eres una IA experta en gestión del tiempo y ámbito académico. "
    "Tienes acceso a herramientas de Clockify mediante el protocolo MCP para consultar "
    "proyectos, registrar tiempos o ver espacios de trabajo reales. Responde siempre en español. "
    "Cuando el usuario mencione que tiene ciertas asignaturas (por ejemplo: 'tengo Matemáticas, "
    "Física e Historia'), interpreta que quiere registrarlas en el sistema. Pregúntale si quiere "
    "añadirlas y, si confirma, usa add_multiple_subjects para crearlas todas de una vez. "
    "Nunca guardes asignaturas solo como contexto de conversación sin confirmar con el usuario. "
    "IMPORTANTE: Solo debes responder preguntas relacionadas con gestión de asignaturas y "
    "tiempo de estudio. Si el usuario pregunta algo fuera de este ámbito, explícale amablemente "
    "que estás limitado a estas funciones. "
    "REGLA DE EXTRACCIÓN DE ARGUMENTOS:\n"
    "Cuando llames a cualquier herramienta que requiera el parámetro 'subject_name', "
    "debes usar ÚNICAMENTE el nombre exacto de la asignatura tal y como está registrada "
    "en el sistema (por ejemplo: 'Matemáticas', 'Programación').\n"
    "NUNCA uses abreviaturas (como 'Matem'), ni arrastres erratas del usuario (como 'Matemómáticas'). "
    "Si el nombre que menciona el usuario no coincide exactamente con las asignaturas activas, "
    "usa primero la herramienta 'get_subjects' para verificar el nombre real antes de invocar otra herramienta."
)

WELLBEING_PROMPT = (
    "Eres un asistente empático y comprensivo especializado en bienestar y salud mental para estudiantes. "
    "Tu objetivo es escuchar al usuario, validar cómo se siente (estrés, cansancio, falta de motivación) y "
    "ofrecerle consejos prácticos y amigables para mejorar su estado de ánimo y descansar. "
    "No eres un profesional médico, así que prioriza consejos de estilo de vida, pausas activas o técnicas de relajación."
)

GENERAL_PROMPT = (
    "Eres un asistente amigable y conversacional. Responde cordialmente a los saludos y "
    "preguntas generales. Si el usuario necesita ayuda con sus estudios, recomiéndale hablar de sus asignaturas "
    "o tiempos de estudio; y si se siente estresado o cansado, ofrécete a escucharle y ayudarle con su bienestar."
)

academic_agent.set_system_instruction(ACADEMIC_PROMPT)
wellbeing_agent.set_system_instruction(WELLBEING_PROMPT)
general_agent.set_system_instruction(GENERAL_PROMPT)


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


        await db_service.insert_message(
            user_id=user_id, 
            role="user", 
            content=request.message
        )

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

        #NOTE: PARA DEPURACIÓN
        print(f"Mensaje recibido del usuario con ID: {user_id}")

        domain = await orchestrator.route_intent(request.message)
        print(f"Dominio detectado por el orquestador: {domain}")

        if domain == "BIENESTAR":
            active_agent = wellbeing_agent
            filtered_tools = [t for t in tools_raw if t["name"].startswith("wb_")]
            
        elif domain == "ACADEMICO":
            active_agent = academic_agent
            filtered_tools = [t for t in tools_raw if not t["name"].startswith("wb_") and t["name"] != "get_agent_capabilities"]
            
        else:
            active_agent = general_agent
            # El general no usa herramientas
            filtered_tools = []

        active_agent.set_config(filtered_tools)

        async def custom_tool_executor(name: str, arguments: dict):
            # Inyectamos el user_id del token en los argumentos de la herramienta
            if name != "get_agent_capabilities":
                arguments["user_id"] = user_id
            return await mcp_client.call_tool(name, arguments)

        result = await active_agent.run_agentic_conversation(
            user_message=request.message,
            tool_executor=custom_tool_executor
        )

        await db_service.insert_message(
            user_id=user_id,
            role="assistant",
            content=result.text,
            agent_used=domain
        )
        return {"response": result.text}

    except Exception as e:
        print(f"Error crítico en handle_chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
 

@app.post("/api/chat/proactive-greeting")
async def get_proactive_greeting(user_id: str = Depends(get_current_user_id)):
    """
    Endpoint que llama React justo al hacer Login. 
    Llama directamente al Agente de Bienestar para generar un saludo proactivo.
    """
    # Comprobar si hay algún reporte de bienestar reciente para personalizar el saludo
    latest_wellbeing = await db_service.get_latest_wellbeing_report(user_id)
    
    prompt = (
        "El usuario acaba de iniciar sesión en la plataforma. "
        "Dale un saludo cálido, breve y proactivo. Pregúntale activamente qué tal ha descansado "
        "o cómo afronta el día de hoy."
    )
    
    if latest_wellbeing:
        prompt += f" Ten en cuenta que en su último registro dijo haber dormido {latest_wellbeing.get('sleep_hours', 'N/A')} horas."

    wellbeing_agent.set_config([])  # Sin tools para un saludo directo
    result = await wellbeing_agent.run_agentic_conversation(
        user_message=prompt,
        tool_executor=None
    )

    # Guardar la pregunta del bot en el historial
    await db_service.insert_message(
        user_id=user_id,
        role="assistant",
        content=result.text,
        agent_used="BIENESTAR"
    )

    return {"response": result.text, "agent_used": "BIENESTAR"}

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


@app.get("/api/chat/history")
async def get_chat_history(user_id: str = Depends(get_current_user_id)):
    """
     Devuelve los últimos mensajes del usuario desde MongoDB 
    para pintarlos en la interfaz de React al abrir la app.
    """
    messages = await db_service.get_history(user_id=user_id, limit=50)
    return {"history": messages}


@app.post("/api/chat/reset")
async def reset_chat(user_id: str = Depends(get_current_user_id)):
    """
     Reinicia la memoria del bot en RAM y vacía la colección 
    'history' de este usuario en MongoDB.
    """
    academic_agent.clear_history()
    wellbeing_agent.clear_history()
    general_agent.clear_history()
    
    # Borramos también la persistencia en Mongo para este usuario
    deleted_count = await db_service.clear_history(user_id)
    
    return {
        "message": "Conversación reiniciada correctamente", 
        "deleted_messages": deleted_count
    }