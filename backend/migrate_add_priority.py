"""
Script de migración: añade el campo `priority: null` a todas las tareas existentes.

Uso:
    python migrate_add_priority.py

Requiere que estés en el entorno donde las variables de entorno del .env son accesibles,
O bien ejecutarlo desde dentro del contenedor Docker con:
    docker compose exec backend python migrate_add_priority.py

    docker compose -f docker-compose.dev.yml exec backend python migrate_add_priority.py

"""

"""
Script de migración: añade los campos `priority: null` y `tags: []` a todas las tareas existentes.
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()


async def migrate():
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://db:27017/tfg_bienestar")
    db_name = "tfg_bienestar"

    print(f"Conectando a MongoDB: {mongodb_uri}, BD: {db_name}")
    client = AsyncIOMotorClient(mongodb_uri)
    db = client[db_name]
    tasks = db["tasks"]

    # Actualiza los documentos que NO tienen priority
    result_priority = await tasks.update_many(
        {"priority": {"$exists": False}},
        {"$set": {"priority": None}}
    )
    print(f"priority - Documentos actualizados: {result_priority.modified_count}")

    # Actualiza los documentos que NO tienen tags
    result_tags = await tasks.update_many(
        {"tags": {"$exists": False}},
        {"$set": {"tags": []}}
    )
    print(f"tags - Documentos actualizados: {result_tags.modified_count}")

    client.close()


if __name__ == "__main__":
    asyncio.run(migrate())