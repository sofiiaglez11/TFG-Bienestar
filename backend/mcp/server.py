
# Archivo con las tools, resources y prompts
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

mcp = FastMCP(name="Clockify")

@mcp.tool()
async def get_active_workspaces():
    # llamar al método de clokify que lo haga para obtener los espacios de trabajo activos



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