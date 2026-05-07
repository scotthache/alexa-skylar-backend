from fastapi import FastAPI, Request
import re
from datetime import datetime
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

    def extract_section(name: str, next_sections=None):
        next_sections = next_sections or []
        if next_sections:
            next_alt = '|'.join(re.escape(s) for s in next_sections)
            pattern = rf'{re.escape(name)}(.*?)(?=\n[^\n]*(?:{next_alt})|\n?═|$)'
        else:
            pattern = rf'{re.escape(name)}(.*?)(?=\n?═|$)'
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else ''

    def section_bullets(section_text: str, prefix='•'):
        items = []
        for raw in section_text.splitlines():
            cleaned = raw.strip()
            if cleaned.startswith(prefix):
                items.append(cleaned[len(prefix):].strip())
        return items

    def spoken_temp_phrase(temp_text: str):
        temp_match = re.search(r'(-?\d+)°C', temp_text)
        feels_match = re.search(r'feels like (-?\d+)°C', temp_text, re.IGNORECASE)
        temp = int(temp_match.group(1)) if temp_match else None
        feels_like = int(feels_match.group(1)) if feels_match else None
        if temp is None:
            return '', None, None
        phrase = f'{temp} degrees'
        if feels_like is not None and feels_like != temp:
            phrase += f', feels like {feels_like}'
        return phrase, temp, feels_like if feels_like is not None else temp

    def spoken_forecast_phrase(forecast_text: str):
        match = re.search(r'High\s+(-?\d+)°C,\s+low\s+(-?\d+)°C,\s*(.*)', forecast_text, re.IGNORECASE)
        if match:
            return f'a high of {match.group(1)}, a low of {match.group(2)}, with {match.group(3).strip().lower()}'
        return forecast_text.lower().replace('°c', '')

    def natural_time_label(value: str):
        value = value.strip()
        try:
            dt = datetime.strptime(value, '%I:%M %p')
        except ValueError:
            return value

        hour = dt.hour
        minute = dt.minute
        if hour == 12 and minute == 0:
            return 'noon'
        if hour == 0 and minute == 0:
            return 'midnight'

        spoken_hour = hour % 12 or 12
        if minute == 0:
            return f"{spoken_hour} o'clock"
        return dt.strftime('%I:%M %p').lstrip('0').lower()

    def naturalize_calendar_event(event_text: str):
        match = re.match(r'(\d{1,2}:\d{2} [AP]M)–(\d{1,2}:\d{2} [AP]M):\s*(.*)', event_text)
        if not match:
            return event_text
        start, end, title = match.groups()
        start_spoken = natural_time_label(start)
        end_spoken = natural_time_label(end)
        if end_spoken in ('noon', 'midnight') or "o'clock" in end_spoken:
            return f'{title} from {start_spoken} to {end_spoken}'
        return f'{title} from {start_spoken} to {end_spoken}'

    def condense_news_item(item: str):
        item = re.sub(r'\s+', ' ', item).strip()
        if ' — ' in item:
            title, summary = item.split(' — ', 1)
            summary = re.sub(r'\[[^\]]*\]', '', summary).strip()
            first_sentence = re.split(r'(?<=[.!?])\s+', summary)[0].strip()
            first_sentence = first_sentence.rstrip(' .')
            if len(first_sentence) > 180:
                first_sentence = first_sentence[:177].rsplit(' ', 1)[0] + '...'
            return f'{title}. {first_sentence}.' if first_sentence else f'{title}.'
        return item.rstrip('.') + '.'

    date_match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), (.*?)\n', text)
    date_str = date_match.group(2) if date_match else 'today'

    condition = extract_line('Current conditions') or extract_line('Conditions')
    temp_line = extract_line('Temperature') or ''
    forecast_line = extract_line("Today's forecast") or ''
    rain_line = extract_line('Chance of rain') or '0%'
    wind_line = extract_line('Wind') or ''
    humidity_line = extract_line('Humidity') or ''

    temp_phrase, temp, feels_like = spoken_temp_phrase(temp_line)

    if not condition and forecast_line:
        forecast_parts = [part.strip() for part in forecast_line.split(',') if part.strip()]
        if forecast_parts:
            condition = forecast_parts[-1]
    if not condition:
        condition = 'the weather is doing its mysterious thing'

    rain_match = re.search(r'(\d+)%', rain_line)
    rain_chance = int(rain_match.group(1)) if rain_match else 0

    cond_lower = condition.lower()
    weather_adlib = ''
    if rain_chance >= 60 or 'rain' in cond_lower or 'shower' in cond_lower or 'drizzle' in cond_lower:
        weather_adlib = "It looks like an umbrella kind of day, unless you're in the mood for surprise character development. "
    elif temp is not None and temp < 0:
        weather_adlib = "It's below freezing, so dress warm unless you'd like to become part of the landscape. "
    elif temp is not None and temp <= 5:
        weather_adlib = "It's got a proper chill to it, so a good jacket is a smart move. "
    elif 'snow' in cond_lower or 'flurr' in cond_lower or 'ice' in cond_lower:
        weather_adlib = 'Watch your step out there. The weather is feeling a little dramatic. '
    elif 'sun' in cond_lower or 'clear' in cond_lower:
        weather_adlib = 'Pretty decent out there, by Ontario standards. '
    elif 'fog' in cond_lower or 'mist' in cond_lower:
        weather_adlib = "It's a bit murky, so maybe let the coffee wake up before the driving does. "

    calendar_events = section_bullets(extract_section('CALENDAR', ['EMAILS', 'LOCAL NEWS', 'WORLD NEWS', 'SLACK']))

    email_section = extract_section('EMAILS', ['LOCAL NEWS', 'WORLD NEWS', 'SLACK'])
    email_count = len(re.findall(r'•\s+From:', email_section))
    if email_count == 0:
        email_summary = 'Inbox is calm right now, which is always a nice way to start the day.'
    elif email_count == 1:
        email_summary = 'You have one email that looks like it wants attention.'
    else:
        email_summary = f'You have about {email_count} emails worth a look.'

    outlook_lines = section_bullets(extract_section('Next few days outlook:', ['📋 CALENDAR', 'CALENDAR', 'EMAILS', 'LOCAL NEWS', 'WORLD NEWS', 'SLACK']), prefix='-')
    local_news_items = section_bullets(extract_section('LOCAL NEWS', ['WORLD NEWS', "WHAT'S GOIN' ON IN THE AI WORLD", 'SLACK']))
    world_news_items = section_bullets(extract_section('WORLD NEWS', ["WHAT'S GOIN' ON IN THE AI WORLD", 'SLACK']))
    ai_world_items = section_bullets(extract_section("WHAT'S GOIN' ON IN THE AI WORLD", ['SLACK']))

    intro = f"Good morning Scott. You're listening to Skylar FM, coming to you live with your morning report for {date_str}. "

    weather = f"Starting with the weather: in Waterloo right now, it's {condition.lower()}"
    if temp_phrase:
        weather += f' and {temp_phrase}. '
    else:
        weather += '. '
    if forecast_line:
        weather += f"For today, expect {spoken_forecast_phrase(forecast_line)}. "
    if wind_line:
        weather += f'Wind is {wind_line}. '
    if humidity_line:
        weather += f'Humidity is at {humidity_line}. '
    weather += weather_adlib

    outlook = ''
    if outlook_lines:
        if len(outlook_lines) == 1:
            outlook = f"Looking a little farther out, {spoken_forecast_phrase(outlook_lines[0].split(': ', 1)[1]) if ': ' in outlook_lines[0] else outlook_lines[0]}. "
        else:
            chunks = []
            for item in outlook_lines:
                if ': ' in item:
                    day, details = item.split(': ', 1)
                    chunks.append(f'{day} brings {spoken_forecast_phrase(details)}')
                else:
                    chunks.append(item)
            outlook = 'For the next few days, ' + '; then '.join(chunks) + '. '

    if calendar_events:
        if len(calendar_events) == 1:
            calendar = f"Then on your schedule today, you've got {naturalize_calendar_event(calendar_events[0])}. "
        elif len(calendar_events) == 2:
            calendar = f"Then on your schedule today, you've got {naturalize_calendar_event(calendar_events[0])}, and {naturalize_calendar_event(calendar_events[1])}. "
        else:
            spoken_events = [naturalize_calendar_event(event) for event in calendar_events]
            calendar = "Then on your schedule today, you've got " + ', '.join(spoken_events[:-1]) + f", and {spoken_events[-1]}. "
    else:
        calendar = 'Then on the schedule, nothing major is booked, which is either peaceful or suspicious. '

    emails = 'Next up, ' + email_summary[:1].lower() + email_summary[1:] + ' '

    local_news = ''
    if local_news_items:
        local_bits = [condense_news_item(item) for item in local_news_items[:3]]
        local_news = 'In local news, ' + ' '.join(local_bits) + ' '

    world_news = ''
    if world_news_items:
        world_bits = [condense_news_item(item) for item in world_news_items[:3]]
        world_news = 'And around the world, ' + ' '.join(world_bits) + ' '

    ai_world = ''
    if ai_world_items:
        ai_bits = [condense_news_item(item) for item in ai_world_items[:3]]
        ai_world = "And now, what's goin' on in the AI world: " + ' '.join(ai_bits) + ' '

    closing = "That's the latest from the Skylar morning desk. Have a great day!"
    return intro + weather + outlook + calendar + emails + local_news + world_news + ai_world + closing


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
