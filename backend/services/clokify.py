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
        """Obtiene la lista de workspaces del usuario."""
        url = f"{self.base_url}/workspaces"
        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                return response.json()
            else:
                return f"Error {response.status_code}: {response.text}"
        except Exception as e:
            return f"Error de conexión: {str(e)}"
        

    def _set_workspace_if_null(self, workspace_id):
        """Método interno para asegurar que siempre tengamos un ID de workspace."""
        if workspace_id is None:
            if self.current_workspace:
                return self.current_workspace.get('id')
            else:
                raise ValueError("No hay workspace especificado ni predeterminado.")
        return workspace_id
    
    def set_current_workspace(self, workspace_id):
        """Permite cambiar el workspace actual."""

        if any(ws.get('id') == workspace_id for ws in self.workspaces):
            self.current_workspace = next(ws for ws in self.workspaces if ws.get('id') == workspace_id)
            return f"Workspace actual cambiado a: {self.current_workspace.get('name')}"
        else:
            return "ID de workspace no encontrado entre los workspaces disponibles."


    ############################################################################
    # METHODS FOR PROJECTS

    def get_projects(self, workspace_id=None):
        """Obtiene la lista de proyectos de un workspace específico."""

        try:
            ws_id = self._set_workspace_if_null(workspace_id)
        except ValueError as e:
            return str(e)
        

        url = f"{self.base_url}/workspaces/{workspace_id}/projects"
        
        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                return response.json()
            else:
                return f"Error {response.status_code}: {response.text}"
        except Exception as e:
            return f"Error de conexión: {str(e)}"
        
    
    
        
    
    def add_new_project(self, project_name, workspace_id = None):
        """Agrega un nuevo proyecto a un workspace específico."""

        try:
            workspace_id = self._set_workspace_if_null(workspace_id)
        except ValueError as e:
            return str(e)

        


        url = f"{self.base_url}/workspaces/{workspace_id}/projects"
        payload = {
            "name": project_name,
            "color": "#000000"  # Puedes personalizar el color del proyecto
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)

            if response.status_code == 201:
                return response.json()
            else:
                return f"Error {response.status_code}: {response.text}"
        except Exception as e:
            return f"Error de conexión: {str(e)}"
        

    
# main de prueba 
if __name__ == "__main__":

    service = ClockifyService()

    workspaces = service.get_workspaces()
    
    my_worskpace = workspaces[0]
    my_worskpace_id = my_worskpace.get('id')
    print(f"Workspace: {my_worskpace.get('name')}, ID: {my_worskpace.get('id')}")

    nombre_proyecto = "Prueba TFG Bienestar2"
    resultado = service.add_new_project(my_worskpace_id, nombre_proyecto)
    print(resultado)

    service.get_projects(my_worskpace.get('id'))