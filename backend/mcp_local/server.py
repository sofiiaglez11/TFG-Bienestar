 
import os
import sys
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from datetime import datetime, timezone
 
 
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
 
from services.clockify_service import ClockifyService
from services.database_service import DatabaseService
import asyncio
from typing import Optional


from collections import defaultdict
from datetime import timedelta


db_service = DatabaseService()




async def _get_user_clockify_service(user_id: str) -> ClockifyService:
    """Devuelve una instancia de ClockifyService inicializada con la API Key del usuario."""
    user = await db_service.get_user_by_id(user_id)
    if user and user.get("clockify"):
        cdata = user["clockify"]
        # Soporta tanto el campo nuevo "api_key" como "token" por retrocompatibilidad
        api_key = cdata.get("api_key") or cdata.get("token")
        return ClockifyService(
            api_key=api_key,
            workspace_id=cdata.get("workspace_id")
        )
    return ClockifyService()

mcp = FastMCP(name="Clockify")
 
 
############################################################################
# HELPERS INTERNOS (no son tools, el LLM no las ve directamente)

import unicodedata

def _normalize(text: str) -> str:
    """Elimina tildes y pasa a minúsculas para comparación."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', text.lower())
        if unicodedata.category(c) != 'Mn'
    )

async def _find_subject_by_name(user_id: str, name: str, include_archived: bool = False) -> dict | None:
    """Busca una asignatura por nombre (case-insensitive, sin tildes) entre las del usuario."""
    subjects = await db_service.get_subjects_by_user(user_id, include_archived=include_archived)
    return next((s for s in subjects if _normalize(s["name"]) == _normalize(name)), None)

 
 
async def _find_task_by_title(subject_id: str, title: str) -> dict | None:
    """Busca una tarea por título (case-insensitive) dentro de una asignatura."""
    tasks = await db_service.get_tasks_by_subject(subject_id)
    return next((t for t in tasks if t["title"].lower() == title.lower()), None)
 
 
async def _build_clockify_name(task: dict) -> str:
    """
    Construye el nombre a usar en Clockify para una tarea recorriendo
    la cadena de ancestros en la BD.
    Resultado: 'abuelo/padre/hijo' (sin límite de niveles).
    El nombre de cada nodo es siempre su 'title' propio de la BD.
    """
    parts = [task["title"]]
    current = task
    while current.get("parent_task_id"):
        parent = await db_service.get_task_by_id(current["parent_task_id"])
        if not parent:
            break
        parts.insert(0, parent["title"])
        current = parent
    return "/".join(parts)


async def _update_clockify_names_recursive(
    task: dict, cs: "ClockifyService", project_id: str
) -> None:
    """
    Actualiza en Clockify el nombre de 'task' y, recursivamente, el de todos
    sus descendientes, recalculando la ruta completa desde la BD para cada uno.
    Los errores individuales se registran pero no interrumpen la propagación.
    """
    if task.get("clockify_task_id"):
        try:
            new_name = await _build_clockify_name(task)
            cs.update_task(
                project_id=project_id,
                task_id=task["clockify_task_id"],
                new_name=new_name
            )
        except Exception as e:
            print(
                f"[CLOCKIFY NAME SYNC] Error al renombrar '{task.get('title')}' "
                f"(clockify_task_id={task.get('clockify_task_id')}): {e}",
                file=sys.stderr, flush=True
            )
    # Propagar a hijos directos
    children = await db_service.get_subtasks(task["_id"])
    for child in children:
        await _update_clockify_names_recursive(child, cs, project_id)


 
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
    Devuelve un resumen del tiempo total dedicado a cada asignatura de forma agregada desde Clockify.
    Úsala cuando el usuario pregunte 'cuánto tiempo he dedicado a X' o 'resumen de tiempo'.
    """
    try:
        print(f"[MCP TOOL: GET_TIME_SPENT_SUMMARY] Iniciando consulta para user_id={user_id}", file=sys.stderr, flush=True)
        subjects = await db_service.get_subjects_by_user(user_id)
        print(f"[MCP TOOL: GET_TIME_SPENT_SUMMARY] Asignaturas encontradas: {len(subjects)} -> {[s.get('name') for s in subjects]}", file=sys.stderr, flush=True)
        
        cs = await _get_user_clockify_service(user_id)
        if not cs.api_key:
            print("[MCP TOOL: GET_TIME_SPENT_SUMMARY] Error: No se encontró API Key de Clockify.", file=sys.stderr, flush=True)
            return "No tienes configurada tu API Key de Clockify para poder consultar las horas dedicadas."

        clockify_entries = await asyncio.to_thread(cs.get_time_entries, days_back=365)
        print(f"[MCP TOOL: GET_TIME_SPENT_SUMMARY] Entradas obtenidas de Clockify: {len(clockify_entries)}", file=sys.stderr, flush=True)

        project_seconds = {}
        for entry in clockify_entries:
            pid = entry.get("projectId")
            print(f"[MCP TOOL: GET_TIME_SPENT_SUMMARY] Entry ID: {entry.get('id')} | ProjectID: {pid} | Desc: {entry.get('description')} | Start: {entry.get('start')} | End: {entry.get('end')} | Dur: {entry.get('duration')}", file=sys.stderr, flush=True)

            if not pid:
                continue

            seconds = 0.0
            start_iso = entry.get("start")
            end_iso = entry.get("end")

            if start_iso and end_iso:
                try:
                    dt1 = datetime.fromisoformat(start_iso.replace('Z', '+00:00'))
                    dt2 = datetime.fromisoformat(end_iso.replace('Z', '+00:00'))
                    seconds = (dt2 - dt1).total_seconds()
                except Exception as ex:
                    print(f"[MCP TOOL: GET_TIME_SPENT_SUMMARY] Error al parsear fechas: {ex}", file=sys.stderr, flush=True)

            if seconds <= 0 and entry.get("duration"):
                dur_str = entry.get("duration")
                import re
                h = int(re.search(r"(\d+)H", dur_str).group(1)) if re.search(r"(\d+)H", dur_str) else 0
                m = int(re.search(r"(\d+)M", dur_str).group(1)) if re.search(r"(\d+)M", dur_str) else 0
                s = int(re.search(r"(\d+)S", dur_str).group(1)) if re.search(r"(\d+)S", dur_str) else 0
                seconds = h * 3600 + m * 60 + s

            if seconds > 0:
                project_seconds[pid] = project_seconds.get(pid, 0.0) + seconds

        time_summary = []
        for s in subjects:
            pid = s.get("clockify_project_id")
            total_seconds = project_seconds.get(pid, 0.0) if pid else 0.0
            
            hours, remainder = divmod(total_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            time_summary.append(f"- {s['name']}: {int(hours)}h {int(minutes)}m")
            print(f"[MCP TOOL: GET_TIME_SPENT_SUMMARY] Asignatura '{s['name']}' (PID: {pid}) -> {int(hours)}h {int(minutes)}m (segundos: {total_seconds})", file=sys.stderr, flush=True)

        res_str = "Resumen de tiempo dedicado a tus asignaturas:\n" + "\n".join(time_summary)
        print(f"[MCP TOOL: GET_TIME_SPENT_SUMMARY] Resultado:\n{res_str}", file=sys.stderr, flush=True)
        return res_str
    except Exception as e:
        print(f"[MCP TOOL ERROR: GET_TIME_SPENT_SUMMARY] {e}", file=sys.stderr, flush=True)
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
        cs = await _get_user_clockify_service(user_id)
        if not cs.api_key:
            return "No tienes configurada tu API Key de Clockify. Conéctala desde el menú de perfil antes de añadir asignaturas."
        # 1. Crear el proyecto en Clockify
        project = cs.add_new_project(name, workspace_id)
        clockify_project_id = project.get("id")
 
        # 2. Guardar la asignatura en MongoDB
        subject = await db_service.create_subject(
            user_id=user_id,
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
        cs = await _get_user_clockify_service(user_id)
        if not cs.api_key:
            return "No tienes configurada tu API Key de Clockify. Conéctala desde el menú de perfil antes de añadir asignaturas."

        # Obtenemos los proyectos ya existentes en Clockify
        existing_projects = cs.get_projects(workspace_id)
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
                project = cs.add_new_project(name, workspace_id)
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
async def get_subjects(user_id: str, include_archived: bool = False):
    """
    Devuelve la lista de asignaturas del usuario.
    Por defecto solo muestra las activas. Usa include_archived=True si el usuario
    pregunta por asignaturas archivadas o quiere ver todas.
    Úsala cuando el usuario pregunte 'Qué asignaturas tengo', 'Muéstrame mis asignaturas'
    o cuando busques una asignatura que el usuario menciona y no aparece en la lista activa.
    """
    try:
        subjects = await db_service.get_subjects_by_user(user_id=user_id, include_archived=include_archived)
 
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
async def edit_subject(user_id: str, subject_name: str, new_name: str = None, note: str = None,
                       weekly_hours_goal: int = None, period_name: str = None, is_archived: bool = None):
    """
    Edita una asignatura existente. Permite cambiar su nombre, su objetivo de horas
    semanales y/o el periodo académico al que pertenece.
    Úsala cuando el usuario diga 'cambia el nombre de X a Y', 'quiero dedicar N horas
    semanales a X' o 'mueve X al periodo Y'.
    Solo se actualizan los campos que el usuario especifique — los demás se quedan igual.
    """
    try:
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."

        updates = {}

        cs = await _get_user_clockify_service(user_id)
        cs.update_project(subject["clockify_project_id"], new_name, note, is_archived)

        if new_name:
            updates["name"] = new_name
        if weekly_hours_goal is not None:
            updates["weekly_hours_goal"] = weekly_hours_goal
        if period_name:
            period = await db_service.get_period_by_user_and_name(user_id, period_name)
            if not period:
                return f"No encontré ningún periodo llamado '{period_name}'."
            updates["period_id"] = period["_id"]

        if not updates:
            return "No me has indicado qué quieres cambiar de la asignatura."

        await db_service.update_subject(subject["_id"], **updates)
        


        cambios = []
        if new_name:
            cambios.append(f"nombre → '{new_name}'")
        if weekly_hours_goal is not None:
            cambios.append(f"objetivo semanal → {weekly_hours_goal}h")
        if period_name:
            cambios.append(f"periodo → '{period_name}'")

        return f"Asignatura '{subject_name}' actualizada: {', '.join(cambios)}."
    except Exception as e:
        return f"Error al editar la asignatura: {str(e)}"


# @mcp.tool()
# async def delete_subject(user_id: str, subject_name: str):
#     """
#     Elimina permanentemente una asignatura y todo su historial (tareas, sesiones de tiempo).
#     Antes de llamar a esta herramienta, SIEMPRE pide confirmación explícita al usuario,
#     ya que la acción no se puede deshacer. Si el usuario solo quiere dejar de trabajar
#     en ella sin perder el historial, sugiere usar archive_subject en su lugar.
#     """
#     try:
#         subject = await _find_subject_by_name(user_id, subject_name)
#         if not subject:
#             return f"No encontré ninguna asignatura llamada '{subject_name}'."

#         # Borrar de la BD primero (tareas, sesiones, asignatura)
#         await db_service.delete_subject(subject["_id"])

#         # Intentar borrar el proyecto en Clockify (no crítico si falla)
#         clockify_note = ""
#         try:
#             cs = await _get_user_clockify_service(user_id)
#             if cs.api_key and subject.get("clockify_project_id"):
#                 cs.delete_project(subject["clockify_project_id"])
#         except Exception as ce:
#             clockify_note = f" (aviso: no se pudo eliminar el proyecto de Clockify: {ce})"

#         return f"Asignatura '{subject_name}' eliminada correctamente junto con todas sus tareas y sesiones.{clockify_note}"
#     except Exception as e:
#         return f"Error al eliminar la asignatura: {str(e)}"

@mcp.tool()
async def delete_subject(user_id: str, subject_name: str):
    """
    Elimina PERMANENTEMENTE una asignatura y todo su historial (tareas, sesiones de tiempo).
    Esta acción NO se puede deshacer.

    FLUJO OBLIGATORIO antes de llamar a esta herramienta:
    1. Pide SIEMPRE confirmación explícita al usuario: '¿Estás seguro de que quieres eliminar
       permanentemente la asignatura o prefieres archivarla?'
       - Si prefiere archivar: usa archive_subject y no hagas nada más.
       - Si confirma eliminar: continúa con este flujo.
    2. La asignatura debe estar archivada primero (is_archived=True). Si no lo está, indicáselo al usuario para que la archive

    """
    try:
        # Buscar incluyendo archivadas
        subject = await _find_subject_by_name(user_id, subject_name, include_archived=True)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."

        if not subject.get("is_archived"):
            return (
                f"La asignatura '{subject_name}' no está archivada. "
                f"Dile al usuario que tiene que archivarla primero, "
            )

        # Intentar borrar de Clockify  
        cs = await _get_user_clockify_service(user_id)
        if cs.api_key and subject.get("clockify_project_id"):
            try:
                cs.delete_project(subject["clockify_project_id"])
            except Exception as ce:
                error_str = str(ce)
                print(f"[Clockify delete error] {ce}", file=sys.stderr, flush=True)

                if "active project" in error_str.lower() or "501" in error_str:
                    return (
                        f"Clockify indica que el proyecto '{subject_name}' no está archivado allí. "
                        f"Llama a archive_subject para sincronizar el estado en Clockify "
                        f"y luego vuelve a llamar a delete_subject."
                    )

                # Si hay cualquier otro error de Clockify
                return (
                    f"No se pudo eliminar el proyecto de Clockify ({ce}). "
                    f"La asignatura NO ha sido eliminada del sistema para evitar inconsistencias. "
                    f"Informa al usuario y pregúntale cómo quiere proceder."
                )

        # Solo si Clockify ha ido bien: borrar de MongoDB
        await db_service.delete_subject(subject["_id"])

        return (
            f"Asignatura '{subject_name}' eliminada permanentemente junto con todas sus "
            f"tareas y sesiones de tiempo."
        )
    except Exception as e:
        return f"Error al eliminar la asignatura: {str(e)}"


 
 
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
 
# @mcp.tool()
# async def archive_subject(user_id: str, subject_name: str):
#     """
#     Archiva una asignatura sin borrar su historial (tareas, tiempo dedicado, deadlines).
#     Úsala cuando el usuario ya no vaya a trabajar más en una asignatura, por ejemplo al
#     terminar un cuatrimestre, en vez de eliminarla del todo.
#     """
#     try:
#         subject = await _find_subject_by_name(user_id, subject_name)
#         if not subject:
#             return f"No encontré ninguna asignatura llamada '{subject_name}'."
#         await db_service.update_subject(subject["_id"], is_archived=True)
#         return f"Asignatura '{subject_name}' archivada correctamente."
#     except Exception as e:
#         return f"Error al archivar la asignatura: {str(e)}"
 
@mcp.tool()
async def archive_subject(user_id: str, subject_name: str):
    """
    Archiva una asignatura: la marca como inactiva en el sistema y la oculta en Clockify.
    Úsala cuando el usuario ya no vaya a trabajar más en una asignatura (por ejemplo, al
    terminar un cuatrimestre) pero quiera conservar el historial de tiempo y tareas.
    Una asignatura archivada NO aparece en las listas normales.
    IMPORTANTE: archivar es el paso previo obligatorio antes de poder eliminar una asignatura.
    Si el usuario quiere eliminarla definitivamente, primero archívala con esta herramienta
    y luego usa delete_subject.
    """
    try:
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."

        if subject.get("is_archived"):
            return f"La asignatura '{subject_name}' ya está archivada."

        # rchivar en Clockify 
        cs = await _get_user_clockify_service(user_id)
        if cs.api_key and subject.get("clockify_project_id"):
            try:
                cs.archive_project(subject["clockify_project_id"])
            except Exception as ce:
                print(f"[Clockify archive error] {ce}", file=sys.stderr, flush=True)
                return (
                    f"No se pudo archivar el proyecto '{subject_name}' en Clockify: {ce}. "
                    f"La asignatura NO ha sido archivada para evitar inconsistencias."
                )

        # Archivar en MongoDB
        await db_service.update_subject(subject["_id"], is_archived=True)

        return (
            f"Asignatura '{subject_name}' archivada correctamente. "
            f"Ya no aparecerá en tus listas activas ni en Clockify. "
            f"Si quieres eliminarla definitivamente (esto borrará todo su historial), usa delete_subject."
        )
    except Exception as e:
        return f"Error al archivar la asignatura: {str(e)}"

@mcp.tool()
async def unarchive_subject(user_id: str, subject_name: str):
    """
    Desarchiva una asignatura: la vuelve a marcar como activa en el sistema y en Clockify.
    Úsala cuando el usuario quiera recuperar una asignatura que había archivado previamente,
    por ejemplo si se equivocó o quiere retomarla.
    Las asignaturas archivadas no aparecen en las listas normales, pero siguen existiendo.
    """
    try:
        # Buscar incluyendo archivadas, que es donde estará
        subject = await _find_subject_by_name(user_id, subject_name, include_archived=True)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}', ni activa ni archivada."

        if not subject.get("is_archived"):
            return f"La asignatura '{subject_name}' ya está activa, no está archivada."

        # Desarchivar en Clockify
        cs = await _get_user_clockify_service(user_id)
        if cs.api_key and subject.get("clockify_project_id"):
            try:
                cs.unarchive_project(subject["clockify_project_id"])
            except Exception as ce:
                print(f"[Clockify unarchive error] {ce}", file=sys.stderr, flush=True)
                return (
                    f"No se pudo desarchivar el proyecto '{subject_name}' en Clockify: {ce}. "
                    f"La asignatura NO ha sido desarchivada para evitar inconsistencias."
                )

        # Desarchivar en MongoDB
        await db_service.update_subject(subject["_id"], is_archived=False)

        return (
            f"Asignatura '{subject_name}' desarchivada correctamente. "
            f"Vuelve a aparecer en tus listas activas y en Clockify."
        )
    except Exception as e:
        return f"Error al desarchivar la asignatura: {str(e)}"

 
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
                    workspace_id: str = None, priority: int = None,
                    tags: list[str] = None):
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
    - priority: Prioridad opcional de la tarea, entero del 1 al 5.
        REGLA CRÍTICA DE PRIORIDAD: 5 = prioridad MÁS ALTA (máxima urgencia), 1 = prioridad MÁS BAJA (mínima urgencia).
        Escala: 1 = muy baja, 2 = baja, 3 = media, 4 = alta, 5 = muy alta. NUNCA interpretes 1 como prioridad máxima.
        Si el usuario no menciona prioridad, no la preguntes; déjala como None.
    - tags: Lista opcional de etiquetas (strings) para categorizar la tarea.
        Ejemplos: ['teórico', 'difícil'], ['repaso', 'examen'].
        Si el usuario no menciona tags, déjalo como None (lista vacía en BD).
    '''
    
    try:
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."

        parent_task_id = None
        clockify_task_id = None

        if parent_task_title:
            parent_task = await _find_task_by_title(subject["_id"], parent_task_title)
            if not parent_task:
                return f"No encontré ninguna tarea llamada '{parent_task_title}' en '{subject_name}'."
            parent_task_id = parent_task["_id"]

        # Comprobar duplicados: misma asignatura, mismo titulo (case-insensitive) y mismo padre
        existing_tasks = await db_service.get_tasks_by_subject(subject["_id"])
        duplicate = next(
            (t for t in existing_tasks
             if t["title"].lower() == title.lower()
             and t.get("parent_task_id") == parent_task_id),
            None
        )
        if duplicate:
            nivel = (
                f"como subtarea de '{parent_task_title}'"
                if parent_task_id
                else f"en '{subject_name}' (nivel raiz)"
            )
            return (
                f"Ya existe una tarea llamada '{title}' {nivel}. "
                f"Usa un nombre diferente para evitar confusiones."
            )

        # Construir el nombre Clockify: si tiene padre, incluir la ruta completa
        clockify_name = title
        if parent_task_id:
            # Construimos un doc temporal para calcular la ruta completa de ancestros
            temp_task = {"title": title, "parent_task_id": parent_task_id, "_id": None}
            clockify_name = await _build_clockify_name(temp_task)

        cs = await _get_user_clockify_service(user_id)
        if cs.api_key:
            clockify_task = cs.add_new_task(
                project_id=subject["clockify_project_id"],
                task_name=clockify_name,
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
            clockify_task_id=clockify_task_id,
            priority=priority,
            tags=tags
        )
        return f"Tarea '{title}' añadida a '{subject_name}' correctamente."
    except Exception as e:
        return f"Error al añadir la tarea: {str(e)}"
 
 
# @mcp.tool()
# async def get_tasks(user_id: str, subject_name: str, only_pending: bool = False):
#     """
#     Devuelve la lista de tareas de una asignatura.
#     Úsala cuando el usuario pregunte 'qué tareas tengo de X' o 'muéstrame las tareas de X'.
#     only_pending=True para mostrar solo las que faltan por completar.
#     Si hay subtareas, muestralas de forma jerarquizada, se tiene que entender en el mensaje
#     cuál es la tarea principal y cuáles son sus subtareas.
#     """
#     try:
#         subject = await _find_subject_by_name(user_id, subject_name)
#         if not subject:
#             return f"No encontré ninguna asignatura llamada '{subject_name}'."
 
#         tasks = await db_service.get_tasks_by_subject(subject["_id"], include_completed=not only_pending)
#         if not tasks:
#             return f"No tienes tareas registradas para '{subject_name}'."
 
#         result = f"Tareas de {subject_name}:\n"
#         for t in tasks:
#             state = "✅" if t["completed"] else "⏳"
#             date = f" (vence: {t['due_date']})" if t.get("due_date") else ""
#             result += f"- {state} {t['title']}{date}\n"
#         return result
#     except Exception as e:
#         return f"Error al obtener las tareas: {str(e)}"
 

@mcp.tool()
async def get_tasks(user_id: str, subject_name: str, only_pending: bool = False):
    """
    Devuelve las tareas de una asignatura como datos estructurados (JSON).
    Úsala cuando el usuario pregunte 'qué tareas tengo de X' o 'muéstrame las tareas de X'.
    only_pending=True para mostrar solo las pendientes.

    La respuesta es un JSON con esta estructura:
    {
      "subject": "Nombre asignatura",
      "total": N,
      "tasks": [
        {
          "title": "...",
          "completed": bool,
          "due_date": "...",      // null si no tiene fecha
          "description": "...",
          "subtasks": [           // lista vacía si no tiene subtareas
            { "title": "...", "completed": bool, "due_date": "...", "description": "..." }
          ]
        }
      ]
    }

    Interpreta estos datos para presentarlos de forma clara al usuario:
    - Muestra cada tarea principal y debajo sus subtareas con jerarquía visible
    - Indica siempre si están completadas o pendientes
    - Menciona la fecha de vencimiento si existe
    """
    try:
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."

        all_tasks = await db_service.get_tasks_by_subject(subject["_id"], include_completed=not only_pending)
        if not all_tasks:
            return f"No tienes tareas registradas para '{subject_name}'."

        # Separar tareas raíz de subtareas y agruparlas por padre
        all_task_ids = {t["_id"] for t in all_tasks}
        root_tasks = [
            t for t in all_tasks 
            if not t.get("parent_task_id") or t.get("parent_task_id") not in all_task_ids
        ]
        
        subtasks_by_parent = {}
        for t in all_tasks:
            pid = t.get("parent_task_id")
            if pid and pid in all_task_ids:
                subtasks_by_parent.setdefault(pid, []).append(t)

        def serialize(t):
            children = subtasks_by_parent.get(t["_id"], [])
            children.sort(key=lambda st: st.get("priority") or 0, reverse=True)
            return {
                "title": t.get("title"),
                "completed": t.get("completed", False),
                "due_date": t.get("due_date"),
                "description": t.get("description") or "",
                "priority": t.get("priority"),  # int 1-5 o null
                "tags": t.get("tags") or [],
                "subtasks": [serialize(child) for child in children]
            }

        # Ordenar tareas raíz por prioridad descendente (5=muy alta primero, None al final)
        root_tasks.sort(key=lambda t: t.get("priority") or 0, reverse=True)

        tasks_data = [serialize(root) for root in root_tasks]

        return json.dumps({
            "subject": subject_name,
            "total": len(all_tasks),
            "tasks": tasks_data
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"Error al obtener las tareas: {str(e)}"

 
    
@mcp.tool()
async def complete_task(user_id: str, subject_name: str, task_title: str, completed: bool = True):
    """
    Marca una tarea como completada o pendiente.
    Úsala cuando el usuario diga 'ya terminé X' o 'marca X como hecha'.
    Para revertirla: completed=False.
    """
    try:
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."

        task = await _find_task_by_title(subject["_id"], task_title)
        if not task:
            return f"No encontré ninguna tarea llamada '{task_title}' en '{subject_name}'."

        # 1. Actualizar en MongoDB
        await db_service.mark_task_completed(task["_id"], completed)

        # 2. Sincronizar en Clockify (no crítico)
        try:
            cs = await _get_user_clockify_service(user_id)
            if cs.api_key and task.get("clockify_task_id") and subject.get("clockify_project_id"):
                clockify_status = "DONE" if completed else "ACTIVE"
                cs.update_task(
                    project_id=subject["clockify_project_id"],
                    task_id=task["clockify_task_id"],
                    status=clockify_status,
                    new_name=task['title']
                )
        except Exception:
            pass  # no crítico

        estado = "completada" if completed else "pendiente"
        return f"Tarea '{task_title}' marcada como {estado}."
    except Exception as e:
        return f"Error al completar la tarea: {str(e)}"



@mcp.tool()
async def edit_task(user_id: str, subject_name: str, task_title: str,
                    new_title: str = None, description: str = None,
                    due_date: str = None, priority: int = None,
                    tags: list[str] = None):
    """
    Edita una tarea existente: título, descripción, fecha de vencimiento, prioridad o tags.
    Para marcar una tarea como completada o revertirla, usa complete_task.
    Para cambiar la jerarquía (padre/subtarea), usa set_task_hierarchy.
    due_date debe tener formato ISO 8601 (ej: '2026-07-20').
    priority: entero del 1 al 5 (5=prioridad MÁS ALTA / máxima, 1=prioridad MÁS BAJA / mínima. 1=muy baja, 2=baja, 3=media, 4=alta, 5=muy alta).
        Pasa 0 o un valor centinela si el usuario quiere eliminar la prioridad (la dejarás como None en BD).
    tags: lista completa de tags que debe tener la tarea tras la edición.
        Para AÑADIR un tag: lee los tags actuales con get_tasks y pasa la lista con el nuevo tag añadido.
        Para QUITAR un tag: lee los tags actuales con get_tasks y pasa la lista sin ese tag.
        Para BORRAR todos los tags: pasa una lista vacía [].
    """
    try:
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."

        task = await _find_task_by_title(subject["_id"], task_title)
        if not task:
            return f"No encontré ninguna tarea llamada '{task_title}' en '{subject_name}'."

        updates = {}
        if new_title:
            updates["title"] = new_title
        if description is not None:
            updates["description"] = description
        if due_date is not None:
            updates["due_date"] = due_date
        if priority is not None:
            # Permitir borrar la prioridad pasando 0
            updates["priority"] = None if priority == 0 else priority
        if tags is not None:
            # Normalizar: sin duplicados, sin espacios en los extremos
            updates["tags"] = list(dict.fromkeys(t.strip() for t in tags if t.strip()))

        if not updates:
            return "No me has indicado qué quieres cambiar de la tarea."

        # 1. Actualizar en MongoDB
        await db_service.update_task(task["_id"], **updates)

        # 2. Si cambia el nombre, sincronizar con Clockify:
        #    - La propia tarea recibe su nueva ruta (padre/nuevo_nombre)
        #    - Todos sus descendientes también deben actualizarse (su ruta incluye el nombre de esta tarea)
        if new_title:
            try:
                cs = await _get_user_clockify_service(user_id)
                if cs.api_key and subject.get("clockify_project_id"):
                    # Obtener el doc actualizado de la tarea para calcular la ruta correcta
                    updated_task = await db_service.get_task_by_id(task["_id"])
                    if updated_task:
                        await _update_clockify_names_recursive(
                            updated_task,
                            cs,
                            subject["clockify_project_id"]
                        )
            except Exception as e:
                print(f"[CLOCKIFY SYNC] Error al sincronizar nombres tras renombrar: {e}",
                      file=sys.stderr, flush=True)  # no crítico

        print(f"[UPDATE TASK] {updates}", file=sys.stderr, flush=True)

        cambios = []
        if new_title:
            cambios.append(f"título: '{new_title}'")
        if description is not None:
            cambios.append("descripción actualizada")
        if due_date is not None:
            cambios.append(f"fecha límite: '{due_date}'")
        if priority is not None:
            p_label = {0: "eliminada", 1: "muy baja", 2: "baja", 3: "media", 4: "alta", 5: "muy alta"}.get(priority, str(priority))
            cambios.append(f"prioridad: {p_label}")
        if tags is not None:
            cambios.append(f"tags: {updates.get('tags', [])!r}")

        return f"Tarea '{task_title}' actualizada: {', '.join(cambios)}."
    except Exception as e:
        return f"Error al editar la tarea: {str(e)}"


@mcp.tool()
async def set_task_hierarchy(user_id: str, subject_name: str,
                              child_task_titles: list, parent_task_title: str = None):
    """
    Establece la jerarquía padre-hijo entre tareas de una asignatura.
    Usa este tool SIEMPRE que el usuario quiera que una o varias tareas sean
    subtareas de otra, o que dejen de serlo.

    Parámetros:
    - child_task_titles: lista de títulos de las tareas que se van a convertir en subtareas.
    - parent_task_title: título de la tarea padre. Si es None o vacío, las tareas hijas
      pasan a ser tareas raíz (sin padre).

    IMPORTANTE: usa siempre los títulos exactos de las tareas, nunca sus IDs.
    Este tool resuelve los IDs internamente para evitar errores.
    """
    try:
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."

        # Resolver ID del padre (o None si se quiere hacer tarea raíz)
        parent_id = None
        if parent_task_title:
            parent_task = await _find_task_by_title(subject["_id"], parent_task_title)
            if not parent_task:
                return f"No encontré la tarea padre '{parent_task_title}' en '{subject_name}'."
            parent_id = parent_task["_id"]

        cs = await _get_user_clockify_service(user_id)

        resultados = []
        for child_title in child_task_titles:
            child_task = await _find_task_by_title(subject["_id"], child_title)
            if not child_task:
                resultados.append(f"⚠️ No encontré '{child_title}'")
                continue

            # Evitar ciclos: la tarea hija no puede ser padre de sí misma
            if parent_id and str(child_task["_id"]) == str(parent_id):
                resultados.append(f"⚠️ '{child_title}' no puede ser su propio padre")
                continue

            # 1. Actualizar la jerarquía en MongoDB
            await db_service.update_task(child_task["_id"], parent_task_id=parent_id)

            # 2. Sincronizar nombres en Clockify: la tarea y todos sus descendientes
            #    reciben nuevas rutas basadas en la jerarquía actualizada.
            if cs.api_key and subject.get("clockify_project_id"):
                try:
                    # Obtener el doc actualizado (ya tiene el nuevo parent_task_id)
                    updated_child = await db_service.get_task_by_id(child_task["_id"])
                    if updated_child:
                        await _update_clockify_names_recursive(
                            updated_child,
                            cs,
                            subject["clockify_project_id"]
                        )
                except Exception as e:
                    print(
                        f"[CLOCKIFY SYNC] Error al sincronizar nombres tras mover '{child_title}': {e}",
                        file=sys.stderr, flush=True
                    )  # no crítico

            if parent_id:
                resultados.append(f"✅ '{child_title}' → subtarea de '{parent_task_title}'")
            else:
                resultados.append(f"✅ '{child_title}' → tarea raíz")

            print(f"[HIERARCHY] {child_title} parent_id={parent_id}", file=sys.stderr, flush=True)

        return "\n".join(resultados)
    except Exception as e:
        return f"Error al establecer jerarquía: {str(e)}"


# @mcp.tool()
# async def delete_task(user_id: str, subject_name: str, task_title: str,
#                       confirmed: bool = False, workspace_id: str = None):
#     """
#     Elimina permanentemente una tarea y todas sus subtareas (en cascada).
#     IMPORTANTE: SIEMPRE pide confirmación explícita al usuario antes de llamar
#     a esta herramienta, ya que la acción NO se puede deshacer.
#     Solo llama a este tool con confirmed=True cuando el usuario haya confirmado
#     explícitamente que quiere borrar la tarea.

#     Si la tarea tiene subtareas, también se eliminarán.
#     """
#     if not confirmed:
#         return (
#             "Esta acción eliminará la tarea y todas sus subtareas de forma permanente. "
#             "¿Confirmas que quieres borrarla? Dime 'sí, bórrala' para proceder."
#         )

#     try:
#         subject = await _find_subject_by_name(user_id, subject_name)
#         if not subject:
#             return f"No encontré ninguna asignatura llamada '{subject_name}'."

#         task = await _find_task_by_title(subject["_id"], task_title)
#         if not task:
#             return f"No encontré ninguna tarea llamada '{task_title}' en '{subject_name}'."

#         task_id = task["_id"]
#         clockify_task_id = task.get("clockify_task_id")

#         # 1. Borrar en MongoDB (cascade=True borra subtareas también)
#         deleted_ids = await db_service.delete_task(task_id, cascade=True)
#         num_deleted = len(deleted_ids)

#         # 2. Intentar borrar en Clockify (no crítico — requiere plan de pago)
#         clockify_note = ""
#         try:
#             cs = await _get_user_clockify_service(user_id)
#             if cs.api_key and clockify_task_id and subject.get("clockify_project_id"):
#                 ok = cs.delete_task(
#                     project_id=subject["clockify_project_id"],
#                     task_id=clockify_task_id,
#                     workspace_id=workspace_id
#                 )
#                 if not ok:
#                     clockify_note = " (no se pudo eliminar en Clockify)"
#         except Exception as e:
#             print(f"[DELETE TASK] Error Clockify: {e}", file=sys.stderr, flush=True)
#             pass  # no crítico

#         print(f"[DELETE TASK] '{task_title}' → {num_deleted} tarea(s) eliminadas: {deleted_ids}", file=sys.stderr, flush=True)

#         if num_deleted == 1:
#             return f"🗑️ Tarea '{task_title}' eliminada correctamente.{clockify_note}"
#         else:
#             return (
#                 f"🗑️ Tarea '{task_title}' y {num_deleted - 1} subtarea(s) eliminadas correctamente.{clockify_note}"
#             )

#     except Exception as e:
#         return f"Error al eliminar la tarea: {str(e)}"

@mcp.tool()
async def delete_task(user_id: str, subject_name: str, task_title: str):
    """
    Elimina PERMANENTEMENTE una tarea y todo su historial de tiempo tanto de MongoDB como de Clockify.
    Esta acción NO se puede deshacer.


    FLUJO OBLIGATORIO antes de llamar a esta herramienta:
    Pide SIEMPRE confirmación explícita al usuario:
       '¿Estás seguro de que quieres eliminar permanentemente la tarea "{task_title}" de "{subject_name}"?
       Ten en cuenta que esta operación es irreversible y se borrarán todos los tiempos y registros asociados a ella.'
       - Si el usuario NO ha confirmado explícitamente todavía, NO llames a esta herramienta; pregúntale primero y espera su confirmación.
       - Si confirma eliminar: llama a esta herramienta.
    """
    try:
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."


        task = await _find_task_by_title(subject["_id"], task_title)
        if not task:
            all_tasks = await db_service.get_tasks_by_subject(subject["_id"], include_completed=True)
            titles = [t.get("title") for t in all_tasks]
            return f"No encontré ninguna tarea llamada '{task_title}' en '{subject_name}'. Tareas disponibles: {', '.join(titles) if titles else 'ninguna'}."


        # 1. Eliminar en Clockify si existe
        clockify_task_id = task.get("clockify_task_id")
        clockify_proj_id = subject.get("clockify_project_id")
        if clockify_task_id and clockify_proj_id:
            try:
                cs = await _get_user_clockify_service(user_id)
                cs_resp = cs.delete_task(
                    project_id=clockify_proj_id,
                    task_id=clockify_task_id,
                    task_name=task.get("title")
                )
            except Exception as ce:
                # NO BORRAR DE MONGO SI CLOCKIFY FALLA (para evitar inconsistencias)
                return (
                    f"No se pudo eliminar la tarea de Clockify ({ce}). "
                    f"La tarea NO ha sido eliminada del sistema para evitar inconsistencias."
                )


        # 2. Eliminar en MongoDB (tarea y sus time_entries)
        await db_service.delete_task(task["_id"])
        return f"Tarea '{task_title}' y todos sus tiempos eliminados permanentemente tanto de Clockify como de la base de datos."
    except Exception as e:
        return f"Error al eliminar la tarea: {str(e)}"



 
 
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

    description: texto descriptivo para la entrada en Clockify. Si el usuario ha mencionado
    en qué va a trabajar concretamente (ej: "voy a estudiar el tema 3"), úsalo como descripción.
    Si no, déjalo vacío para que el sistema genere uno automáticamente.
    """
    try:
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
 
        # Construir descripción automática si no se proporcionó una
        if not description:
            if task_title:
                description = f"{subject_name} · {task_title}"
            else:
                description = f"Estudiando {subject_name}"

        # Arrancamos el timer real en Clockify (end_time=None -> cronómetro en marcha)
        cs = await _get_user_clockify_service(user_id)
        if not cs.api_key:
            return "No tienes configurada tu API Key de Clockify. Conéctala desde el menú de perfil para poder registrar tiempo."
        cs.create_time_entry(
            description=description,
            project_id=subject["clockify_project_id"],
            task_id=clockify_task_id,
            end_time=None,
            workspace_id=workspace_id
        )
 
        print(f"FIN TOOL START TIMER", file=sys.stderr, flush=True)

        return f"Cronómetro iniciado para '{subject_name}'{' (' + task_title + ')' if task_title else ''}."
    except Exception as e:
        return f"Error al iniciar el cronómetro: {str(e)}"
 
 
 
@mcp.tool()
async def stop_timer(user_id: str):
    """
    Detiene el cronómetro que esté en marcha ahora mismo.
    Úsala cuando el usuario diga 'para el cronómetro', 'ya he terminado de estudiar' o 'ya paré'.
    NO necesita ningún parámetro de asignatura — para el cronómetro que esté activo, sea cual sea.
    NO llames a start_timer después de esta herramienta salvo que el usuario lo pida explícitamente.
    """
    try:
        cs = await _get_user_clockify_service(user_id)
        
        # Obtener el timer activo directamente de Clockify
        active_entry = cs.get_active_time_entry()
        # print(f"TOOL STOP TIMER: active_entry={active_entry}", file=sys.stderr, flush=True)
        
        if not active_entry:
            return "No tienes ningún cronómetro en marcha ahora mismo."
        
        # cs.stop_time_entry(active_entry["id"])
        cs.stop_time_entry()

        return "Cronómetro detenido y guardado correctamente."
    except Exception as e:
        # print(f"Error al detener el cronómetro: {str(e)}", file=sys.stderr, flush=True)
        return f"Error al detener el cronómetro: {str(e)}"

@mcp.tool()
async def get_active_time_entry(user_id: str):
    """
    Devuelve el cronómetro que esté en marcha ahora mismo.
    Úsala cuando el usuario pregunte 'cuánto tiempo llevo estudiando?' o 'cuánto tiempo llevo con el cronómetro en marcha?'.
    """
    try:
        cs = await _get_user_clockify_service(user_id)
        
        # Obtener el timer activo directamente de Clockify
        active_entry = cs.get_active_time_entry()
        # print(f"TOOL GET ACTIVE TIME ENTRY: active_entry={active_entry}", file=sys.stderr, flush=True)
        
        if not active_entry:
            return "No tienes ningún cronómetro en marcha ahora mismo."
        
        return f"Cronómetro activo: {active_entry}"
    except Exception as e:
        # print(f"Error al obtener el cronómetro activo: {str(e)}", file=sys.stderr, flush=True)
        return f"Error al obtener el cronómetro activo: {str(e)}"

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
 
        clockify_task_id = None
        if task_title:
            task = await _find_task_by_title(subject["_id"], task_title)
            if not task:
                return f"No encontré ninguna tarea llamada '{task_title}' en '{subject_name}'."
            clockify_task_id = task.get("clockify_task_id")
 
        cs = await _get_user_clockify_service(user_id)
        if not cs.api_key:
            return "No tienes configurada tu API Key de Clockify para poder registrar la entrada de tiempo."

        await asyncio.to_thread(
            cs.create_time_entry,
            description=description or f"Estudiando {subject_name}",
            project_id=subject.get("clockify_project_id"),
            task_id=clockify_task_id,
            start_time=start_time,
            end_time=end_time
        )
        return f"Entrada registrada en Clockify: '{subject_name}' de {start_time} a {end_time}."
    except Exception as e:
        return f"Error al registrar la entrada de tiempo: {str(e)}"
 

 

# @mcp.tool()
# async def get_time_summary(user_id: str, subject_name: str):
#     """
#     Consulta de solo lectura: devuelve el tiempo total dedicado a una asignatura
#     y sus últimas sesiones registradas, SIN detener ningún cronómetro en marcha.
#     NO usar esta herramienta para parar el tiempo — para eso existe stop_timer.
#     Úsala cuando el usuario pregunte 'cuánto tiempo llevo estudiando X' o 
#     'cuántas horas le he dedicado a X'.
#     """
#     try:
#         print(f"[DEBUG] get_time_summary - user_id: {user_id}, subject_name: '{subject_name}'", file=sys.stderr, flush=True)
#         subject = await _find_subject_by_name(user_id, subject_name)
#         print(f"[DEBUG] subject encontrado: {subject}", file=sys.stderr, flush=True)
#         if not subject:
#             return f"No encontré ninguna asignatura llamada '{subject_name}'."
 
#         entries = await db_service.get_time_entries_by_subject(subject["_id"])
#         if not entries:
#             return f"No tienes ninguna sesión registrada para '{subject_name}' todavía."
 
#         result = f"Sesiones de {subject_name}:\n"
#         # for e in entries[:10]:
#         for e in entries:
#             fin = e.get("end_time") or "en curso"
#             result += f"- {e['start_time']} -> {fin}\n"
#         return result
#     except Exception as e:
#         return f"Error al obtener el resumen de tiempo: {str(e)}"



@mcp.tool()
async def get_time_summary(user_id: str, subject_name: Optional[str] = None, days_back: Optional[int] = 60):
    """
    Consulta de solo lectura: devuelve el resumen de tiempo directamente desde Clockify,
    agrupado por tarea y con el total acumulado.

    - Si se pasa `subject_name`, filtra por esa asignatura usando su projectId real de Clockify.
    - Si `subject_name` es None o "todas", devuelve el resumen general de todas las asignaturas.
    - `days_back` permite especificar cuántos días atrás consultar (por defecto 60 días).
    """
    try:
        print(f"[MCP TOOL: GET_TIME_SUMMARY] user_id={user_id}, subject_name='{subject_name}', days_back={days_back}", file=sys.stderr, flush=True)
        # 1. Credenciales y servicio Clockify
        user_creds = await db_service.get_clockify_credentials(user_id)
        if not user_creds or not user_creds.get("api_key"):
            print("[MCP TOOL: GET_TIME_SUMMARY] Error: Sin API Key", file=sys.stderr, flush=True)
            return "No tienes configurada tu API Key de Clockify."

        clockify = ClockifyService(api_key=user_creds["api_key"])

        # 2. Si hay asignatura concreta, resolver su projectId desde la BD
        target_project_id = None
        is_all = not subject_name or subject_name.strip().lower() in ["todas", "all"]

        subject = None
        if not is_all:
            subject = await _find_subject_by_name(user_id, subject_name)
            print(f"[MCP TOOL: GET_TIME_SUMMARY] Subject encontrado en BD: {subject}", file=sys.stderr, flush=True)
            if not subject:
                return f"No encontré ninguna asignatura llamada '{subject_name}'."
            target_project_id = subject.get("clockify_project_id")
            if not target_project_id:
                return f"La asignatura '{subject_name}' no tiene proyecto vinculado en Clockify."

            all_tasks = await db_service.get_tasks_by_subject(subject["_id"])
            task_id_to_name = {
                t["clockify_task_id"]: t["title"]
                for t in all_tasks
                if t.get("clockify_task_id")
            }
            print(f"[MCP TOOL: GET_TIME_SUMMARY] Task map en BD: {task_id_to_name}", file=sys.stderr, flush=True)
        else:
            task_id_to_name = {}

        # 3. Obtener entradas de Clockify
        days = days_back if (days_back and days_back > 0) else 60
        entries = await asyncio.to_thread(clockify.get_time_entries, days_back=days)
        print(f"[MCP TOOL: GET_TIME_SUMMARY] Entradas brutas devueltas por Clockify ({days}d): {len(entries)}", file=sys.stderr, flush=True)

        if not entries:
            return f"No tienes ninguna sesión registrada en Clockify en los últimos {days} días."

        # 4. Filtrar por projectId si se pidió asignatura concreta
        if not is_all:
            entries = [e for e in entries if e.get("projectId") == target_project_id]
            print(f"[MCP TOOL: GET_TIME_SUMMARY] Entradas tras filtrar por projectId ({target_project_id}): {len(entries)}", file=sys.stderr, flush=True)

        if not entries:
            label = subject_name if not is_all else "ninguna asignatura"
            return f"No encontré registros en Clockify para '{label}' en los últimos {days} días."

        # 5. Calcular duración en minutos para cada entrada
        def _parse_duration(entry: dict) -> int:
            iso_dur = entry.get("duration")
            if iso_dur:
                import re
                h = int(re.search(r"(\d+)H", iso_dur).group(1)) if re.search(r"(\d+)H", iso_dur) else 0
                m = int(re.search(r"(\d+)M", iso_dur).group(1)) if re.search(r"(\d+)M", iso_dur) else 0
                s = int(re.search(r"(\d+)S", iso_dur).group(1)) if re.search(r"(\d+)S", iso_dur) else 0
                total_m = h * 60 + m + round(s / 60)
                if total_m > 0:
                    return total_m

            st_raw = entry.get("start")
            end_raw = entry.get("end")
            if st_raw and end_raw and end_raw != "⏱️ En curso":
                try:
                    dt1 = datetime.fromisoformat(st_raw.replace("Z", "+00:00"))
                    dt2 = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
                    diff_m = round((dt2 - dt1).total_seconds() / 60)
                    return max(0, diff_m)
                except Exception as ex:
                    print(f"[MCP TOOL: GET_TIME_SUMMARY] Error calculando diff: {ex}", file=sys.stderr, flush=True)
            return 0

        def _fmt_dt(raw: str) -> str:
            return raw[:16].replace("T", " ") if raw else "?"

        # 6. Agrupar por tarea
        groups: dict[str, list] = defaultdict(list)

        for entry in entries:
            task_cid = entry.get("taskId")
            task_name = task_id_to_name.get(task_cid, "Sin tarea asignada") if task_cid else "Sin tarea asignada"
            minutes = _parse_duration(entry)
            print(f"[MCP TOOL: GET_TIME_SUMMARY] Entry: ID={entry.get('id')} task_cid={task_cid} -> task_name='{task_name}' minutes={minutes}", file=sys.stderr, flush=True)
            groups[task_name].append({
                "id": entry.get("id"),
                "start": _fmt_dt(entry.get("start")),
                "end": _fmt_dt(entry.get("end")) if entry.get("end") else "⏱️ En curso",
                "description": entry.get("description") or "",
                "minutes": minutes
            })

        # 7. Construir JSON de respuesta
        by_task = []
        total_minutes = 0
        for task_name, sessions in groups.items():
            task_total = sum(s["minutes"] for s in sessions)
            total_minutes += task_total
            by_task.append({
                "task": task_name,
                "total_minutes": task_total,
                "sessions": sessions
            })

        by_task.sort(key=lambda x: x["total_minutes"], reverse=True)

        res_json = json.dumps({
            "subject": subject_name if not is_all else "Todas",
            "total_minutes": total_minutes,
            "by_task": by_task
        }, ensure_ascii=False, indent=2)

        print(f"[MCP TOOL: GET_TIME_SUMMARY] JSON de salida:\n{res_json}", file=sys.stderr, flush=True)
        return res_json

    except Exception as e:
        print(f"[MCP TOOL ERROR: GET_TIME_SUMMARY] {str(e)}", file=sys.stderr, flush=True)
        return f"Error al consultar Clockify: {str(e)}"

@mcp.tool()
async def log_study_hours(user_id: str, subject_name: str, hours: float,
                          task_title: str = None, description: str = ""):
    """
    Registra una sesión de estudio indicando solo cuántas horas se han dedicado,
    sin necesidad de especificar hora de inicio ni fin. El sistema calcula automáticamente
    que la sesión terminó ahora y empezó hace X horas.
    """
    try:
        print(f"[MCP TOOL: LOG_STUDY_HOURS] user_id={user_id}, subject_name='{subject_name}', hours={hours}, task_title='{task_title}', desc='{description}'", file=sys.stderr, flush=True)
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=hours)
        start_time = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        subject = await _find_subject_by_name(user_id, subject_name)
        print(f"[MCP TOOL: LOG_STUDY_HOURS] Subject encontrado: {subject}", file=sys.stderr, flush=True)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."

        clockify_task_id = None
        if task_title:
            task = await _find_task_by_title(subject["_id"], task_title)
            print(f"[MCP TOOL: LOG_STUDY_HOURS] Task encontrada: {task}", file=sys.stderr, flush=True)
            if task:
                clockify_task_id = task.get("clockify_task_id")

        cs = await _get_user_clockify_service(user_id)
        if not cs.api_key:
            return "No tienes configurada tu API Key de Clockify para poder registrar las horas."

        res = await asyncio.to_thread(
            cs.create_time_entry,
            description=description or f"Estudiando {subject_name}",
            project_id=subject["clockify_project_id"],
            task_id=clockify_task_id,
            start_time=start_time,
            end_time=end_time
        )
        print(f"[MCP TOOL: LOG_STUDY_HOURS] Respuesta de Clockify: {res}", file=sys.stderr, flush=True)

        h = int(hours)
        m = int((hours - h) * 60)
        return f"Registradas {h}h {m}m de estudio en '{subject_name}'{' (' + task_title + ')' if task_title else ''} en Clockify."
    except Exception as e:
        print(f"[MCP TOOL ERROR: LOG_STUDY_HOURS] {e}", file=sys.stderr, flush=True)
        return f"Error al registrar las horas: {str(e)}"
        

@mcp.tool()
async def edit_logged_study_hours(user_id: str, time_entry_id: Optional[str] = None, subject_name: Optional[str] = None,
                                  new_subject_name: Optional[str] = None, new_task_title: Optional[str] = None,
                                  new_start_time: Optional[str] = None, new_end_time: Optional[str] = None,
                                  new_description: Optional[str] = None):
    """
    Edita una entrada de tiempo (sesión de estudio / cronómetro) ya registrada en Clockify.
    """
    try:
        print(f"[MCP TOOL: EDIT_LOGGED_STUDY_HOURS] time_entry_id={time_entry_id}, subject_name='{subject_name}', new_subject='{new_subject_name}', new_task='{new_task_title}', new_start='{new_start_time}', new_end='{new_end_time}', new_desc='{new_description}'", file=sys.stderr, flush=True)
        cs = await _get_user_clockify_service(user_id)
        if not cs.api_key:
            return "No tienes configurada tu API Key de Clockify para poder editar las entradas."

        target_id = time_entry_id
        subject = None

        if not target_id:
            if not subject_name:
                return "Debes indicar el ID de la entrada de tiempo o el nombre de la asignatura para localizar la sesión a editar."

            subject = await _find_subject_by_name(user_id, subject_name)
            if not subject:
                return f"No encontré ninguna asignatura llamada '{subject_name}'."

            entries = await asyncio.to_thread(cs.get_time_entries, days_back=60)
            filtered = [e for e in entries if e.get("projectId") == subject.get("clockify_project_id")]
            if not filtered:
                return f"No encontré sesiones de estudio registradas para la asignatura '{subject_name}'."
            target_id = filtered[0].get("id")

        print(f"[MCP TOOL: EDIT_LOGGED_STUDY_HOURS] Target entry ID a modificar: {target_id}", file=sys.stderr, flush=True)

        if not target_id:
            return "No se pudo identificar la entrada de tiempo a editar."

        new_project_id = None
        new_sub = None
        if new_subject_name:
            new_sub = await _find_subject_by_name(user_id, new_subject_name)
            if not new_sub:
                return f"No encontré la nueva asignatura llamada '{new_subject_name}'."
            new_project_id = new_sub.get("clockify_project_id")

        new_clockify_task_id = None
        if new_task_title:
            ref_sub_id = new_sub["_id"] if new_sub else (subject["_id"] if subject else None)
            if ref_sub_id:
                task = await _find_task_by_title(ref_sub_id, new_task_title)
                if task:
                    new_clockify_task_id = task.get("clockify_task_id")

        if new_start_time and not new_start_time.endswith('Z') and '+' not in new_start_time:
            new_start_time += 'Z'
        if new_end_time and not new_end_time.endswith('Z') and '+' not in new_end_time:
            new_end_time += 'Z'

        res = await asyncio.to_thread(
            cs.update_time_entry,
            time_entry_id=target_id,
            description=new_description,
            project_id=new_project_id,
            task_id=new_clockify_task_id,
            start_time=new_start_time,
            end_time=new_end_time
        )
        print(f"[MCP TOOL: EDIT_LOGGED_STUDY_HOURS] Resultado de update_time_entry: {res}", file=sys.stderr, flush=True)

        if isinstance(res, dict) and res.get("error"):
            return f"Error al actualizar la entrada de tiempo: {res['error']}"

        return f"Entrada de tiempo '{target_id}' actualizada correctamente en Clockify."
    except Exception as e:
        print(f"[MCP TOOL ERROR: EDIT_LOGGED_STUDY_HOURS] {e}", file=sys.stderr, flush=True)
        return f"Error al editar la entrada de tiempo: {str(e)}"

@mcp.tool()
async def delete_time_entry(user_id: str, time_entry_id: Optional[str] = None, subject_name: Optional[str] = None,
                            task_title: Optional[str] = None, date: Optional[str] = None):
    """
    Elimina una sesión de estudio / entrada de tiempo (cronómetro) registrada en Clockify.
    """
    try:
        print(f"[MCP TOOL: DELETE_TIME_ENTRY] time_entry_id={time_entry_id}, subject_name='{subject_name}', task_title='{task_title}', date='{date}'", file=sys.stderr, flush=True)
        cs = await _get_user_clockify_service(user_id)
        if not cs.api_key:
            return "No tienes configurada tu API Key de Clockify para poder eliminar la entrada de tiempo."

        target_id = time_entry_id

        if not target_id:
            entries = await asyncio.to_thread(cs.get_time_entries, days_back=60)
            if not entries:
                return "No se encontraron entradas de tiempo registradas para eliminar."

            target_project_id = None
            subject = None
            if subject_name:
                subject = await _find_subject_by_name(user_id, subject_name)
                if subject:
                    target_project_id = subject.get("clockify_project_id")

            target_task_id = None
            if task_title and subject:
                task = await _find_task_by_title(subject["_id"], task_title)
                if task:
                    target_task_id = task.get("clockify_task_id")

            filtered = []
            for e in entries:
                if target_project_id and e.get("projectId") != target_project_id:
                    continue
                if target_task_id and e.get("taskId") != target_task_id:
                    continue
                if date and not (e.get("start") and date in e.get("start")):
                    continue
                filtered.append(e)

            print(f"[MCP TOOL: DELETE_TIME_ENTRY] Entradas coincidentes: {len(filtered)}", file=sys.stderr, flush=True)

            if not filtered:
                return "No se encontró ninguna sesión de estudio que coincida con los criterios especificados."
            
            target_id = filtered[0].get("id")

        print(f"[MCP TOOL: DELETE_TIME_ENTRY] Target entry ID a eliminar: {target_id}", file=sys.stderr, flush=True)

        if not target_id:
            return "No se pudo identificar el ID de la entrada de tiempo a eliminar."

        res = await asyncio.to_thread(cs.delete_time_entry, time_entry_id=target_id)
        print(f"[MCP TOOL: DELETE_TIME_ENTRY] Resultado del borrado: {res}", file=sys.stderr, flush=True)

        if isinstance(res, dict) and res.get("error"):
            return f"Error al eliminar la entrada de tiempo: {res['error']}"

        return f"Entrada de tiempo '{target_id}' eliminada correctamente de Clockify."
    except Exception as e:
        print(f"[MCP TOOL ERROR: DELETE_TIME_ENTRY] {e}", file=sys.stderr, flush=True)
        return f"Error al eliminar la entrada de tiempo: {str(e)}"
         
 
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


@mcp.tool()
async def set_subject_grade(user_id: str, subject_name: str, grade: float):
    """
    Registra o actualiza la nota de una asignatura (de 0 a 10).
    Úsala cuando el usuario mencione la nota de un examen o asignatura (ej: 'saqué un 8.5 en Matemáticas').
    """
    try:
        subject = await _find_subject_by_name(user_id, subject_name)
        if not subject:
            return f"No encontré ninguna asignatura llamada '{subject_name}'."
        
        await db_service.update_subject_grade(subject["_id"], grade)
        return f"Nota de {grade} guardada para la asignatura '{subject_name}'."
    except Exception as e:
        return f"Error al guardar la nota: {str(e)}"


############################################################################
# TOOLS PARA ESTADÍSTICAS

# @mcp.tool()
# async def get_hours_by_subject_analytics(user_id: str, subject_name: str = None):
#     """
#     Esta herramienta devuelve la relación entre horas estudiadas (Clockify) y notas obtenidas por cada asignatura.
    
#     - Si se especifica 'subject_name', devuelve las estadísticas solo de esa asignatura.
#     - Si no se especifica 'subject_name', devuelve las estadísticas de todas las asignaturas.
    
#     Usa esta herramienta cuando el usuario quiera saber su rendimiento por asignatura.
#     """
#     try:
#         subject = await _find_subject_by_name(user_id, subject_name) if subject_name else None
#         if subject_name and not subject:
#             return f"No encontré ninguna asignatura llamada '{subject_name}'."
        
#         analytics = await db_service.get_analytics_by_subject(user_id, subject["_id"] if subject else None)
#         return analytics
#     except Exception as e:
#         return f"Error al obtener las estadísticas de horas por asignatura: {str(e)}"


# @mcp.tool()
# async def analyze_student_performance(user_id: str) -> str:
#     """
#     Realiza un análisis inteligente de las estadísticas de estudio y calificaciones del alumno utilizando IA.
#     Examina la relación entre las horas dedicadas (desde Clockify), las metas semanales y las notas obtenidas,
#     ofreciendo recomendaciones personalizadas.
#     """
#     try:
#         subjects = await db_service.get_subjects_by_user(user_id)
#         if not subjects:
#             return "No tienes asignaturas registradas para poder realizar el análisis."
            
#         # Obtener periodo activo si lo hay
#         active_period = await db_service.get_active_period(user_id)
#         start_date = None
#         end_date = None
#         period_name = "periodo actual"
#         if active_period:
#             start_date = active_period.get("start_date")
#             end_date = active_period.get("end_date")
#             period_name = active_period.get("name", "periodo actual")

#         # Obtener credenciales de Clockify del usuario
#         clockify_creds = await db_service.get_clockify_credentials(user_id)
        
#         # Obtener entradas de tiempo de Clockify
#         clockify_entries = []
#         if clockify_creds and clockify_creds.get("api_key"):
#             try:
#                 cs = ClockifyService(
#                     api_key=clockify_creds["api_key"] or clockify_creds.get("token"),
#                     workspace_id=clockify_creds.get("workspace_id")
#                 )
#                 if start_date or end_date:
#                     clockify_entries = await asyncio.to_thread(
#                         cs.get_time_entries, start_date=start_date, end_date=end_date
#                     )
#                 else:
#                     clockify_entries = await asyncio.to_thread(
#                         cs.get_time_entries, days_back=365
#                     )
#             except Exception as e:
#                 print(f"Error fetching Clockify entries: {e}")

#         # Agrupar segundos de Clockify por projectId
#         project_seconds = {}
#         for entry in clockify_entries:
#             pid = entry.get("projectId")
#             if not pid:
#                 continue
#             start_iso = entry.get("start")
#             end_iso = entry.get("end")
#             if start_iso and end_iso:
#                 try:
#                     dt1 = datetime.fromisoformat(start_iso.replace('Z', '+00:00'))
#                     dt2 = datetime.fromisoformat(end_iso.replace('Z', '+00:00'))
#                     seconds = (dt2 - dt1).total_seconds()
#                     project_seconds[pid] = project_seconds.get(pid, 0.0) + seconds
#                 except Exception:
#                     pass

#         analytics_data = []
#         for subject in subjects:
#             s_id = str(subject["_id"])
#             clockify_project_id = subject.get("clockify_project_id")
            
#             # Obtener segundos del proyecto desde Clockify
#             seconds = 0.0
#             if clockify_project_id and clockify_project_id in project_seconds:
#                 seconds = project_seconds[clockify_project_id]
                
#             total_hours = round(seconds / 3600.0, 2)
#             analytics_data.append({
#                 "name": subject.get("name", "Asignatura"),
#                 "hours": total_hours,
#                 "weekly_hours_goal": subject.get("weekly_hours_goal", 0),
#                 "grade": subject.get("grade")
#             })

#         # Preparar prompt para Gemini
#         prompt = f"""
#         Como un asesor académico inteligente y experto en bienestar estudiantil, analiza el siguiente rendimiento del alumno en el periodo "{period_name}".
        
#         Datos de las asignaturas (horas reales registradas en Clockify vs metas semanales y calificaciones obtenidas):
#         {analytics_data}
        
#         Por favor, realiza un análisis detallado que incluya:
#         1. **Resumen General**: Una valoración de cómo va el alumno en general.
#         2. **Relación Esfuerzo vs. Resultados**: Identifica asignaturas donde el esfuerzo (horas) se traduzca en buenas notas, o si hay asignaturas de alto esfuerzo y baja nota (donde tal vez necesite cambiar de método), o asignaturas con notas bajas y pocas horas (donde falte dedicación).
#         3. **Cumplimiento de Metas**: Evalúa si está alcanzando las metas semanales de estudio.
#         4. **Consejos y Recomendaciones**: Da 3 consejos prácticos, realistas y motivadores para mejorar su bienestar y rendimiento en el estudio.
        
#         Responde en español de manera empática, clara y estructurada usando formato Markdown.
#         """
        
#         # Llamar a Gemini utilizando el SDK configurado en la app
#         from google import genai
#         client = genai.Client()
#         response = client.models.generate_content(
#             model="gemini-3.5-flash-lite",
#             contents=prompt
#         )
#         return response.text
#     except Exception as e:
#         return f"Error al generar el análisis de rendimiento: {str(e)}"


if __name__ == "__main__":
    mcp.run()