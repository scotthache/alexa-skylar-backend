from fastapi import FastAPI, Request
import re

app = FastAPI()

SAMPLE_REPORT = """☀️ DAILY MORNING REPORT
Tuesday, April 14, 2026
════════════════════════════════════════════════════════════

📋 WEATHER
────────────────────────────────────────────────────────────
Wellesley, Ontario Weather:
Temperature: 20°C
Conditions: Sunny

📋 CALENDAR
────────────────────────────────────────────────────────────
No upcoming events today.

📋 EMAILS
────────────────────────────────────────────────────────────
No unread emails.

📋 SLACK
────────────────────────────────────────────────────────────
No Slack mentions today.

📋 TRELLO
────────────────────────────────────────────────────────────
No priority tasks.

════════════════════════════════════════════════════════════
Report generated at 05:18 PM
"""

def format_for_alexa(text: str) -> str:
    """Format report for Alexa"""
    intro = "Good morning Scott. It's Skylar with your morning report. "
    
    text = re.sub(r'═+', '', text)
    text = re.sub(r'─+', '', text)
    text = text.replace('DAILY MORNING REPORT', '')
    text = text.replace('Tuesday, April', '')
    text = text.replace('📋 WEATHER', 'WEATHER.')
    text = text.replace('📋 CALENDAR', 'CALENDAR.')
    text = text.replace('📋 EMAILS', 'EMAILS.')
    text = text.replace('📋 SLACK', 'SLACK.')
    text = text.replace('📋 TRELLO', 'PRIORITY TASKS.')
    text = text.replace('☀️', '')
    text = text.replace('•', '')
    
    lines = [line.strip() for line in text.split('\n') if line.strip() and 'Report generated' not in line]
    continuous = ' '.join(lines)
    continuous = re.sub(r'\s+', ' ', continuous)
    
    closing = " That's your complete morning briefing. Have a great day!"
    return intro + continuous + closing

@app.post("/alexa")
async def handle_alexa(request: Request):
    body = await request.json()
    intent_name = body.get('request', {}).get('intent', {}).get('name', '')
    
    text = "I'm not sure how to help with that."
    
    if intent_name == "ReadMorningReportIntent":
        text = format_for_alexa(SAMPLE_REPORT)
    
    return {
        "version": "1.0",
        "sessionAttributes": {},
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": text
            },
            "shouldEndSession": True
        }
    }

@app.get("/health")
async def health():
    return {"status": "ok"}
