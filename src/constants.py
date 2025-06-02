import os
import dotenv

dotenv.load_dotenv()

MOTION_API_KEY = os.environ.get("MOTION_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
NEW_MOTION_TOKEN_URL = os.environ.get(
    "NEW_MOTION_TOKEN_URL", "https://tim7.pythonanywhere.com/"
)
NEW_MOTION_TOKEN_KEY = os.environ.get(
    "NEW_MOTION_TOKEN_KEY",
    "sdgsdgsdgssddsssdgertr53i723486957309rujgbnodicziuzgtufguztuz%%%gkdsjfo",
)
