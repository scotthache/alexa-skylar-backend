from fastapi import FastAPI, Request
import re

app = FastAPI()

SKYLAR_IMAGE_URL = "https://drive.google.com/uc?export=view&id=1JPWChru2sYvAfStivzhtZdMecDGWQ9gT"

def get_cached_report() -> str:
    """Read the cached morning report"""
    try:
        with open('/Users/scotthache/.openclaw/workspace/alexa_report_cache.txt', 'r') as f:
            return f.read()
    except:
        return "The morning report is not available."

def format_for_alexa(text: str) -> str:
    """Format report for Alexa"""
    intro = "Good morning Scott. It's Skylar with your morning report. "
    
    text = re.sub(r'═+', '', text)
    text = re.sub(r'─+', '', text)
    text = text.replace('DAILY MORNING REPORT', '')
    text = text.replace('Tuesday, April', '')
    text = text.replace('Wednesday, April', '')
    text = text.replace('Thursday, April', '')
    text = text.replace('Friday, April', '')
    text = text.replace('Monday, April', '')
    text = text.replace('📋 WEATHER', 'WEATHER.')
    text = text.replace('📋 CALENDAR', 'CALENDAR.')
    text = text.replace('📋 EMAILS', 'EMAILS.')
    text = text.replace('📋 SLACK', 'SLACK.')
    text = text.replace('📋 TRELLO', 'PRIORITY TASKS.')
    text = text.replace('☀️', '')
    text = text.replace('📅', '')
    text = text.replace('📧', '')
    text = text.replace('💬', '')
    text = text.replace('•', '')
    
    lines = [line.strip() for line in text.split('\n') if line.strip() and 'Report generated' not in line]
    continuous = ' '.join(lines)
    continuous = re.sub(r'\s+', ' ', continuous)
    
    closing = " That's your complete morning briefing. Have a great day!"
    full = intro + continuous + closing
    
    if len(full) > 5000:
        full = full[:4997] + "..."
    
    return full

@app.post("/alexa")
async def handle_alexa(request: Request):
    body = await request.json()
    intent_name = body.get('request', {}).get('intent', {}).get('name', '')
    
    text = "I'm not sure how to help with that."
    
    if intent_name == "ReadMorningReportIntent":
        report = get_cached_report()
        text = format_for_alexa(report)
    
    return {
        "version": "1.0",
        "sessionAttributes": {},
        "response": {
            "outputSpeech": {
                "type": "SSML",
                "ssml": f'<speak><amazon:image id="Skylar" src="{SKYLAR_IMAGE_URL}"/>{text}</speak>'
            },
            "shouldEndSession": True
        }
    }

@app.get("/health")
async def health():
    return {"status": "ok"}
