import logging
from fastapi import FastAPI, Response
from .sms_router import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(title="SMS → Google Calendar Bot")


@app.get("/health")
def health_head():
    return Response(status_code=200)


app.include_router(router)
