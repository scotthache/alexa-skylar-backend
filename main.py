from fastapi import FastAPI
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
import subprocess
from datetime import datetime
import sys
import re

load_dotenv()

app = FastAPI()

class AlexaRequest(BaseModel):
    query: str

class AlexaResponse(BaseModel):
    speak: str

OPENCLAW_SESSION_KEY = os.getenv("OPENCLAW_SESSION_KEY", "default")
OPENCLAW_API_URL = os.getenv("OPENCLAW_API_URL", "http://localhost:8000")

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
        
        if result.returncode == 0:
            # Extract report between the === markers
            lines = result.stdout.split('\n')
            
            # Find start (DAILY MORNING REPORT line)
            start_idx = -1
            for i, line in enumerate(lines):
                if 'DAILY MORNING REPORT' in line:
                    start_idx = i - 1  # Include the === line
                    break
            
            # Find end (Report generated line)
            end_idx = len(lines)
            for i, line in enumerate(lines):
                if 'Report generated at' in line:
                    end_idx = i + 1
                    break
            
            if start_idx >= 0:
                report_text = '\n'.join(lines[start_idx:end_idx])
                return report_text
            
            return "I couldn't extract the morning report content."
        else:
            print(f"Script error: {result.stderr}", file=sys.stderr)
            return "There was an error generating the morning report."
    except subprocess.TimeoutExpired:
        return "The morning report took too long to generate. Please try again."
    except Exception as e:
        print(f"Error getting morning report: {e}", file=sys.stderr)
        return f"Sorry, I encountered an error. {str(e)[:80]}"

def format_for_alexa(text: str) -> str:
    """Format text for Alexa speech with proper pacing"""
    # Add intro
    intro = "Good morning Scott. It's Skylar with your morning report. "
    
    # Clean up visual separators
    text = re.sub(r'═+', '', text)
    text = re.sub(r'─+', '', text)
    text = text.replace('📋', '')
    text = text.replace('☀️', 'Weather:')
    text = text.replace('📅', 'Today\'s schedule:')
    text = text.replace('📧', 'Emails needing attention:')
    text = text.replace('💬', 'Slack mentions:')
    text = text.replace('📋', 'Priority tasks:')
    text = text.replace('•', '')
    text = text.replace('From:', 'From')
    text = text.replace('Subject:', 'Subject')
    
    # Remove extra whitespace
    text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
    
    # Combine intro + report
    full_text = intro + text
    
    # Limit to 5000 chars
    if len(full_text) > 5000:
        full_text = full_text[:4997] + "..."
    
    return full_text

@app.post("/alexa")
async def handle_alexa(req: AlexaRequest):
    """Handle Alexa requests"""
    query = req.query.strip()
    
    if not query:
        return AlexaResponse(speak="I didn't catch that. Could you repeat?")
    
    # Check for morning report intent
    if is_morning_report_query(query):
        report = get_morning_report()
        formatted = format_for_alexa(report)
        print(f"Alexa report length: {len(formatted)} chars", file=sys.stderr)
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
