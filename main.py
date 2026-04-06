cat > main.py << 'EOF'
from fastapi import FastAPI
from pydantic import BaseModel
import subprocess
import json
from datetime import datetime

app = FastAPI()

class AlexaRequest(BaseModel):
    query: str

class AlexaResponse(BaseModel):
    speak: str

@app.post("/alexa")
async def handle_alexa(req: AlexaRequest):
    query = req.query.strip()
    
    # Test: just return the query back
    return AlexaResponse(speak=f"You asked: {query}")

@app.post("/test-calendar")
async def test_calendar():
    """Test endpoint to debug calendar"""
    try:
        result = subprocess.run(
            ["gog", "calendar", "list", "--account", "scott@platinumsynergy.ca", "--json", "--max", "1"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return {"error": f"gog failed: {result.stderr}"}
        
        data = json.loads(result.stdout)
        events = data.get("events", [])
        
        if not events:
            return {"error": "No events"}
        
        event = events[0]
        summary = event.get("summary", "NO SUMMARY")
        
        return {
            "success": True,
            "summary": summary,
            "raw_event": event
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
async def health():
    return {"status": "ok"}
EOF


[paste the code above]
