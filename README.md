# SMS → Google Calendar 

Send messages to automatically create calendar events!

Uses FastAPI, OpenAI, Twilio & Google Calendar + Drive (for photos) API.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create `.env` file:**
   ```env
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   OPENAI_API_KEY=your_openai_api_key
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   GOOGLE_REFRESH_TOKEN=your_google_refresh_token
   DRIVE_FOLDER_ID=your_google_drive_folder_id
   TIMEZONE=America/Los_Angeles
   ```

3. **Enable Google APIs:**
   - Google Calendar API
   - Google Drive API

4. **Configure Twilio webhook:**
   - Point to: `https://your-domain.com/sms`

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

