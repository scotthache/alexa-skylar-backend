from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/alexa")
async def handle_alexa(request: Request):
    body = await request.json()
    return {
        "version": "1.0",
        "sessionAttributes": {},
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": "Good morning Scott. It's Skylar. This is a test response."
            },
            "shouldEndSession": True
        }
    }

@app.get("/health")
async def health():
    return {"status": "ok"}
