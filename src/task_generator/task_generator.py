from datetime import datetime, timedelta


class TaskGenerator:
    def __init__(self, start_date):
        # Ensure start_date is a Monday
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)

        # Calculate days until Monday (Monday is 0 in weekday())
        days_to_subtract = start_date.weekday()

        # Set start_date to the Monday of the current week
        self.start_date = start_date - timedelta(days=days_to_subtract)

    def generate_task_for_week(
        self,
        week_number,
        task_name,
        task_duration,
        workspace_id,
        project_id,
        shorthand="",
    ):
        # Find the start of week (Monday)
        week_start = self.start_date + timedelta(weeks=week_number - 1)
        # Calculate Saturday (5 days after Monday)
        deadline = (week_start + timedelta(days=1)).isoformat()
        # Week before deadline for auto scheduling
        week_before_deadline = (
            self.start_date + timedelta(weeks=week_number - 2)
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
