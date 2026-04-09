import logging
from fastapi import FastAPI
from .sms_router import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(title="SMS → Google Calendar Bot")


@app.get("/health")
@app.head("/health")
def health():
    return {"status": "ok"}


app.include_router(router)
