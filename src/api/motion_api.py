import sys
import time
import requests
from datetime import datetime, timezone

class MotionAPI:
    def __init__(self, api_key, max_calls_per_minute=12, period_in_seconds=60, token_file_path="token.txt"):
        self.api_key = api_key
        self.max_calls = max_calls_per_minute
        self.period = period_in_seconds
        self.request_count = 0
        self.last_request_time = time.time()
        self.token_file_path = token_file_path
        self.token = None
        self.load_token()

    def load_token(self):
        try:
            with open(self.token_file_path, 'r') as file:
                self.token = file.read().strip()
        except FileNotFoundError:
            print(f"Token file not found: {self.token_file_path}")
        except Exception as e:
            print(f"An error occurred while loading the token: {e}")

    def _rate_limit(self):
        # Reset request count every period
        current_time = time.time()
        if current_time - self.last_request_time >= self.period:
            self.request_count = 0
            self.last_request_time = current_time

        # If request count is at limit, sleep until a period has passed since the last request
        while self.request_count >= self.max_calls:
            wait_time = self.period - (current_time - self.last_request_time)
            sys.stdout.write(f'\rRate limit reached, waiting for {wait_time:.2f} seconds...')
            sys.stdout.flush()
            time.sleep(1)
            current_time = time.time()
            if current_time - self.last_request_time >= self.period:
                self.request_count = 0
                self.last_request_time = current_time

        # Clear the timer line
        sys.stdout.write('\r')
        sys.stdout.flush()

    def _request(self, method, endpoint, params=None, data=None):
        self._rate_limit()  # Ensure compliance with rate limit before making a request

        url = f"https://api.usemotion.com/v1{endpoint}"
        headers = {"X-API-Key": self.api_key}

        if data:
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"

        response = requests.request(method, url, headers=headers, params=params, json=data)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)
        
        self.request_count += 1
        return response.json()
    
    def _request_internal(self, method, endpoint, params=None, data=None):
        self._rate_limit()  # Ensure compliance with rate limit before making a request

        url = f"https://internal.usemotion.com{endpoint}"
        headers = {"Authorization": "Bearer " + self.token}

        if data:
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"

        response = requests.request(method, url, headers=headers, params=params, json=data)
        print(response.json())
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)
        
        self.request_count += 1
        return response.json()

    def get_projects(self, workspace_id):
        endpoint = "/projects"
        params = {"workspaceId": workspace_id}
        return self._request("GET", endpoint, params)

    def get_project_id(self, workspace_id, project_name):
        projects = self.get_projects(workspace_id)
        for project in projects.get("projects", []):
            if project["name"].lower() == project_name.lower():
                return project["id"]
        return None  # Return None if no matching project is found


    def get_workspaces(self):
        endpoint = "/workspaces"
        return self._request("GET", endpoint)

    def get_workspace_id(self, workspace_name):
        workspaces = self.get_workspaces()
        for workspace in workspaces.get("workspaces", []):
            if workspace["name"].lower() == workspace_name.lower():
                return workspace["id"]
        return None  # Return None if no matching workspace is found
    
    def get_tasks_in_project(self, project_id):
        params = {"projectId": project_id}
        response = self.get_tasks(params)
        return response.get("tasks", [])
    
    def get_tasks(self, params=None):
        endpoint = "/tasks"
        response = self._request("GET", endpoint, params)
        return response.get("tasks", [])
    
    def get_tasks_by_date_range(self, start_date, end_date):
        tasks = self.get_tasks()
        for task in tasks:
            print(task["name"] + " " + str(task["scheduledStart"]))
        start_date = start_date.replace(tzinfo=timezone.utc)
        end_date = end_date.replace(tzinfo=timezone.utc)
        scheduled_tasks = [
            task for task in tasks
            if "scheduledStart" in task and task["scheduledStart"] is not None
        ]
        filtered_tasks = [
            task for task in scheduled_tasks
            if self.parse_date(task["scheduledStart"]) >= start_date
            and self.parse_date(task["scheduledStart"]) <= end_date
        ]
        return filtered_tasks
    
    def parse_date(self, date_string):
        # Assuming dueDate is in ISO 8601 format (e.g., "2023-09-28T16:46:48.821-06:00")
        try:
            # Convert to offset-aware datetime object in UTC
            dt = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc)
        except ValueError as e:
            print(f"Failed to parse date string {date_string}: {e}")
            return None  # or handle error as appropriate
    
    def create_task(self, task, workspace_id=None):
        endpoint = "/tasks"
        
        # Check if workspace_id is provided
        if workspace_id is None:
            if "workspaceId" in task:
                workspace_id = task["workspaceId"]
            else:
                raise ValueError("workspace_id is required but was not provided")
        
        # Prepare task_data by merging provided workspace_id with task data
        # If projectId is provided in task data, it will be included as well
        task_data = {
            "workspaceId": workspace_id,
            **task  # Merge with other task data
        }
        
        return self._request("POST", endpoint, data=task_data)
    
    def update_task(self, task, internal=False):
        task_id = task["id"]
        endpoint = f"/tasks/{task_id}"
        if internal:
            endpoint = f"/team_tasks/{task_id}"
            return self._request_internal("PATCH", endpoint, data=task)
        return self._request("PATCH", endpoint, data=task)