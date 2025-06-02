import json
import os
from datetime import datetime, timedelta

import natsort
import pytz
from api.motion_api import MotionAPI
from pdf_parser.pdf_extractor import FileExtractor
from overview.overview import get_upcoming_week_tasks
from api.google_api import GoogleCalendarAPI
from prettify import colorize
from task_generator.task_generator import TaskGenerator
import constants
import re


def task_generator(api: MotionAPI, file_ending="pdf", config_from_file=True):
    CONFIG_FROM_FILE = {}
    if config_from_file:
        config_path = "config.json"
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
            CONFIG_FROM_FILE.update(config)

    # Create a config dictionary by merging DEFAULT_CONFIG with CONFIG_FROM_FILE
    config = CONFIG_FROM_FILE.copy()

    # Use get() for accessing configuration values with defaults
    start_date_str = input(
        "Enter the start date (YYYY-MM-DD) or leave empty for today: "
    )
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        except ValueError:
            print("Invalid date format. Using today's date instead.")
            start_date = datetime.now()
    else:
        start_date = config.get("start_date", datetime.now())

    task_generator = TaskGenerator(start_date)

    pdf_dir = config.get("pdf_dir", "")
    if not pdf_dir:
        pdf_dir = input("Enter the PDF directory path: ")

    shorthand = config.get("shorthand", "")
    if not shorthand:
        shorthand = input("Enter the shorthand name: ")

    task_name = config.get("task_name", "")
    if not task_name:
        task_name = input("Enter the task name: ")

    task_duration = config.get("task_duration", 0)
    if not task_duration:
        task_duration = int(input("Enter the task duration in minutes: "))

    workspace_id = None
    while workspace_id is None:
        workspace_name = config.get("workspace_name", "")
        if not workspace_name:
            workspace_name = input("Enter the workspace name: ")
        workspace_id = api.get_workspace_id(workspace_name)
        if workspace_id is None:
            print(f"Workspace '{workspace_name}' not found. Please try again.")
            config["workspace_name"] = ""  # Clear invalid workspace name

    project_id = None
    while project_id is None:
        project_name = config.get("project_name", "")
        if not project_name:
            project_name = input("Enter the project name: ")
        project_id = api.get_project_id(workspace_id, project_name)
        if project_id is None:
            print(f"Project '{project_name}' not found. Please try again.")
            config["project_name"] = ""  # Clear invalid project name

    files = os.listdir(pdf_dir)
    sorted_files = natsort.natsorted(files)
    print("Files in directory:")
    for i, filename in enumerate(sorted_files):
        print(f"{i+1}: {filename}")

    blocking_name = None
    tasks_in_project = None
    if input("Do you want to add a blocking task? (y/n): ") == "y":
        blocking_name = input(
            "Enter the name of the task that should block for the same week: "
        )
        tasks_in_project = api.get_tasks_in_project(project_id)

    if input("Do you want to add a file ending? defaults to pdf (y/n): ") == "y":
        file_ending = input("Enter the file ending: ")

    for filename in sorted_files:
        if filename.endswith("." + file_ending):
            week_pattern = r"exercise_(\d+)"
            name_pattern = r"(.+)\." + file_ending
            week_number, pdf_name = FileExtractor.extract_week_number_and_name(
                filename, number_pattern=week_pattern, name_pattern=name_pattern
            )
            week_number = week_number + 1
            if week_number:
                if blocking_name:
                    blocking_ids = [
                        task["id"]
                        for task in tasks_in_project
                        if (
                            blocking_name in task["name"]
                            and f"W{week_number}:" in task["name"]
                        )
                    ]
                else:
                    blocking_ids = None
                name = (
                    task_name.strip()
                    # + " "
                    # + pdf_name.replace("_", " ").replace("-", " ")
                )
                task = task_generator.generate_task_for_week(
                    week_number,
                    name,
                    task_duration,
                    workspace_id,
                    project_id,
                    shorthand,
                )

                print(f"Week {week_number} Task:")
                print(task)

                if input("Do you want to push these tasks to Motion? (y/n): ") == "y":
                    entered_task = api.create_task(task)
                    if blocking_ids:
                        blockingTasks = []
                        block_task = {
                            "type": "NORMAL",
                            "id": entered_task["id"],
                        }
                        for blockingTaskId in blocking_ids:
                            blockingTasks.append(blockingTaskId)
                        block_task["blockedByTaskIds"] = blockingTasks
                        api.update_task(block_task, True)
                        print("Blocking task added")

    api.update_tasks_if_duration_exceeds(workspace_name, project_name, 45)


def get_upcoming_week_events(api: GoogleCalendarAPI):
    today = datetime.today()
    start_date = today + timedelta(days=(-today.weekday()))
    start_date = start_date.replace(hour=0, minute=0, second=0)
    end_date = start_date + timedelta(days=6)
    end_date = end_date.replace(hour=23, minute=59, second=59)
    events = api.get_events_by_date_range(start_date, end_date)
    print(json.dumps(api.get_colors(), indent=4, sort_keys=True))
    if not events:
        print("No upcoming events found.")
    else:
        for event in events:
            if event.get("transparency", "") == "transparent":
                continue
            if not event.get("summary"):
                event["summary"] = "[No title]"
            start = datetime.fromisoformat(
                event["start"].get("dateTime", event["start"].get("date"))
            )
            print(
                colorize(event["summary"], event["colorHex"]),
                " ",
                start.strftime("%d.%m.%Y %H:%M"),
            )


def reshedule_tasks(api: MotionAPI):
    """This function takes all the non completed tasks of a project and
    a start and end date and reschedules them to fit evenly in that time"""
    # workspace_name = input("Enter the workspace name: ")
    # project_name = input("Enter the project name: ")
    workspace_name = "Uni_Tim"
    project_name = "ENLP"
    schedule_name = "Work hours"
    workspace_id = api.get_workspace_id(workspace_name)
    project_id = api.get_project_id(workspace_id, project_name)
    schedules = api.get_schedules()
    if workspace_id is None or project_id is None:
        print("Workspace or project not found.")
        return
    # tasks = api.get_tasks_in_project(project_id)
    # start_date = datetime.fromisoformat(input("Enter the start date (YYYY-MM-DD): "))
    # end_date = datetime.fromisoformat(input("Enter the end date (YYYY-MM-DD): "))

    # Find the matching schedule
    schedule = next((s for s in schedules if s["name"] == schedule_name), None)
    if not schedule:
        print(f"Schedule '{schedule_name}' not found.")
        return

    # Define the timezone you want to convert to
    timezone = pytz.timezone("Europe/Berlin")

    # Parse the start and end dates, initially in UTC
    start_date = datetime.fromisoformat("2024-08-28").replace(
        hour=0, minute=0, second=0, tzinfo=pytz.utc
    )
    end_date = datetime.fromisoformat("2024-09-07").replace(
        hour=23, minute=59, second=59, tzinfo=pytz.utc
    )

    # no_reschedule_patterns = ["Do Exercise"]
    no_reschedule_patterns = []  # ["Do Exercise"]

    if start_date > end_date:
        print("Start date must be before end date.")
        return
    api.reschedule_tasks_by_week(
        project_id,
        start_date,
        end_date,
        schedule,
        no_reschedule_patterns,
    )


def main():
    motion_api = MotionAPI(constants.MOTION_API_KEY)
    google_api = GoogleCalendarAPI("google_client_secret.json", "google_token.pickle")

    action = input(
        "What do you want to do? (task_generator[tg]/overview/google/chunk[c]/reshedule): "
    )
    if action == "task_generator" or action == "tg" or action == "task_generator":
        task_generator(motion_api)
    elif action == "o":
        get_upcoming_week_tasks(motion_api, google_api)
    elif action == "chunk":
        motion_api.update_tasks_if_duration_exceeds("Uni_Tim", "DMML", 90)
    elif action == "reschedule" or action == "r":
        reshedule_tasks(motion_api)
    elif action == "overview":
        weeks_offset = int(input("Enter the number of weeks to offset: "))
        get_upcoming_week_tasks(motion_api, google_api, weeks_offset=weeks_offset)
    elif action == "google":
        print(get_upcoming_week_events(google_api))
    elif action == "chunk" or action == "c":
        workspace_name = "Uni_Tim"
        project_name = "DLAM"
        motion_api.update_tasks_if_duration_exceeds(workspace_name, project_name, 45)
    elif action == "exit":
        exit()
    else:
        print("Invalid action")


if __name__ == "__main__":
    main()
