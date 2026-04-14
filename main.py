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
Report generated at 05:20 PM
"""

def format_for_alexa(text: str) -> str:
    """Format report for Alexa with SSML"""
    intro = "Good morning Scott. <break time='500ms'/> It's Skylar with your morning report. <break time='1s'/> "
    
    text = re.sub(r'═+', '', text)
    text = re.sub(r'─+', '', text)
    text = text.replace('DAILY MORNING REPORT', '')
    text = text.replace('Tuesday, April', '')
    text = text.replace('📋 WEATHER', '<break time="500ms"/> Weather. ')
    text = text.replace('📋 CALENDAR', '<break time="500ms"/> Calendar. ')
    text = text.replace('📋 EMAILS', '<break time="500ms"/> Emails. ')
    text = text.replace('📋 SLACK', '<break time="500ms"/> Slack. ')
    text = text.replace('📋 TRELLO', '<break time="500ms"/> Priority Tasks. ')
    text = text.replace('☀️', '')
    text = text.replace('•', '')
    
    lines = [line.strip() for line in text.split('\n') if line.strip() and 'Report generated' not in line]
    continuous = ' '.join(lines)
    continuous = re.sub(r'\s+', ' ', continuous)
    
    closing = " <break time='500ms'/> That's your complete morning briefing. Have a great day!"
    full = intro + continuous + closing
    
    return f"<speak>{full}</speak>"

@app.post("/alexa")
async def handle_alexa(request: Request):
    body = await request.json()
    intent_name = body.get('request', {}).get('intent', {}).get('name', '')
    
    text = "I'm not sure how to help with that."
    output_type = "PlainText"
    
    if intent_name == "ReadMorningReportIntent":
        text = format_for_alexa(SAMPLE_REPORT)
        output_type = "SSML"
    
    return {
        "version": "1.0",
        "sessionAttributes": {},
        "response": {
            "outputSpeech": {
                "type": output_type,
                "ssml" if output_type == "SSML" else "text": text
            },
            "shouldEndSession": True
        }
    }

@app.get("/health")
async def health():
    return {"status": "ok"}
