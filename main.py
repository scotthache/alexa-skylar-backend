from fastapi import FastAPI, Request
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
import subprocess
import sys
import re
import json

load_dotenv()

app = FastAPI()

OPENCLAW_SESSION_KEY = os.getenv("OPENCLAW_SESSION_KEY", "default")
OPENCLAW_API_URL = os.getenv("OPENCLAW_API_URL", "http://localhost:8000")
SKYLAR_IMAGE_URL = "https://drive.google.com/uc?export=view&id=1JPWChru2sYvAfStivzhtZdMecDGWQ9gT"

def get_morning_report() -> str:
    """Get morning report from Mac via SSH"""
    try:
        # SSH into Mac and run the report script
        result = subprocess.run([
            'ssh', 
            'scotthache@skylar.local',
            'python3 /Users/scotthache/.openclaw/workspace/daily_morning_report.py'
        ], capture_output=True, text=True, timeout=60)
        
        print(f"SSH return code: {result.returncode}", file=sys.stderr)
        
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
                return '\n'.join(lines[start_idx:end_idx])
        
        return "Unable to generate morning report"
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return "Error generating report"

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

def build_alexa_response(text: str, should_end: bool = True) -> dict:
    """Build proper Alexa response format"""
    return {
        "version": "1.0",
        "sessionAttributes": {},
        "response": {
            "outputSpeech": {
                "type": "SSML",
                "ssml": f'<speak><amazon:image id="Skylar" src="{SKYLAR_IMAGE_URL}"/>{text}</speak>'
            },
            "shouldEndSession": should_end
        }
    }

@app.post("/alexa")
async def handle_alexa(request: Request):
    """Handle Alexa skill request"""
    try:
        body = await request.json()
        
        intent_name = body.get('request', {}).get('intent', {}).get('name', '')
        intent_slots = body.get('request', {}).get('intent', {}).get('slots', {})
        
        # Handle morning report intent
        if intent_name == "ReadMorningReportIntent":
            report = get_morning_report()
            formatted = format_for_alexa(report)
            return build_alexa_response(formatted)
        
        # Handle ask skylar intent
        if intent_name == "AskSkylarIntent":
            query = ""
            if 'query' in intent_slots:
                query = intent_slots['query'].get('value', '')
            
            if query and any(k in query.lower() for k in ["morning report", "daily report", "read my report"]):
                report = get_morning_report()
                formatted = format_for_alexa(report)
                return build_alexa_response(formatted)
            
            # Forward to OpenClaw
            if query:
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
                            reply = data.get("message", "No response")
                            if len(reply) > 500:
                                reply = reply[:497] + "..."
                            return build_alexa_response(reply)
                except:
                    pass
        
        return build_alexa_response("I'm not sure how to help with that.")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return build_alexa_response("There was an error processing your request.")

@app.get("/health")
async def health():
    return {"status": "ok"}
