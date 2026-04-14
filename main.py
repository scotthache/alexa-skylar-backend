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
Humidity: 60%
Wind: 17 km/h

📋 CALENDAR
────────────────────────────────────────────────────────────
 • 12:00 PM - Scott & Catherine - Open Elevate Q&A
 • 1:00 PM - The Boys & Catherine: LC communication & Elevate Billing

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
Report generated at 05:24 PM
"""

def format_for_alexa(text: str) -> str:
    """Format report for Alexa with natural language"""
    
    # Extract date
    date_match = re.search(r'(Tuesday|Wednesday|Thursday|Friday|Monday), (.*?)\n', text)
    date_str = date_match.group(2) if date_match else "today"
    
    # Extract weather
    weather_temp = re.search(r'Temperature: (\d+)°C', text)
    weather_cond = re.search(r'Conditions: (\w+)', text)
    temp = weather_temp.group(1) if weather_temp else "20"
    cond = weather_cond.group(1) if weather_cond else "sunny"
    
    # Extract calendar events
    calendar_section = re.search(r'📋 CALENDAR.*?(?=📋|════)', text, re.DOTALL)
    calendar_events = []
    if calendar_section:
        event_lines = re.findall(r'•\s+(.*?)(?:\n|$)', calendar_section.group(0))
        calendar_events = event_lines
    
    # Build natural response
    intro = f"Good morning Scott. It's Skylar with your morning report for {date_str}. "
    
    weather = f"The current weather in Wellesley is {temp} degrees and {cond.lower()}. "
    
    if calendar_events:
        calendar = "On your schedule today you have "
        for i, event in enumerate(calendar_events):
            if i == len(calendar_events) - 1:
                calendar += f"and {event}. "
            else:
                calendar += f"{event}, "
    else:
        calendar = "You have no events scheduled today. "
    
    closing = "Have a great day!"
    
    full = intro + weather + calendar + closing
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
                ("ssml" if output_type == "SSML" else "text"): text
            },
            "shouldEndSession": True
        }
    }

@app.get("/health")
async def health():
    return {"status": "ok"}
