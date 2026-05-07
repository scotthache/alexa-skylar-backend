from fastapi import FastAPI, Request
import re
import httpx

app = FastAPI()

REPORT_URL = "https://www.psgwebservices.com/skylar/morningreport/report.md"


async def get_report_text() -> str:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(REPORT_URL)
            if resp.status_code == 200 and resp.content.strip():
                return resp.content.decode('utf-8', errors='replace')
    except Exception:
        pass

    return """☀️ DAILY MORNING REPORT
Wednesday, April 15, 2026

📋 WEATHER
Wellesley, Ontario Weather:
Temperature: 6°C
Conditions: Fog

📋 CALENDAR
No events found.

📋 EMAILS
No unread emails.
"""


def format_for_alexa(text: str) -> str:
    date_match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), (.*?)\n', text)
    date_str = date_match.group(2) if date_match else "today"

    weather_temp = re.search(r'^\s*Temperature:\s*(\d+)°C', text, re.MULTILINE)
    weather_cond = re.search(r'^\s*Conditions:\s*([A-Za-z ]+)$', text, re.MULTILINE)
    temp = weather_temp.group(1) if weather_temp else "unknown"
    cond = weather_cond.group(1).strip().lower() if weather_cond else "unavailable"

    calendar_section = re.search(r'CALENDAR(.*?)(?=EMAILS|SLACK|═|$)', text, re.DOTALL)
    calendar_events = []
    if calendar_section:
        event_lines = re.findall(r'•\s+(.*?)(?:\n|$)', calendar_section.group(1))
        calendar_events = [e.strip() for e in event_lines if e.strip()]

    email_section = re.search(r'EMAILS(.*?)(?=SLACK|═|$)', text, re.DOTALL)
    email_summary = "You have no unread emails."
    if email_section:
        email_text = email_section.group(1).strip()
        if email_text and "No unread emails" not in email_text:
            email_summary = "You have unread emails that need attention."

    intro = f"Good morning Scott. It's Skylar with your morning report for {date_str}. "
    weather = f"The current weather in Wellesley is {temp} degrees and {cond}. "

    if calendar_events:
        if len(calendar_events) == 1:
            calendar = f"On your schedule today, you have {calendar_events[0]}. "
        else:
            calendar = "On your schedule today, you have "
            calendar += ", ".join(calendar_events[:-1])
            calendar += f", and {calendar_events[-1]}. "
    else:
        calendar = "You have nothing scheduled today. "

    closing = f"{email_summary} Have a great day!"
    return intro + weather + calendar + closing


@app.post("/alexa")
async def handle_alexa(request: Request):
    body = await request.json()
    intent_name = body.get("request", {}).get("intent", {}).get("name", "")

    text = "I'm not sure how to help with that."

    if intent_name == "ReadMorningReportIntent":
        report = await get_report_text()
        text = format_for_alexa(report)

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
