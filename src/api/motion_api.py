import os
import jwt
import constants
import sys
import time
import requests
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
        if not self.token:
            return False
        try:
            # Read the token from disk if it exists
            if not self.token and os.path.exists(self.token_file_path):
                with open(self.token_file_path, "r") as file:
                    self.token = file.read()

            # If the file does not exist or the token is still empty, request a new one
            if not self.token:
                response = requests.get(
                    self.token_url, params={"key": constants.NEW_MOTION_TOKEN_KEY}
                )
                response.raise_for_status()
                self.token = response.json().get("access_token", "")

                # Persist the freshly retrieved token
                with open(self.token_file_path, "w") as file:
                    file.write(self.token)

            # Validate the token we now have; refresh if needed
            if self.is_token_valid():
                return
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
        self,
        method,
        endpoint,
        params=None,
        data=None,
        limit=None,
        max_retries=3,
        direct_list=False,
    ):
        """Make a request to the Motion API and return the response data
        Parameters:
            method (str): The HTTP method to use (e.g., "GET", "POST", "PATCH")
            endpoint (str): The API endpoint (e.g., "/tasks")
            params (dict): Query parameters to include in the request
            data (dict): Data to include in the request body
            limit (int): The maximum number of pages to fetch (default: None)
            max_retries (int): Maximum number of retries for 429 responses
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
            retries = 0
            while retries <= max_retries:
                try:
                    response = requests.request(
                        method, url, headers=headers, params=params, json=data
                    )

                    # Handle rate limiting (HTTP 429)
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        sys.stdout.write(
                            f"\rRate limited by server. Retrying after {retry_after} seconds... (Retry {retries+1}/{max_retries})"
                        )
                        sys.stdout.flush()
                        time.sleep(retry_after)
                        retries += 1
                        continue

                    response.raise_for_status()  # Raise HTTPError for other bad responses
                    break  # Break the retry loop if request succeeds

                except requests.exceptions.HTTPError as e:
                    if response.status_code == 429 and retries < max_retries:
                        retries += 1
                        continue
                    raise  # Re-raise the exception if it's not a 429 or max retries exceeded

            # Clear retry message if shown
            if retries > 0:
                sys.stdout.write("\r" + " " * 80 + "\r")
                sys.stdout.flush()

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

    def _request_internal(self, method, endpoint, params=None, data=None):
        self._rate_limit()  # Ensure compliance with rate limit before making a request

        url = f"https://internal.usemotion.com{endpoint}"
        headers = {"Authorization": "Bearer " + self.token}

        if data:
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"

            data = {"data": data}

        response = requests.request(
            method, url, headers=headers, params=params, json=data
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx and 5xx)

        self.request_count += 1
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
        response = self.get_tasks(params)
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

    def get_tasks(self, params=None, limit=None):
        endpoint = "/tasks"
        response = self._request("GET", endpoint, params, limit=limit)
        return response

    def get_tasks_by_date_range(self, start_date, end_date):
        """
        Gets scheduled entities between two dates using the internal API

        Parameters:
            start_date (datetime): The start date
            end_date (datetime): The end date

        Returns:
            dict: Organized scheduled entities with tasks, chunks, and their relationships
        """
        self.refresh_token_if_invalid()
        endpoint = "/v2/scheduled-entities"

        # Ensure dates are properly formatted with timezone info
        if not start_date.tzinfo:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if not end_date.tzinfo:
            end_date = end_date.replace(tzinfo=timezone.utc)

        # Format dates in ISO format with timezone offset
        start_iso = start_date.isoformat()
        end_iso = end_date.isoformat()

        # Build request payload
        data = {
            "include": ["task", "blockingTimeslot", "event"],
            "filters": {
                "completed": "include",
                "myCalendarsOnly": False,
                "scheduled": {"from": start_iso, "to": end_iso},
                "calendarsOptions": {"alwaysIncludeCalendarIds": []},
            },
        }

        response = self._request_internal("POST", endpoint, data=data)

        # Extract and organize the data
        result = {
            "regular_tasks": [],  # Tasks without chunks
            "chunked_tasks": [],  # Parent tasks with chunks
            "chunks": [],  # Individual chunks
            "calendar_events": [],  # Calendar events
            "all_scheduled_entities": [],  # All scheduled items with timing information
        }

        # Process scheduled entities
        scheduled_entities = {}
        if "models" in response and "scheduledEntities" in response["models"]:
            scheduled_entities = response["models"]["scheduledEntities"]

        # Process tasks
        tasks = {}
        if "models" in response and "tasks" in response["models"]:
            tasks = response["models"]["tasks"]

        # Process chunks
        chunks = {}
        if "models" in response and "chunks" in response["models"]:
            chunks = response["models"]["chunks"]

        # Process calendar events
        calendar_events = {}
        if "models" in response and "calendarEvents" in response["models"]:
            calendar_events = response["models"]["calendarEvents"]

        # Process projects
        projects = {}
        if "models" in response and "projects" in response["models"]:
            projects = response["models"]["projects"]

        # First, determine which chunks are scheduled within our date range
        chunks_in_timeframe = set()
        for entity_id, entity in scheduled_entities.items():
            if entity.get("type") == "CHUNK":
                chunks_in_timeframe.add(entity_id)

        # Then only include tasks that have at least one chunk in the timeframe
        tasks_with_chunks = {}
        for task_id, task in tasks.items():
            if "chunkIds" in task and task["chunkIds"]:
                # Check if any of this task's chunks are in our timeframe
                task_chunks_in_timeframe = [
                    chunk_id
                    for chunk_id in task["chunkIds"]
                    if chunk_id in chunks_in_timeframe
                ]

                if (
                    task_chunks_in_timeframe
                ):  # Only include if it has chunks in our timeframe
                    tasks_with_chunks[task_id] = task
                    task_with_chunks = task.copy()
                    task_with_chunks["chunks"] = []
                    task_with_chunks["chunkIds"] = (
                        task_chunks_in_timeframe  # Only keep relevant chunks
                    )

                    # Add project info if available
                    if task.get("projectId") and task["projectId"] in projects:
                        task_with_chunks["project"] = projects[task["projectId"]]
                    else:
                        task_with_chunks["project"] = None

                    result["chunked_tasks"].append(task_with_chunks)

        # Process all scheduled entities
        for entity_id, entity in scheduled_entities.items():
            entity_type = entity.get("type")
            scheduled_entity = entity.copy()

            # Add duration based on schedule
            if "schedule" in entity and not entity.get("timeless"):
                start = entity["schedule"].get("start")
                end = entity["schedule"].get("end")
                if start and end:
                    # If they are timestamps, calculate duration
                    if "T" in start and "T" in end:
                        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                        duration_minutes = (end_dt - start_dt).total_seconds() / 60
                        scheduled_entity["scheduled_duration"] = duration_minutes

            # Handle based on entity type
            if entity_type == "TASK":
                if entity_id in tasks:
                    task_data = tasks[entity_id]
                    scheduled_entity.update(task_data)

                    # Add project info if available
                    if (
                        task_data.get("projectId")
                        and task_data["projectId"] in projects
                    ):
                        scheduled_entity["project"] = projects[task_data["projectId"]]
                    else:
                        scheduled_entity["project"] = None

                    # If not a chunked task, add to regular tasks
                    if entity_id not in tasks_with_chunks:
                        result["regular_tasks"].append(scheduled_entity)

            elif entity_type == "CHUNK":
                if entity_id in chunks:
                    chunk_data = chunks[entity_id]
                    scheduled_entity.update(chunk_data)

                    # Link to parent task
                    parent_task_id = chunk_data.get("parentTaskId")
                    if parent_task_id:
                        scheduled_entity["parent_task"] = tasks.get(parent_task_id)

                        # Add to parent task's chunks list
                        for task in result["chunked_tasks"]:
                            if task["id"] == parent_task_id:
                                task["chunks"].append(scheduled_entity)
                                break

                    result["chunks"].append(scheduled_entity)

            elif entity_type == "EVENT":
                if entity_id in calendar_events:
                    event_data = calendar_events[entity_id]
                    scheduled_entity.update(event_data)
                    result["calendar_events"].append(scheduled_entity)

            # Add to all scheduled entities
            result["all_scheduled_entities"].append(scheduled_entity)

        return result

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
            endpoint = f"/v2/tasks/{task_id}"
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
            if duration and duration > duration_limit:
                # Step 5: Update the task if duration is higher than 90 minutes
                task_update = {
                    "id": task["id"],
                    "type": "NORMAL",
                    "minimumDuration": 45,
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
