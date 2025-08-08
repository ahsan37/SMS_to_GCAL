import logging
from fastapi import APIRouter, Request, Header, HTTPException, Response, FastAPI
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from .config import settings
from .llm_parser import parse_event
from .google_client import get_calendar_service, get_drive_service
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
from requests.auth import HTTPBasicAuth
from googleapiclient.http import MediaIoBaseUpload
import io

logger = logging.getLogger(__name__)
router = APIRouter()
app = FastAPI()

@app.head("/sms")
async def sms_head():
    return Response(status_code=200)

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

        local_tz = ZoneInfo(settings.TIMEZONE)
        current_time = datetime.now(local_tz)

        def ensure_local_iso8601(dt_str: str, fallback_to_now: bool = False) -> str:
            try:
                parsed = datetime.fromisoformat(dt_str)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=local_tz)
                else:
                    parsed = parsed.astimezone(local_tz)
                return parsed.replace(microsecond=0).isoformat()
            except Exception as e:
                if fallback_to_now:
                    logger.warning("Invalid datetime '%s', using current time: %s", dt_str, e)
                    return current_time.replace(microsecond=0).isoformat()
                raise

        # Check if the LLM returned a naive timestamp without time context
        start_parsed = datetime.fromisoformat(ev["start"].replace('Z', '+00:00') if ev["start"].endswith('Z') else ev["start"])
        logger.info("Analyzing LLM start time: '%s' (tzinfo: %s)", ev["start"], start_parsed.tzinfo)
        
        if start_parsed.tzinfo is None:
            # If no timezone info AND the text doesn't contain explicit time references, use current time
            time_keywords = ['at', 'pm', 'am', ':', 'tomorrow', 'today', 'tonight', 'morning', 'afternoon', 'evening']
            has_time_context = any(word in body.lower() for word in time_keywords)
            logger.info("Time context check - Message: '%s', Has time keywords: %s", body, has_time_context)
            
            if not has_time_context:
                logger.info("No explicit time in message, using current time: %s instead of LLM suggestion: %s", 
                           current_time.isoformat(), ev["start"])
                start_iso = current_time.replace(microsecond=0).isoformat()
            else:
                logger.info("Time context found, using LLM suggestion with timezone correction")
                start_iso = ensure_local_iso8601(ev["start"])
        else:
            logger.info("LLM provided timezone-aware timestamp, converting to local timezone")
            start_iso = ensure_local_iso8601(ev["start"])
            
        logger.info("Final start time: %s (%s)", start_iso, settings.TIMEZONE)

        event = {
            "summary": ev["title"],
            "description": ev.get("description", ""),
            "start": {"dateTime": start_iso, "timeZone": settings.TIMEZONE},
        }

        if "end" in ev:
            logger.info("🏁 LLM provided end time: %s", ev["end"])
            end_iso = ensure_local_iso8601(ev["end"])
            event["end"] = {"dateTime": end_iso, "timeZone": settings.TIMEZONE}
        else:
            duration_mins = ev.get("durationMinutes", 60)
            logger.info("No end time provided, using duration: %d minutes", duration_mins)
            start_dt_local = datetime.fromisoformat(start_iso)
            end_dt_local = start_dt_local + timedelta(minutes=duration_mins)
            end_iso = end_dt_local.replace(microsecond=0).isoformat()
            event["end"] = {"dateTime": end_iso, "timeZone": settings.TIMEZONE}
            
        logger.info("Final end time: %s (%s)", event["end"]["dateTime"], settings.TIMEZONE)

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


        logger.info("Sending event to Google Calendar:")
        logger.info("   Title: %s", event["summary"])
        logger.info("   Start: %s (%s)", event["start"]["dateTime"], event["start"]["timeZone"])
        logger.info("   End: %s (%s)", event["end"]["dateTime"], event["end"]["timeZone"])
        logger.info("   Calendar ID: %s", settings.CALENDAR_ID)
        
        cal_svc = get_calendar_service()
        created = cal_svc.events().insert(
            calendarId=settings.CALENDAR_ID,
            body=event,
            supportsAttachments=True
        ).execute()
        
        event_id = created.get("id")
        event_link = created.get("htmlLink", "")
        logger.info(" Event successfully created!")
        logger.info("   Event ID: %s", event_id)
        logger.info("   Event URL: %s", event_link)
        
        # Parse the start time for a friendly reply
        start_dt = datetime.fromisoformat(start_iso)
        friendly_time = start_dt.strftime("%I:%M %p on %m/%d/%Y").replace(" 0", " ").lstrip("0")
        reply = f" Created \"{ev['title']}\" at {friendly_time} ({settings.TIMEZONE})"

    except Exception as e:
        logger.exception("Failed to process SMS webhook")
        reply = f"Error: {e}"

    twiml = MessagingResponse()
    twiml.message(reply)
    return Response(content=str(twiml), media_type="application/xml")
