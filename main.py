from fastapi import FastAPI
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
import subprocess
from datetime import datetime
import sys
import re
import json

load_dotenv()

app = FastAPI()

class AlexaRequest(BaseModel):
    query: str = None
    request: dict = None

class AlexaResponse(BaseModel):
    speak: str

OPENCLAW_SESSION_KEY = os.getenv("OPENCLAW_SESSION_KEY", "default")
OPENCLAW_API_URL = os.getenv("OPENCLAW_API_URL", "http://localhost:8000")

# Skylar's avatar image from Google Drive
SKYLAR_IMAGE_URL = "https://drive.google.com/uc?export=view&id=1JPWChru2sYvAfStivzhtZdMecDGWQ9gT"

def is_morning_report_query(query: str) -> bool:
    """Check if query is asking for morning report"""
    if not query:
        return False
    keywords = ["morning report", "daily report", "read my report", "what's my report", "read report", "morning briefing"]
    return any(k in query.lower() for k in keywords)

def get_morning_report() -> str:
    """Run the morning report script and get the text version"""
    try:
        print(f"DEBUG: Starting morning report generation", file=sys.stderr)
        
        result = subprocess.run([
            'python3',
            '/Users/scotthache/.openclaw/workspace/daily_morning_report.py'
        ], capture_output=True, text=True, timeout=60)
        
        print(f"DEBUG: Script returned code {result.returncode}", file=sys.stderr)
        print(f"DEBUG: STDOUT length: {len(result.stdout)}", file=sys.stderr)
        
        if result.returncode == 0 and result.stdout:
            lines = result.stdout.split('\n')
            start_idx = -1
            for i, line in enumerate(lines):
                if 'DAILY MORNING REPORT' in line:
                    start_idx = i
                    break
            
            end_idx = len(lines)
            for i, line in enumerate(lines):
                if 'Report generated at' in line:
                    end_idx = i + 1
                    break
            
            if start_idx >= 0:
                report_text = '\n'.join(lines[start_idx:end_idx])
                return report_text
            else:
                return "I couldn't extract the morning report content."
        else:
            return "There was an error generating the morning report."
    except subprocess.TimeoutExpired:
        return "The morning report took too long to generate."
    except Exception as e:
        print(f"DEBUG: Exception: {str(e)}", file=sys.stderr)
        return f"Error generating report"

def format_for_alexa(text: str) -> str:
    """Format text for Alexa speech as one continuous flow"""
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
    text = text.replace('From:', 'From')
    text = text.replace('Subject:', 'Subject')
    
    lines = [line.strip() for line in text.split('\n') if line.strip() and 'Report generated' not in line]
    continuous_text = ' '.join(lines)
    continuous_text = re.sub(r'(WEATHER|CALENDAR|EMAILS|SLACK|PRIORITY TASKS)\.', r'\1. ', continuous_text)
    continuous_text = re.sub(r'\s+', ' ', continuous_text)
    
    closing = " That's your complete morning briefing. Have a great day!"
    full_text = intro + continuous_text + closing
    
    if len(full_text) > 5000:
        full_text = full_text[:4997] + "..."
    
    return full_text

def add_image_to_ssml(text: str) -> str:
    """Wrap text in SSML with image for Echo Show devices"""
    ssml = f'<speak><amazon:image id="Skylar" src="{SKYLAR_IMAGE_URL}"/>{text}</speak>'
    return ssml

@app.post("/alexa")
async def handle_alexa(req: dict):
    """Handle Alexa requests - accept raw JSON"""
    print(f"DEBUG: Received request: {json.dumps(req)[:200]}", file=sys.stderr)
    
    query = None
    
    # Try to extract query from different formats
    if isinstance(req, dict):
        query = req.get('query')
        if not query and 'request' in req:
            # Alexa skill format
            request_obj = req['request']
            if 'intent' in request_obj:
                intent_name = request_obj['intent'].get('name', '')
                print(f"DEBUG: Intent name: {intent_name}", file=sys.stderr)
                
                if intent_name == 'ReadMorningReportIntent':
                    report = get_morning_report()
                    formatted = format_for_alexa(report)
                    formatted = add_image_to_ssml(formatted)
                    return AlexaResponse(speak=formatted)
                
                # Check intent slots for query
                if 'slots' in request_obj['intent']:
                    slots = request_obj['intent']['slots']
                    if 'query' in slots:
                        query = slots['query'].get('value')
            
            # Also check for utterance text
            if 'intent' in request_obj and not query:
                intent_name = request_obj['intent'].get('name', '')
                # Fallback: if we got here with intent name, respond accordingly
                if intent_name:
                    print(f"DEBUG: No query found, intent was {intent_name}", file=sys.stderr)
    
    if not query:
        query = ""
    
    query = str(query).strip()
    print(f"DEBUG: Query extracted: '{query}'", file=sys.stderr)
    
    if not query:
        return AlexaResponse(speak="I didn't catch that. Could you repeat?")
    
    # Check for morning report
    if is_morning_report_query(query):
        print(f"DEBUG: Detected morning report query", file=sys.stderr)
        report = get_morning_report()
        formatted = format_for_alexa(report)
        formatted = add_image_to_ssml(formatted)
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
