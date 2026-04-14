from fastapi import FastAPI
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
import subprocess
from datetime import datetime

load_dotenv()

app = FastAPI()

class AlexaRequest(BaseModel):
    query: str

class AlexaResponse(BaseModel):
    speak: str

OPENCLAW_SESSION_KEY = os.getenv("OPENCLAW_SESSION_KEY", "default")
OPENCLAW_API_URL = os.getenv("OPENCLAW_API_URL", "http://localhost:8000")

def is_calendar_query(query: str) -> bool:
    """Check if query is about calendar"""
    keywords = ["calendar", "schedule", "meeting", "appointment", "event", "today", "tomorrow"]
    return any(k in query.lower() for k in keywords)

def is_morning_report_query(query: str) -> bool:
    """Check if query is asking for morning report"""
    keywords = ["morning report", "daily report", "read my report", "what's my report"]
    return any(k in query.lower() for k in keywords)

def get_morning_report() -> str:
    """Run the morning report script and get the text version"""
    try:
        result = subprocess.run([
            'python3',
            '/Users/scotthache/.openclaw/workspace/daily_morning_report.py'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            # Extract just the report content from output
            lines = result.stdout.split('\n')
            report_lines = []
            in_report = False
            
            for line in lines:
                if '═' in line and 'DAILY MORNING REPORT' in lines[lines.index(line):lines.index(line)+2] if lines.index(line) < len(lines)-1 else False:
                    in_report = True
                    continue
                if in_report and '✅ Daily Morning Report complete' in line:
                    break
                if in_report and line.strip():
                    report_lines.append(line)
            
            if report_lines:
                return '\n'.join(report_lines)
            else:
                return "I couldn't generate the morning report right now."
        else:
            return "There was an error generating the morning report."
    except Exception as e:
        print(f"Error getting morning report: {e}")
        return "Sorry, I couldn't retrieve the morning report at this time."

def format_for_alexa(text: str) -> str:
    """Format text for Alexa speech with proper pacing"""
    # Remove unnecessary characters and add pauses
    text = text.replace('═', '')
    text = text.replace('─', '')
    text = text.replace('•', '')
    
    # Add breaks between sections
    text = text.replace('☀️', '. ')
    text = text.replace('📅', '. Today\'s schedule: ')
    text = text.replace('📧', '. Emails needing attention: ')
    text = text.replace('💬', '. Slack mentions: ')
    text = text.replace('📋', '. Priority tasks: ')
    
    # Remove extra spaces
    text = ' '.join(text.split())
    
    # Limit to 3000 chars for Alexa (roughly 10 minutes of speech)
    if len(text) > 3000:
        text = text[:2997] + "..."
    
    return text

@app.post("/alexa")
async def handle_alexa(req: AlexaRequest):
    """
    Receive query from Alexa skill.
    Forward to OpenClaw or handle special intents.
    Return response.
    """
    query = req.query.strip()
    
    if not query:
        return AlexaResponse(speak="I didn't catch that. Could you repeat?")
    
    # Check for morning report intent
    if is_morning_report_query(query):
        report = get_morning_report()
        formatted = format_for_alexa(report)
        return AlexaResponse(speak=formatted)
    
    # Default: forward to OpenClaw
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OPENCLAW_API_URL}/sessions/send",
                json={
                    "sessionKey": OPENCLAW_SESSION_KEY,
                    "message": query,
                    "timeoutSeconds": 10
                },
                timeout=15.0
            )
            
            if response.status_code == 200:
                data = response.json()
                reply = data.get("message", "No response received")
                
                # Shorten for voice if needed
                if len(reply) > 500:
                    reply = reply[:497] + "..."
                
                return AlexaResponse(speak=reply)
            else:
                return AlexaResponse(speak="Sorry, I couldn't process that right now.")
    
    except Exception as e:
        print(f"Error: {e}")
        return AlexaResponse(speak="There was an error processing your request.")

@app.get("/health")
async def health():
    return {"status": "ok"}
