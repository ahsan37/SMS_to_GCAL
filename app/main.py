import logging
from fastapi import FastAPI
from .sms_router import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(title="SMS → Google Calendar Bot")
app.include_router(router)
