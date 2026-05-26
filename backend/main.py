from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from services.clockify import ClockifyService
from services.openai import OpenAIService
from services.gemini import GeminiService


app = FastAPI(title="TFG Bienestar")

clockify = ClockifyService()
# openai_api = OpenAIService()
gemini_api = GeminiService()

# Para hacer la prueba con el frontend
class ChatRequest(BaseModel):
    message: str
    workspace_id: str = None
 

@app.post("/api/chat")
async def handle_chat(request: ChatRequest):
    try:
        # Fetch both projects and recent time entries (last 7 days)
        workspace_id = request.workspace_id
        projects = clockify.get_projects(workspace_id)
        time_entries = clockify.get_time_entries(workspace_id, days_back=7)
        
        # Package all the clockify context for Gemini
        clockify_context = {
            "active_projects": projects,
            "recent_time_entries": time_entries
        }
        
        # Generating response with Gemini
        response = gemini_api.chat_with_context(
            user_message=request.message,
            clockify_data=clockify_context 
        )
        
        return {"response": response}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))