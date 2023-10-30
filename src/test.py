from datetime import datetime, timedelta
import json
from api import GoogleCalendarAPI

api = GoogleCalendarAPI("google_client_secret.json", "google_token.pickle")

print({color["name"] for color in api.get_colors()})
