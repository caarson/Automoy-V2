\
"""
Minimal OmniParser server with FastAPI on port 8000.

Exposes /probe/ (health check) and a placeholder /parse/ route.
"""
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/probe/")
def probe():
    return {"status": "ok"}

@app.post("/parse/")
def parse_image():
    # Placeholder for parsing logic
    # You can load YOLO model + caption model here
    return {"screen_info": "Parsed screen info goes here"}

if __name__ == "__main__":
    uvicorn.run("omniparserserver.server:app", host="0.0.0.0", port=8000, reload=False)
