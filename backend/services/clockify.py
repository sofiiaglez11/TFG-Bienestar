import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
 
 
# Cargamos las variables del archivo .env que creamos en la raíz
load_dotenv()
 
class ClockifyService:
 
    # Constructor to initialize the service with API key and base URL
    def __init__(self):
        self.api_key = os.getenv("CLOCKIFY_API_KEY")
        self.base_url = "https://api.clockify.me/api/v1"
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
        self.workspaces = self.get_workspaces() # TODO ver si esto es necesario o lo hacemos cada vez que se necesite, para no hacer llamadas innecesarias a la API
        self.current_workspace = self.workspaces[0] if self.workspaces else None
 
    ############################################################################
    # METHODS FOR WORKSPACES -> NOTE: no los estoy usando
 
    def get_workspaces(self):
        """"Returns a list of workspaces for the authenticated user."""
        url = f"{self.base_url}/workspaces"
        
        response = requests.get(url, headers=self.headers)
 
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()
    
    def get_current_workspace_id(self):
        """"Helper method to get the default workspace ID, which is the first one in the list of workspaces."""
        if self.current_workspace:
            return self.current_workspace.get('id')
        else:
            raise ValueError("No hay workspaces disponibles para el usuario.")
        
 
    def _set_workspace_if_null(self, workspace_id):
        """"Private mehod to ensure we always have a workspace ID."""
 
        if workspace_id is None:
            if self.current_workspace:
                return self.current_workspace.get('id')
            else:
                raise ValueError("No hay workspace especificado ni predeterminado.")
        return workspace_id
    
    def set_current_workspace(self, workspace_id):
        """Changes the current workspace to the one specified by workspace_id, if it exists in the list of available workspaces."""
 
        if any(ws.get('id') == workspace_id for ws in self.workspaces):
            self.current_workspace = next(ws for ws in self.workspaces if ws.get('id') == workspace_id)
            return f"Workspace actual cambiado a: {self.current_workspace.get('name')}"
        else:
            return "ID de workspace no encontrado entre los workspaces disponibles."
 
 
    ############################################################################
    # METHODS FOR PROJECTS
 
    def get_projects(self, workspace_id=None):
        """"Returns a list of projects for a given workspace ID. If no workspace ID is provided, it uses the current workspace."""
 
        
        workspace_id = self._set_workspace_if_null(workspace_id)
        
 
        url = f"{self.base_url}/workspaces/{workspace_id}/projects" 
        response = requests.get(url, headers=self.headers)
 
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()
        
    
 
    
    def add_new_project(self, project_name, workspace_id = None): #TODO ver si le añado el color como parámetro opcional (no lo considero importante)
        """"Creates a new project in the specified workspace. If no workspace ID is provided, it uses the current workspace."""
 
        workspace_id = self._set_workspace_if_null(workspace_id)
 
        url = f"{self.base_url}/workspaces/{workspace_id}/projects"
        payload = {
            "name": project_name,
            "color": "#000000" 
        }
 
         
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    
 
    ############################################################################
    # METHODS FOR TASKS
    def get_tasks(self, project_id: str, workspace_id: str = None) -> list:
        """
        Retrieves tasks for a given project in a specified workspace.
        If no workspace ID is provided, it uses the current workspace.
        """
        workspace_id = self._set_workspace_if_null(workspace_id)
 
        url = f"{self.base_url}/workspaces/{workspace_id}/projects/{project_id}/tasks"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def add_new_task(self, project_id: str, task_name: str, workspace_id: str = None) -> dict:
        """
        Creates a new task in the specified project and workspace.
        If no workspace ID is provided, it uses the current workspace.
        """
        workspace_id = self._set_workspace_if_null(workspace_id)
 
        url = f"{self.base_url}/workspaces/{workspace_id}/projects/{project_id}/tasks"
        payload = {
            "name": task_name
        }
 
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    
    def get_task_by_id(self, project_id: str, task_id: str, workspace_id: str = None) -> dict:
        """
        Retrieves a specific task by its ID within a given project and workspace.
        If no workspace ID is provided, it uses the current workspace.
        """
        workspace_id = self._set_workspace_if_null(workspace_id)
 
        url = f"{self.base_url}/workspaces/{workspace_id}/projects/{project_id}/tasks/{task_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
 
 
 
    ############################################################################
    # METHODS FOR TIME ENTRIES
 
    def get_time_entries(self, workspace_id: str = None, days_back: int = 7) -> list:
        """
        Retrieves time entries from the specified workspace for the last X days.
        """
        if not workspace_id:
            workspace_id = self.get_current_workspace_id()
 
        # Calculate start and end times in ISO format (required by Clockify)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days_back)
 
        url = f"{self.base_url}/workspaces/{workspace_id}/user/{self.get_user_id()}/time-entries"
        
        # Query parameters to filter by date
        params = {
            "start": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "page-size": 50 # Retrieve up to 50 entries
        }
 
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        
        # We parse the response to extract only what's useful for the AI
        entries = response.json()
        simplified_entries = []
        
        for entry in entries:
            simplified_entries.append({
                "description": entry.get("description", "No description"),
                "start": entry.get("timeInterval", {}).get("start"),
                "end": entry.get("timeInterval", {}).get("end"),
                "duration": entry.get("timeInterval", {}).get("duration")
            })
            
        return simplified_entries
    
    
 
    def create_time_entry(self, description: str, project_id: str = None, task_id: str = None,
                          start_time: str = None, end_time: str = None, workspace_id: str = None) -> dict:
        """
        Creates a new time entry in Clockify. If start_time is None, starts right now.
        If end_time is None, it starts a running timer (no end).
        """
        # 🐛 FIX: antes se llamaba a self._set_workspace_if_null() sin pasar workspace_id,
        # así que el workspace que le pasaras aquí se ignoraba siempre.
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
 
    def stop_time_entry(self, time_entry_id: str, workspace_id: str = None) -> dict:
        """
        Detiene un cronómetro en marcha, fijando su hora de fin a este momento.
        Clockify no tiene un endpoint "stop" dedicado: se actualiza la entrada con PATCH.
        """
        workspace_id = self._set_workspace_if_null(workspace_id)
 
        url = f"{self.base_url}/workspaces/{workspace_id}/time-entries/{time_entry_id}"
        payload = {
            "end": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }
 
        response = requests.patch(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()
    
    
 
 
    ############################################################################
    # METHODS FOR USERS
 
    def get_user_id(self) -> str:
        """
        Helper method to get the current user ID, needed for time entries.
        """
        url = f"{self.base_url}/user"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json().get("id")
 
