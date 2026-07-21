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
        self.time_entries = self.db["time_entries"]
        # self.deadlines = self.db["deadlines"]
 
    async def ensure_indexes(self):
        """
        Crea los índices necesarios. Llamar una vez al arrancar la app (p.ej. en el
        lifespan de main.py), es idempotente: si el índice ya existe, Mongo no hace nada.
        """
        await self.subjects.create_index([("user_id", 1), ("period_id", 1)])
        await self.tasks.create_index([("subject_id", 1)])
        await self.tasks.create_index([("parent_task_id", 1)])
        await self.time_entries.create_index([("subject_id", 1), ("start_time", -1)])
        await self.time_entries.create_index([("task_id", 1)])
        # await self.deadlines.create_index([("user_id", 1), ("date", 1)])
        await self.periods.create_index([("user_id", 1)])
 
 
    ############################################################################
    # METHODS FOR USERS
 
    async def create_user(self, email: str, name: str, hashed_password: str) -> dict:
        """Crea un nuevo usuario en la base de datos."""
        user = {
            "email": email,
            "name": name,
            "password": hashed_password,
            "current_period_id": None,
            "clockify_api_key": None
        }
        result = await self.users.insert_one(user)
        user["_id"] = str(result.inserted_id)
        return user
 
    async def get_user_by_email(self, email: str) -> dict | None:
        """Busca un usuario por su email."""
        return await self.users.find_one({"email": email})
 
    async def update_clockify_key(self, user_id: str, api_key: str):
        """Actualiza la API key de Clockify de un usuario."""
        await self.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"clockify_api_key": api_key}}
        )
 
    async def update_current_period(self, user_id: str, period_id: str):
        """Actualiza el periodo académico actual de un usuario."""
        await self.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"current_period_id": period_id}}
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
 
    async def create_subject(self, user_id: str, name: str, clockify_project_id: str,
                              weekly_hours_goal: int = 0, period_id: str = None) -> dict:
        """
        Crea una nueva asignatura asociada a un usuario.
        period_id es opcional: una asignatura puede no pertenecer a ningún periodo
        si el usuario decide no organizarse por cuatrimestres/trimestres.
        """
        subject = {
            "user_id": user_id,
            "period_id": period_id,
            "name": name,
            "clockify_project_id": clockify_project_id,
            "weekly_hours_goal": weekly_hours_goal,
            "is_archived": False,
        }
        result = await self.subjects.insert_one(subject)
        subject["_id"] = str(result.inserted_id)
        return subject
 
    async def get_subjects_by_user(self, user_id: str, include_archived: bool = False) -> list:
        """Devuelve todas las asignaturas de un usuario (por defecto, sin las archivadas)."""
        query = {"user_id": user_id}
        if not include_archived:
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
 
    # async def create_task(self, user_id: str, subject_id: str, title: str,
    #                       description: str = "", due_date: str = None,
    #                       parent_task_id: str = None, clockify_task_id: str = None) -> dict:
    #     """
    #     Crea una nueva tarea asociada a una asignatura.
    #     parent_task_id es opcional: si se indica, esta tarea es una subtarea de otra.
    #     clockify_task_id es opcional: solo las tareas raíz (sin parent) se reflejan en
    #     Clockify, ya que Clockify no soporta subtareas anidadas de verdad.
    #     """
    #     task = {
    #         "user_id": user_id,
    #         "subject_id": subject_id,
    #         "parent_task_id": parent_task_id,
    #         "clockify_task_id": clockify_task_id,
    #         "title": title,
    #         "description": description,
    #         "due_date": due_date,
    #         "completed": False
    #     }
    #     result = await self.tasks.insert_one(task)
    #     task["_id"] = str(result.inserted_id)
    #     return task

    async def create_task(self, user_id: str, title: str, subject_id: str = None,
                          description: str = "", due_date: str = None,
                          type: str = "task", parent_task_id: str = None, 
                          clockify_task_id: str = None) -> dict:
        """
        Crea un elemento de trabajo o evento en el sistema (Tarea, Examen, Entrega, etc.).
        type puede ser: 'task', 'exam', 'assignment' u 'other'.
        subject_id es opcional para permitir eventos globales o administrativos.
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
            "completed": False
        }
        result = await self.tasks.insert_one(task)
        task["_id"] = str(result.inserted_id)
        return task
 
    async def get_tasks_by_subject(self, subject_id: str, include_completed: bool = True) -> list:
        """Devuelve todas las tareas de una asignatura (opcionalmente solo las pendientes)."""
        query = {"subject_id": subject_id}
        if not include_completed:
            query["completed"] = False
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
        """Actualiza campos sueltos de una tarea (title, description, due_date, completed...)."""
        if not fields:
            return
        await self.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": fields})
 
    async def mark_task_completed(self, task_id: str, completed: bool = True):
        """Atajo para marcar una tarea como completada/pendiente."""
        await self.update_task(task_id, completed=completed)
 
    async def delete_task(self, task_id: str):
        """Elimina una tarea por su ID. No borra en cascada sus subtareas ni time_entries."""
        await self.tasks.delete_one({"_id": ObjectId(task_id)})


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
 
 
    ############################################################################
    # METHODS FOR TIME ENTRIES
 
    async def create_time_entry(self, user_id: str, subject_id: str,
                                start_time: str, end_time: str = None,
                                task_id: str = None, description: str = "") -> dict:
        """
        Crea una nueva entrada de tiempo.
        - subject_id es siempre obligatorio.
        - task_id es opcional: puede dedicarse tiempo a la asignatura en general,
          sin tarea concreta asociada.
        - end_time es opcional: si es None, se interpreta como un cronómetro en marcha
          (equivalente al timer activo de Clockify).
        """
        time_entry = {
            "user_id": user_id,
            "subject_id": subject_id,
            "task_id": task_id,
            "description": description,
            "start_time": start_time,
            "end_time": end_time
        }
        result = await self.time_entries.insert_one(time_entry)
        time_entry["_id"] = str(result.inserted_id)
        return time_entry
 
    async def get_time_entries_by_subject(self, subject_id: str) -> list:
        """Devuelve todas las entradas de tiempo de una asignatura, más recientes primero."""
        cursor = self.time_entries.find({"subject_id": subject_id}).sort("start_time", -1)
        time_entries = await cursor.to_list(100)
        for te in time_entries:
            te["_id"] = str(te["_id"])
        return time_entries
 
    async def get_time_entries_by_task(self, task_id: str) -> list:
        """Devuelve todas las entradas de tiempo de una tarea concreta."""
        cursor = self.time_entries.find({"task_id": task_id}).sort("start_time", -1)
        time_entries = await cursor.to_list(100)
        for te in time_entries:
            te["_id"] = str(te["_id"])
        return time_entries
 
    async def get_active_time_entry(self, user_id: str) -> dict | None:
        """
        Devuelve la entrada de tiempo en marcha del usuario (end_time == None), si hay una.
        Útil para comprobar si ya hay un cronómetro corriendo antes de arrancar otro.
        """
        entry = await self.time_entries.find_one({"user_id": user_id, "end_time": None})
        if entry:
            entry["_id"] = str(entry["_id"])
        return entry
 
    async def stop_time_entry(self, time_entry_id: str, end_time: str = None) -> dict | None:
        """Detiene un cronómetro en marcha, fijando su end_time (por defecto, ahora mismo)."""
        end_time = end_time or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        await self.time_entries.update_one(
            {"_id": ObjectId(time_entry_id)},
            {"$set": {"end_time": end_time}}
        )
        return await self.time_entries.find_one({"_id": ObjectId(time_entry_id)})
 
    async def delete_time_entry(self, time_entry_id: str):
        """Elimina una entrada de tiempo por su ID."""
        await self.time_entries.delete_one({"_id": ObjectId(time_entry_id)})
 
 
    # ############################################################################
    # # METHODS FOR DEADLINES
 
    # async def create_deadline(self, user_id: str, title: str, date: str,
    #                            type: str = "assignment", subject_id: str = None,
    #                            task_id: str = None) -> dict:
    #     """
    #     Crea una entrega, examen o fecha importante.
    #     type: 'assignment', 'exam' u 'other'.
    #     date: string en formato ISO 8601 (ej: '2026-07-15').
    #     subject_id y task_id son opcionales e independientes entre sí:
    #     - ninguno de los dos -> deadline "libre" (ej. algo administrativo)
    #     - solo subject_id -> deadline general de la asignatura (ej. examen final)
    #     - subject_id + task_id -> deadline de una tarea concreta
    #     """
    #     deadline = {
    #         "user_id": user_id,
    #         "subject_id": subject_id,
    #         "task_id": task_id,
    #         "title": title,
    #         "date": date,
    #         "type": type
    #     }
    #     result = await self.deadlines.insert_one(deadline)
    #     deadline["_id"] = str(result.inserted_id)
    #     return deadline
 
    # async def get_deadlines_by_user(self, user_id: str) -> list:
    #     """Devuelve todas las entregas y exámenes de un usuario, ordenados por fecha."""
    #     cursor = self.deadlines.find({"user_id": user_id}).sort("date", 1)
    #     deadlines = await cursor.to_list(100)
    #     for d in deadlines:
    #         d["_id"] = str(d["_id"])
    #     return deadlines
 
    # async def get_deadlines_by_subject(self, subject_id: str) -> list:
    #     """Devuelve las entregas y exámenes de una asignatura concreta, ordenados por fecha."""
    #     cursor = self.deadlines.find({"subject_id": subject_id}).sort("date", 1)
    #     deadlines = await cursor.to_list(100)
    #     for d in deadlines:
    #         d["_id"] = str(d["_id"])
    #     return deadlines
 
    # async def get_deadline_by_id(self, deadline_id: str) -> dict | None:
    #     """Devuelve un deadline por su ID."""
    #     deadline = await self.deadlines.find_one({"_id": ObjectId(deadline_id)})
    #     if deadline:
    #         deadline["_id"] = str(deadline["_id"])
    #     return deadline
 
    # async def update_deadline(self, deadline_id: str, **fields):
    #     """Actualiza campos sueltos de un deadline (title, date, type...)."""
    #     if not fields:
    #         return
    #     await self.deadlines.update_one({"_id": ObjectId(deadline_id)}, {"$set": fields})
 
    # async def delete_deadline(self, deadline_id: str):
    #     """Elimina una entrega o examen por su ID."""
    #     await self.deadlines.delete_one({"_id": ObjectId(deadline_id)})
 
