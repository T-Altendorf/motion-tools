import json
import os
from datetime import datetime, timedelta

import natsort
from api.motion_api import MotionAPI
from pdf_parser.pdf_extractor import FileExtractor
from overview.overview import get_upcoming_week_tasks
from api.google_api import GoogleCalendarAPI
from prettify import colorize
from task_generator.task_generator import TaskGenerator
import constants


def task_generator(api: MotionAPI, file_ending="pdf"):
    task_generator = TaskGenerator(datetime(2024, 4, 15))

    # task_generator: TaskGenerator = TaskGenerator(datetime.now())

    pdf_dir = "/Users/timaltendorf/Library/CloudStorage/OneDrive-stud.tu-darmstadt.de/EDU/TU/24 SoSe/Statistische Modellierung/exercise/sheets"
    # pdf_dir = input("Enter the path to the directory: ")
    shorthand = "STMD"
    task_name = "Do Exercise "
    task_duration = 150

    # task_name = input("Enter the task name: ")
    # task_duration = int(input("Enter the task duration in minutes: "))

    workspace_id = None
    while workspace_id is None:
        # workspace_name = input("Enter the workspace name: ")
        workspace_name = "Uni_Tim"
        workspace_id = api.get_workspace_id(workspace_name)
        if workspace_id is None:
            print(f"Workspace '{workspace_name}' not found. Please try again.")

    project_id = None
    while project_id is None:
        # project_name = input("Enter the project name: ")
        project_name = "StatMod"
        project_id = api.get_project_id(workspace_id, project_name)
        if project_id is None:
            print(f"Project '{project_name}' not found. Please try again.")

    files = os.listdir(pdf_dir)
    sorted_files = natsort.natsorted(files)

    blocking_name = None
    tasks_in_project = None
    if input("Do you want to add a blocking task? (y/n): ") == "y":
        blocking_name = input(
            "Enter the name of the task that should block for the same week: "
        )
        tasks_in_project = api.get_tasks_in_project(project_id)

    if input("Do you want to add a file ending? defaults to pdf (y/n): ") == "y":
        file_ending = input("Enter the file ending: ")
    start_from_week = input("Enter the start week (default is 1): ")
    if start_from_week:
        start_from_week = int(start_from_week)
    else:
        start_from_week = 1
    for filename in sorted_files:
        if filename.endswith("." + file_ending):
            week_number, pdf_name = FileExtractor.extract_week_number_and_name(filename)
            if week_number >= start_from_week:
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
                    + " "
                    + pdf_name.replace("_", " ").replace("-", " ")
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
                            "id": entered_task["id"],
                            "workspaceId": workspace_id,
                        }
                        for blockingTaskId in blocking_ids:
                            blockingTasks.append({"blockedId": blockingTaskId})
                        block_task["blockingTasks"] = blockingTasks
                        api.update_task(block_task, True)
                        print("Blocking task added")

    if task_duration >= 90:
        api.update_tasks_if_duration_exceeds(workspace_name, project_name, 90)


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


def main():
    motion_api = MotionAPI(constants.MOTION_API_KEY)
    google_api = GoogleCalendarAPI("google_client_secret.json", "google_token.pickle")

    action = input("What do you want to do? (task_generator/overview): ")
    if action == "t":
        task_generator(motion_api)
    elif action == "o":
        get_upcoming_week_tasks(motion_api, google_api)
    elif action == "chunk":
        motion_api.update_tasks_if_duration_exceeds("Uni_Tim", "DMML", 90)
    elif action == "google":
        print(get_upcoming_week_events(google_api))
    elif action == "exit":
        exit()
    else:
        print("Invalid action")


if __name__ == "__main__":
    main()
