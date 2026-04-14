from fastapi import FastAPI
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
import subprocess
from datetime import datetime
import sys

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
        ], capture_output=True, text=True, timeout=60)
        
        print(f"Script return code: {result.returncode}", file=sys.stderr)
        print(f"STDOUT length: {len(result.stdout)}", file=sys.stderr)
        print(f"STDERR: {result.stderr[:500]}", file=sys.stderr)
        
        if result.returncode == 0:
            # Find the actual report content (between === lines)
            lines = result.stdout.split('\n')
            report_start = -1
            report_end = -1
            
            for i, line in enumerate(lines):
                if '═' in line and 'DAILY MORNING REPORT' in ''.join(lines[max(0,i-1):i+2]):
                    report_start = i
                if report_start > -1 and i > report_start and '═' in line and 'Report generated' in ''.join(lines[max(0,i-1):i+2]):
                    report_end = i
                    break
            
            if report_start > -1:
                report_lines = lines[report_start:report_end if report_end > -1 else len(lines)]
                report_text = '\n'.join(report_lines)
                if len(report_text.strip()) > 100:
                    return report_text
            
            return "I couldn't generate the complete morning report. Please try again."
        else:
            print(f"Script error: {result.stderr}", file=sys.stderr)
            return "There was an error generating the morning report."
    except subprocess.TimeoutExpired:
        return "The morning report took too long to generate. Please try again."
    except Exception as e:
        print(f"Error getting morning report: {e}", file=sys.stderr)
        return f"Sorry, I couldn't retrieve the morning report. Error: {str(e)[:100]}"

def format_for_alexa(text: str) -> str:
    """Format text for Alexa speech with proper pacing"""
    # Remove unnecessary characters
    text = text.replace('═', '')
    text = text.replace('─', '')
    text = text.replace('•', '')
    
    # Add pauses between sections
    text = text.replace('☀️', '. Weather. ')
    text = text.replace('📅', '. Schedule. ')
    text = text.replace('📧', '. Emails. ')
    text = text.replace('💬', '. Slack mentions. ')
    text = text.replace('📋', '. Priority tasks. ')
    
    # Remove extra spaces
    text = ' '.join(text.split())
    
    # Limit to 5000 chars for Alexa (roughly 15 minutes of speech)
    if len(text) > 5000:
        text = text[:4997] + "..."
    
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
        print(f"Error: {e}", file=sys.stderr)
        return AlexaResponse(speak="There was an error processing your request.")

@app.get("/health")
async def health():
    return {"status": "ok"}
