from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PORT: int = 8000
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    OPENAI_API_KEY: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str
    GOOGLE_REFRESH_TOKEN: str
    TIMEZONE: str = "America/Los_Angeles"
    CALENDAR_ID: str = "primary"
    DRIVE_FOLDER_ID: str

    class Config:
        env_file = ".env"

settings = Settings()