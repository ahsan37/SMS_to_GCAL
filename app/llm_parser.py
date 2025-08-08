import json
from openai import OpenAI
from .config import settings
from datetime import datetime
from zoneinfo import ZoneInfo

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def build_prompt(user_text: str) -> str:
    local_tz = ZoneInfo(settings.TIMEZONE)
    now_local = datetime.now(local_tz)
    today = now_local.date().isoformat()
    now_iso_with_tz = now_local.replace(microsecond=0).isoformat()
    return f"""
    You are an assistant that extracts structured calendar event data from natural language text messages.

    Timezone: {settings.TIMEZONE}. Today's date is {today} and the current datetime is {now_iso_with_tz} (use this timezone for relative phrases like "today", "tomorrow", or "now").

    If no explicit date or time is mentioned in the message, assume the event starts at the current datetime above. If no duration is specified, assume 1 hour.

    Respond ONLY with JSON using these keys:
    - title (string)
    - description (string, optional)
    - start (ISO8601 timestamp WITH timezone offset, e.g. '2025-07-06T14:00:00-07:00')
    - end (ISO8601 timestamp WITH timezone offset) OR durationMinutes (integer, default to 60 if not specified)

    Rules:
    - Always include a timezone offset in timestamps (no 'Z' unless the time is truly UTC; prefer the offset for {settings.TIMEZONE}).
    - Interpret all dates/times in the {settings.TIMEZONE} timezone unless another timezone is explicitly stated in the message.

    Input message: \"{user_text}\"
    """

async def parse_event(text: str) -> dict:
    prompt = build_prompt(text)

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user",   "content": text},
        ],
        temperature=0,
    )
    raw = resp.choices[0].message.content.strip()

    
    if raw.startswith("```json"):
        raw = raw[len("```json"):].strip()
    if raw.endswith("```"):
        raw = raw[:-3].strip()
        
    print(raw)
    return json.loads(raw)      
