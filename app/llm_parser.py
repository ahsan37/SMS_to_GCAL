import json
from openai import OpenAI
from .config import settings
from datetime import date

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def build_prompt(user_text: str) -> str:
    today = date.today().isoformat() 
    return f"""
    You are an assistant that extracts structured calendar event data from natural language text messages.

    Today’s date is {today}. If no explicit date is mentioned in the message, assume the event is for today.

    Respond ONLY with JSON using these keys:
    - title (string)
    - description (string, optional)
    - start (ISO8601 timestamp, e.g. '2025-07-06T14:00:00')
    - end (ISO8601 timestamp) OR durationMinutes (integer)

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
