import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from bson import ObjectId
from datetime import datetime, timezone
 
 
load_dotenv()
 
class DatabaseService:
 
    def __init__(self):
        self.client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
        self.db = self.client["tfg_bienestar"]
 
        # Colecciones
        self.users = self.db["users"]
 
        self.periods = self.db["periods"]
        self.subjects = self.db["subjects"]
        self.tasks = self.db["tasks"]
        # self.time_entries = self.db["time_entries"]
        self.history = self.db["history"]
        self.wellbeing_entries = self.db["wellbeing_entries"]
        self.study_reports = self.db["study_reports"]
        self.study_plans = self.db["study_plans"]

    async def ensure_indexes(self):
        """
        Crea los índices necesarios. Llamar una vez al arrancar la app (p.ej. en el
        lifespan de main.py), es idempotente: si el índice ya existe, Mongo no hace nada.
        """
        await self.subjects.create_index([("user_id", 1), ("period_id", 1)])
        await self.tasks.create_index([("subject_id", 1)])
        await self.tasks.create_index([("parent_task_id", 1)])
        
        await self.tasks.create_index("tags")
        # await self.deadlines.create_index([("user_id", 1), ("date", 1)])
        await self.periods.create_index([("user_id", 1)])
        await self.history.create_index([("user_id", 1), ("timestamp", -1)])
        await self.wellbeing_entries.create_index([("user_id", 1), ("date", -1)])
        await self.study_reports.create_index([("user_id", 1), ("timestamp", -1)])
        await self.study_reports.create_index("clockify_time_entry_id")
        await self.study_plans.create_index([("user_id", 1), ("status", 1)])
 

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
                msg["timestamp"] = msg["timestamp"].isoformat()

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
 
    async def create_user(self, email: str, name: str, hashed_password: str) -> dict:
        """Crea un nuevo usuario en la base de datos."""
        user = {
            "email": email,
            "name": name,
            "password": hashed_password,
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
        """
        or_conditions = []
        if clockify_user_id:
            or_conditions.append({"clockify.clockify_user_id": clockify_user_id})
        if api_key:
            or_conditions.append({"clockify.api_key": api_key})

        if not or_conditions:
            return None

        query = {"$or": or_conditions}
        if exclude_user_id:
            try:
                query["_id"] = {"$ne": ObjectId(exclude_user_id)}
            except Exception:
                pass

        return await self.users.find_one(query)


    async def update_clockify_credentials(self, user_id: str, api_key: str, workspace_id: str = None, clockify_user_id: str = None):
        """Actualiza la API Key y Workspace de Clockify del usuario."""
        clockify_data = {
            "api_key": api_key,
            "workspace_id": workspace_id,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        if clockify_user_id:
            clockify_data["clockify_user_id"] = clockify_user_id
        await self.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"clockify": clockify_data}}
        )
        return clockify_data

    async def update_clockify_key(self, user_id: str, api_key: str):
        """Compatibilidad: Actualiza la API key de Clockify de un usuario."""
        return await self.update_clockify_credentials(user_id=user_id, auth_type="api_key", token=api_key)

    async def get_clockify_credentials(self, user_id: str) -> dict | None:
        """Devuelve las credenciales de Clockify de un usuario."""
        user = await self.get_user_by_id(user_id)
        if user:
            return user.get("clockify")
        return None

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
 
    async def create_subject(self, user_id: str, name: str, clockify_project_id: str,
                              weekly_hours_goal: int = 0, period_id: str = None, grade: float = None,
                              description: str = None, evaluation_criteria: str = None,
                              notes: str = None) -> dict:
        """
        Crea una nueva asignatura asociada a un usuario.
        period_id es opcional: una asignatura puede no pertenecer a ningún periodo
        si el usuario decide no organizarse por cuatrimestres/trimestres.
        description: breve descripción de qué trata la asignatura.
        evaluation_criteria: cómo se evalúa (ej: '60% examen, 40% prácticas').
        notes: anotaciones libres del usuario (ej: 'me gusta mucho', 'el profe explica muy bien').
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
        }
        result = await self.subjects.insert_one(subject)
        subject["_id"] = str(result.inserted_id)
        return subject

 
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
        Al crearlas, el campo status por defecto es "PENDING".
        """
        task = {
            "user_id": user_id,
            "subject_id": subject_id,
            "parent_task_id": parent_task_id,
            "clockify_task_id": clockify_task_id,
            "title": title,
            "description": description,
            "due_date": due_date,
            "type": type,
            "status":"PENDING", # "PENDING", "ACTIVE", "COMPLETED"
            "priority": priority,
            "tags": tags if tags is not None else []
        }
        result = await self.tasks.insert_one(task)
        task["_id"] = str(result.inserted_id)
        return task

    async def get_tasks_by_subject(self, subject_id: str, include_completed: bool = True, include_active: bool = True, include_in_progress: bool = True, include_pending: bool = True) -> list:
        """Devuelve todas las tareas de una asignatura según los filtros de estado."""
        query = {"subject_id": subject_id}
        
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

        cursor = self.tasks.find(query)
        tasks = await cursor.to_list(100)
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
        await self.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": fields})

    async def mark_task_completed(self, task_id: str, completed: bool = True):
        """Marcar una tarea como completada ("COMPLETED") o revertirla a pendiente ("PENDING")."""
        new_status = "COMPLETED" if completed else "PENDING"
        await self.update_task(task_id, status=new_status)

    async def mark_task_active(self, task_id: str, active: bool = True):
        """Marcar una tarea como activa ("ACTIVE") o revertirla a pendiente ("PENDING")."""
        new_status = "ACTIVE" if active else "PENDING"
        await self.update_task(task_id, status=new_status)

    async def mark_task_in_progress(self, task_id: str, in_progress: bool = True):
        """Alias de compatibilidad para mark_task_active."""
        await self.mark_task_active(task_id, active=in_progress)

    async def delete_task(self, task_id: str):
        """Elimina una tarea por su ID, eliminando también sus subtareas y entradas de tiempo."""
        str_id = str(task_id)
        task_oid = ObjectId(str_id)
        # Eliminar entradas de tiempo vinculadas
        await self.time_entries.delete_many({"task_id": str_id})
        # Eliminar subtareas
        await self.tasks.delete_many({"parent_task_id": str_id})
        # Eliminar la propia tarea
        await self.tasks.delete_one({"_id": task_oid})


    async def get_tasks_by_tag(self, user_id: str, tag: str) -> list:
        """Devuelve todas las tareas del usuario que contengan el tag indicado."""
        cursor = self.tasks.find({"user_id": user_id, "tags": tag})
        tasks = await cursor.to_list(200)
        for t in tasks:
            t["_id"] = str(t["_id"])
        return tasks

    async def get_all_tags(self, user_id: str) -> list:
        """Devuelve la lista de tags únicos usados por el usuario en sus tareas."""
        pipeline = [
            {"$match": {"user_id": user_id, "tags": {"$exists": True, "$ne": []}}},
            {"$unwind": "$tags"},
            {"$group": {"_id": "$tags"}},
            {"$sort": {"_id": 1}}
        ]
        result = await self.tasks.aggregate(pipeline).to_list(200)
        return [doc["_id"] for doc in result]


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
 
    async def delete_time_entry(self, time_entry_id: str):
        """Elimina una entrada de tiempo por su ID."""
        await self.time_entries.delete_one({"_id": ObjectId(time_entry_id)})
 
 
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
        Crea un nuevo plan de estudio para el usuario.
        Archiva cualquier otro plan de estudio activo previo.
        """
        # Archivar planes activos previos del usuario
        await self.study_plans.update_many(
            {"user_id": user_id, "status": "active"},
            {"$set": {"status": "archived"}}
        )

        now = datetime.now(timezone.utc)
        plan = {
            "user_id": user_id,
            "title": title,
            "items": items,
            "start_date": start_date or now.strftime("%Y-%m-%d"),
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