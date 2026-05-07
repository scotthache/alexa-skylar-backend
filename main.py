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
    def extract_line(label: str):
        match = re.search(rf'^\s*{re.escape(label)}:\s*(.+)$', text, re.MULTILINE)
        return match.group(1).strip() if match else None

    date_match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), (.*?)\n', text)
    date_str = date_match.group(2) if date_match else "today"

    condition = extract_line('Current conditions') or extract_line('Conditions') or 'unavailable'
    temp_line = extract_line('Temperature') or 'unknown'
    forecast_line = extract_line("Today's forecast") or ''
    rain_line = extract_line('Chance of rain') or '0%'
    wind_line = extract_line('Wind') or ''
    humidity_line = extract_line('Humidity') or ''

    temp_match = re.search(r'(-?\d+)°C', temp_line)
    feels_match = re.search(r'feels like (-?\d+)°C', temp_line, re.IGNORECASE)
    temp = int(temp_match.group(1)) if temp_match else None
    feels_like = int(feels_match.group(1)) if feels_match else temp

    rain_match = re.search(r'(\d+)%', rain_line)
    rain_chance = int(rain_match.group(1)) if rain_match else 0

    cond_lower = condition.lower()
    weather_adlib = ""
    if rain_chance >= 60 or 'rain' in cond_lower or 'shower' in cond_lower or 'drizzle' in cond_lower:
        weather_adlib = "It looks like an umbrella kind of day, unless you're in the mood for surprise character development. "
    elif temp is not None and temp < 0:
        weather_adlib = "It's below freezing, so dress warm unless you'd like to become part of the landscape. "
    elif temp is not None and temp <= 5:
        weather_adlib = "It's got a proper chill to it, so a good jacket is a smart move. "
    elif 'snow' in cond_lower or 'flurr' in cond_lower or 'ice' in cond_lower:
        weather_adlib = "Watch your step out there. The weather is feeling a little dramatic. "
    elif 'sun' in cond_lower or 'clear' in cond_lower:
        weather_adlib = "Pretty decent out there, by Ontario standards. "
    elif 'fog' in cond_lower or 'mist' in cond_lower:
        weather_adlib = "It's a bit murky, so maybe let the coffee wake up before the driving does. "

    calendar_section = re.search(r'CALENDAR(.*?)(?=EMAILS|SLACK|═|$)', text, re.DOTALL)
    calendar_events = []
    if calendar_section:
        event_lines = re.findall(r'•\s+(.*?)(?:\n|$)', calendar_section.group(1))
        calendar_events = [e.strip() for e in event_lines if e.strip()]

    email_section = re.search(r'EMAILS(.*?)(?=SLACK|═|$)', text, re.DOTALL)
    email_summary = "Inbox is calm right now, which is always a nice way to start the day."
    if email_section:
        email_text = email_section.group(1).strip()
        email_count = len(re.findall(r'•\s+From:', email_text))
        if email_text and 'No unread emails' not in email_text and email_count > 0:
            if email_count == 1:
                email_summary = 'You have one unread email waiting for you.'
            else:
                email_summary = f'You have about {email_count} unread emails worth a look.'

    outlook_match = re.search(r'Next few days outlook:\n(.*?)(?=\n\s*📋|\n\s*SLACK|\n?═|$)', text, re.DOTALL)
    outlook_lines = []
    if outlook_match:
        for raw in outlook_match.group(1).splitlines():
            cleaned = raw.strip()
            if cleaned.startswith('- '):
                outlook_lines.append(cleaned[2:])

    intro = f"Good morning Scott. You're listening to Skylar FM, coming to you live with your morning report for {date_str}. "
    weather = f"In Waterloo right now, it's {condition.lower()} and {temp_line}. "
    if forecast_line:
        weather += f"For today, {forecast_line.lower()}. "
    if wind_line:
        weather += f"Wind is {wind_line}. "
    if humidity_line:
        weather += f"Humidity is sitting at {humidity_line}. "
    weather += weather_adlib

    if calendar_events:
        if len(calendar_events) == 1:
            calendar = f"On the schedule today, you've got {calendar_events[0]}. "
        elif len(calendar_events) == 2:
            calendar = f"On the schedule today, you've got {calendar_events[0]}, and {calendar_events[1]}. "
        else:
            calendar = "On the schedule today, you've got " + ", ".join(calendar_events[:-1]) + f", and {calendar_events[-1]}. "
    else:
        calendar = "Your calendar is clear today, which is either peaceful or suspicious. "

    outlook = ""
    if outlook_lines:
        if len(outlook_lines) == 1:
            outlook = f"Looking ahead, {outlook_lines[0]}. "
        else:
            outlook = "Looking ahead, " + "; then ".join(outlook_lines) + ". "

    closing = f"{email_summary} That's the latest from the Skylar morning desk. Have a great day!"
    return intro + weather + calendar + outlook + closing


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
