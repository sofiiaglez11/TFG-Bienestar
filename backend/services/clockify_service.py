import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import sys

load_dotenv()

class ClockifyService:

    def __init__(self, api_key: str = None, workspace_id: str = None):
        self.api_key = api_key or os.getenv("CLOCKIFY_API_KEY")
        self.base_url = "https://api.clockify.me/api/v1"
        self.headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key or ""
        }
        self._workspace_id = workspace_id
        self._current_workspace = None

    def get_workspaces(self):
        """Devuelve la lista de espacios de trabajo del usuario autenticado."""
        url = f"{self.base_url}/workspaces"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    def get_current_workspace_id(self):
        """Helper para obtener el workspace_id por defecto."""
        if self._workspace_id:
            return self._workspace_id
        workspaces = self.get_workspaces()
        if workspaces:
            self._workspace_id = workspaces[0].get('id')
            return self._workspace_id
        else:
            raise ValueError("No hay workspaces disponibles para el usuario en Clockify.")

    def _set_workspace_if_null(self, workspace_id):
        """Asegura que siempre tengamos un ID de workspace."""
        if workspace_id is None:
            return self.get_current_workspace_id()
        return workspace_id
    
    def set_current_workspace(self, workspace_id):
        """Cambia el workspace actual al especificado si existe entre los disponibles."""
        workspaces = self.get_workspaces()
        if any(ws.get('id') == workspace_id for ws in workspaces):
            self._workspace_id = workspace_id
            return f"Workspace actual cambiado a: {workspace_id}"
        else:
            return "ID de workspace no encontrado entre los workspaces disponibles."

    ############################################################################
    # METHODS FOR PROJECTS
 
    def get_projects(self, workspace_id=None):
        workspace_id = self._set_workspace_if_null(workspace_id)
        url = f"{self.base_url}/workspaces/{workspace_id}/projects" 
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    def add_new_project(self, project_name, workspace_id=None):
        workspace_id = self._set_workspace_if_null(workspace_id)
        url = f"{self.base_url}/workspaces/{workspace_id}/projects"
        payload = {
            "name": project_name,
            "color": "#000000" 
        }
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        return response.json()

    ############################################################################
    # METHODS FOR TASKS
 
    def get_tasks(self, project_id: str, workspace_id: str = None) -> list:
        workspace_id = self._set_workspace_if_null(workspace_id)
        url = f"{self.base_url}/workspaces/{workspace_id}/projects/{project_id}/tasks"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def add_new_task(self, project_id: str, task_name: str, workspace_id: str = None) -> dict:
        workspace_id = self._set_workspace_if_null(workspace_id)
        url = f"{self.base_url}/workspaces/{workspace_id}/projects/{project_id}/tasks"
        payload = {"name": task_name}
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_task_by_id(self, project_id: str, task_id: str, workspace_id: str = None) -> dict:
        workspace_id = self._set_workspace_if_null(workspace_id)
        url = f"{self.base_url}/workspaces/{workspace_id}/projects/{project_id}/tasks/{task_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    ############################################################################
    # METHODS FOR TIME ENTRIES
 
    def get_time_entries(self, workspace_id: str = None, days_back: int = 7) -> list:
        workspace_id = self._set_workspace_if_null(workspace_id)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days_back)
 
        url = f"{self.base_url}/workspaces/{workspace_id}/user/{self.get_user_id()}/time-entries"
        params = {
            "start": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "page-size": 50
        }
 
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        
        entries = response.json()
        simplified_entries = []
        for entry in entries:
            simplified_entries.append({
                "description": entry.get("description", "Sin descripción"),
                "start": entry.get("timeInterval", {}).get("start"),
                "end": entry.get("timeInterval", {}).get("end"),
                "duration": entry.get("timeInterval", {}).get("duration")
            })
        return simplified_entries

    def create_time_entry(self, description: str, project_id: str = None, task_id: str = None,
                          start_time: str = None, end_time: str = None, workspace_id: str = None) -> dict:

        # print(f"CREATE TIME ENTRY -> DESCRIPTION: {description}, PROJECT ID: {project_id}, TASK ID: {task_id}, START TIME: {start_time}, END TIME: {end_time}", file=sys.stderr, flush=True)
        workspace_id = self._set_workspace_if_null(workspace_id)
        url = f"{self.base_url}/workspaces/{workspace_id}/time-entries"

        if not start_time:
            start_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = {
            "description": description,
            "start": start_time
        }
        if project_id:
            payload["projectId"] = project_id
        if task_id:
            payload["taskId"] = task_id
        if end_time:
            payload["end"] = end_time

        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()



    def stop_time_entry(self, time_entry_id: str = None, workspace_id: str = None) -> dict:
        """Para el timer activo del usuario en Clockify."""
        workspace_id = self._set_workspace_if_null(workspace_id)
        user_id = self.get_user_id()
        url = f"{self.base_url}/workspaces/{workspace_id}/user/{user_id}/time-entries"
        payload = {
            "end": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        response = requests.patch(url, headers=self.headers, json=payload)
        print(f"STOP TIME ENTRY RESPONSE: {response.status_code}", file=sys.stderr, flush=True)
        response.raise_for_status()
        return response.json()
        
    def get_active_time_entry(self) -> dict | None:
        """Devuelve el timer activo del usuario en Clockify, si hay uno."""
        user_id = self.get_user_id()
        workspace_id = self.get_current_workspace_id()
        url = f"{self.base_url}/workspaces/{workspace_id}/user/{user_id}/time-entries"
        params = {"in-progress": "true"}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        entries = response.json()
        return entries[0] if entries else None
    
    ############################################################################
    # METHODS FOR USERS
 
    def get_user_id(self) -> str:
        url = f"{self.base_url}/user"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json().get("id")