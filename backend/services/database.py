import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from bson import ObjectId


load_dotenv()

class DatabaseService:

    def __init__(self):
        self.client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
        self.db = self.client["tfg_bienestar"]

        # Colecciones
        self.users = self.db["users"]
        self.subjects = self.db["subjects"]
        self.deadlines = self.db["deadlines"]


    ############################################################################
    # METHODS FOR USERS

    async def create_user(self, email: str, name: str, hashed_password: str) -> dict:
        """Crea un nuevo usuario en la base de datos."""
        user = {
            "email": email,
            "name": name,
            "password": hashed_password,
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


    ############################################################################
    # METHODS FOR SUBJECTS

    async def create_subject(self, user_id: str, name: str, clockify_project_id: str,
                              weekly_hours_goal: int = 0) -> dict:
        """Crea una nueva asignatura asociada a un usuario."""
        subject = {
            "user_id": user_id,
            "name": name,
            "clockify_project_id": clockify_project_id,
            "weekly_hours_goal": weekly_hours_goal,
        }
        result = await self.subjects.insert_one(subject)
        subject["_id"] = str(result.inserted_id)
        return subject

    async def get_subjects_by_user(self, user_id: str) -> list:
        """Devuelve todas las asignaturas de un usuario."""
        cursor = self.subjects.find({"user_id": user_id})
        subjects = await cursor.to_list(100)
        for s in subjects:
            s["_id"] = str(s["_id"])
        return subjects

    async def delete_subject(self, subject_id: str):
        """Elimina una asignatura por su ID."""
        await self.subjects.delete_one({"_id": ObjectId(subject_id)})


    ############################################################################
    # METHODS FOR DEADLINES

    async def create_deadline(self, user_id: str, subject_id: str, title: str,
                               date: str, type: str = "assignment") -> dict:
        """
        Crea una entrega o examen.
        type: 'assignment' o 'exam'
        date: string en formato ISO 8601 (ej: '2026-07-15')
        """
        deadline = {
            "user_id": user_id,
            "subject_id": subject_id,
            "title": title,
            "date": date,
            "type": type
        }
        result = await self.deadlines.insert_one(deadline)
        deadline["_id"] = str(result.inserted_id)
        return deadline

    async def get_deadlines_by_user(self, user_id: str) -> list:
        """Devuelve todas las entregas y exámenes de un usuario, ordenados por fecha."""
        cursor = self.deadlines.find({"user_id": user_id}).sort("date", 1)
        deadlines = await cursor.to_list(100)
        for d in deadlines:
            d["_id"] = str(d["_id"])
        return deadlines

    async def delete_deadline(self, deadline_id: str):
        """Elimina una entrega o examen por su ID."""
        await self.deadlines.delete_one({"_id": ObjectId(deadline_id)})
