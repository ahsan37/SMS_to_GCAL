from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from .config import settings

def get_credentials():
    creds = Credentials(
        token=None,
        refresh_token=settings.GOOGLE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=[
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/drive.file",
        ],
    )
    creds.refresh(Request())
    return creds

def get_calendar_service():
    creds = get_credentials()
    return build("calendar", "v3", credentials=creds)

def get_drive_service():
    creds = get_credentials()
    return build("drive", "v3", credentials=creds)
