 
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from datetime import datetime, timezone
 
# Archivo con las tools, resources y prompts
 
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
 
from services.clockify_service import ClockifyService
from services.database_service import DatabaseService
 
 
db_service = DatabaseService()
clockify_service = ClockifyService()
 
 
mcp = FastMCP(name="Clockify")
 
 
############################################################################
# HELPERS INTERNOS (no son tools, el LLM no las ve directamente)
 
async def _find_subject_by_name(user_id: str, name: str) -> dict | None:
    """Busca una asignatura por nombre (case-insensitive) entre las del usuario."""
    subjects = await db_service.get_subjects_by_user(user_id)
    return next((s for s in subjects if s["name"].lower() == name.lower()), None)
 
 
async def _find_task_by_title(subject_id: str, title: str) -> dict | None:
    """Busca una tarea por título (case-insensitive) dentro de una asignatura."""
    tasks = await db_service.get_tasks_by_subject(subject_id)
    return next((t for t in tasks if t["title"].lower() == title.lower()), None)
 
 
 
@mcp.tool()
async def get_agent_capabilities() -> str:
    """
    Devuelve la lista de herramientas disponibles para que el LLM pueda explicarlas
    al usuario de forma amigable.
    Úsala cuando el usuario pregunte '¿qué puedes hacer?', 'ayuda', quiera saber tus 
    funciones o cuando haga una consulta que esté fuera de tu ámbito (es decir, que no tengas ninguna tool específica
    que se encargue de eso) o que no esté clara.
    IMPORTANTE: No inventes herramientas ni funciones que no existan. Solo describe las que
    realmente están disponibles en el MCP.
    """
    try:
        herramientas = await mcp.list_tools()
        
        lineas = []
        for tool in herramientas:
            if tool.name != "get_agent_capabilities":
                lineas.append(f"- {tool.name}: {tool.description}")
            
        return "\n".join(lineas)
        
    except Exception as e:
        return f"Error: {str(e)}"
 
 
# TOOLS FOR PLANNING AND ORGANIZATION

# @mcp.tool()
# async def get_user_schedule(user_id: str):
#     """
#     Devuelve un resumen del horario del usuario, incluyendo asignaturas, tareas y deadlines.
#     Úsala cuando el usuario pregunte 'muéstrame mi horario' o 'qué tengo planeado'.
#     """
#     try:
#         subjects = await db_service.get_subjects_by_user(user_id)
#         periods = await db_service.get_periods_by_user(user_id)
#         tasks = []
#         for subject in subjects:
#             subject_tasks = await db_service.get_tasks_by_subject(subject["_id"])
#             tasks.extend(subject_tasks)
 
#         result = "Resumen de tu planificación:\n"
#         result += "\nAsignaturas:\n"
#         for s in subjects:
#             result += f"- {s['name']}\n"
 
#         result += "\nPeriodos:\n"
#         for p in periods:
#             marca = " (activo)" if p.get("is_active") else ""
#             result += f"- {p['name']}{marca}\n"
 
#         result += "\nTareas:\n"
#         for t in tasks:
#             estado = "✅" if t["completed"] else "⏳"
#             result += f"- {estado} {t['title']} (de {t['subject_id']})\n"
 
#         return result
#     except Exception as e:
#         return f"Error al obtener el resumen del horario: {str(e)}"
    

@mcp.tool()
async def get_user_progress(user_id: str):
    """
    Devuelve un resumen del progreso del usuario en sus asignaturas y tareas.
    Úsala cuando el usuario pregunte 'cuánto he avanzado' o 'qué progreso tengo'.
    """
    try:
        subjects = await db_service.get_subjects_by_user(user_id)
        progress_summary = []
 
        for s in subjects:
            tasks = await db_service.get_tasks_by_subject(s["_id"])
            total_tasks = len(tasks)
            completed_tasks = sum(1 for t in tasks if t["completed"])
            progress_summary.append(f"- {s['name']}: {completed_tasks}/{total_tasks} tareas completadas")
 
        return "Progreso de tus asignaturas:\n" + "\n".join(progress_summary)
    except Exception as e:
        return f"Error al obtener el progreso: {str(e)}"
    

@mcp.tool()
async def get_time_spent_summary(user_id: str):
    """
    Devuelve un resumen del tiempo total dedicado a cada asignatura.
    Úsala cuando el usuario pregunte 'cuánto tiempo he dedicado a X' o 'resumen de tiempo'.
    """
    try:
        subjects = await db_service.get_subjects_by_user(user_id)
        time_summary = []
 
        for s in subjects:
            entries = await db_service.get_time_entries_by_subject(s["_id"])
            total_seconds = sum(
                (datetime.fromisoformat(e["end_time"]) - datetime.fromisoformat(e["start_time"])).total_seconds()
                for e in entries if e.get("end_time")
            )
            hours, remainder = divmod(total_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            time_summary.append(f"- {s['name']}: {int(hours)}h {int(minutes)}m")
 
        return "Resumen de tiempo dedicado a tus asignaturas:\n" + "\n".join(time_summary)
    except Exception as e:
        return f"Error al obtener el resumen de tiempo: {str(e)}"
    

# TOOLS FOR SUBJECTS
@mcp.tool()
async def add_subject(user_id: str, name: str, weekly_hours_goal: int = 0, workspace_id: str = None):
    """
    Añade una nueva asignatura al sistema.
    IMPORTANTE: Antes de llamar a esta herramienta, asegúrate de tener el nombre
    de la asignatura. Si el usuario no lo ha especificado, pregúntaselo primero.
    No inventes ni supongas nombres.
    Úsala cuando el usuario diga 'Tengo la asignatura X' o 'Añade la asignatura X'.
    Necesita el nombre de la asignatura y opcionalmente un objetivo de horas semanales y un workspace_id.
    """
    try:
        # 1. Crear el proyecto en Clockify
        project = clockify_service.add_new_project(name, workspace_id)
        clockify_project_id = project.get("id")
 
        # 2. Guardar la asignatura en MongoDB
        subject = await db_service.create_subject(
            user_id=user_id,  # TODO: reemplazar por el ID real cuando haya login
            name=name,
            clockify_project_id=clockify_project_id,
            weekly_hours_goal=weekly_hours_goal
        )
 
        return f"Asignatura '{name}' añadida correctamente."
 
    except Exception as e:
        return f"Error al añadir la asignatura: {str(e)}"
 
 
@mcp.tool()
async def add_multiple_subjects(user_id: str, names: list[str], workspace_id: str = None):
    try:
        added = []
        skipped = []
 
        # Obtenemos los proyectos ya existentes en Clockify
        existing_projects = clockify_service.get_projects(workspace_id)
        existing_project_names = [p["name"].lower() for p in existing_projects]
 
        for name in names:
            # Comprobar si ya existe en MongoDB
            existing_subjects = await db_service.get_subjects_by_user(user_id)
            if any(s["name"].lower() == name.lower() for s in existing_subjects):
                skipped.append(name)
                continue
 
            # Comprobar si ya existe en Clockify
            if name.lower() in existing_project_names:
                # El proyecto ya existe en Clockify, buscar su ID
                project = next(p for p in existing_projects if p["name"].lower() == name.lower())
                clockify_project_id = project.get("id")
            else:
                # Crear el proyecto en Clockify
                project = clockify_service.add_new_project(name, workspace_id)
                clockify_project_id = project.get("id")
 
            await db_service.create_subject(
                user_id=user_id,
                name=name,
                clockify_project_id=clockify_project_id
            )
            added.append(name)
 
        result = ""
        if added:
            result += f"Asignaturas añadidas: {', '.join(added)}. "
        if skipped:
            result += f"Ya existían en el sistema: {', '.join(skipped)}."
        return result
 
    except Exception as e:
        return f"Error al añadir las asignaturas: {str(e)}"
    
 
@mcp.tool()
async def get_subjects(user_id: str):
    """
    Devuelve la lista de asignaturas del usuario.
    Úsala cuando el usuario pregunte 'Qué asignaturas tengo' o 'Muéstrame mis asignaturas'.
    """
    try:
        subjects = await db_service.get_subjects_by_user(user_id=user_id)
 
        if not subjects:
            return "No tienes ninguna asignatura registrada todavía."
 
        result = "Tus asignaturas:\n"
        for s in subjects:
            goal = f" (objetivo: {s['weekly_hours_goal']}h/semana)" if s.get('weekly_hours_goal') else ""
            result += f"- {s['name']}{goal}\n"
 
        return result
 
    except Exception as e:
        return f"Error al obtener las asignaturas: {str(e)}"
 
 
############################################################################
# TOOLS FOR PERIODS
 
@mcp.tool()
async def create_period(user_id: str, name: str, start_date: str, end_date: str = None):
    """
    Crea un nuevo periodo académico (cuatrimestre, trimestre, curso escolar, o cualquier
    periodo que el usuario quiera usar para organizar sus asignaturas) y lo establece
    automáticamente como el periodo activo.
    IMPORTANTE: pregunta el nombre y la fecha de inicio si el usuario no los ha dado.
    Úsala cuando el usuario diga 'empiezo un cuatrimestre nuevo' o similar.
    start_date y end_date deben tener formato ISO 8601 (ej: '2026-09-01'). end_date es
    opcional si el periodo aún no tiene fecha de fin definida.
    """
    try:
        period = await db_service.create_period(
            user_id=user_id,
            name=name,
            start_date=start_date,
            end_date=end_date
        )
        await db_service.set_active_period(user_id, period["_id"])
        return f"Periodo '{name}' creado y establecido como periodo activo."
    except Exception as e:
        return f"Error al crear el periodo: {str(e)}"
 
 
@mcp.tool()
async def get_periods(user_id: str):
    """
    Devuelve la lista de periodos académicos del usuario.
    Úsala cuando el usuario pregunte 'qué periodos tengo' o 'muéstrame mis cuatrimestres'.
    """
    try:
        periods = await db_service.get_periods_by_user(user_id)
        if not periods:
            return "No tienes ningún periodo académico registrado todavía."
 
        result = "Tus periodos:\n"
        for p in periods:
            marca = " (activo)" if p.get("is_active") else ""
            fin = p.get("end_date") or "sin fecha de fin"
            result += f"- {p['name']}: {p['start_date']} -> {fin}{marca}\n"
        return result
    except Exception as e:
        return f"Error al obtener los periodos: {str(e)}"
 
 
@mcp.tool()
async def set_current_period(user_id: str, period_name: str):
    """
    Establece un periodo ya existente como el periodo activo del usuario.
    A partir de ese momento, cuando el usuario hable de sus asignaturas sin especificar
    periodo, se entenderá que se refiere a este.
    Úsala cuando el usuario diga 'cambia al cuatrimestre X' o 'ahora estoy en Y'.
    """
    try:
        period = await db_service.get_period_by_user_and_name(user_id, period_name)
        if not period:
            return f"No encontré ningún periodo llamado '{period_name}'."
        await db_service.set_active_period(user_id, period["_id"])
        return f"Periodo activo cambiado a '{period_name}'."
    except Exception as e:
        return f"Error al cambiar de periodo: {str(e)}"
 
 
@mcp.tool()
async def get_current_period(user_id: str):
    """
    Devuelve el periodo académico activo del usuario, si tiene uno definido.
    Úsala cuando el usuario pregunte 'en qué periodo estoy' o 'qué cuatrimestre tengo activo'.
    """
    try:
        period = await db_service.get_active_period(user_id)
        if not period:
            return "No tienes ningún periodo activo ahora mismo."
        fin = period.get("end_date") or "sin fecha de fin"
        return f"Tu periodo activo es '{period['name']}' ({period['start_date']} -> {fin})."
    except Exception as e:
        return f"Error al obtener el periodo activo: {str(e)}"
 
 
############################################################################
# TOOLS FOR SUBJECTS (adicionales)
 
@mcp.tool()
async def archive_subject(user_id: str, subject_name: str):
    """
    Archiva una asignatura sin borrar su historial (tareas, tiempo dedicado, deadlines).
    Úsala cuando el usuario ya no vaya a trabajar más en una asignatura, por ejemplo al
    terminar un cuatrimestre, en vez de eliminarla del todo.
    """
    try:
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."
        await db_service.update_subject(subject["_id"], is_archived=True)
        return f"Asignatura '{subject_name}' archivada correctamente."
    except Exception as e:
        return f"Error al archivar la asignatura: {str(e)}"
 
 
@mcp.tool()
async def assign_subject_to_period(user_id: str, subject_name: str, period_name: str):
    """
    Asocia una asignatura ya existente a un periodo académico ya existente.
    Úsala si el usuario añadió una asignatura sin periodo y luego quiere organizarla dentro de uno.
    """
    try:
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."
        period = await db_service.get_period_by_user_and_name(user_id, period_name)
        if not period:
            return f"No encontré ningún periodo llamado '{period_name}'."
        await db_service.update_subject(subject["_id"], period_id=period["_id"])
        return f"Asignatura '{subject_name}' asignada al periodo '{period_name}'."
    except Exception as e:
        return f"Error al asignar la asignatura al periodo: {str(e)}"
 
 
############################################################################
# TOOLS FOR TASKS
 
@mcp.tool()
async def add_task(user_id: str, subject_name: str, title: str, description: str = "",
                    due_date: str = None, parent_task_title: str = None,
                    workspace_id: str = None):
    # """
    # Añade una nueva tarea a una asignatura. Opcionalmente puede ser una subtarea de
    # otra tarea ya existente (parent_task_title).
    # IMPORTANTE: asegúrate de tener el nombre de la asignatura y el título de la tarea.
    # Si el usuario no los ha especificado, pregúntaselos primero.
    # Úsala cuando el usuario diga 'añade la tarea X a la asignatura Y' o 'tengo que hacer X de Y'.
    # due_date, si se indica, debe tener formato ISO 8601 (ej: '2026-07-20').
    # """
    '''
    Crea un nuevo elemento en la agenda del usuario. 
    Úsala tanto para tareas normales como para exámenes, entregas de proyectos o fechas importantes.
    
    Parámetros obligatorios:
    - title: El nombre de la tarea o evento (ej: 'Examen Final', 'Entrega Práctica 1').
    
    Parámetros condicionales/opcionales:
    - subject_name: Nombre de la asignatura asociada. Puede ser omitido para eventos globales.
    - due_date: Fecha límite en formato ISO 8601 ('2026-07-15'). Es OBLIGATORIA si es un examen o entrega.
    - type: Especifica la naturaleza del evento. Valores válidos: 
        'task' (por defecto), 
        'exam' (para exámenes/recuperaciones), 
        'assignment' (para entregas de trabajos) u 
        'other'.
    '''
    
    try:
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."
 
        parent_task_id = None
        clockify_task_id = None
 
        if parent_task_title:
            # Es una subtarea: no se refleja en Clockify (no soporta tareas anidadas)
            parent_task = await _find_task_by_title(subject["_id"], parent_task_title)
            if not parent_task:
                return f"No encontré ninguna tarea llamada '{parent_task_title}' en '{subject_name}'."
            parent_task_id = parent_task["_id"]
        else:
            # Es una tarea raíz: la reflejamos también en Clockify
            clockify_task = clockify_service.add_new_task(
                project_id=subject["clockify_project_id"],
                task_name=title,
                workspace_id=workspace_id
            )
            clockify_task_id = clockify_task.get("id")
 
        await db_service.create_task(
            user_id=user_id,
            subject_id=subject["_id"],
            title=title,
            description=description,
            due_date=due_date,
            parent_task_id=parent_task_id,
            clockify_task_id=clockify_task_id
        )
        return f"Tarea '{title}' añadida a '{subject_name}' correctamente."
    except Exception as e:
        return f"Error al añadir la tarea: {str(e)}"
 
 
@mcp.tool()
async def get_tasks(user_id: str, subject_name: str, only_pending: bool = False):
    """
    Devuelve la lista de tareas de una asignatura.
    Úsala cuando el usuario pregunte 'qué tareas tengo de X' o 'muéstrame las tareas de X'.
    only_pending=True para mostrar solo las que faltan por completar.
    """
    try:
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."
 
        tasks = await db_service.get_tasks_by_subject(subject["_id"], include_completed=not only_pending)
        if not tasks:
            return f"No tienes tareas registradas para '{subject_name}'."
 
        result = f"Tareas de {subject_name}:\n"
        for t in tasks:
            estado = "✅" if t["completed"] else "⏳"
            fecha = f" (vence: {t['due_date']})" if t.get("due_date") else ""
            result += f"- {estado} {t['title']}{fecha}\n"
        return result
    except Exception as e:
        return f"Error al obtener las tareas: {str(e)}"
 
 
@mcp.tool()
async def complete_task(user_id: str, subject_name: str, task_title: str):
    """
    Marca una tarea como completada.
    Úsala cuando el usuario diga 'ya terminé X' o 'marca X como hecha'.
    """
    try:
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."
 
        task = await _find_task_by_title(subject["_id"], task_title)
        if not task:
            return f"No encontré ninguna tarea llamada '{task_title}' en '{subject_name}'."
 
        await db_service.mark_task_completed(task["_id"])
        return f"Tarea '{task_title}' marcada como completada."
    except Exception as e:
        return f"Error al completar la tarea: {str(e)}"
    
async def edit_task(subject_name: str, task_title:str, description: str = "",
                    due_date: str = None, parent_task_title: str = None,
                    workspace_id: str = None):
    """
    Edita una tarea existente de una asignatura. Permite cambiar su descripción, fecha de vencimiento,
    asignarla a otra tarea como subtarea, o actualizar su representación en Clockify.
    Úsala cuando el usuario diga 'cambia la tarea X de Y' o 'edita la tarea X de Y'.
    """


 
 
############################################################################
# TOOLS FOR TIME ENTRIES
 
@mcp.tool()
async def start_timer(user_id: str, subject_name: str, task_title: str = None, description: str = "",
                       workspace_id: str = None):
    """
    Inicia un cronómetro activo, ahora mismo, dedicado a una asignatura (y opcionalmente
    a una tarea concreta dentro de ella).
    Úsala cuando el usuario diga 'voy a ponerme a estudiar X' o 'empieza a contar el tiempo de X'.
    IMPORTANTE: comprueba primero si ya hay un cronómetro en marcha; si lo hay, dile al
    usuario que debe pararlo antes de empezar uno nuevo (usa stop_timer).
    """
    try:
        existing = await db_service.get_active_time_entry(user_id)
        if existing:
            return "Ya tienes un cronómetro en marcha. Para antes uno con stop_timer."
 
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."
 
        task = None
        clockify_task_id = None
        task_id = None
        if task_title:
            task = await _find_task_by_title(subject["_id"], task_title)
            if not task:
                return f"No encontré ninguna tarea llamada '{task_title}' en '{subject_name}'."
            task_id = task["_id"]
            clockify_task_id = task.get("clockify_task_id")
 
        # Arrancamos el timer real en Clockify (end_time=None -> cronómetro en marcha)
        clockify_service.create_time_entry(
            description=description or f"Estudiando {subject_name}",
            project_id=subject["clockify_project_id"],
            task_id=clockify_task_id,
            end_time=None,
            workspace_id=workspace_id
        )
 
        # Y lo reflejamos en nuestra propia base de datos
        start_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        await db_service.create_time_entry(
            user_id=user_id,
            subject_id=subject["_id"],
            task_id=task_id,
            start_time=start_time,
            end_time=None,
            description=description or f"Estudiando {subject_name}"
        )
 
        return f"Cronómetro iniciado para '{subject_name}'{' (' + task_title + ')' if task_title else ''}."
    except Exception as e:
        return f"Error al iniciar el cronómetro: {str(e)}"
 
 
@mcp.tool()
async def stop_timer(user_id: str):
    """
    Detiene el cronómetro que esté en marcha ahora mismo.
    Úsala cuando el usuario diga 'para el cronómetro' o 'ya he terminado de estudiar'.
    """
    try:
        entry = await db_service.get_active_time_entry(user_id)
        if not entry:
            return "No tienes ningún cronómetro en marcha ahora mismo."
 
        await db_service.stop_time_entry(entry["_id"])
        return "Cronómetro detenido y guardado correctamente."
    except Exception as e:
        return f"Error al detener el cronómetro: {str(e)}"
 
 
@mcp.tool()
async def log_time_entry(user_id: str, subject_name: str, start_time: str, end_time: str,
                          task_title: str = None, description: str = ""):
    """
    Registra manualmente una sesión de estudio ya finalizada, con hora de inicio y fin
    ya conocidas (a diferencia de start_timer/stop_timer, que son para tiempo real).
    Útil cuando el usuario dice 'estuve estudiando Matemáticas de 10:00 a 12:00 hoy'.
    IMPORTANTE: start_time y end_time deben tener formato ISO 8601 (ej: '2026-07-08T10:00:00Z').
    Si existe una tareaa concreta para esa sesión, se puede indicar task_title; si no, se deja vacío.
    """
    try:
        if not start_time.endswith('Z') and '+' not in start_time:
            start_time += 'Z'
        if not end_time.endswith('Z') and '+' not in end_time:
            end_time += 'Z'
 
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."
 
        task_id = None
        if task_title:
            task = await _find_task_by_title(subject["_id"], task_title)
            if not task:
                return f"No encontré ninguna tarea llamada '{task_title}' en '{subject_name}'."
            task_id = task["_id"]
 
        await db_service.create_time_entry(
            user_id=user_id,
            subject_id=subject["_id"],
            task_id=task_id,
            start_time=start_time,
            end_time=end_time,
            description=description or f"Estudiando {subject_name}"
        )
        return f"Entrada registrada: '{subject_name}' de {start_time} a {end_time}."
    except Exception as e:
        return f"Error al registrar la entrada de tiempo: {str(e)}"
 

 
@mcp.tool()
async def get_time_summary(user_id: str, subject_name: str):
    """
    Devuelve el resumen de tiempo dedicado a una asignatura, con sus últimas sesiones.
    Úsala cuando el usuario pregunte 'cuánto tiempo llevo en X' o 'muéstrame mis sesiones de X'.
    devuelve el tiempo dedicado en un formato amigable (horas y minutos) para el usuario.
    """
    try:
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."
 
        entries = await db_service.get_time_entries_by_subject(subject["_id"])
        if not entries:
            return f"No tienes ninguna sesión registrada para '{subject_name}' todavía."
 
        result = f"Sesiones de {subject_name}:\n"
        # for e in entries[:10]:
        for e in entries:
            fin = e.get("end_time") or "en curso"
            result += f"- {e['start_time']} -> {fin}\n"
        return result
    except Exception as e:
        return f"Error al obtener el resumen de tiempo: {str(e)}"
 
 
# ############################################################################
# TOOLS FOR WELLBEING


@mcp.tool()
async def wb_add_wellbeing_report(user_id: str, date: str, sleep_hours: float, sleep_quality: int, mood_score: int, energy_level: int, notes: str = ""):
    """
    Registra un informe de bienestar del usuario.
    Úsala cuando el usuario quiera registrar su estado de ánimo o bienestar.
    """
    try:
        await db_service.create_wellbeing_report(
            user_id=user_id,
            date=date,
            sleep_hours=sleep_hours,
            sleep_quality=sleep_quality,
            mood_score=mood_score,
            energy_level=energy_level,
            notes=notes
        )
        return "Informe de bienestar registrado correctamente."
    except Exception as e:
        return f"Error al registrar el informe de bienestar: {str(e)}"


@mcp.tool()
async def wb_get_wellbeing_report(user_id: str):
    """
    Obtiene el informe de bienestar del usuario.
    Úsala cuando el usuario quiera consultar su estado de ánimo o bienestar.
    """
    try:
        report = await db_service.get_wellbeing_report(user_id)
        if not report:
            return "No tienes ningún informe de bienestar registrado todavía."
        return report
    except Exception as e:
        return f"Error al obtener el informe de bienestar: {str(e)}"


@mcp.tool()
async def wb_get_wellbeing_trends(user_id: str):
    """
    Obtiene las tendencias de bienestar del usuario.
    Úsala cuando el usuario quiera consultar las tendencias de su estado de ánimo o bienestar.
    """
    try:
        trends = await db_service.get_wellbeing_trends(user_id)
        if not trends:
            return "No tienes ninguna tendencia de bienestar registrada todavía."
        return trends
    except Exception as e:
        return f"Error al obtener las tendencias de bienestar: {str(e)}"


if __name__ == "__main__":
    mcp.run()

    