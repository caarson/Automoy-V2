from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

# Define base directory (where this script lives)
BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.txt")

app = FastAPI()

# Mount static files (CSS/JS) and HTML templates
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/command")
async def main_command(command: str = Form(...)):
    print(f"Main command received: {command}")
    return {"status": "success", "message": f"Command '{command}' received."}

@app.post("/correction")
async def correction_command(message: str = Form(...)):
    print(f"Correction message received: {message}")
    return {"status": "success", "message": f"Correction '{message}' received."}

@app.post("/temperature")
async def set_temperature(value: float = Form(...)):
    # Update config.txt
    lines = []
    with open(CONFIG_PATH, "r") as f:
        lines = f.readlines()
    with open(CONFIG_PATH, "w") as f:
        for line in lines:
            if line.strip().startswith("TEMPERATURE:"):
                f.write(f"TEMPERATURE: {value}\n")
            else:
                f.write(line)
    print(f"Temperature updated to {value}")
    return {"status": "success", "value": value}
