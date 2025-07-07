import logging
from fastapi import APIRouter, Request, Header, HTTPException, Response
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from .config import settings
from .llm_parser import parse_event
from .google_client import get_calendar_service, get_drive_service
from datetime import datetime, timedelta
import requests
from requests.auth import HTTPBasicAuth
from googleapiclient.http import MediaIoBaseUpload
import io

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/sms")
async def sms_webhook(
    request: Request,
    x_twilio_signature: str = Header(...),
):
    url = str(request.url)
    form = await request.form()
    data = dict(form)
    logger.info("Received SMS webhook at %s", url)

    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    if not validator.validate(url, data, x_twilio_signature):
        logger.warning("Invalid Twilio signature")
        raise HTTPException(400, "Invalid Twilio signature")

    body = data.get("Body", "").strip()
    logger.info("Incoming SMS body: %s", body)

    media_count = int(data.get("NumMedia", 0))
    downloaded_files = []
    for i in range(media_count):
        media_url = data[f"MediaUrl{i}"]
        resp = requests.get(
            media_url,
            auth=HTTPBasicAuth(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        )
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "application/octet-stream")
        name = media_url.split("/")[-1]
        downloaded_files.append((name, resp.content, ct))
    if downloaded_files:
        logger.info("Downloaded %d media files", len(downloaded_files))

    try:
        ev = await parse_event(body)
        logger.info("LLM parsed event: %s", ev)
        start = ev["start"]
        event = {
            "summary": ev["title"],
            "description": ev.get("description", ""),
            "start": {"dateTime": start, "timeZone": settings.TIMEZONE},
        }
        if "end" in ev:
            event["end"] = {"dateTime": ev["end"], "timeZone": settings.TIMEZONE}
        else:
            dt = datetime.fromisoformat(start)
            end_iso = (dt + timedelta(minutes=ev.get("durationMinutes", 60))).isoformat()
            event["end"] = {"dateTime": end_iso, "timeZone": settings.TIMEZONE}

        attachments = []
        if downloaded_files:
            drive_svc = get_drive_service()
            for idx, (orig_name, file_bytes, content_type) in enumerate(downloaded_files, start=1):
                ext = content_type.split("/")[-1]                       
                safe_title = ev["title"].lower().replace(" ", "_")      
                filename = f"{safe_title}_{idx}.{ext}"                  

                media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=content_type)
                meta = {
                    "name": filename,
                    "parents": [settings.DRIVE_FOLDER_ID],
                }
                file = drive_svc.files().create(
                    body=meta,
                    media_body=media,
                    fields="id,webViewLink"
                ).execute()

                file_id = file["id"]
                view_link = file.get("webViewLink")

                drive_svc.permissions().create(
                    fileId=file_id,
                    body={"role":"reader", "type":"anyone"}
                ).execute()

                attachments.append({
                    "fileUrl": view_link,
                    "title": filename
                })

            event["attachments"] = attachments
            logger.info("Built attachments: %s", attachments)


        cal_svc = get_calendar_service()
        created = cal_svc.events().insert(
            calendarId=settings.CALENDAR_ID,
            body=event,
            supportsAttachments=True
        ).execute()
        logger.info("Event created (ID=%s)", created.get("id"))
        reply = f"Created \"{ev['title']}\" at {start}"

    except Exception as e:
        logger.exception("Failed to process SMS webhook")
        reply = f"Error: {e}"

    twiml = MessagingResponse()
    twiml.message(reply)
    return Response(content=str(twiml), media_type="application/xml")
