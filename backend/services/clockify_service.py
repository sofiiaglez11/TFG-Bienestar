from asyncio import timeouts
import requests
import httpx
from datetime import datetime, timedelta, timezone
import sys

class ClockifyService:

    def __init__(self, api_key: str = None, workspace_id: str = None):
        self.api_key = api_key
        self.base_url = "https://api.clockify.me/api/v1"
        self.headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key or ""
        }
        self._workspace_id = workspace_id
        self._current_workspace = None
        self._cached_user_id = None  # evita llamadas repetidas a /user

    @staticmethod
    async def validate_api_key(api_key: str) -> dict:
        """
        Valida una API Key contra el endpoint /user de Clockify.
        Devuelve los datos del usuario (id, name, defaultWorkspace) si es válida.
        Lanza ValueError si la clave es inválida o hay error de red.
        """
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                response = await client.get(
                    "https://api.clockify.me/api/v1/user",
                    headers={"X-Api-Key": api_key}
                )
            except httpx.RequestError as exc:
                raise ValueError(f"No se pudo conectar con Clockify: {exc}")

        if response.status_code == 401:
            raise ValueError(
                "La API Key introducida no es válida. "
                "Compruébala en tu perfil de Clockify."
            )
        if response.status_code != 200:
            raise ValueError(
                f"Error inesperado al conectar con Clockify (código {response.status_code})."
            )

        return response.json()  # contiene id, name, defaultWorkspace, etc.

    ############################################################################
    # METHODS FOR WORKSPACES
         

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
            "name": project_name
        }
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def delete_project(self, project_id: str, workspace_id: str = None) -> dict:
        """Elimina un proyecto de Clockify por su ID."""
        if not project_id:
            return {}
        workspace_id = self._set_workspace_if_null(workspace_id)
        url = f"{self.base_url}/workspaces/{workspace_id}/projects/{project_id}"
        response = requests.delete(url, headers=self.headers)

        print(f"[DELETE PROJECT RESPONSE]: {response.status_code} \t {response.content}", file=sys.stderr, flush=True)

        if response.status_code == 404:
            return {}
        response.raise_for_status()


        return response.json() if response.content else {}

    def archive_project(self, project_id: str, workspace_id: str = None) -> dict:
        """Archiva un proyecto de Clockify (lo oculta sin borrarlo).
        Funciona en todos los planes, incluido el gratuito.
        """
        if not project_id:
            return {}
        workspace_id = self._set_workspace_if_null(workspace_id)
        url = f"{self.base_url}/workspaces/{workspace_id}/projects/{project_id}"
        
        get_response = requests.get(url, headers=self.headers)
        if get_response.status_code == 404:
            return {}
        get_response.raise_for_status()
        current_name = get_response.json().get("name", "")

        payload = {"name": current_name, "archived": True}
        response = requests.put(url, json=payload, headers=self.headers)
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        return response.json() if response.content else {}

    def unarchive_project(self, project_id: str, workspace_id: str = None) -> dict:
        """Desarchiva un proyecto de Clockify (lo vuelve a mostrar como activo)."""
        if not project_id:
            return {}
        workspace_id = self._set_workspace_if_null(workspace_id)
        url = f"{self.base_url}/workspaces/{workspace_id}/projects/{project_id}"

        get_response = requests.get(url, headers=self.headers)
        if get_response.status_code == 404:
            return {}
        get_response.raise_for_status()
        current_name = get_response.json().get("name", "")

        payload = {"name": current_name, "archived": False}
        response = requests.put(url, json=payload, headers=self.headers)
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        return response.json() if response.content else {}


    def update_project(self, project_id: str, new_name: str = None, note: str = None, is_archived: bool = None, workspace_id: str = None) -> dict:
        """Actualiza el nombre de un proyecto de Clockify por su ID."""
        if not project_id:
            return {}
        workspace_id = self._set_workspace_if_null(workspace_id)
        url = f"{self.base_url}/workspaces/{workspace_id}/projects/{project_id}"

        payload = {}
        if new_name:
            payload["name"] = new_name
        if note:
            payload["note"] = note
        if is_archived:
            payload["archived"] = is_archived

        response = requests.put(url, json=payload, headers=self.headers)
        print(f"UPDATE PROJECT RESPONSE: {response.status_code} \n {response.content}", file=sys.stderr, flush=True)
        response.raise_for_status()
        return response.json() if response.content else {}

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

    # def update_task(self, project_id: str, task_id: str, new_name: str = None, note: str = None, is_archived: bool = None, workspace_id: str = None) -> dict:
    #     """Actualiza una tarea de Clockify por su ID."""
    #     if not task_id:
    #         return {}
    #     workspace_id = self._set_workspace_if_null(workspace_id)
    #     url = f"{self.base_url}/workspaces/{workspace_id}/projects/{project_id}/tasks/{task_id}"

    #     payload = {}
    #     if new_name:
    #         payload["name"] = new_name
    #     if note:
    #         payload["note"] = note
    #     if is_archived:
    #         payload["archived"] = is_archived

    #     response = requests.put(url, json=payload, headers=self.headers)
    #     print(f"UPDATE TASK RESPONSE: {response.status_code} \n {response.content}", file=sys.stderr, flush=True)
    #     response.raise_for_status()
    #     return response.json() if response.content else {}


    def update_task(self, project_id: str, task_id: str,
                new_name: str = None, status: str = None,
                workspace_id: str = None) -> dict:
        """Actualiza nombre y/o status de una tarea de Clockify.
        status puede ser 'ACTIVE' o 'DONE'.
        """
        if not task_id:
            return {}
        workspace_id = self._set_workspace_if_null(workspace_id)
        url = f"{self.base_url}/workspaces/{workspace_id}/projects/{project_id}/tasks/{task_id}"

        payload = {}
        if new_name:
            payload["name"] = new_name
        if status:
            payload["status"] = status  # "ACTIVE" o "DONE"

        if not payload:
            return {}

        response = requests.put(url, json=payload, headers=self.headers)
        print(f"[UPDATE TASK RESPONSE]: {response.status_code} \t {payload} \t {response.content}", file=sys.stderr, flush=True)
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        return response.json() if response.content else {}

    # def delete_task(self, project_id: str, task_id: str, workspace_id: str = None) -> bool:
    #     """
    #     Elimina una tarea de Clockify.
    #     Clockify no permite borrar tareas en estado ACTIVE, así que primero
    #     las marca como DONE y luego hace el DELETE.
    #     Devuelve True si se borró correctamente, False en cualquier otro caso.
    #     """
    #     if not task_id:
    #         return False
    #     workspace_id = self._set_workspace_if_null(workspace_id)  

    #     # 1. Marcar como DONE para que Clockify permita el borrado
    #     self.update_task(
    #         project_id=project_id,
    #         task_id=task_id,
    #         status="DONE",
    #         workspace_id=workspace_id
    #     )

    #     # 2. Borrar la tarea
    #     url = f"{self.base_url}/workspaces/{workspace_id}/projects/{project_id}/tasks/{task_id}"
    #     print(f"[DELETE TASK] DELETE {url}", file=sys.stderr, flush=True)
    #     response = requests.delete(url, headers=self.headers)
    #     print(
    #         f"[DELETE TASK RESPONSE]: status={response.status_code} body={response.text[:300]}",
    #         file=sys.stderr, flush=True
    #     )
    #     return response.status_code in (200, 204)


    def delete_task(self, project_id: str, task_id: str, task_name: str, workspace_id: str = None) -> bool:
        """Elimina una tarea de Clockify por su ID, eliminando antes sus tiempos y marcándola como DONE"""

        if not task_id:
            return False

        workspace_id = self._set_workspace_if_null(workspace_id)

        # 1. Eliminar todas las entradas de tiempo asociadas a la tarea
        try: 
            self.delete_time_entries_for_task(project_id=project_id, task_id=task_id, workspace_id=workspace_id)
        except Exception as e:
            print(f"[ERROR] Al eliminar entradas de tiempo para la tarea {task_id}: {e}", file=sys.stderr, flush=True)
            return False

        # 2. Marcar la tarea como DONE para permitir su borrado
        try: 
            if not task_name:
                try: 
                    task_info = self.get_task_by_id(project_id=project_id, task_id=task_id, workspace_id=workspace_id)
                    task_name = task_info.get("name")
                except Exception as e:
                    print(f"[ERROR] Al obtener el nombre de la tarea {task_id}: {e}", file=sys.stderr, flush=True)
                    task_name = "Tarea"


            self.update_task(project_id=project_id, task_id=task_id, new_name=task_name, status="DONE", workspace_id=workspace_id)

        except Exception as e:
            print(f"[ERROR] Al marcar la tarea {task_id} como DONE: {e}", file=sys.stderr, flush=True)
            return False

        # 3. Borrar la tarea enviando DELETE
        url = f"{self.base_url}/workspaces/{workspace_id}/projects/{project_id}/tasks/{task_id}"
        response = requests.delete(url, headers=self.headers)
        print(f"[DELETE TASK RESPONSE]: {response.status_code} \t {response.content}",
                file=sys.stderr, flush=True)

        if response.status_code == 404:
            return False
        response.raise_for_status()

        return response.json() if response.content else {}


        


                
    ############################################################################
    # METHODS FOR TIME ENTRIES
 
    def get_time_entries(self, workspace_id: str = None, days_back: int = None,
                         start_date=None, end_date=None) -> list:
        workspace_id = self._set_workspace_if_null(workspace_id)

        if start_date or end_date:
            if not start_date:
                start_dt = datetime.now(timezone.utc) - timedelta(days=365)
            elif isinstance(start_date, str):
                if 'T' not in start_date:
                    start_dt = datetime.fromisoformat(f"{start_date}T00:00:00+00:00")
                else:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            else:
                start_dt = start_date

            if not end_date:
                end_dt = datetime.now(timezone.utc) + timedelta(days=7)
            elif isinstance(end_date, str):
                if 'T' not in end_date:
                    end_dt = datetime.fromisoformat(f"{end_date}T23:59:59+00:00")
                else:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            else:
                end_dt = end_date
        else:
            days = days_back if days_back is not None else 365
            end_dt = datetime.now(timezone.utc) + timedelta(days=7)
            start_dt = datetime.now(timezone.utc) - timedelta(days=days)

        user_id = self.get_user_id()
        url = f"{self.base_url}/workspaces/{workspace_id}/user/{user_id}/time-entries"
        
        start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        base_params = {
            "start": start_str,
            "end": end_str,
            "page-size": 200,
        }

        print(f"[CLOCKIFY SERVICE: GET_TIME_ENTRIES] User ID: {user_id} | Workspace ID: {workspace_id}", file=sys.stderr, flush=True)
        print(f"[CLOCKIFY SERVICE: GET_TIME_ENTRIES] Rango fechas enviado a Clockify -> start: {start_str} | end: {end_str} (days_back={days_back})", file=sys.stderr, flush=True)

        all_entries = []
        page = 1
        while True:
            params = {**base_params, "page": page}
            print(f"[CLOCKIFY SERVICE: GET_TIME_ENTRIES] Peticion GET {url} params={params}", file=sys.stderr, flush=True)
            response = requests.get(url, headers=self.headers, params=params)
            print(f"[CLOCKIFY SERVICE: GET_TIME_ENTRIES] Response status={response.status_code}", file=sys.stderr, flush=True)
            response.raise_for_status()
            page_entries = response.json()
            print(f"[CLOCKIFY SERVICE: GET_TIME_ENTRIES] Entradas en pagina {page}: {len(page_entries)}", file=sys.stderr, flush=True)

            if not page_entries:
                break
            for entry in page_entries:
                item = {
                    "id": entry.get("id"),
                    "description": entry.get("description", "Sin descripción"),
                    "start": entry.get("timeInterval", {}).get("start"),
                    "end": entry.get("timeInterval", {}).get("end"),
                    "duration": entry.get("timeInterval", {}).get("duration"),
                    "projectId": entry.get("projectId"),
                    "taskId": entry.get("taskId"),
                }
                print(f"   -> [ENTRY] ID={item['id']} | Start={item['start']} | End={item['end']} | ProjectID={item['projectId']} | TaskID={item['taskId']} | Desc='{item['description']}'", file=sys.stderr, flush=True)
                all_entries.append(item)
            if len(page_entries) < 200:
                break  # última página
            page += 1

        print(f"[CLOCKIFY SERVICE: GET_TIME_ENTRIES] Total entradas finales devueltas: {len(all_entries)}", file=sys.stderr, flush=True)
        return all_entries

    def get_time_entry(self, time_entry_id: str, workspace_id: str = None) -> dict:
        """Devuelve los detalles de una entrada de tiempo específica por su ID."""
        if not time_entry_id:
            return {}
        workspace_id = self._set_workspace_if_null(workspace_id)
        url = f"{self.base_url}/workspaces/{workspace_id}/time-entries/{time_entry_id}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        return response.json() if response.content else {}

    def create_time_entry(self, description: str, project_id: str = None, task_id: str = None,
                          start_time: str = None, end_time: str = None, workspace_id: str = None) -> dict:

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

        print(f"[CLOCKIFY SERVICE: CREATE_TIME_ENTRY] POST {url} | Payload: {payload}", file=sys.stderr, flush=True)
        response = requests.post(url, headers=self.headers, json=payload)
        print(f"[CLOCKIFY SERVICE: CREATE_TIME_ENTRY] Status: {response.status_code} | Response: {response.content[:300]}", file=sys.stderr, flush=True)
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


    def delete_time_entry(self, time_entry_id: str, workspace_id: str = None) -> dict:
        """Elimina una entrada de tiempo de Clockify por su ID."""

        if not time_entry_id:
            raise ValueError("Se requiere un ID de entrada de tiempo para eliminarla.")
        workspace_id = self._set_workspace_if_null(workspace_id)

        url = f"{self.base_url}/workspaces/{workspace_id}/time-entries/{time_entry_id}"

        response = requests.delete(url, headers=self.headers)
        print(f"[DELETE TIME ENTRY RESPONSE]: {response.status_code} \t {response.content}", file=sys.stderr, flush=True)

        if response.status_code == 404:
            return {}
        response.raise_for_status()
        return response.json() if response.content else {"deleted_id": time_entry_id, "success": True}

    def delete_time_entries_for_task(self, project_id: str, task_id: str, workspace_id: str = None) -> dict:
        """"Busca y elimina todas las entradas de tiempo asociadas a una tarea en Clockify"""

        if not task_id:
            raise ValueError("Se requiere un ID de tarea para eliminar sus entradas de tiempo.")
        workspace_id = self._set_workspace_if_null(workspace_id)
        user_id = self.get_user_id()
        url = f"{self.base_url}/workspaces/{workspace_id}/user/{user_id}/time-entries"
        params = {"page-size": 200}
        deleted_count = 0

        try: 
            res = requests.get(url, headers=self.headers, params=params)
            if res.ok:
                for entry in res.json():
                    entry_task_id = entry.get("taskId") or (entry.get("task") and entry["task"].get("id"))
                    if entry_task_id == task_id:
                        entry_id = entry.get("id")
                        if entry_id:
                            self.delete_time_entry(entry_id, workspace_id)
                            deleted_count += 1
            return {"deleted_count": deleted_count}
        except Exception as e:
            print(f"[ERROR] Al eliminar entradas de tiempo para la tarea {task_id}: {e}", file=sys.stderr, flush=True)
            return {"deleted_count": deleted_count, "error": str(e)}

    def update_time_entry(self, time_entry_id: str, description: str = None, project_id: str = None,
                          task_id: str = None, start_time: str = None, end_time: str = None, workspace_id: str = None) -> dict:
        """Actualiza una entrada de tiempo de Clockify por su ID, preservando los datos requeridos."""
        if not time_entry_id:
            raise ValueError("Se requiere un ID de entrada de tiempo para actualizarla.")
        workspace_id = self._set_workspace_if_null(workspace_id)

        try:
            # Obtener datos existentes para rellenar campos obligatorios que Clockify exige en PUT
            existing = self.get_time_entry(time_entry_id, workspace_id=workspace_id)
            existing_interval = existing.get("timeInterval", {}) if existing else {}

            start = start_time or existing_interval.get("start")
            if not start:
                raise ValueError(f"No se pudo determinar el parámetro 'start' para la entrada {time_entry_id}.")

            payload = {
                "start": start,
                "description": description if description is not None else existing.get("description", ""),
                "billable": existing.get("billable", False) if existing else False
            }

            p_id = project_id if project_id is not None else existing.get("projectId")
            if p_id:
                payload["projectId"] = p_id

            t_id = task_id if task_id is not None else existing.get("taskId")
            if t_id:
                payload["taskId"] = t_id

            e_time = end_time if end_time is not None else existing_interval.get("end")
            if e_time:
                payload["end"] = e_time

            url = f"{self.base_url}/workspaces/{workspace_id}/time-entries/{time_entry_id}"
            response = requests.put(url, headers=self.headers, json=payload)
            print(f"[UPDATE TIME ENTRY RESPONSE]: status={response.status_code} payload={payload}", file=sys.stderr, flush=True)
            response.raise_for_status()
            return response.json() if response.content else {}
        except Exception as e:
            print(f"[ERROR] Al actualizar la entrada de tiempo {time_entry_id}: {e}", file=sys.stderr, flush=True)
            return {"error": str(e)}

    ############################################################################
    # METHODS FOR USERS
 
    def get_user_id(self) -> str:
        """Devuelve el ID del usuario autenticado. Usa caché para evitar llamadas repetidas."""
        if self._cached_user_id:
            return self._cached_user_id
        url = f"{self.base_url}/user"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        self._cached_user_id = response.json().get("id")
        return self._cached_user_id