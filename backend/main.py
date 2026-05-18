from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from services.clockify import ClockifyService
from services.openai import OpenAIService
from services.gemini import Gemini


app = FastAPI(title="TFG Bienestar")

# Inicializamos nuestros servicios
clockify = ClockifyService()
# openai_api = OpenAIService()
gemini_api = Gemini()
# Definimos qué datos esperamos recibir desde el Frontend
class ChatRequest(BaseModel):
    message: str
    workspace_id: str = None

@app.post("/api/chat")
async def chat_asistente(request: ChatRequest):
    try:
        # 1. Buscamos los proyectos actuales del usuario en Clockify para darle contexto a la IA
        # (Más adelante aquí buscaremos las horas trabajadas en su lugar)
        proyectos = clockify.get_projects(request.workspace_id)
        
        # 2. Le mandamos el mensaje del usuario + los proyectos a ChatGPT
        respuesta_ia = gemini_api.chat_with_context(
            user_message=request.message,
            clockify_data=proyectos
        )
        
        # 3. Devolvemos la respuesta al Frontend
        return {"response": respuesta_ia}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))