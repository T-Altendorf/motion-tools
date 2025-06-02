from datetime import datetime, timedelta


class TaskGenerator:
    def __init__(self, start_date):
        self.start_date = start_date

    def generate_task_for_week(
        self,
        week_number,
        task_name,
        task_duration,
        workspace_id,
        project_id,
        shorthand="",
    ):
        deadline = (self.start_date + timedelta(weeks=week_number)).isoformat()
        week_before_deadline = (
            self.start_date + timedelta(weeks=week_number - 1)
        ).isoformat()
        task = {
            "name": f"{shorthand}-W{week_number}: {task_name}",
            "dueDate": deadline,
            "duration": task_duration,
            "workspaceId": workspace_id,
            "projectId": project_id,
            "autoScheduled": {
                "startDate": week_before_deadline,
            },
        }
        return task
