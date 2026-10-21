import os
import re
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import sys
import secrets
import unicodedata
from typing import Optional
from services.encryption_service import EncryptionService
from pymongo import ReturnDocument

 
 
load_dotenv()

# Tipos de tarea cuya fecha es fija: el agente planificador no puede reprogramarlos.
FIXED_DATE_TYPES = {"exam", "assignment"}


def task_can_be_rescheduled(task: dict) -> bool:
    """True si el planificador puede mover la fecha de la tarea (exámenes y entregas tienen fecha fija)."""
    return (task or {}).get("type") not in FIXED_DATE_TYPES

 
class DatabaseService:
 
    def __init__(self):
        self.client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
        self.db = self.client["tfg_bienestar"]
 
        # Colecciones
        self.users = self.db["users"]
 
        self.periods = self.db["periods"]
        self.subjects = self.db["subjects"]
        self.tasks = self.db["tasks"]
        self.history = self.db["history"]
        self.wellbeing_entries = self.db["wellbeing_entries"]
        self.study_reports = self.db["study_reports"]
        self.study_plans = self.db["study_plans"]
        self.courses = self.db["courses"]
        self.user_tags = self.db["user_tags"]

    async def ensure_indexes(self):
        """
        Crea los índices necesarios. Llamar una vez al arrancar la app (p.ej. en el
        lifespan de main.py), es idempotente: si el índice ya existe, Mongo no hace nada.
        """
        await self.subjects.create_index([("user_id", 1), ("period_id", 1)])
        await self.subjects.create_index([("course_id", 1), ("user_id", 1)])
        await self.tasks.create_index([("subject_id", 1)])
        await self.tasks.create_index([("parent_task_id", 1)])
        
        await self.tasks.create_index("tags")
        await self.user_tags.create_index([("user_id", 1), ("name", 1)], unique=True)
        # await self.deadlines.create_index([("user_id", 1), ("date", 1)])
        await self.periods.create_index([("user_id", 1)])
        await self.history.create_index([("user_id", 1), ("timestamp", -1)])
        await self.wellbeing_entries.create_index([("user_id", 1), ("date", -1)])
        await self.study_reports.create_index([("user_id", 1), ("timestamp", -1)])
        await self.study_plans.create_index([("user_id", 1), ("status", 1)])
        await self.users.create_index("share_code", unique=True, sparse=True)
        await self.courses.create_index("enrollment_code", unique=True)
        await self.courses.create_index("teacher_ids")
        await self.courses.create_index("student_ids")
 

    ############################################################################
    # METHODS FOR HISTORY

    async def get_history(self, user_id: str, limit: int = 50, skip: int = 0) -> list[dict]:
        """
        Recupera N mensajes de un usuario ordenados cronológicamente con paginación.
        - skip: número de mensajes a saltar (para paginación al hacer scroll hacia arriba)
        """
        # Buscamos por user_id y ordenamos por timestamp descendente (más recientes primero)
        cursor = self.history.find({"user_id": user_id}).sort("timestamp", -1).skip(skip).limit(limit)
        messages = await cursor.to_list(length=limit)

        # Invertimos la lista para devolverlos en orden cronológico (del más antiguo al más reciente)
        messages.reverse()

        # Normalizamos los campos de MongoDB a formatos amigables para JSON
        for msg in messages:
            msg["_id"] = str(msg["_id"])
            if isinstance(msg.get("timestamp"), datetime):
                msg["timestamp"] = msg["timestamp"].replace(tzinfo=timezone.utc).isoformat()

        return messages

    async def insert_message(self, user_id: str, role: str, content: str, agent_used: str = None) -> dict:
        """
        Guarda un mensaje en la base de datos.
        - role: 'user' o 'assistant'
        - content: el texto del mensaje
        - agent_used: 'ACADEMICO', 'BIENESTAR', 'GENERAL' (opcional)
        """
        message_doc = {
            "user_id": user_id,
            "role": role,
            "content": content,
            "agent_used": agent_used,
            "timestamp": datetime.now(timezone.utc)
        }

        result = await self.history.insert_one(message_doc)
        message_doc["_id"] = str(result.inserted_id)
        message_doc["timestamp"] = message_doc["timestamp"].isoformat()
        return message_doc


    async def clear_history(self, user_id: str) -> int:
        """Borra el historial guardado en BD al reiniciar chat."""
        result = await self.history.delete_many({"user_id": user_id})
        return result.deleted_count
 
    ############################################################################
    # METHODS FOR USERS
 
    async def create_user(self, email: str, name: str, hashed_password: str, role: str = "student") -> dict:
        """Crea un nuevo usuario en la base de datos."""
        user = {
            "email": email,
            "name": name,
            "password": hashed_password,
            "role": role,
            "current_period_id": None,
            "clockify": None
        }
        result = await self.users.insert_one(user)
        user["_id"] = str(result.inserted_id)
        return user

    async def get_user_by_email(self, email: str) -> dict | None:
        """Busca un usuario por su email."""
        user = await self.users.find_one({"email": email})
        if user:
            user["_id"] = str(user["_id"])
        return user

    async def get_user_by_id(self, user_id: str) -> dict | None:
        """Busca un usuario por su ID."""
        try:
            user = await self.users.find_one({"_id": ObjectId(user_id)})
            if user:
                user["_id"] = str(user["_id"])
            return user
        except Exception:
            return None

    async def update_user(self, user_id: str, **fields) -> bool:
        """Actualiza campos sueltos del usuario (p.ej. last_daily_plan_review_date)."""
        if not fields:
            return False
        try:
            res = await self.users.update_one({"_id": ObjectId(user_id)}, {"$set": fields})
            return res.matched_count > 0
        except Exception:
            return False

    async def get_study_flow_state(self, user_id: str) -> bool:
        """Devuelve True si el usuario está en el flujo de recogida de informe de sesión."""
        try:
            user = await self.users.find_one({"_id": ObjectId(user_id)}, {"in_study_report_flow": 1})
            return bool(user.get("in_study_report_flow", False)) if user else False
        except Exception:
            return False

    async def set_study_flow_state(self, user_id: str, state: bool, session_entry_id: str = None) -> None:
        """Activa o desactiva el flujo de recogida de informe de sesión para un usuario.
        Si state=True, guarda también el clockify_time_entry_id de la sesión recién registrada.
        Si state=False, limpia el ID pendiente.
        """
        try:
            fields = {"in_study_report_flow": state}
            if state and session_entry_id:
                fields["pending_session_entry_id"] = session_entry_id
            elif not state:
                fields["pending_session_entry_id"] = None
            await self.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": fields}
            )
        except Exception:
            pass

    async def get_pending_session_entry_id(self, user_id: str) -> str | None:
        """Devuelve el clockify_time_entry_id de la sesión pendiente de informe, si existe."""
        try:
            user = await self.users.find_one({"_id": ObjectId(user_id)}, {"pending_session_entry_id": 1})
            return user.get("pending_session_entry_id") if user else None
        except Exception:
            return None

    async def get_user_by_clockify_id_or_key(
        self, clockify_user_id: str = None, api_key: str = None, exclude_user_id: str = None
    ) -> dict | None:
        """
        Busca si algún usuario en la BD ya tiene vinculada la misma cuenta de Clockify
        (por ID de usuario en Clockify o por API Key), excluyendo opcionalmente a exclude_user_id.
        La comparación por api_key se realiza recuperando todos los usuarios con datos de Clockify
        y comparando la api_key descifrada, ya que el valor en BD está cifrado con Fernet.
        """
        or_conditions = []
        if clockify_user_id:
            or_conditions.append({"clockify.clockify_user_id": clockify_user_id})

        # No podemos comparar api_key directamente en la query porque está cifrada en BD.
        # La búsqueda por api_key se realiza en memoria tras descifrar.
        if not or_conditions and not api_key:
            return None

        if or_conditions:
            query = {"$or": or_conditions}
            if exclude_user_id:
                try:
                    query["_id"] = {"$ne": ObjectId(exclude_user_id)}
                except Exception:
                    pass
            found = await self.users.find_one(query)
            if found:
                return found

        # Búsqueda por api_key: comparar en memoria descifrado
        if api_key:
            cursor = self.users.find({"clockify": {"$ne": None}})
            async for user in cursor:
                if exclude_user_id:
                    try:
                        if user["_id"] == ObjectId(exclude_user_id):
                            continue
                    except Exception:
                        pass
                stored = (user.get("clockify") or {}).get("api_key", "")
                try:
                    decrypted = EncryptionService.decrypt(stored) if EncryptionService.is_fernet_token(stored) else stored
                    if decrypted == api_key:
                        return user
                except Exception:
                    pass

        return None


    async def update_clockify_credentials(self, user_id: str, api_key: str, workspace_id: str = None, clockify_user_id: str = None):
        """Actualiza la API Key (cifrada con Fernet) y Workspace de Clockify del usuario."""
        encrypted_key = EncryptionService.encrypt(api_key)
        clockify_data = {
            "api_key": encrypted_key,
            "workspace_id": workspace_id,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        if clockify_user_id:
            clockify_data["clockify_user_id"] = clockify_user_id
        await self.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"clockify": clockify_data}}
        )
        # Devolvemos la key en claro para que el llamador pueda usarla
        return {**clockify_data, "api_key": api_key}

    # async def update_clockify_key(self, user_id: str, api_key: str):
    #     """Compatibilidad: Actualiza la API key de Clockify de un usuario."""
    #     return await self.update_clockify_credentials(user_id=user_id, auth_type="api_key", token=api_key)

    async def get_clockify_credentials(self, user_id: str) -> dict | None:
        """
        Devuelve las credenciales de Clockify de un usuario con la api_key descifrada.
        Si el valor almacenado no es un token Fernet válido (datos legacy), se devuelve tal cual.
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return None
        creds = user.get("clockify")
        if not creds:
            return None
        # Descifrar api_key si está cifrada
        raw_key = creds.get("api_key", "")
        if raw_key and EncryptionService.is_fernet_token(raw_key):
            try:
                creds = {**creds, "api_key": EncryptionService.decrypt(raw_key)}
            except ValueError:
                # Si falla el descifrado (clave cambiada, datos corruptos), devolver None
                # para forzar al usuario a volver a vincular su cuenta.
                return None
        return creds

    async def update_current_period(self, user_id: str, period_id: str):
        """Actualiza el periodo académico actual de un usuario."""
        await self.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"current_period_id": period_id}}
        )

    async def update_subject_grade(self, subject_id: str, grade: float):
        """Actualiza la nota/calificación de una asignatura."""
        await self.subjects.update_one(
            {"_id": ObjectId(subject_id)},
            {"$set": {"grade": grade}}
        )
        return True
    

    async def generate_share_code(self, user_id: str) -> str:
        """
        Genera el código de compartir del usuario. Es idempotente: si el usuario
        ya tiene un código, se devuelve el existente en lugar de sobreescribirlo,
        para que no se pueda "regenerar" e invalidar el código que ya haya
        compartido con otros.
        """
        existing = await self.users.find_one({"_id": ObjectId(user_id)})
        if existing and existing.get("share_code"):
            return existing["share_code"]

        for _ in range(10):
            code = secrets.token_urlsafe(6).upper()
            # Asegurar que ningún otro usuario tiene ya este código asignado
            in_use = await self.users.find_one({"share_code": code})
            if not in_use:
                await self.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {"share_code": code}}
                )
                return code

        # Respaldo con mayor entropía en caso extremo de colisiones
        code = secrets.token_hex(4).upper()
        await self.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"share_code": code}}
        )
        return code


    async def get_user_by_share_code(self, code: str) -> dict | None:
        return await self.users.find_one({"share_code": code.upper()})

    async def add_followed_user(self, user_id: str, followed_user_id: str) -> None:
        await self.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$addToSet": {"followed_users": followed_user_id}}
        )

    async def remove_followed_user(self, user_id: str, followed_user_id: str) -> None:
        await self.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$pull": {"followed_users": followed_user_id}}
        )

    async def get_followed_users(self, user_id: str) -> list:
        user = await self.get_user_by_id(user_id)
        result = []
        for fid in user.get("followed_users", []):
            fu = await self.get_user_by_id(fid)
            if fu:
                result.append({
                    "user_id": fid,
                    "name": fu.get("name", "Estudiante"),
                    "email": fu.get("email", "")
                })
        return result

    async def get_followers(self, user_id: str) -> list:
        """Obtiene la lista de usuarios que tienen a user_id en su lista de followed_users."""
        cursor = self.users.find({"followed_users": user_id})
        followers = []
        async for u in cursor:
            followers.append({
                "user_id": str(u["_id"]),
                "name": u.get("name", "Estudiante"),
                "email": u.get("email", "")
            })
        return followers

    async def remove_follower(self, user_id: str, follower_user_id: str) -> None:
        """Revoca el acceso quitando user_id de la lista followed_users del seguidor."""
        await self.users.update_one(
            {"_id": ObjectId(follower_user_id)},
            {"$pull": {"followed_users": user_id}}
        )

 
 
    ############################################################################
    # METHODS FOR PERIODS
 
    async def create_period(self, user_id: str, name: str, start_date: str, end_date: str) -> dict:
        """Crea un nuevo periodo académico asociado a un usuario."""
        period = {
            "user_id": user_id,
            "name": name,
            "start_date": start_date,
            "end_date": end_date
        }
        result = await self.periods.insert_one(period)
        period["_id"] = str(result.inserted_id)
        return period
 
    async def get_periods_by_user(self, user_id: str) -> list:
        """Devuelve todos los periodos académicos de un usuario."""
        cursor = self.periods.find({"user_id": user_id})
        periods = await cursor.to_list(100)
        for p in periods:
            p["_id"] = str(p["_id"])
        return periods
 
    async def get_period_by_id(self, period_id: str) -> dict | None:
        """Devuelve un periodo académico por su ID."""
        period = await self.periods.find_one({"_id": ObjectId(period_id)})
        if period:
            period["_id"] = str(period["_id"])
        return period
 
    async def get_period_by_user_and_name(self, user_id: str, name: str) -> dict | None:
        """Devuelve un periodo académico por su nombre y usuario."""
        period = await self.periods.find_one({"user_id": user_id, "name": name})
        if period:
            period["_id"] = str(period["_id"])
        return period
 
    async def update_period(self, period_id: str, **fields):
        """Actualiza campos sueltos de un periodo (name, start_date, end_date)."""
        if not fields:
            return
        await self.periods.update_one({"_id": ObjectId(period_id)}, {"$set": fields})
 
    async def set_active_period(self, user_id: str, period_id: str):
        """
        Marca un periodo como el activo del usuario, desactivando el resto.
        NOTA: usamos un campo is_active en el propio documento de period (en vez de
        users.current_period_id) porque, mientras no haya login real, user_id es un
        string plano ("default_user") y no un ObjectId válido -- convertirlo con
        ObjectId(user_id) fallaría con InvalidId.
        """
        await self.periods.update_many({"user_id": user_id}, {"$set": {"is_active": False}})
        await self.periods.update_one({"_id": ObjectId(period_id)}, {"$set": {"is_active": True}})
 
    async def get_active_period(self, user_id: str) -> dict | None:
        """Devuelve el periodo activo del usuario, si tiene uno."""
        period = await self.periods.find_one({"user_id": user_id, "is_active": True})
        if period:
            period["_id"] = str(period["_id"])
        return period
 
    async def delete_period(self, period_id: str):
        """
        Elimina un periodo académico por su ID.
        NOTA: no toca las subjects que lo referencian, para no borrar datos de asignaturas
        por accidente. Si quieres "liberar" esas asignaturas (dejarlas sin periodo) antes
        de borrar, hazlo explícitamente con update_subject(subject_id, period_id=None).
        """
        await self.periods.delete_one({"_id": ObjectId(period_id)})
 
 
    ############################################################################
    # METHODS FOR SUBJECTS
 
    async def create_subject(self, user_id: str, name: str, clockify_project_id: str, weekly_hours_goal: int = 0, 
        period_id: Optional[str] = None, grade: Optional[float] = None, description: Optional[str] = None, 
        evaluation_criteria: Optional[str] = None, notes: Optional[str] = None,
        course_id: Optional[str] = None) -> dict:
        """
        Crea una nueva asignatura asociada a un usuario.
        Por defecto, 'grade' se inicializa a None.
        """
        subject = {
            "user_id": user_id,
            "period_id": period_id,
            "name": name,
            "clockify_project_id": clockify_project_id,
            "weekly_hours_goal": weekly_hours_goal,
            "grade": grade, 
            "description": description,
            "evaluation_criteria": evaluation_criteria,
            "notes": notes,
            "is_archived": False,
            "course_id": course_id,  # None = asignatura propia; string ObjectId = creada al matricularse en un curso
        }
        result = await self.subjects.insert_one(subject)
        subject["_id"] = str(result.inserted_id)
        return subject


    async def update_subject_grade(self, subject_id: str, grade: Optional[float]):
        """Actualiza o elimina (si es None) la nota/calificación de una asignatura."""
        await self.subjects.update_one(
            {"_id": ObjectId(subject_id)},
            {"$set": {"grade": grade}}
        )
        return True

    async def get_subjects_by_user(self, user_id: str, include_archived: bool = False, only_archived: bool = False) -> list:
        """Devuelve todas las asignaturas de un usuario (activas, archivadas o todas)."""
        query = {"user_id": user_id}
        if only_archived:
            query["is_archived"] = True
        elif not include_archived:
            query["is_archived"] = {"$ne": True}
        cursor = self.subjects.find(query)
        subjects = await cursor.to_list(100)
        for s in subjects:
            s["_id"] = str(s["_id"])
        return subjects
 
    async def get_subjects_by_period(self, period_id: str) -> list:
        """Devuelve todas las asignaturas asociadas a un periodo concreto."""
        cursor = self.subjects.find({"period_id": period_id})
        subjects = await cursor.to_list(100)
        for s in subjects:
            s["_id"] = str(s["_id"])
        return subjects
 
    async def get_subject_by_id(self, subject_id: str) -> dict | None:
        """Devuelve una asignatura por su ID."""
        subject = await self.subjects.find_one({"_id": ObjectId(subject_id)})
        if subject:
            subject["_id"] = str(subject["_id"])
        return subject
 
    async def update_subject(self, subject_id: str, **fields):
        """
        Actualiza campos sueltos de una asignatura (name, weekly_hours_goal,
        period_id, is_archived...). Ej: update_subject(id, is_archived=True)
        para archivarla al cerrar un periodo, en vez de borrarla.
        """
        if not fields:
            return
        await self.subjects.update_one({"_id": ObjectId(subject_id)}, {"$set": fields})
 
    async def delete_subject(self, subject_id: str):
        """Elimina una asignatura por su ID."""
        await self.subjects.delete_one({"_id": ObjectId(subject_id)})
 
 
    ############################################################################
    # METHODS FOR TASKS


    async def create_task(self, user_id: str, title: str, subject_id: str = None,
                          description: str = "", due_date: str = None,
                          type: str = "task", parent_task_id: str = None, 
                          clockify_task_id: str = None,
                          priority: int = None, tags: list = None) -> dict:
        """
        Crea un elemento de trabajo o evento en el sistema (Tarea, Examen, Entrega, etc.).
        type puede ser: 'task', 'exam', 'assignment' u 'other'.
        subject_id es opcional para permitir eventos globales o administrativos.
        priority es opcional: entero entre 1 (muy baja) y 5 (muy alta).
        Los tipos 'exam' y 'assignment' tienen fecha fija: el agente planificador no puede reprogramarlos.
        Al crearlas, el campo status por defecto es "PENDING".
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        task = {
            "user_id": user_id,
            "subject_id": subject_id,
            "parent_task_id": parent_task_id,
            "clockify_task_id": clockify_task_id,
            "title": title,
            "description": description,
            "due_date": due_date,
            "type": type,
            "status": "PENDING", # "PENDING", "ACTIVE", "COMPLETED"
            "priority": priority,
            "tags": await self.canonicalize_tags(user_id, tags),
            "created_at": now_iso,
            "completed_at": None
        }
        result = await self.tasks.insert_one(task)
        task["_id"] = str(result.inserted_id)
        return task

    async def plan_item_is_fixed(self, item: dict) -> bool:
        """True si alguna tarea vinculada a la actividad del plan tiene fecha fija (examen/entrega)."""
        for tid in (item or {}).get("linked_task_ids", []):
            try:
                t = await self.get_task_by_id(str(tid))
            except Exception:
                t = None
            if t and not task_can_be_rescheduled(t):
                return True
        return False

    async def get_tasks_by_subject(self, subject_id: str = None, user_id: str = None, include_completed: bool = True, include_active: bool = True, include_in_progress: bool = True, include_pending: bool = True, priorities: list[int] = None) -> list:
        """Devuelve todas las tareas de una asignatura (o de todas las asignaturas si subject_id es None y se pasa user_id) según filtros de estado y prioridades."""
        query = {}
        if subject_id:
            query["subject_id"] = subject_id
        elif user_id:
            query["user_id"] = user_id
        
        # Combinar la opción include_active e include_in_progress por compatibilidad
        want_active = include_active or include_in_progress
        
        allowed_statuses = []
        if include_pending:
            allowed_statuses.append("PENDING")
        if want_active:
            allowed_statuses.extend(["ACTIVE", "IN_PROGRESS"])
        if include_completed:
            allowed_statuses.append("COMPLETED")

        # Si no se incluyen todos los estados posibles, añadir el filtro $in a la query
        if len(allowed_statuses) < 4:
            query["status"] = {"$in": allowed_statuses}

        if priorities:
            # Soportar filtro por lista de prioridades (ej: [1, 2])
            query["priority"] = {"$in": priorities}

        cursor = self.tasks.find(query)
        tasks = await cursor.to_list(300)
        for t in tasks:
            t["_id"] = str(t["_id"])
        return tasks


    async def get_subtasks(self, parent_task_id: str) -> list:
        """Devuelve las subtareas de una tarea concreta."""
        cursor = self.tasks.find({"parent_task_id": parent_task_id})
        subtasks = await cursor.to_list(100)
        for t in subtasks:
            t["_id"] = str(t["_id"])
        return subtasks

    async def get_task_by_id(self, task_id: str) -> dict | None:
        """Devuelve una tarea por su ID."""
        task = await self.tasks.find_one({"_id": ObjectId(task_id)})
        if task:
            task["_id"] = str(task["_id"])
        return task

    async def update_task(self, task_id: str, **fields):
        """Actualiza campos sueltos de una tarea (title, description, due_date, status...)."""
        if not fields:
            return
        
        # Gestionar automáticamente completed_at según la actualización de status
        if "status" in fields:
            if fields["status"] == "COMPLETED" and "completed_at" not in fields:
                fields["completed_at"] = datetime.now(timezone.utc).isoformat()
            elif fields["status"] in ["PENDING", "ACTIVE", "IN_PROGRESS"] and "completed_at" not in fields:
                fields["completed_at"] = None

        await self.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": fields})

    async def mark_task_completed(self, task_id: str, completed: bool = True):
        """Marcar una tarea como completada ("COMPLETED") o revertirla a pendiente ("PENDING")."""
        new_status = "COMPLETED" if completed else "PENDING"
        completed_at = datetime.now(timezone.utc).isoformat() if completed else None
        await self.update_task(task_id, status=new_status, completed_at=completed_at)


    async def mark_task_active(self, task_id: str, active: bool = True):
        """Marcar una tarea como activa ("ACTIVE") o revertirla a pendiente ("PENDING")."""
        new_status = "ACTIVE" if active else "PENDING"
        await self.update_task(task_id, status=new_status)

    async def mark_task_in_progress(self, task_id: str, in_progress: bool = True):
        """Alias de compatibilidad para mark_task_active."""
        await self.mark_task_active(task_id, active=in_progress)

    async def delete_task(self, task_id: str):
        """Elimina una tarea por su ID, eliminando también sus subtareas y entradas de tiempo."""

        print(f"[DEBUG] El ID de la tarea a eliminar es: {task_id}", file=sys.stderr)
        str_id = str(task_id)
        task_oid = ObjectId(str_id)
        # Eliminar entradas de tiempo vinculadas
        # await self.time_entries.delete_many({"task_id": str_id})
        # print(f"[DEBUG] Entradas de tiempo eliminadas", file=sys.stderr)
        # Eliminar subtareas
        await self.tasks.delete_many({"parent_task_id": str_id})
        # Eliminar la propia tarea
        await self.tasks.delete_one({"_id": task_oid})
        print(f"[DEBUG] Tarea eliminada", file=sys.stderr)



    @staticmethod
    def _norm_tag(name: str) -> str:
        """Normaliza el nombre de una etiqueta: sin espacios en los extremos y en minúsculas."""
        return (name or "").strip().lower()

    @staticmethod
    def _fold_tag(name: str) -> str:
        """Clave de comparación: minúsculas y sin tildes (conserva la ñ). 'Estadísticas' -> 'estadisticas'."""
        out = []
        for c in unicodedata.normalize("NFD", (name or "").strip().lower()):
            if unicodedata.category(c) == "Mn" and not (c == "\u0303" and out and out[-1] == "n"):
                continue
            out.append(c)
        return unicodedata.normalize("NFC", "".join(out))

    @classmethod
    def _pick_canonical(cls, names: list) -> str:
        """Entre variantes de la misma etiqueta, prefiere la que lleva tildes (la ortográficamente correcta)."""
        cands = sorted({cls._norm_tag(n) for n in names})
        with_accents = [c for c in cands if c != cls._fold_tag(c)]
        return (with_accents or cands)[0]

    async def canonicalize_tags(self, user_id: str, tags: list | None) -> list:
        """
        Normaliza una lista de etiquetas y, si ya existe una variante equivalente (misma etiqueta
        sin tildes / con otras mayúsculas) entre las del usuario, reutiliza el nombre existente.
        """
        incoming = self.normalize_tags(tags)
        if not incoming:
            return []
        existing = [t["name"] for t in await self.get_all_tags(user_id)]
        groups = {}
        for n in existing:
            groups.setdefault(self._fold_tag(n), []).append(n)
        canon = {k: self._pick_canonical(v) for k, v in groups.items()}
        return list(dict.fromkeys(canon.get(self._fold_tag(t), t) for t in incoming))

    async def merge_duplicate_tags(self, user_id: str) -> list:
        """
        Fusiona etiquetas duplicadas del usuario (distintas solo en mayúsculas o tildes) en una sola,
        actualizando tareas y colores. Devuelve [{'from': ..., 'to': ...}].
        """
        names = [t["name"] for t in await self.get_all_tags(user_id)]
        groups = {}
        for n in names:
            groups.setdefault(self._fold_tag(n), []).append(n)
        merged = []
        for group in groups.values():
            if len(group) < 2:
                continue
            canonical = self._pick_canonical(group)
            for n in group:
                if n != canonical:
                    await self.rename_tag(user_id, n, canonical)
                    merged.append({"from": n, "to": canonical})
        return merged

    @classmethod
    def normalize_tags(cls, tags: list | None) -> list:
        """Normaliza una lista de etiquetas: minúsculas, sin vacías y sin duplicados (conserva el orden)."""
        if not tags:
            return []
        return list(dict.fromkeys(n for n in (cls._norm_tag(t) for t in tags) if n))

    async def get_tasks_by_tag(self, user_id: str, tag: str) -> list:
        """Devuelve todas las tareas del usuario que contengan el tag indicado."""
        cursor = self.tasks.find({"user_id": user_id, "tags": self._norm_tag(tag)})
        tasks = await cursor.to_list(200)
        for t in tasks:
            t["_id"] = str(t["_id"])
        return tasks

    async def get_all_tags(self, user_id: str) -> list:
        """Devuelve la lista de tags (objetos dict con 'name' y 'color') del usuario."""
        # 1. Obtener tags configurados por el usuario
        cursor = self.user_tags.find({"user_id": user_id})
        saved_tags = await cursor.to_list(500)
        tag_dict = {t["name"]: t.get("color") for t in saved_tags if "name" in t}

        # 2. Buscar tags usados en tareas que aún no estén registrados explícitamente
        pipeline = [
            {"$match": {"user_id": user_id, "tags": {"$exists": True, "$ne": []}}},
            {"$unwind": "$tags"},
            {"$group": {"_id": "$tags"}},
            {"$sort": {"_id": 1}}
        ]
        result = await self.tasks.aggregate(pipeline).to_list(200)
        task_tags = [doc["_id"] for doc in result]

        # Combinar
        all_tag_names = list(set(list(tag_dict.keys()) + task_tags))
        all_tag_names.sort()

        return [
            {
                "name": name,
                "color": tag_dict.get(name) # None si no tiene color asignado explícitamente
            }
            for name in all_tag_names
        ]

    async def upsert_user_tag(self, user_id: str, name: str, color: str) -> dict:
        """Guarda o actualiza la configuración de color de una etiqueta para el usuario."""
        clean_name = self._norm_tag(name)
        if not clean_name:
            raise ValueError("El nombre de la etiqueta no puede estar vacío")
            
        doc = {
            "user_id": user_id,
            "name": clean_name,
            "color": color
        }
        await self.user_tags.update_one(
            {"user_id": user_id, "name": clean_name},
            {"$set": doc},
            upsert=True
        )
        return doc

    async def delete_user_tag(self, user_id: str, name: str):
        """Elimina el color guardado de una etiqueta del usuario."""
        await self.user_tags.delete_one({"user_id": user_id, "name": self._norm_tag(name)})

    async def rename_tag(self, user_id: str, old_name: str, new_name: str) -> str:
        """
        Renombra una etiqueta en todas las tareas del usuario y mueve su color.
        Si ya existía una etiqueta con el nombre nuevo, se fusionan (se conserva el color de la nueva).
        Devuelve el nombre normalizado final.
        """
        old = (old_name or "").strip()   # sin lower(): puede haber etiquetas antiguas con mayúsculas
        new = self._norm_tag(new_name)
        if not old or not new:
            raise ValueError("El nombre de la etiqueta no puede estar vacío")
        if old == new:
            return new

        # addToSet + pull en dos pasos para no duplicar si la tarea ya tenía la etiqueta nueva
        await self.tasks.update_many({"user_id": user_id, "tags": old}, {"$addToSet": {"tags": new}})
        await self.tasks.update_many({"user_id": user_id, "tags": old}, {"$pull": {"tags": old}})

        old_doc = await self.user_tags.find_one({"user_id": user_id, "name": old})
        if old_doc:
            if await self.user_tags.find_one({"user_id": user_id, "name": new}):
                await self.user_tags.delete_one({"_id": old_doc["_id"]})
            else:
                await self.user_tags.update_one({"_id": old_doc["_id"]}, {"$set": {"name": new}})
        return new


    async def get_chronological_events(self, user_id: str, subject_id: str = None) -> list:
        """Devuelve tareas, exámenes y entregas con fecha límite, ordenados cronológicamente."""
        query = {"user_id": user_id, "due_date": {"$ne": None}}
        if subject_id:
            query["subject_id"] = subject_id
            
        cursor = self.tasks.find(query).sort("due_date", 1)
        events = await cursor.to_list(100)
        for e in events:
            e["_id"] = str(e["_id"])
        return events
 
 
    # ############################################################################
    # # METHODS FOR TIME ENTRIES
 
    # async def create_time_entry(self, user_id: str, subject_id: str,
    #                             task_id: str = None, description: str = "") -> dict:
    #     """
    #     Crea una nueva entrada de tiempo.
    #     - subject_id es siempre obligatorio.
    #     - task_id es opcional: puede dedicarse tiempo a la asignatura en general,
    #       sin tarea concreta asociada.
    #     """
    #     time_entry = {
    #         "user_id": user_id,
    #         "subject_id": subject_id,
    #         "task_id": task_id,
    #         "description": description
    #     }
    #     result = await self.time_entries.insert_one(time_entry)
    #     time_entry["_id"] = str(result.inserted_id)
    #     return time_entry
 
    # async def get_time_entries_by_subject(self, subject_id: str) -> list:
    #     """Devuelve todas las entradas de tiempo de una asignatura, más recientes primero."""
    #     cursor = self.time_entries.find({"subject_id": subject_id})
    #     time_entries = await cursor.to_list(100)
    #     for te in time_entries:
    #         te["_id"] = str(te["_id"])
    #     return time_entries
 
    # async def get_time_entries_by_task(self, task_id: str) -> list:
    #     """Devuelve todas las entradas de tiempo de una tarea concreta."""
    #     cursor = self.time_entries.find({"task_id": task_id})
    #     time_entries = await cursor.to_list(100)
    #     for te in time_entries:
    #         te["_id"] = str(te["_id"])
    #     return time_entries
 
    # async def get_active_time_entry(self, user_id: str) -> dict | None:
    #     """
    #     Devuelve la entrada de tiempo en marcha del usuario (end_time == None), si hay una.
    #     Útil para comprobar si ya hay un cronómetro corriendo antes de arrancar otro.
    #     """
    #     entry = await self.time_entries.find_one({"user_id": user_id, "end_time": None})
    #     if entry:
    #         entry["_id"] = str(entry["_id"])
    #     return entry
 
    # async def delete_time_entry(self, time_entry_id: str):
    #     """Elimina una entrada de tiempo por su ID."""
    #     await self.time_entries.delete_one({"_id": ObjectId(time_entry_id)})
 
 
    # ############################################################################
    # # METHODS FOR WELLBEING
    

    async def create_wellbeing_report(self, user_id: str, date: str, sleep_hours: float, sleep_quality: int, mood_score: int, energy_level: int, notes: str = "") -> dict:
        """
        Crea un informe de bienestar del usuario.
        Úsala cuando el usuario quiera registrar su estado de ánimo o bienestar.
        """
        try:
            wellbeing_entry = {
                "user_id": user_id,
                "date": date,
                "sleep_hours": sleep_hours,
                "sleep_quality": sleep_quality,
                "mood_score": mood_score,
                "energy_level": energy_level,
                "notes": notes
            }
            result = await self.wellbeing_entries.insert_one(wellbeing_entry)
            wellbeing_entry["_id"] = str(result.inserted_id)
            return wellbeing_entry
        except Exception as e:
            return f"Error al registrar el informe de bienestar: {str(e)}"
    

    async def get_latest_wellbeing_report(self, user_id: str) -> dict | None:
        """Devuelve el últomo informe registrado ordenado por fecha."""
        report = await self.wellbeing_entries.find_one(
            {"user_id": user_id},
            sort=[("date", -1)]
        )
        if report:
            report["_id"] = str(report["_id"])
        return report
 
    async def get_wellbeing_report(self, user_id: str) -> dict | None:
        """Devuelve el informe de bienestar más reciente del usuario."""
        return await self.get_latest_wellbeing_report(user_id)

    async def has_wellbeing_report_for_date(self, user_id: str, date_str: str) -> bool:
        """Verifica si el usuario ya ha registrado un informe de bienestar para una fecha concreta (YYYY-MM-DD)."""
        count = await self.wellbeing_entries.count_documents({
            "user_id": user_id,
            "date": date_str
        })
        return count > 0


    async def get_wellbeing_trends(self, user_id: str) -> list:
        """Devuelve los últimos 7 informes de bienestar ordenados por fecha."""
        cursor = self.wellbeing_entries.find(
            {"user_id": user_id}
        ).sort("date", -1).limit(7)
        entries = await cursor.to_list(7)
        for e in entries:
            e["_id"] = str(e["_id"])
        return entries

    async def upsert_wellbeing_report(self, user_id: str, date: str, sleep_hours: float = None, sleep_quality: int = None, mood_score: int = None,
        energy_level: int = None, notes: str = None,) -> dict:
        """
        Crea o actualiza el informe de bienestar de un día (uno por user_id + date).
        Solo se modifican los campos que se pasan (not None); el resto se conserva.
        Las notas nuevas se añaden a las anteriores en lugar de sobrescribirlas.
        Devuelve el documento completo tras la operación.
        """
        for name, value in (("sleep_quality", sleep_quality),
                            ("mood_score", mood_score),
                            ("energy_level", energy_level)):
            if value is not None and not (1 <= int(value) <= 5):
                raise ValueError(f"{name} debe estar entre 1 y 5 (recibido: {value}).")
        if sleep_hours is not None and not (0 <= float(sleep_hours) <= 24):
            raise ValueError(f"sleep_hours debe estar entre 0 y 24 (recibido: {sleep_hours}).")

        incoming = {
            "sleep_hours": sleep_hours,
            "sleep_quality": sleep_quality,
            "mood_score": mood_score,
            "energy_level": energy_level,
        }
        to_set = {k: v for k, v in incoming.items() if v is not None}

        # Notas: concatenar con las existentes
        if notes:
            existing = await self.wellbeing_entries.find_one(
                {"user_id": user_id, "date": date}, {"notes": 1}
            )
            prev = (existing or {}).get("notes")
            to_set["notes"] = f"{prev} | {notes}" if prev else notes

        # Al crear el documento, los campos no informados quedan a None (misma forma que create_wellbeing_report)
        all_fields = list(incoming) + ["notes"]
        set_on_insert = {k: None for k in all_fields if k not in to_set}

        update = {"$setOnInsert": set_on_insert}
        if to_set:
            update["$set"] = to_set

        doc = await self.wellbeing_entries.find_one_and_update(
            {"user_id": user_id, "date": date},
            update,
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        doc["_id"] = str(doc["_id"])
        return doc


    ############################################################################
    # METHODS FOR STUDY REPORTS

    async def create_study_report(
        self,
        user_id: str,
        clockify_time_entry_id: str,
        subject_name: str = None,
        study_quality: int = None,
        goals_achieved: bool = None,
        goals_description: str = None,
        distractions: str = None,
        breaks_taken: int = None,
        mood_before: int = None,
        mood_after: int = None,
        notes: str = None
    ) -> dict:
        """
        Crea un informe de sesión de estudio vinculado OBLIGATORIAMENTE a una entrada de tiempo de Clockify.
        Todos los campos son opcionales excepto user_id y clockify_time_entry_id.
        """
        if not clockify_time_entry_id:
            raise ValueError("Se requiere obligatoriamente un 'clockify_time_entry_id' para registrar un informe de sesión.")

        report = {
            "user_id": user_id,
            "clockify_time_entry_id": clockify_time_entry_id,
            "subject_name": subject_name,
            "timestamp": datetime.now(timezone.utc),
            "study_quality": study_quality,
            "goals_achieved": goals_achieved,
            "goals_description": goals_description,
            "distractions": distractions,
            "breaks_taken": breaks_taken,
            "mood_before": mood_before,
            "mood_after": mood_after,
            "notes": notes,
        }
        result = await self.study_reports.insert_one(report)
        report["_id"] = str(result.inserted_id)
        report["timestamp"] = report["timestamp"].isoformat()
        return report

    async def get_study_reports_by_user(self, user_id: str, limit: int = 10, subject_name: str = None) -> list[dict]:
        """
        Devuelve los informes de sesión del usuario ordenados del más reciente al más antiguo.
        Filtra opcionalmente por nombre de asignatura.
        """
        query = {"user_id": user_id}
        if subject_name:
            query["subject_name"] = {"$regex": subject_name, "$options": "i"}
        cursor = self.study_reports.find(query).sort("timestamp", -1).limit(limit)
        reports = await cursor.to_list(limit)
        for r in reports:
            r["_id"] = str(r["_id"])
            if isinstance(r.get("timestamp"), datetime):
                r["timestamp"] = r["timestamp"].isoformat()
        return reports

    async def get_study_report_by_time_entry(self, user_id: str, clockify_time_entry_id: str) -> dict | None:
        """Devuelve el informe de sesión asociado a un clockify_time_entry_id concreto, si existe."""
        report = await self.study_reports.find_one({"user_id": user_id, "clockify_time_entry_id": clockify_time_entry_id})
        if report:
            report["_id"] = str(report["_id"])
            if isinstance(report.get("timestamp"), datetime):
                report["timestamp"] = report["timestamp"].isoformat()
        return report

    ############################################################################
    # METHODS FOR STUDY PLANS


    async def create_study_plan(
        self,
        user_id: str,
        title: str,
        items: list,
        start_date: str = None,
        end_date: str = None
    ) -> dict:
        """
        Crea un nuevo plan de estudio asociando sesiones a asignaturas y tareas existentes
        sin generar tareas basura en la lista global.
        """
        await self.study_plans.update_many(
            {"user_id": user_id, "status": "active"},
            {"$set": {"status": "archived"}}
        )

        now = datetime.now(timezone.utc)
        base_start = start_date or now.strftime("%Y-%m-%d")

        try:
            base_dt = datetime.strptime(base_start, "%Y-%m-%d").replace(tzinfo=ZoneInfo("Europe/Madrid"))
        except Exception:
            try:
                base_dt = datetime.strptime(base_start, "%Y-%m-%d")
            except Exception:
                base_dt = now

        weekday_map = {
            "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
            "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6
        }

        # Cargar tareas existentes del usuario para hacer referencias cruzadas
        user_tasks = await self.tasks.find({"user_id": user_id}).to_list(length=1000)

        processed_items = []
        for item in items:
            it = dict(item) if isinstance(item, dict) else {}
            day_raw = str(it.get("day", "")).strip()
            due_date = it.get("due_date")

            if not due_date:
                if re.match(r"^\d{4}-\d{2}-\d{2}$", day_raw):
                    due_date = day_raw
                elif day_raw.lower() in weekday_map:
                    target_wd = weekday_map[day_raw.lower()]
                    days_ahead = (target_wd - base_dt.weekday() + 7) % 7
                    due_date = (base_dt + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                else:
                    due_date = base_start
            
            it["due_date"] = due_date
            subj_name = it.get("subject_name")
            desc = it.get("description") or it.get("task", "")
            # Conservar los vínculos ya resueltos por la herramienta MCP (linked_task_titles -> ids)
            linked_tasks = [str(x) for x in (it.get("linked_task_ids") or [])]

            if subj_name:
                sub_doc = await self.subjects.find_one({
                    "user_id": user_id,
                    "name": {"$regex": f"^{re.escape(subj_name)}$", "$options": "i"}
                })
                if sub_doc:
                    subj_id = str(sub_doc["_id"])
                    it["subject_id"] = subj_id

                    # Si la actividad menciona el título de una tarea existente, vincula la tarea y actualiza su vencimiento
                    for task in user_tasks:
                        if str(task.get("subject_id")) == subj_id:
                            t_title = task.get("title", "").strip()
                            if t_title.lower() in desc.lower() and len(t_title) > 2:
                                t_id = str(task["_id"])
                                if t_id not in linked_tasks:
                                    linked_tasks.append(t_id)
                                # Exámenes/entregas: se vinculan pero nunca se les cambia la fecha
                                if task.get("due_date") != due_date and task_can_be_rescheduled(task):
                                    await self.update_task(t_id, due_date=due_date)

            it["linked_task_ids"] = linked_tasks
            # NUNCA se invoca create_task: las actividades como 'Revisar' se quedan solo dentro del plan
            processed_items.append(it)

        plan = {
            "user_id": user_id,
            "title": title,
            "items": processed_items,
            "start_date": base_start,
            "end_date": end_date,
            "status": "active",
            "created_at": now.isoformat()
        }

        result = await self.study_plans.insert_one(plan)
        plan["_id"] = str(result.inserted_id)
        return plan

    async def get_active_study_plan(self, user_id: str) -> dict | None:
        """Devuelve el plan de estudio actualmente activo del usuario."""
        plan = await self.study_plans.find_one({"user_id": user_id, "status": "active"})
        if plan:
            plan["_id"] = str(plan["_id"])
        return plan

    async def update_study_plan_items(self, user_id: str, plan_id: str, items: list) -> bool:
        """Reemplaza la lista de actividades (items) de un plan de estudio del usuario."""
        try:
            res = await self.study_plans.update_one(
                {"_id": ObjectId(plan_id), "user_id": user_id},
                {"$set": {"items": items, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            return res.matched_count > 0
        except Exception:
            return False

    async def update_study_plan_status(self, user_id: str, plan_id: str, status: str) -> bool:
        """Actualiza el estado de un plan de estudio ('active', 'completed', 'archived', 'cancelled')."""
        try:
            res = await self.study_plans.update_one(
                {"_id": ObjectId(plan_id), "user_id": user_id},
                {"$set": {"status": status}}
            )
            return res.modified_count > 0
        except Exception:
            return False


    ############################################################################
    # METHODS FOR COURSES

    async def create_course(self, teacher_id: str, name: str, description: Optional[str] = None,
                            academic_year: Optional[str] = None) -> dict:
        """
        Crea un nuevo curso. Genera un código de matriculación único.
        academic_year: ej. '2025/26', '2026/27'
        """
        # Generar un código único (6 chars, mayúsculas)
        for _ in range(10):
            code = secrets.token_urlsafe(6).upper()[:8]
            existing = await self.courses.find_one({"enrollment_code": code})
            if not existing:
                break

        course = {
            "name": name,
            "description": description,
            "academic_year": academic_year,  # ej. '2025/26'
            "teacher_ids": [teacher_id],
            "student_ids": [],
            "enrollment_code": code,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True,
            "student_summaries": {}  # { student_id: { text, generated_at } }
        }
        result = await self.courses.insert_one(course)
        course["_id"] = str(result.inserted_id)
        return course

    async def get_course_by_id(self, course_id: str) -> dict | None:
        """Devuelve un curso por su ID."""
        try:
            course = await self.courses.find_one({"_id": ObjectId(course_id)})
            if course:
                course["_id"] = str(course["_id"])
            return course
        except Exception:
            return None

    async def get_courses_by_teacher(self, teacher_id: str) -> list:
        """Devuelve todos los cursos donde el usuario es profesor."""
        cursor = self.courses.find({"teacher_ids": teacher_id})
        courses = await cursor.to_list(100)
        for c in courses:
            c["_id"] = str(c["_id"])
        return courses

    async def get_enrolled_courses(self, student_id: str) -> list:
        """
        Devuelve los cursos en los que el usuario está matriculado como alumno.
        Busca subjects con course_id != null y user_id == student_id,
        luego obtiene esos cursos.
        """
        # Buscar subjects que tienen course_id (matriculaciones)
        cursor = self.subjects.find(
            {"user_id": student_id, "course_id": {"$ne": None}},
            {"course_id": 1}
        )
        subj_docs = await cursor.to_list(200)
        course_ids = list({s["course_id"] for s in subj_docs if s.get("course_id")})

        if not course_ids:
            return []

        oid_list = []
        for cid in course_ids:
            try:
                oid_list.append(ObjectId(cid))
            except Exception:
                pass

        cursor2 = self.courses.find({"_id": {"$in": oid_list}})
        courses = await cursor2.to_list(200)
        for c in courses:
            c["_id"] = str(c["_id"])
        return courses

    async def get_course_by_enrollment_code(self, code: str) -> dict | None:
        """Busca un curso por su código de matriculación."""
        course = await self.courses.find_one({"enrollment_code": code.upper()})
        if course:
            course["_id"] = str(course["_id"])
        return course

    async def add_student_to_course(self, course_id: str, student_id: str) -> None:
        """Añade un alumno al array student_ids del curso (idempotente)."""
        try:
            await self.courses.update_one(
                {"_id": ObjectId(course_id)},
                {"$addToSet": {"student_ids": student_id}}
            )
        except Exception:
            pass

    async def remove_student_from_course(self, course_id: str, student_id: str) -> None:
        """Quita un alumno del array student_ids del curso y desvincula sus asignaturas."""
        try:
            await self.courses.update_one(
                {"_id": ObjectId(course_id)},
                {"$pull": {"student_ids": student_id}}
            )
            await self.subjects.update_many(
                {"course_id": course_id, "user_id": student_id},
                {"$set": {"course_id": None}}
            )
        except Exception:
            pass

    async def get_subjects_by_course_and_user(self, course_id: str, student_id: str) -> list:
        """Devuelve las subjects del alumno para un curso concreto."""
        cursor = self.subjects.find({"course_id": course_id, "user_id": student_id})
        subjects = await cursor.to_list(10)
        for s in subjects:
            s["_id"] = str(s["_id"])
        return subjects



    async def update_course(self, course_id: str, **fields) -> None:
        """Actualiza campos sueltos de un curso (name, description, academic_year, is_active...)."""
        if not fields:
            return
        try:
            await self.courses.update_one(
                {"_id": ObjectId(course_id)},
                {"$set": fields}
            )
        except Exception:
            pass

    async def delete_course(self, course_id: str) -> None:
        """Elimina un curso y desvincula sus subjects (pone course_id a None en todos los alumnos)."""
        try:
            # Desvincular subjects asociadas
            await self.subjects.update_many(
                {"course_id": course_id},
                {"$set": {"course_id": None}}
            )
            await self.courses.delete_one({"_id": ObjectId(course_id)})
        except Exception:
            pass