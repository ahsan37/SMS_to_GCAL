import json
import logging
from openai import OpenAI
from .config import settings
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
client = OpenAI(api_key=settings.OPENAI_API_KEY)

def build_prompt(user_text: str) -> str:
    local_tz = ZoneInfo(settings.TIMEZONE)
    now_local = datetime.now(local_tz)
    today = now_local.date().isoformat()
    now_iso_with_tz = now_local.replace(microsecond=0).isoformat()
    return f"""
    You are an assistant that extracts structured calendar event data from natural language text messages.

    Current context:
    - Timezone: {settings.TIMEZONE}
    - Today's date: {today}
    - Current datetime: {now_iso_with_tz}

    CRITICAL: If no explicit time is mentioned in the message, use the current datetime above as the start time.

    Respond ONLY with JSON using these keys:
    - title (string)
    - description (string, optional)
    - start (ISO8601 timestamp WITH timezone offset, e.g. '2025-07-06T14:00:00-07:00')
    - end (ISO8601 timestamp WITH timezone offset) OR durationMinutes (integer, default to 60 if not specified)

    Examples:
    - "work test" → start should be "{now_iso_with_tz}" (current time)
    - "dinner at 7pm" → start should be "2025-07-06T19:00:00-07:00" (7pm today)
    - "meeting tomorrow 2pm" → start should be tomorrow at 2pm with timezone offset

    MANDATORY RULES:
    1. ALWAYS include timezone offset in timestamps (never use 'Z' or naive timestamps)
    2. Use {settings.TIMEZONE} timezone for all times unless message specifies otherwise
    3. If message has NO TIME specified, use current datetime: {now_iso_with_tz}

    Input message: \"{user_text}\"
    """

async def parse_event(text: str) -> dict:
    local_tz = ZoneInfo(settings.TIMEZONE)
    current_time = datetime.now(local_tz)
    logger.info("Parsing event at %s (%s) for text: '%s'", 
                current_time.isoformat(), settings.TIMEZONE, text)
    
    prompt = build_prompt(text)
    logger.debug("LLM prompt context - Current time: %s, Timezone: %s", 
                 current_time.isoformat(), settings.TIMEZONE)

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user",   "content": text},
        ],
        temperature=0,
    )
    raw = resp.choices[0].message.content.strip()
    logger.info("LLM raw response: %s", raw)

    if raw.startswith("```json"):
        raw = raw[len("```json"):].strip()
    if raw.endswith("```"):
        raw = raw[:-3].strip()
        
    parsed_event = json.loads(raw)
    logger.info("LLM parsed event: %s", parsed_event)
    
    # Log timezone analysis of the returned start time
    try:
        start_dt = datetime.fromisoformat(parsed_event["start"].replace('Z', '+00:00') if parsed_event["start"].endswith('Z') else parsed_event["start"])
        if start_dt.tzinfo is None:
            logger.warning("LLM returned NAIVE timestamp (no timezone): %s", parsed_event["start"])
        else:
            logger.info("LLM returned timezone-aware timestamp: %s (offset: %s)", 
                       parsed_event["start"], start_dt.strftime('%z'))
    except Exception as e:
        logger.error("Invalid timestamp format from LLM: %s - %s", parsed_event["start"], e)
    
    return parsed_event      
