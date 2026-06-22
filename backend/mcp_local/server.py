
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Archivo con las tools, resources y prompts

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from services.clockify import ClockifyService

clockify_service = ClockifyService()


mcp = FastMCP(name="Clockify")

@mcp.tool()
async def get_active_workspaces():
    try:
        return clockify_service.get_workspaces()
    except Exception as e:
        return f"Error: {str(e)}"
    

@mcp.tool()
async def get_projects(workspace_id: str = None):
    try:
        return clockify_service.get_projects(workspace_id)
    except Exception as e:
        return f"Error: {str(e)}"



@mcp.prompt()
def greet_user(name: str, style: str = "friendly") -> str:
    """Generate a greeting prompt"""
    styles = {
        "friendly": "Por favor, escribe un saludo amigable",
        "formal": "Por favor, escribe un saludo formal y profesional",
        "casual": "Por favor, escribe un saludo casual y relajado",
    }

    return f"{styles.get(style, styles['friendly'])} for someone named {name}."

    
    
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