from datetime import datetime, timedelta
import re

from api.motion_api import MotionAPI
from api.google_api import GoogleCalendarAPI
from prettify import colorize
import pytz


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


def format_scheduled_time(
    scheduled_entity, time_format="%d.%m.%y", timezone="Europe/Berlin"
):
    """Format the scheduled time of an entity for display

    Args:
        scheduled_entity: The entity to format time for
        time_format: The time format to use (default: German format "%d.%m.%y")
        timezone: The timezone to convert times to (default: "Europe/Berlin")
    """

    start_time = None

    # Try to get the scheduled start time
    if "scheduledStart" in scheduled_entity and scheduled_entity["scheduledStart"]:
        try:
            start_time = datetime.fromisoformat(
                scheduled_entity["scheduledStart"].replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            pass
    elif "schedule" in scheduled_entity and "start" in scheduled_entity["schedule"]:
        try:
            start = scheduled_entity["schedule"]["start"]
            if "T" in start:  # Has time component
                start_time = datetime.fromisoformat(start.replace("Z", "+00:00"))
            else:  # Date only
                start_time = datetime.fromisoformat(f"{start}T00:00:00+00:00")
        except (ValueError, TypeError):
            pass

    if start_time:
        # Convert to the specified timezone
        tz = pytz.timezone(timezone)
        start_time = start_time.astimezone(tz)

        # Format time based on whether it's just a date or has a time component
        if (
            start_time.hour == 0
            and start_time.minute == 0
            and "T" not in scheduled_entity.get("schedule", {}).get("start", "")
        ):
            return f"({start_time.strftime(time_format)})"
        else:
            return f"({start_time.strftime(f'{time_format} %H:%M')})"
    return ""


class Workspace:
    def __init__(self, id, name, color_mapping=None):
        self.id = id
        self.name = name
        self.projects = {}
        self.total_duration = 0
        self.color_mapping = color_mapping or {}
        self.processed_chunk_ids = set()  # Track processed chunks to avoid duplicates

    def add_task(self, task, is_chunk=False):
        # Skip if this is a chunk we've already processed
        if is_chunk and task["id"] in self.processed_chunk_ids:
            return

        if is_chunk:
            self.processed_chunk_ids.add(task["id"])

        project_id = task["project"]["id"] if task.get("project") else "No project"
        project_name = task["project"]["name"] if task.get("project") else "No project"
        project_description = (
            task["project"]["description"] if task.get("project") else ""
        )
        project_color_tag = re.search(r"\[GoogleColor=(.*?)\]", project_description)
        project_color_name = (
            project_color_tag.group(1) if project_color_tag else "Calendar Color"
        )

        if self.name == "Private Projects" and project_name == "No project":
            # If the workspace is "Private Projects" and the project name is "No project",
            # set a default project name and description
            project_color_name = "Tangerine"

        # Get color based on name
        project_color = next(
            (
                color["background"]
                for color in self.color_mapping.values()
                if color["name"] == project_color_name
            ),
            "#616161",
        )

        # Use scheduled_duration if available, otherwise fall back to task duration
        duration = task.get("scheduled_duration", task.get("duration", 0))

        self.projects.setdefault(
            project_id,
            Project(project_id, project_name, project_description, project_color),
        ).add_task(task, duration)

        # Only add to total duration if not a chunk (parent tasks will include chunk durations)
        if not is_chunk:
            self.total_duration += duration


class Project:
    def __init__(self, id, name, description="", color="#616161"):
        self.id = id
        self.name = name
        self.tasks = []
        self.total_duration = 0
        self.description = description
        self.color = color

    def add_task(self, task, duration):
        task_copy = task.copy()
        task_copy["effective_duration"] = duration
        self.tasks.append(task_copy)
        self.total_duration += duration


def get_upcoming_week_tasks(
    motion_api: MotionAPI, google_api: GoogleCalendarAPI, weeks_offset=0
):
    # Get the start and end dates for the week with offset
    today = datetime.today()
    start_date = today + timedelta(days=(-today.weekday() + weeks_offset * 7))
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=6)
    end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    # Adjust message based on offset
    week_description = "this week"
    if weeks_offset < 0:
        week_description = (
            f"{abs(weeks_offset)} week{'s' if abs(weeks_offset) > 1 else ''} ago"
        )
    elif weeks_offset > 0:
        week_description = (
            f"{weeks_offset} week{'s' if weeks_offset > 1 else ''} from now"
        )

    print(
        f"Tasks for {week_description} ({start_date.strftime('%d.%m.%Y')} to {end_date.strftime('%d.%m.%Y')})\n"
    )

    # Fetch all scheduled entities between the start and end dates
    scheduled_data = motion_api.get_tasks_by_date_range(start_date, end_date)
    events = google_api.get_events_by_date_range(start_date, end_date)

    motion_workspaces = motion_api.get_workspaces()
    motion_workspaces = {ws["id"]: ws for ws in motion_workspaces}

    # Create a mapping of chunk IDs to parent task IDs to help with filtering
    chunk_to_parent = {}
    for task in scheduled_data["chunked_tasks"]:
        for chunk in task.get("chunks", []):
            chunk_to_parent[chunk["id"]] = task["id"]

    # Initialize dictionaries to store time spent per workspace and project
    workspaces = {}

    colors = google_api.get_colors()
    color_time = {}
    color_to_name = {colorId: color["name"] for colorId, color in colors.items()}
    color_to_hex = {colorId: color["background"] for colorId, color in colors.items()}
    events_by_color = {}

    # Process regular tasks (which don't have chunks)
    for task in scheduled_data["regular_tasks"]:
        if "workspaceId" in task:
            workspace_id = task["workspaceId"]
            workspace = workspaces.setdefault(
                workspace_id,
                Workspace(
                    workspace_id,
                    motion_workspaces.get(workspace_id, {"name": "Unknown"})["name"],
                    colors,
                ),
            )
            workspace.add_task(task)

    # Process chunked tasks - include the parent task for structure, but don't count its duration directly
    for task in scheduled_data["chunked_tasks"]:
        if "workspaceId" in task:
            workspace_id = task["workspaceId"]
            # Create a copy with zero duration for the parent task
            task_copy = task.copy()

            # Calculate the sum of the scheduled chunks' durations for this parent task
            total_chunk_duration = sum(
                chunk.get("scheduled_duration", chunk.get("duration", 0))
                for chunk in task.get("chunks", [])
            )
            task_copy["scheduled_duration"] = total_chunk_duration

            workspace = workspaces.setdefault(
                workspace_id,
                Workspace(
                    workspace_id,
                    motion_workspaces.get(workspace_id, {"name": "Unknown"})["name"],
                    colors,
                ),
            )
            workspace.add_task(task_copy)

            # Mark all chunks as processed so we don't show them again at the top level
            for chunk in task.get("chunks", []):
                workspace.processed_chunk_ids.add(chunk["id"])

    # Add events to colors
    for event in events:
        color_id = event.get("colorId", "0")  # Default to color 0 if not specified
        color_name = color_to_name.get(color_id, "Default")
        color_time[color_id] = color_time.get(color_id, 0) + event["duration"]
        events_by_color.setdefault(color_id, []).append(event)

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
        percentage = (
            (workspace.total_duration / total_time) * 100 if total_time > 0 else 0
        )
        print(
            f"{workspace.name}: {minutes_to_hours_str(workspace.total_duration)} ({percentage:.2f}%)"
        )

        for project in workspace.projects.values():
            proj_percentage = (
                (project.total_duration / total_time) * 100 if total_time > 0 else 0
            )
            print(
                colorize(
                    f"    {project.name}: {minutes_to_hours_str(project.total_duration)} ({proj_percentage:.2f}%)",
                    project.color,
                )
            )

            for task in project.tasks:
                if "04 Modernize" in task.get("name", ""):
                    continue

                # Check if it's a parent task with chunks
                if "chunks" in task and task["chunks"]:
                    task_time = format_scheduled_time(task)
                    print(f"      [CHUNKED] {task['name']} {task_time}")

                    # Sort chunks by scheduled start time if available
                    sorted_chunks = sorted(
                        task["chunks"],
                        key=lambda c: (
                            c.get(
                                "scheduledStart", c.get("schedule", {}).get("start", "")
                            )
                            if isinstance(
                                c.get(
                                    "scheduledStart",
                                    c.get("schedule", {}).get("start", ""),
                                ),
                                str,
                            )
                            else ""
                        ),
                    )

                    for chunk in sorted_chunks:
                        chunk_duration = chunk.get(
                            "scheduled_duration", chunk.get("effective_duration", 0)
                        )
                        chunk_time = format_scheduled_time(chunk)

                        # For chunks, display the scheduled time instead of "Unnamed Chunk"
                        if not chunk.get("name"):
                            display_name = chunk_time.strip(
                                "()"
                            )  # Use the time as the name
                        else:
                            display_name = f"{chunk.get('name')} {chunk_time}"

                        print(
                            f"        {minutes_to_hours_str(chunk_duration).ljust(7)}{display_name}"
                        )
                else:
                    # Skip standalone chunks that are part of a parent task (they're shown under parent)
                    if task["id"] in chunk_to_parent:
                        continue

                    task_duration = task.get(
                        "effective_duration", task.get("duration", 0)
                    )
                    task_time = format_scheduled_time(task)

                    # Use task.get() with a default value to handle missing 'name' key
                    task_name = task.get("name", "Unnamed Task")

                    # If no name but we have a parent task, try to get name from there
                    if task_name == "Unnamed Task" and task.get("parent_task"):
                        parent_name = task["parent_task"].get(
                            "name", "Unnamed Parent Task"
                        )
                        task_name = f"{parent_name} (chunk)"

                    print(
                        f"      {minutes_to_hours_str(task_duration).ljust(7)}{task_name} {task_time}"
                    )

    print("\nPercentage time used per color:")
    for color_id, time_spent in color_time.items():
        color_name = color_to_name.get(color_id, "Default")
        percentage = (time_spent / total_time) * 100 if total_time > 0 else 0
        print(
            colorize(
                f"{color_name}: {minutes_to_hours_str(time_spent)} ({percentage:.2f}%)",
                color_to_hex.get(color_id, "#616161"),
            )
        )

        # Sort events by start time
        sorted_events = sorted(
            events_by_color.get(color_id, []),
            key=lambda e: e.get("start", {}).get(
                "dateTime", e.get("start", {}).get("date", "")
            ),
        )

        for event in sorted_events:
            event_time = ""
            if "start" in event:
                try:
                    start_str = event["start"].get(
                        "dateTime", event["start"].get("date", "")
                    )
                    if "T" in start_str:  # Has time component
                        event_start = datetime.fromisoformat(
                            start_str.replace("Z", "+00:00")
                        )
                    else:  # Date only
                        event_start = datetime.fromisoformat(
                            f"{start_str}T00:00:00+00:00"
                        )

                    # Convert to the specified timezone
                    tz = pytz.timezone(
                        "Europe/Berlin"
                    )  # Use the same timezone as above
                    event_start = event_start.astimezone(tz)

                    # Format with the same logic as format_scheduled_time
                    time_format = "%d.%m.%y"  # Use the same format as above
                    if "T" in start_str:
                        event_time = f"({event_start.strftime(f'{time_format} %H:%M')})"
                    else:
                        event_time = f"({event_start.strftime(time_format)})"
                except (ValueError, TypeError):
                    pass

            print(
                f"    {minutes_to_hours_str(event['duration']).ljust(7)}{event.get('summary', 'Unnamed Event')} {event_time}"
            )

    # Calculate and display combined times (Motion tasks + Calendar events)
    print("\nCombined time allocation:")

    # Create a mapping of project colors to project tasks
    project_by_color = {}
    for workspace in workspaces.values():
        for project in workspace.projects.values():
            # Extract the color ID from the hex value
            project_color_id = next(
                (
                    cid
                    for cid, details in colors.items()
                    if details["background"] == project.color
                ),
                None,
            )
            if project_color_id:
                if project_color_id not in project_by_color:
                    project_by_color[project_color_id] = {
                        "name": color_to_name.get(project_color_id, "Default"),
                        "color": project.color,
                        "duration": 0,
                        "items": [],
                    }
                project_by_color[project_color_id]["duration"] += project.total_duration
                project_by_color[project_color_id]["items"].append(
                    {
                        "type": "project",
                        "name": f"{workspace.name} - {project.name}",
                        "duration": project.total_duration,
                    }
                )

    # Add events to the color mapping
    for color_id, events_list in events_by_color.items():
        if color_id not in project_by_color:
            project_by_color[color_id] = {
                "name": color_to_name.get(color_id, "Default"),
                "color": color_to_hex.get(color_id, "#616161"),
                "duration": 0,
                "items": [],
            }
        event_duration = sum(event["duration"] for event in events_list)
        project_by_color[color_id]["duration"] += event_duration
        project_by_color[color_id]["items"].append(
            {
                "type": "events",
                "name": f"Calendar Events ({len(events_list)})",
                "duration": event_duration,
            }
        )

    # Display the combined allocation
    for color_id, data in project_by_color.items():
        percentage = (data["duration"] / total_time) * 100 if total_time > 0 else 0
        print(
            colorize(
                f"{data['name']}: {minutes_to_hours_str(data['duration'])} ({percentage:.2f}%)",
                data["color"],
            )
        )

        for item in data["items"]:
            item_percentage = (
                (item["duration"] / total_time) * 100 if total_time > 0 else 0
            )
            print(
                f"    {item['name']}: {minutes_to_hours_str(item['duration'])} ({item_percentage:.2f}%)"
            )
