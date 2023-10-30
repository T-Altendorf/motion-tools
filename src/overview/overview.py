from datetime import datetime, timedelta
import json

from api.motion_api import MotionAPI

def get_upcoming_week_tasks(api: MotionAPI):
        # Get the start and end dates for the upcoming week
        today = datetime.today()
        start_date = today + timedelta(days=(- today.weekday()))
        end_date = start_date + timedelta(days=6)

        print(f"Tasks for the week of {start_date.strftime('%d.%m.%Y')} to {end_date.strftime('%d.%m.%Y')}")

        # Fetch all tasks between the start and end dates
        # Assume a method get_tasks_by_date_range that fetches tasks based on date range
        tasks = api.get_tasks_by_date_range(start_date, end_date)

        # Initialize dictionaries to store time spent per workspace and project
        workspace_time = {}
        project_time = {}
        workspace_names = {}
        project_names = {}
        task_by_workspace = {}

        # Iterate through tasks and accumulate time spent
        for task in tasks:
            workspace_id = task['workspace']['id']
            workspace_names[workspace_id] = task['workspace']['name']
            task_by_workspace[workspace_id] = task_by_workspace.get(workspace_id, []) + [task]
            if task['project'] is None:
                project_id = "No project"
                project_names[project_id] = "No project"
            else:
                project_id = task['project']['id']
                project_names[project_id] = task['project']['name']
            duration = task['duration']  # Assume duration is in minutes

            # Update workspace time
            workspace_time[workspace_id] = workspace_time.get(workspace_id, 0) + duration

            # Update project time
            project_time[project_id] = project_time.get(project_id, 0) + duration

        # Calculate total time spent
        total_time = sum(workspace_time.values())

        # Print percentage time used per workspace and project
        print("Percentage time used per workspace:")
        for workspace_id, time_spent in workspace_time.items():
            percentage = (time_spent / total_time) * 100
            print(f"{workspace_names[workspace_id]}: {percentage:.2f}%")
            for task in task_by_workspace[workspace_id]:
                print(f"    {task['name']}")

        print("\nPercentage time used per project:")
        for project_id, time_spent in project_time.items():
            percentage = (time_spent / total_time) * 100
            print(f"{project_names[project_id]}: {percentage:.2f}%")