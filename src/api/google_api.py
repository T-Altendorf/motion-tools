import pickle
import os
import google.auth
from datetime import datetime
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


class GoogleCalendarAPI:
    def __init__(self, client_secrets_file, token_file=None):
        self.client_secrets_file = client_secrets_file
        self.token_file = token_file
        self.scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
        self.service = self.get_calendar_service()

    def get_calendar_service(self):
        creds = None
        # Check if the token file exists and load credentials from it.
        if os.path.exists(self.token_file):
            with open(self.token_file, "rb") as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, prompt the user to log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, self.scopes
                )
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(self.token_file, "wb") as token:
                pickle.dump(creds, token)
        # Build the Google Calendar API client
        calendar = build("calendar", "v3", credentials=creds)
        return calendar

    def list_upcoming_events(self, calendar_id="primary"):
        # Call the Calendar API
        now = datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
        events_result = (
            self.service.events()
            .list(
                calendarId=calendar_id,
                timeMin=now,
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        return events

    def get_colors(self):
        """Get the color palette for the calendar

        Returns:
            dict: A dictionary of color ids to color names and hex codes"""
        id_to_color_name = {
            "11": "Tomato",
            "4": "Flamingo",
            "6": "Tangerine",
            "5": "Banana",
            "2": "Sage",
            "10": "Basil",
            "7": "Peacock",
            "9": "Blueberry",
            "1": "Lavender",
            "3": "Grape",
            "8": "Graphite",
            "0": "Calendar Color",
        }
        colors = self.service.colors().get().execute()
        for colorId in colors["event"].keys():
            if colors["event"][colorId]["background"] == "#e1e1e1":
                colors["event"][colorId]["background"] = "#616161"
            colors["event"][colorId]["name"] = id_to_color_name[colorId]
        colors["event"]["0"] = {
            "name": "Calendar Color",
            "background": "#4285f4",
            "foreground": "#1d1d1d",
        }
        return colors["event"]

    def get_events_by_date_range(
        self, start_date, end_date, calendar_id="primary", get_transparent=False
    ):
        """Get all events between start_date and end_date
        add colorHex and duration to each event

        Args:
            start_date (datetime): The start date
            end_date (datetime): The end date
            calendar_id (str, optional): The calendar id. Defaults to 'primary'.

        Returns:
            list: A list of events
        """
        # Call the Calendar API
        start_date = start_date.isoformat() + "Z"  # 'Z' indicates UTC time
        end_date = end_date.isoformat() + "Z"
        events_result = (
            self.service.events()
            .list(
                calendarId=calendar_id,
                timeMin=start_date,
                timeMax=end_date,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        colors = self.get_colors()
        return_events = []
        for event in events:
            if not get_transparent and event.get("transparency", "") == "transparent":
                continue
            if not event.get("colorId"):
                # return id of 0 if no color is set
                event["colorId"] = "0"

            event["colorHex"] = colors[event["colorId"]]["background"]

            # calculate duration
            if event.get("start").get("dateTime"):
                start = datetime.fromisoformat(event["start"].get("dateTime"))
                end = datetime.fromisoformat(event["end"].get("dateTime"))
                event["duration"] = (end - start).total_seconds() / 60
            else:
                event["duration"] = 0

            if not event.get("summary"):
                event["summary"] = "[No title]"
            return_events.append(event)

        return return_events
