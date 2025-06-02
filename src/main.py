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


def task_generator(api: MotionAPI, file_ending="pdf"):
    task_generator = TaskGenerator(datetime(2024, 8, 12))

    # task_generator: TaskGenerator = TaskGenerator(datetime.now())

    pdf_dir = "/Users/timaltendorf/Library/CloudStorage/OneDrive-stud.tu-darmstadt.de/EDU/TU/24 SoSe/Neurobiologie/slides"
    # pdf_dir = input("Enter the path to the directory: ")
    shorthand = "NBIO"
    task_name = "Study Anki"
    task_duration = 40

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
        project_name = "NBIO"
        project_id = api.get_project_id(workspace_id, project_name)
        if project_id is None:
            print(f"Project '{project_name}' not found. Please try again.")

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
    else:
        file_ending = "pdf"
    start_from_week = input("Enter the start week (default is 1): ")
    if start_from_week:
        start_from_week = int(start_from_week)
    else:
        start_from_week = 1
    for filename in sorted_files:
        if filename.endswith("." + file_ending):
            print(filename)
            regex_week = r"W(\d{2})-"
            regex_task = r"W\d{2}-(.*)"
            week_number, pdf_name = FileExtractor.extract_week_number_and_name(
                filename, regex_week, regex_task
            )
            print(f"Week {week_number}: {pdf_name}")
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

    action = input("What do you want to do? (task_generator/overview/reshedule): ")
    if action == "t" or action == "task_generator":
        task_generator(motion_api)
    elif action == "o" or action == "overview":
        get_upcoming_week_tasks(motion_api, google_api)
    elif action == "reschedule" or action == "r":
        reshedule_tasks(motion_api)
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
