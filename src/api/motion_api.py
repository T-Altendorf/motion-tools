import jwt
import constants
import sys
import time
import requests
import os
from datetime import datetime, timedelta, timezone
import re
from collections import defaultdict
import pytz


class MotionAPI:
    def __init__(
        self,
        api_key,
        max_calls_per_minute=12,
        period_in_seconds=60,
        token_file_path="token.txt",
    ):
        self.api_key = api_key
        self.max_calls = max_calls_per_minute
        self.period = period_in_seconds
        self.request_count = 0
        self.last_request_time = time.time()
        self.token_file_path = token_file_path
        self.token = None
        self.token_url = constants.NEW_MOTION_TOKEN_URL
        self.load_token()

    def load_token(self):
        try:
            # Read the token from the file
            if not self.token:
                if not os.path.exists(self.token_file_path):
                    with open(self.token_file_path, "w") as file:
                        file.write("")  # Create an empty file if it doesn't exist yet
                with open(self.token_file_path, "r") as file:
                    self.token = file.read()
            if self.is_token_valid():
                return

            response = requests.get(
                self.token_url, params={"key": constants.NEW_MOTION_TOKEN_KEY}
            )
            response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code

            # Assuming the endpoint returns a JSON with an access_token field
            self.token = response.json().get("access_token", "")

            with open(self.token_file_path, "w") as file:
                file.write(self.token)
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
        except Exception as e:
            print(f"An error occurred: {e}")

    def is_token_valid(self):
        try:
            # Decode the token without verification - we're not checking the signature here
            payload = jwt.decode(self.token, options={"verify_signature": False})
            # Get the current time
            now = datetime.utcnow()
            # Get the expiration time from the token
            exp = datetime.utcfromtimestamp(payload["exp"])

            # Check if the current time is before the expiration time
            return now < exp
        except jwt.ExpiredSignatureError:
            # Token is expired
            return False
        except jwt.InvalidTokenError:
            # Token is invalid for some other reason
            return False
        except Exception as e:
            print(f"An error occurred during token validation: {e}")
            return False

    def refresh_token_if_invalid(self):
        if not self.is_token_valid():
            print("Refreshing token...")
            self.load_token()

    def _rate_limit(self):
        # Reset request count every period
        current_time = time.time()
        if current_time - self.last_request_time >= self.period:
            self.request_count = 0
            self.last_request_time = current_time

        # If request count is at limit, sleep until a period has passed since the last request
        while self.request_count >= self.max_calls:
            wait_time = self.period - (current_time - self.last_request_time)
            sys.stdout.write(
                f"\rRate limit reached, waiting for {wait_time:.2f} seconds..."
            )
            sys.stdout.flush()
            time.sleep(1)
            current_time = time.time()
            if current_time - self.last_request_time >= self.period:
                self.request_count = 0
                self.last_request_time = current_time

        # Clear the timer line
        sys.stdout.write("\r")
        sys.stdout.flush()

    def _request(
        self, method, endpoint, params=None, data=None, limit=None, direct_list=False
    ):
        """Make a request to the Motion API and return the response data
        Parameters:
            method (str): The HTTP method to use (e.g., "GET", "POST", "PATCH")
            endpoint (str): The API endpoint (e.g., "/tasks")
            params (dict): Query parameters to include in the request
            data (dict): Data to include in the request body
            limit (int): The maximum number of pages to fetch (default: None)
        Returns:
            list: A list of results from the API
        """
        self._rate_limit()  # Ensure compliance with rate limit before making a request

        url = f"https://api.usemotion.com/v1{endpoint}"
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        all_results = []
        page_count = 0

        while True:
            response = requests.request(
                method, url, headers=headers, params=params, json=data
            )
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)

            self.request_count += 1
            page_count += 1

            response_data = response.json()
            if method == "POST":
                all_results.append(response_data)
            else:
                if direct_list:
                    all_results.extend(response_data)
                else:
                    all_results.extend(response_data.get(endpoint.replace("/", ""), []))

            # Check for stopping conditions: no more results, or page limit reached (if specified)
            if not direct_list:
                next_cursor = response_data.get("meta", {}).get("nextCursor")
                if not next_cursor or (limit and page_count >= limit):
                    break

                # Update cursor parameter for the next request
                if params:
                    params["cursor"] = next_cursor
                else:
                    params = {"cursor": next_cursor}
            else:
                break

        if method == "POST":
            return all_results[0]
        else:
            return all_results

    def _request_internal(
        self, method, endpoint, params=None, data=None, return_keys=None
    ):
        self.refresh_token_if_invalid()

        url = f"https://internal.usemotion.com{endpoint}"
        headers = {"Authorization": "Bearer " + self.token}

        if data:
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"

        print(
            f"method: {method}, endpoint: {endpoint}, params: {params}, data: {data}, return_keys: {return_keys}"
        )
        try:
            response = requests.request(
                method, url, headers=headers, params=params, json=data
            )
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)
        except requests.exceptions.HTTPError as err:
            print(f"HTTP Error occurred: {err}")
            print(f"Response content: {response.content}")
            raise
        except requests.exceptions.RequestException as err:
            print(f"An error occurred: {err}")
            raise
        if return_keys:
            response_data = response.json()
            if isinstance(return_keys, str):
                return response_data.get(return_keys, [])
            return {key: response_data.get(key, []) for key in return_keys}
        return response.json()

    def get_projects(self, workspace_id):
        endpoint = "/projects"
        params = {"workspaceId": workspace_id}
        return self._request("GET", endpoint, params)

    def get_project_id(self, workspace_id, project_name):
        projects = self.get_projects(workspace_id)
        for project in projects:
            if project["name"].lower() == project_name.lower():
                return project["id"]
        return None  # Return None if no matching project is found

    def get_workspaces(self):
        endpoint = "/workspaces"
        return self._request("GET", endpoint)

    def get_workspace_id(self, workspace_name):
        workspaces = self.get_workspaces()
        for workspace in workspaces:
            if workspace["name"].lower() == workspace_name.lower():
                return workspace["id"]
        return None  # Return None if no matching workspace is found

    def get_tasks_in_project(self, project_id):
        params = {"projectId": project_id}
        response = self.get_tasks_legacy(params)
        return response

    def get_schedules(self, params=None):
        endpoint = "/schedules"
        response = self._request("GET", endpoint, params, direct_list=True)
        return response

    def get_scheduled_tasks(self, return_keys=["tasks"], params=None):
        endpoint = "/personal_tasks/scheduled_tasks"
        print(f"endpoint: {endpoint}, params: {params}, return_keys: {return_keys}")
        response = self._request_internal("GET", endpoint, params, None, return_keys)

        if len(return_keys) == 1:
            return response[return_keys[0]]
        elif len(return_keys) == 2:
            return response[return_keys[0]], response[return_keys[1]]
        elif len(return_keys) == 3:
            return (
                response[return_keys[0]],
                response[return_keys[1]],
                response[return_keys[2]],
            )
        else:
            raise ValueError("Invalid number of return keys. Must be 1 to 3.")

    def get_scheduled_projects(self, params=None):
        endpoint = "/personal_tasks/scheduled_tasks"
        response = self._request_internal(
            "GET", endpoint, params, return_keys="projects"
        )
        return response

    def get_tasks_new(self, params=None, limit=None):
        tasks, projects = self.get_scheduled_tasks(["tasks", "projects"], params)
        for task in tasks:
            project_id = task.get("projectId")
            if project_id:
                project = next((p for p in projects if p["id"] == project_id), None)
                if project:
                    task["project"] = project
            else:
                task["project"] = None

            if task.get("chunks"):
                for chunk in task["chunks"]:
                    tasks.append(chunk)

        return tasks

    def get_tasks_legacy(self, params=None, limit=None):
        endpoint = "/tasks"
        response = self._request("GET", endpoint, params, limit=limit)
        return response

    def get_tasks(self, params=None, limit=None):
        return self.get_tasks_legacy(params, limit)

    def get_tasks_by_date_range(self, start_date, end_date):
        tasks = self.get_tasks(limit=10)

        start_date = start_date.replace(tzinfo=timezone.utc)
        end_date = end_date.replace(tzinfo=timezone.utc)
        scheduled_tasks = [
            task
            for task in tasks
            if "scheduledStart" in task and task["scheduledStart"] is not None
        ]
        filtered_tasks = [
            task
            for task in scheduled_tasks
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
        task_data = {"workspaceId": workspace_id, **task}  # Merge with other task data

        return self._request("POST", endpoint, data=task_data)

    def update_task(self, task, internal=False):
        task_id = task["id"]
        endpoint = f"/tasks/{task_id}"
        if internal:
            endpoint = f"/team_tasks/{task_id}"
            return self._request_internal("PATCH", endpoint, data=task)
        return self._request("PATCH", endpoint, data=task)

    def update_tasks_if_duration_exceeds(
        self, workspace_name, project_name, duration_limit
    ):
        # Step 1: Get workspace ID
        workspace_id = self.get_workspace_id(workspace_name)
        if workspace_id is None:
            print(f"Workspace with name {workspace_name} not found.")
            return

        # Step 2: Get project ID
        project_id = self.get_project_id(workspace_id, project_name)
        if project_id is None:
            print(f"Project with name {project_name} not found.")
            return

        # Step 3: Get all tasks for the project ID
        tasks = self.get_tasks_in_project(project_id)

        # Step 4: Iterate over tasks to find ones with duration over 90 minutes
        for task in tasks:
            duration = task.get(
                "duration"
            )  # Assuming the duration is in minutes and available as 'duration'
            if duration and duration >= duration_limit:
                # Step 5: Update the task if duration is higher than 90 minutes
                task_update = {
                    "id": task["id"],
                    "isChunkedTask": True,
                    "minimumDuration": 45,
                    "workspaceId": workspace_id,
                }
                try:
                    self.update_task(task_update, True)
                    print(f"Task {task['id']} updated to allow chunking.")
                except Exception as e:
                    print(f"Failed to update task {task['id']}: {e}")

    def reschedule_tasks_by_week(
        self,
        project_id,
        start_date,
        end_date,
        schedule=None,
        no_reschedule_patterns=None,
    ):
        tasks = self.get_tasks_in_project(project_id)
        week_tasks = defaultdict(list)
        week_pattern = re.compile(r"^[A-Z]{3,4}-W(\d+):")

        for task in tasks:
            if not task.get("completed", False):
                # Check if any no_reschedule_pattern is in the task's name or description
                if any(
                    pattern in task.get("name", "")
                    for pattern in no_reschedule_patterns
                ):
                    continue  # Skip this task
                match = week_pattern.match(task["name"])
                if match:
                    week_number = int(match.group(1))
                    week_tasks[week_number].append(task)

        if not week_tasks:
            print("No uncompleted tasks found with the specified pattern.")
            return

        sorted_weeks = sorted(week_tasks.keys())
        num_weeks = len(sorted_weeks)

        # Determine the total number of available schedule days
        total_days = sum(
            1 for _ in self.generate_schedule_days(start_date, end_date, schedule)
        )

        # Calculate days per week
        days_per_week = total_days / num_weeks if num_weeks else 0
        if schedule is not None:
            timezone_str = schedule.get(
                "timezone", "UTC"
            )  # Default to UTC if timezone is not specified
        else:
            timezone_str = "UTC"
        timezone = pytz.timezone(timezone_str)

        # Assign new scheduled dates to tasks
        for i, week in enumerate(sorted_weeks):
            deadline_day = self.calculate_week_deadline(
                start_date, days_per_week * (i + 1), schedule
            )
            for task in week_tasks[week]:
                # Convert deadline_day to the specified timezone
                deadline_day_with_tz = deadline_day.replace(tzinfo=pytz.utc).astimezone(
                    timezone
                )

                # Set the deadline to 23:59 in the specified timezone
                deadline_day_with_tz = deadline_day_with_tz.replace(
                    hour=23, minute=59, second=0, microsecond=0
                )
                data = {
                    "id": task["id"],
                    "startDate": start_date.isoformat(),
                    "dueDate": deadline_day_with_tz.isoformat(),
                }
                self.update_task(data, True)

    def generate_schedule_days(self, start_date, end_date, schedule=None):
        current_date = start_date
        while current_date <= end_date:
            if (
                schedule is None
                or current_date.strftime("%A").lower() in schedule["schedule"]
            ):
                yield current_date
            current_date += timedelta(days=1)

    def calculate_week_deadline(self, start_date, days_to_add, schedule=None):
        current_date = start_date
        days_added = 0
        while days_added < days_to_add:
            if (
                schedule is None
                or current_date.strftime("%A").lower() in schedule["schedule"]
            ):
                days_added += 1
            current_date += timedelta(days=1)
        return current_date - timedelta(days=1)
