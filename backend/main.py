from asyncio import queues
import asyncio
import os
from datetime import datetime, timezone
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
from services.clockify_service import ClockifyService

from services.auth import verify_password, create_token, hash_password

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from services.auth import SECRET_KEY, ALGORITHM



# Servicios de MCP y de la Base de DAtos
db_service = DatabaseService()
mcp_client = MCPClientService()


ACTIVE_MODEL = os.getenv("LLM_PROVIDER", "gemini")

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
    "proyectos, registrar o consultar tiempos (cronómetros), editar entradas de tiempo registradas "
    "o eliminar sesiones de estudio individuales. Responde siempre en español. "
    "Cuando el usuario pida ver sus sesiones registradas o consultar tiempo de estudio, usa get_time_summary o get_time_spent_summary. "
    "Cuando el usuario quiera corregir o editar una sesión de estudio / cronómetro registrada, usa edit_logged_study_hours. "
    "Cuando el usuario mencione que tiene ciertas asignaturas (por ejemplo: 'tengo Matemáticas, "
    "Física e Historia'), interpreta que quiere registrarlas en el sistema. Pregúntale si quiere "
    "añadirlas y, si confirma, usa add_multiple_subjects para crearlas todas de una vez. "
    "Nunca guardes asignaturas solo como contexto de conversación sin confirmar con el usuario. "
    "IMPORTANTE: Solo debes responder preguntas relacionadas con gestión de asignaturas y "
    "tiempo de estudio. Si el usuario pregunta algo fuera de este ámbito, explícale amablemente "
    "que estás limitado a estas funciones.\n"
    "REGLA DE CONFIRMACIÓN Y BORRADO DE ELEMENTOS (TAREAS, TIEMPOS, ASIGNATURAS):\n"
    "Borrar cualquier elemento es una acción IRREVERSIBLE. Por ello, NUNCA ejecutes herramientas de borrado en el primer turno sin pedir confirmación explícita previa al usuario.\n"
    "1. TAREAS Y REGISTROS DE TIEMPO: Antes de llamar a delete_task o delete_time_entry, debes pedir siempre confirmación explícita al usuario, avisando de que es una acción irreversible y que no se podrá deshacer.\n"
    "2. ASIGNATURAS (FLUJO OBLIGATORIO DE 2 PASOS - ARCHIVAR PRIMERO):\n"
    "   - Si el usuario te pide borrar o eliminar una asignatura, NUNCA llames a delete_subject directamente si no está archivada.\n"
    "   - Primero, la asignatura debe pasar por estar archivada. Puedes preguntarle: 'Antes de borrar una asignatura permanentemente tengo que archivarla. ¿Quieres que lo haga?' o archivarla con archive_subject.\n"
    "   - Una vez archivada la asignatura (usando archive_subject), dile al usuario que la has archivado y explícale claramente:\n"
    "     * Ahora la asignatura está archivada y puede desarchivarla en cualquier momento si lo desea.\n"
    "     * Si lo que quiere es borrarla definitivamente, adviértele explícitamente: 'Ten en cuenta que borrar una asignatura definitivamente es una acción IRREVERSIBLE y que se borrará toda su información asociada: tareas, tiempo registrado (time_entries), etc. ¿Quieres borrarla definitivamente?'\n"
    "   - SOLO si la asignatura YA está archivada Y el usuario te da la confirmación explícita para borrarla definitivamente tras dicha advertencia, debes llamar a delete_subject.\n"
    "REGLA DE EXTRACCIÓN DE ARGUMENTOS:\n"
    "Cuando llames a cualquier herramienta que requiera el parámetro 'subject_name', "
    "debes usar ÚNICAMENTE el nombre exacto de la asignatura tal y como el usuario la escriba en el chat. "
    "Si la asignatura no existe como la ha mencionado en el chat, usa primero get_subjects para obtener la lista de asignaturas. "
    "Cuando el usuario te pregunte por cualquier información relacionada con su tiempo de estudio, no te la inventes, "
    "revisa lo que está guardado en las bases de datos y el clockify usando las herramientas que tienes disponibles.\n"
    "REGLA DE PRIORIDADES DE TAREAS:\n"
    "Las prioridades de las tareas van del 1 al 5 (o sin prioridad/None):\n"
    "- 5 = Prioridad MÁS ALTA (Muy alta / Máxima urgencia).\n"
    "- 4 = Prioridad alta.\n"
    "- 3 = Prioridad media.\n"
    "- 2 = Prioridad baja.\n"
    "- 1 = Prioridad MÁS BAJA (Muy baja / Mínima urgencia).\n"
    "NUNCA interpretes el 1 como la prioridad más alta. El valor 5 es SIEMPRE la máxima prioridad y 1 la mínima.\n"
    "REGLA DE JERARQUÍA Y SUBTAREAS:\n"
    "Las tareas devueltas por get_tasks pueden incluir subtareas anidadas a múltiples niveles de profundidad (tarea -> subtarea -> sub-subtarea...).\n"
    "Al responder al usuario, muestra SIEMPRE la jerarquía utilizando listas Markdown anidadas con sangría (ejemplo:\n- Tarea principal\n  - Subtarea 1\n  - Subtarea 2\n    - Sub-subtarea A).\n"
    "Esto permite que la interfaz del chat active automáticamente los desplegables para cada tarea que tenga subtareas.\n"
    "REGLA DE FECHAS DE VENCIMIENTO:\n"
    "El parámetro 'due_date' acepta fecha sola ('2026-07-20') o fecha con hora en formato ISO ('2026-07-20T18:00:00' o '2026-07-20 18:00'). Si el usuario menciona una hora específica (ej: 'entregar a las 18:00'), inclúyela en el due_date.\n"
    "REGLA DE INFORMACIÓN AL CREAR ENTIDADES (TAREAS, PROYECTOS/ASIGNATURAS, PERIODOS):\n"
    "Al crear con éxito una entidad (tarea, asignatura/proyecto o periodo académico), sé breve, conciso y natural. "
    "Confirma la creación y ofrece de forma sutil y ligera la posibilidad de añadir más información o recordarle las opciones disponibles.\n"
    "- Ejemplo para tareas: 'He creado la tarea X. Si quieres, avísame si deseas añadirle fecha límite, prioridad, descripción o etiquetas.' o bien 'Ya he creado X. Si quieres te puedo recordar qué más información le puedes añadir.'\n"
    "- Ejemplo para asignaturas/proyectos: 'He añadido la asignatura X. Si quieres, avísame si deseas configurarle horas semanales, asociarla a un periodo o si te recuerdo qué más datos puedes añadirle.'\n"
    "- CRÍTICO: Habla SIEMPRE en lenguaje cotidiano y amigable. NUNCA uses nombres técnicos de variables ni código (evita estrictamente términos como 'due_date', 'tags', 'weekly_hours_goal', 'priority', etc.)."
    "Cuando le muestres la lista de tareas al usuario, si hay muchas tareas, e incluyes tareas completadas y pendientes, "
    "añade emojis que permitan visualizar fácilmente el estado de cada una."
    
)

WELLBEING_PROMPT = (
    "Eres un asistente empático y comprensivo especializado en bienestar y salud mental para estudiantes. "
    "Tu objetivo es escuchar al usuario, validar cómo se siente (estrés, cansancio, falta de motivación) y "
    "ofrecerle consejos prácticos y amigables para mejorar su estado de ánimo y descansar. "
    "No eres un profesional médico, así que prioriza consejos de estilo de vida, pausas activas o técnicas de relajación."
    "Tienes acceso a herramientas que te permiten guardar y obtener información sobre los hábitos y "
    "estado de ánimo del usuario. Recuerda usar estas herramientas para ofrecerle un servicio más "
    "personalizado y útil. "
)

# GENERAL_PROMPT = (
#     "Eres un asistente amigable y conversacional. Responde cordialmente a los saludos y "
#     "preguntas generales. Si el usuario necesita ayuda con sus estudios, recomiéndale hablar de sus asignaturas "
#     "o tiempos de estudio; y si se siente estresado o cansado, ofrécete a escucharle y ayudarle con su bienestar."
# )

GENERAL_PROMPT = (
    "Eres un asistente amigable y conversacional. Responde cordialmente a los saludos. "
    "Si el usuario pregunta qué puedes hacer o pide ayuda, usa SIEMPRE la herramienta "
    "get_agent_capabilities para obtener la lista real de funciones disponibles y explícasela "
    "de forma amigable, sin inventarte nada. "
    "Si necesita ayuda con estudios, recomiéndale hablar de asignaturas o tiempos de estudio. "
    "Si se siente estresado, ofrécete a escucharle. "
    "IMPORTANTE: Tú NO dispones de herramientas para crear, modificar o eliminar asignaturas, tareas ni registros de tiempo. "
    "Si el usuario responde 'sí' o te pide una acción sobre sus estudios, NUNCA afirmes haber realizado la acción ni simules haber borrado nada."
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


async def get_timer_context(user_id: str, db_service: DatabaseService) -> str:
    """Comprueba si hay un cronómetro activo en Clockify y devuelve contexto para el agente."""
    try:
        clockify_creds = await db_service.get_clockify_credentials(user_id)
        if not clockify_creds or not clockify_creds.get("api_key"):
            return ""
        
        cs = ClockifyService(
            api_key=clockify_creds["api_key"],
            workspace_id=clockify_creds.get("workspace_id")
        )
        active = await asyncio.to_thread(cs.get_active_time_entry)
        if not active:
            return ""
        
        desc = active.get("description", "sin descripción")
        start = active.get("timeInterval", {}).get("start", "")
        return (
            f"\n[CONTEXTO DEL SISTEMA: El usuario tiene un cronómetro activo "
            f"desde {start} para '{desc}'. Si es relevante para la conversación, "
            f"puedes mencionarlo o recordárselo al usuario.]"
        )
    except Exception:
        return ""
 
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

from typing import Optional
from pydantic import BaseModel, model_validator

class ClockifyCredentialsRequest(BaseModel):
    api_key: Optional[str] = None
    workspace_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data):
        if isinstance(data, dict):
            # Normaliza api_key buscando variantes comunes
            key = data.get("api_key") or data.get("apiKey") or data.get("token")
            if not key:
                raise ValueError("Se requiere la clave API de Clockify (api_key, apiKey o token).")
            data["api_key"] = key
        return data

class SubjectGradeRequest(BaseModel):
    grade: float


##################################################################
def get_datetime_context() -> str:
    """Devuelve la fecha y hora actual formateada en español como contexto para el agente."""
    now = datetime.now()
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    dia_semana = dias[now.weekday()]
    mes = meses[now.month - 1]
    fecha_str = f"{dia_semana}, {now.day} de {mes} de {now.year}"
    hora_str = now.strftime("%H:%M")
    return f"\n[CONTEXTO DEL SISTEMA: La fecha y hora actual es {fecha_str} a las {hora_str}. Usa este dato si el usuario te pregunta qué día es hoy o para calcular fechas límite de tareas.]"


@app.post("/api/chat")
async def handle_chat(request: ChatRequest, user_id: str = Depends(get_current_user_id)):
    try:


        # Recuperamos los últimos 5 mensajes de historial del usuario para tener contexto de la conversación
        history_msgs = await db_service.get_history(user_id=user_id, limit=5)

        user_msg = await db_service.insert_message(
            user_id=user_id, 
            role="user", 
            content=request.message
        )

        date_context = get_datetime_context()
        timer_context = await get_timer_context(user_id, db_service)
        message_with_context = request.message + date_context + timer_context

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

    
        domain = await orchestrator.route_intent(request.message, history_msgs)
        print(f"Dominio detectado por el orquestador: {domain}")

        if domain == "BIENESTAR":
            active_agent = wellbeing_agent
            filtered_tools = [t for t in tools_raw if t["name"].startswith("wb_")]
            
        elif domain == "ACADEMICO":
            active_agent = academic_agent
            filtered_tools = [t for t in tools_raw if not t["name"].startswith("wb_") and t["name"] != "get_agent_capabilities"]
            
        else:  # GENERAL
            active_agent = general_agent
            filtered_tools = [t for t in tools_raw if t["name"] == "get_agent_capabilities"]

        active_agent.set_config(filtered_tools)
        # Cargamos los últimos 5 mensajes al agente para contextualizar la respuesta
        active_agent.load_history(history_msgs)

        async def custom_tool_executor(name: str, arguments: dict):
            # Inyectamos el user_id del token en los argumentos de la herramienta
            if name != "get_agent_capabilities":
                arguments["user_id"] = user_id
            return await mcp_client.call_tool(name, arguments)

        result = await active_agent.run_agentic_conversation(
            user_message=message_with_context,
            tool_executor=custom_tool_executor
        )

        assistant_msg = await db_service.insert_message(
            user_id=user_id,
            role="assistant",
            content=result.text,
            agent_used=domain
        )
        return {
            "response": result.text,
            "agent_used": domain,
            "timestamp": assistant_msg.get("timestamp")
        }

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
    greeting_msg = await db_service.insert_message(
        user_id=user_id,
        role="assistant",
        content=result.text,
        agent_used="BIENESTAR"
    )

    return {
        "response": result.text,
        "agent_used": "BIENESTAR",
        "timestamp": greeting_msg.get("timestamp")
    }

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
async def get_chat_history(
    user_id: str = Depends(get_current_user_id),
    limit: int = 30,
    skip: int = 0
):
    """
    Devuelve los mensajes del historial del usuario desde MongoDB con paginación.
    """
    messages = await db_service.get_history(user_id=user_id, limit=limit, skip=skip)
    has_more = len(messages) == limit
    return {"history": messages, "has_more": has_more}


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



@app.post("/api/user/clockify-credentials")
async def set_clockify_credentials(request: ClockifyCredentialsRequest, user_id: str = Depends(get_current_user_id)):
    """
    Valida la API Key de Clockify contra su API y, si es correcta, la guarda.
    """
    # 1. Validar la clave ANTES de guardar nada
    try:
        clockify_user = await ClockifyService.validate_api_key(request.api_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. La clave es válida → obtener workspace por defecto
    clockify_user_id = clockify_user.get("id")
    default_workspace_id = request.workspace_id or clockify_user.get("defaultWorkspace")

    # 3. Guardar en base de datos
    await db_service.update_clockify_credentials(
        user_id=user_id,
        api_key=request.api_key,
        workspace_id=default_workspace_id,
        clockify_user_id=clockify_user_id
    )

    return {
        "message": "Cuenta de Clockify vinculada correctamente",
        "connected": True,
        "workspace_id": default_workspace_id,
        "clockify_user_id": clockify_user_id,
    }


@app.get("/api/user/clockify-status")
async def get_clockify_status(user_id: str = Depends(get_current_user_id)):
    """
    Devuelve el estado actual de la conexión del usuario con Clockify.
    """
    user = await db_service.get_user_by_id(user_id)
    if not user or not user.get("clockify"):
        return {"connected": False}
    
    cdata = user["clockify"]
    return {
        "connected": True,
        "workspace_id": cdata.get("workspace_id"),
        "updated_at": cdata.get("updated_at")
    }


@app.get("/api/user/me")
async def get_user_me(user_id: str = Depends(get_current_user_id)):
    user = await db_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {
        "email": user.get("email"),
        "name": user.get("name")
    }


@app.post("/api/subjects/{subject_id}/grades")
async def update_grade(subject_id: str, request: SubjectGradeRequest, user_id: str = Depends(get_current_user_id)):
    """
    Actualiza la nota de una asignatura concreta.
    """
    success = await db_service.update_subject_grade(subject_id, request.grade)
    if not success:
        raise HTTPException(status_code=404, detail="Asignatura no encontrada")
    return {"message": "Nota actualizada correctamente", "grade": request.grade}


@app.get("/api/dashboard/student-analytics")
async def get_student_analytics(user_id: str = Depends(get_current_user_id)):
    """
    Devuelve las analíticas agregadas para el dashboard del alumno:
    Cruza las horas dedicadas (desde Clockify) con las notas de cada asignatura.
    """
    try:
        subjects = await db_service.get_subjects_by_user(user_id)
        
        # Obtener periodo activo si lo hay
        active_period = await db_service.get_active_period(user_id)
        start_date = None
        end_date = None
        if active_period:
            start_date = active_period.get("start_date")
            end_date = active_period.get("end_date")

        # Obtener credenciales de Clockify del usuario
        clockify_creds = await db_service.get_clockify_credentials(user_id)
        
        # Obtener entradas de tiempo de Clockify
        clockify_entries = []
        if clockify_creds and clockify_creds.get("api_key"):
            try:
                import asyncio
                cs = ClockifyService(
                    api_key=clockify_creds["api_key"] or clockify_creds.get("token"),
                    workspace_id=clockify_creds.get("workspace_id")
                )
                if start_date or end_date:
                    clockify_entries = await asyncio.to_thread(
                        cs.get_time_entries, start_date=start_date, end_date=end_date
                    )
                else:
                    clockify_entries = await asyncio.to_thread(
                        cs.get_time_entries, days_back=365
                    )
            except Exception as e:
                # Loggear el error pero no fallar la petición completa
                print(f"Error fetching Clockify entries: {e}")
                clockify_entries = []

        # Agrupar segundos de Clockify por projectId
        project_seconds = {}
        for entry in clockify_entries:
            pid = entry.get("projectId")
            if not pid:
                continue
            start_iso = entry.get("start")
            end_iso = entry.get("end")
            if start_iso and end_iso:
                try:
                    dt1 = datetime.fromisoformat(start_iso.replace('Z', '+00:00'))
                    dt2 = datetime.fromisoformat(end_iso.replace('Z', '+00:00'))
                    seconds = (dt2 - dt1).total_seconds()
                    project_seconds[pid] = project_seconds.get(pid, 0.0) + seconds
                except Exception:
                    pass

        analytics = []
        for subject in subjects:
            s_id = str(subject["_id"])
            clockify_project_id = subject.get("clockify_project_id")
            
            # Obtener segundos del proyecto desde Clockify
            seconds = 0.0
            if clockify_project_id and clockify_project_id in project_seconds:
                seconds = project_seconds[clockify_project_id]
                
            total_hours = round(seconds / 3600.0, 2)
            analytics.append({
                "id": s_id,
                "name": subject.get("name", "Asignatura"),
                "hours": total_hours,
                "weekly_hours_goal": subject.get("weekly_hours_goal"),
                "grade": subject.get("grade")
            })
            
        return {"analytics": analytics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar analíticas: {str(e)}")