from datetime import datetime, timedelta
import json
import re

from api.motion_api import MotionAPI
from api.google_api import GoogleCalendarAPI
from prettify import colorize


def minutes_to_hours_str(minutes):
    # Convert minutes to hours and minutes string
    hours = minutes // 60
    minutes = minutes % 60
    if hours == 0:
        return f"{int(minutes)}m"
    else:
        if minutes == 0:
            return f"{int(hours)}h"
        else:
            return f"{int(hours)}h {int(minutes)}m"


class Workspace:
    def __init__(self, id, name, color_mapping={}):
        self.id = id
        self.name = name
        self.projects = {}
        self.total_duration = 0
        self.color_mapping = color_mapping

    def add_task(self, task):
        project_id = task["project"]["id"] if task["project"] else "No project"
        project_name = task["project"]["name"] if task["project"] else "No project"
        project_description = task["project"]["description"] if task["project"] else ""
        project_color_tag = re.search(r"\[GoogleColor=(.*?)\]", project_description)
        project_color_name = (
            project_color_tag.group(1) if project_color_tag else "Calendar Color"
        )
        # Update the following line to look up color based on name, not project_id
        project_color = next(
            (
                color["background"]
                for color in self.color_mapping.values()
                if color["name"] == project_color_name
            ),
            "#616161",
        )
        self.projects.setdefault(
            project_id,
            Project(project_id, project_name, project_description, project_color),
        ).add_task(task)
        self.total_duration += task["duration"]


class Project:
    def __init__(self, id, name, description="", color="#616161"):
        self.id = id
        self.name = name
        self.tasks = []
        self.total_duration = 0
        self.description = description
        self.color = color

    def add_task(self, task):
        self.tasks.append(task)
        self.total_duration += task["duration"]


def get_upcoming_week_tasks(motion_api: MotionAPI, google_api: GoogleCalendarAPI):
    # Get the start and end dates for the upcoming week
    today = datetime.today()
    start_date = today + timedelta(days=(-today.weekday()))
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=6)
    end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    print(
        f"Tasks for the week of {start_date.strftime('%d.%m.%Y')} to {end_date.strftime('%d.%m.%Y')}\n"
    )

    # Fetch all tasks between the start and end dates
    # Assume a method get_tasks_by_date_range that fetches tasks based on date range
    tasks = motion_api.get_tasks_by_date_range(start_date, end_date)
    events = google_api.get_events_by_date_range(start_date, end_date)

    # Initialize dictionaries to store time spent per workspace and project
    workspaces = {}

    colors = google_api.get_colors()
    color_time = {}
    color_to_name = {colorId: color["name"] for colorId, color in colors.items()}
    color_to_hex = {colorId: color["background"] for colorId, color in colors.items()}
    events_by_color = {}

    # Add tasks to workspaces and projects
    for task in tasks:
        workspace_id = task["workspace"]["id"]
        workspaces.setdefault(
            workspace_id, Workspace(workspace_id, task["workspace"]["name"], colors)
        ).add_task(task)

    # Add events to colors
    for event in events:
        color_name = color_to_name[event["colorId"]]
        color_time[event["colorId"]] = color_time.get(color_name, 0) + event["duration"]
        events_by_color[event["colorId"]] = events_by_color.get(
            event["colorId"], []
        ) + [event]

    # Calculate total time spent
    total_time = sum(
        [workspace.total_duration for workspace in workspaces.values()]
    ) + sum(color_time.values())

    print(
        f"Total time planned: {colorize(minutes_to_hours_str(total_time), '#0b8043')} \n"
    )

    # Print percentage time used per workspace and project
    print("Percentage time used per workspace:")
    for workspace_id, workspace in workspaces.items():
        percentage = (workspace.total_duration / total_time) * 100
        print(
            f"{workspace.name}: {minutes_to_hours_str(workspace.total_duration)} ({percentage:.2f}%)"
        )
        for project in workspace.projects.values():
            print(
                colorize(
                    f"    {project.name}: {minutes_to_hours_str(project.total_duration)} ({percentage:.2f}%)",
                    project.color,
                )
            )
            for task in project.tasks:
                print(
                    f"      {minutes_to_hours_str(task['duration']).ljust(7)}{task['name']}"
                )

    print("\nPercentage time used per color:")
    for color_id, time_spent in color_time.items():
        color_name = color_to_name[color_id]
        percentage = (time_spent / total_time) * 100
        print(
            colorize(
                f"{color_name}: {minutes_to_hours_str(time_spent)} ({percentage:.2f}%)",
                color_to_hex[color_id],
            )
        )
        for event in events_by_color[color_id]:
            print(
                f"    {minutes_to_hours_str(event['duration']).ljust(7)}{event['summary']}"
            )
