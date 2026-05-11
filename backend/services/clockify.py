import requests
import os
from dotenv import load_dotenv



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
    # METHODS FOR WORKSPACES

    def get_workspaces(self):
        """"Returns a list of workspaces for the authenticated user."""
        url = f"{self.base_url}/workspaces"
        
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()
        

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


    
# # main de prueba 
# if __name__ == "__main__":

#     service = ClockifyService()

#     workspaces = service.get_workspaces()
    
#     my_worskpace = workspaces[0]
#     my_worskpace_id = my_worskpace.get('id')
#     print(f"Workspace: {my_worskpace.get('name')}, ID: {my_worskpace.get('id')}")

#     nombre_proyecto = "Prueba TFG Bienestar2"
#     resultado = service.add_new_project(nombre_proyecto, my_worskpace_id)
#     print(resultado)

#     service.get_projects(my_worskpace.get('id'))