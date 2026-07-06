
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Archivo con las tools, resources y prompts

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from services.clockify import ClockifyService
from services.database import DatabaseService


db_service = DatabaseService()
clockify_service = ClockifyService()


mcp = FastMCP(name="Clockify")

# @mcp.tool()
# async def get_agent_capabilities() -> str:
#     """
#     Devuelve dinámicamente la lista de todas las herramientas actualmente 
#     registradas y disponibles en este sistema de IA.
#     Úsala cuando el usuario pregunte '¿qué puedes hacer?', 'ayuda' o quiera saber tus funciones.
#     """
#     try:
#         lineas = ["Capacidades actuales del sistema Clockify:\n"]
        
#         # Método oficial de FastMCP para listar las herramientas registradas
#         herramientas = mcp.list_tools()
        
#         for tool in herramientas:
#             nombre = tool.name
#             descripcion = tool.description or "Sin descripción disponible."
            
#             lineas.append(f"🛠️ Herramienta: {nombre}\n   Acción: {descripcion}\n")
            
#         return "\n".join(lineas)
        
#     except Exception as e:
#         return f"No se pudo leer el catálogo de herramientas automáticamente: {str(e)}"

# TOOLS FOR SUBJECTS
@mcp.tool()
async def add_subject(name: str, weekly_hours_goal: int = 0, workspace_id: str = None):
    """
    Añade una nueva asignatura al sistema.
    Crea un proyecto en Clockify y lo registra en la base de datos.
    Úsala cuando el usuario diga 'Tengo la asignatura X' o 'Añade la asignatura X'.
    """
    try:
        # 1. Crear el proyecto en Clockify
        project = clockify_service.add_new_project(name, workspace_id)
        clockify_project_id = project.get("id")

        # 2. Guardar la asignatura en MongoDB
        subject = await db_service.create_subject(
            user_id="default_user",  # TODO: reemplazar por el ID real cuando haya login
            name=name,
            clockify_project_id=clockify_project_id,
            weekly_hours_goal=weekly_hours_goal
        )

        return f"Asignatura '{name}' añadida correctamente."

    except Exception as e:
        return f"Error al añadir la asignatura: {str(e)}"


@mcp.tool()
async def get_subjects():
    """
    Devuelve la lista de asignaturas del usuario.
    Úsala cuando el usuario pregunte 'Qué asignaturas tengo' o 'Muéstrame mis asignaturas'.
    """
    try:
        subjects = await db_service.get_subjects_by_user(user_id="default_user")

        if not subjects:
            return "No tienes ninguna asignatura registrada todavía."

        result = "Tus asignaturas:\n"
        for s in subjects:
            goal = f" (objetivo: {s['weekly_hours_goal']}h/semana)" if s.get('weekly_hours_goal') else ""
            result += f"- {s['name']}{goal}\n"

        return result

    except Exception as e:
        return f"Error al obtener las asignaturas: {str(e)}"

@mcp.tool()
async def get_current_time():
    """Devuelve la hora actual en formato ISO 8601."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

# # TOOOLS FOR WORKSPACES
# @mcp.tool()
# async def get_active_workspaces():
#     '''Devuelve la lista de workspaces activos del usuario en Clockify.'''
#     try:
#         return clockify_service.get_workspaces()
#     except Exception as e:
#         return f"Error: {str(e)}"
    

# @mcp.tool()
# async def set_current_workspace(workspace_id: str):
#     '''Establece el workspace activo del usuario en Clockify.'''
#     try:
#         return clockify_service.set_current_workspace(workspace_id)
#     except Exception as e:
#         return f"Error: {str(e)}"
    
# @mcp.tool()
# async def get_current_workspace_id():
#     '''Devuelve el ID del workspace activo del usuario en Clockify.'''
#     try:
#         return clockify_service.get_current_workspace_id()
#     except Exception as e:
#         return f"Error: {str(e)}"
    

# # TOOLS FOR PROJECTS
# @mcp.tool()
# async def get_projects(workspace_id: str = None):
#     '''Devuelve la lista de proyectos del usuario en Clockify para un workspace dado.'''
#     try:
#         return clockify_service.get_projects(workspace_id)
#     except Exception as e:
#         return f"Error: {str(e)}"

# @mcp.tool()
# async def create_new_project(project_name: str, workspace_id: str = None):
#     '''Crea un nuevo proyecto en Clockify para un workspace dado.'''
#     try:
#         return clockify_service.add_new_project( project_name, workspace_id)
#     except Exception as e:
#         return f"Error: {str(e)}"

# # TOOLS FOR TIME ENTRIES

# @mcp.tool()
# async def get_time_entries(workspace_id: str = None, days_back: int = 7):
#     '''Devuelve las entradas de tiempo del usuario en Clockify para un workspace dado y un número de días hacia atrás.'''
#     try:
#         return clockify_service.get_time_entries(workspace_id, days_back)
#     except Exception as e:
#         return f"Error: {str(e)}"    
    

# @mcp.tool()
# async def start_new_timer(description: str, project_id: str = None, workspace_id: str = None):
#     """
#     Inicia un temporizador activo (Timer) en este preciso instante en Clockify.
#     Usa esta herramienta cuando el usuario pida controlar el tiempo de una tarea en directo.
#     """
#     try:
#         return clockify_service.create_time_entry(
#             description=description,
#             project_id=project_id,
#             start_time=None,
#             end_time=None, # Al ser None, Clockify activa el cronómetro
#             workspace_id=workspace_id
#         )
#     except Exception as e:
#         return f"Error al iniciar el temporizador: {str(e)}"
    

# @mcp.tool()
# async def create_past_time_entry(description: str, start_time: str, end_time: str, project_id: str = None, workspace_id: str = None):
#     """
#     Crea una entrada de tiempo manual en Clockify con una hora de inicio y de fin ya definidas.
#     Útil cuando el usuario dice: 'Registra que estuve trabajando en el TFG de 10:00 a 12:00 hoy'.
    
#     IMPORTANTE: Tanto start_time como end_time deben tener formato ISO 8601 (Ej: '2026-06-22T10:00:00Z').
#     """
#     try:
#         # Nos aseguramos de que los strings lleven la 'Z' (UTC) que exige Clockify si la IA los genera planos
#         if start_time and not start_time.endswith('Z') and '+' not in start_time:
#             start_time += 'Z'
#         if end_time and not end_time.endswith('Z') and '+' not in end_time:
#             end_time += 'Z'

#         resultado = clockify_service.create_time_entry(
#             description=description,
#             project_id=project_id,
#             start_time=start_time,
#             end_time=end_time,
#             workspace_id=workspace_id
#         )
#         return f"Entrada creada con éxito: '{description}' ({start_time} -> {end_time})"
#     except Exception as e:
#         return f"Error al crear la entrada de tiempo manual: {str(e)}"


# # TOOLS FOR USERS

# @mcp.prompt()
# def greet_user(name: str, style: str = "friendly") -> str:
#     """Genera un saludo personalizado para el usuario según el estilo especificado."""
#     styles = {
#         "friendly": "Por favor, escribe un saludo amigable",
#         "formal": "Por favor, escribe un saludo formal y profesional",
#         "casual": "Por favor, escribe un saludo casual y relajado",
#     }

#     return f"{styles.get(style, styles['friendly'])} for someone named {name}."


# # TOOLS FOR USERS
# @mcp.tool()
# async def get_user_id():
#     '''Devuelve el ID del usuario en Clockify.'''
#     try:
#         return clockify_service.get_user_id()
#     except Exception as e:
#         return f"Error: {str(e)}"
    
    
if __name__ == "__main__":
    mcp.run()

    
# Ejemplo de la documentación

# @mcp.tool()
# async def long_running_task(task_name: str, ctx: Context[ServerSession, None], steps: int = 5) -> str:
#     """Execute a task with progress updates."""
#     await ctx.info(f"Starting: {task_name}")

#     for i in range(steps):
#         progress = (i + 1) / steps
#         await ctx.report_progress(
#             progress=progress,
#             total=1.0,
#             message=f"Step {i + 1}/{steps}",
#         )
#         await ctx.debug(f"Completed step {i + 1}")

#     return f"Task '{task_name}' completed"