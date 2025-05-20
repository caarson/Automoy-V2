import os, sys
from pathlib import Path
import socket

# Dynamically compute the project root and add it to the Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from core.operate import AutomoyOperator
import subprocess
import threading
import time
import shutil
import asyncio

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

# Track GUI visibility state (simple in-memory flag for demo)
GUI_VISIBLE = True
CONSOLE_LOG = []

@app.get("/show_gui")
async def show_gui():
    global GUI_VISIBLE
    GUI_VISIBLE = True
    return {"status": "shown"}

@app.get("/hide_gui")
async def hide_gui():
    global GUI_VISIBLE
    GUI_VISIBLE = False
    return {"status": "hidden"}

@app.get("/gui_state")
async def gui_state():
    return {"visible": GUI_VISIBLE}

@app.get("/console_output")
async def get_console_output():
    # Return the last 100 lines of console output
    return {"output": CONSOLE_LOG[-100:]}

# Utility to append to console log (thread-safe)
def append_console_log(line):
    if len(CONSOLE_LOG) > 1000:
        del CONSOLE_LOG[:500]
    CONSOLE_LOG.append(line)

# Example: wrap print to also log to GUI
import builtins
_builtin_print = builtins.print
def gui_print(*args, **kwargs):
    msg = ' '.join(str(a) for a in args)
    append_console_log(msg)
    _builtin_print(*args, **kwargs)
builtins.print = gui_print

# Endpoint to trigger screenshot (simulate hiding GUI, taking screenshot, then showing GUI)
@app.post("/take_screenshot")
async def take_screenshot(background_tasks: BackgroundTasks):
    # Hide GUI
    global GUI_VISIBLE
    GUI_VISIBLE = False
    # Simulate screenshot (replace with actual call if needed)
    def do_screenshot():
        time.sleep(1.5)  # Simulate screenshot delay
        # Show GUI again
        global GUI_VISIBLE
        GUI_VISIBLE = True
        append_console_log("[GUI] Screenshot taken, GUI restored.")
    background_tasks.add_task(do_screenshot)
    append_console_log("[GUI] Screenshot triggered, GUI hidden.")
    return {"status": "screenshot_in_progress", "refresh": True}

# Define paths to processed screenshot
OMNIPARSER_SCREENSHOT_PATH = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "core", "utils", "omniparser", "processed_screenshot.png")
LOCAL_SCREENSHOT_PATH = os.path.join(BASE_DIR, "static", "processed_screenshot.png")

@app.get("/get_latest_screenshot")
async def get_latest_screenshot():
    """Get the latest processed screenshot from OmniParser"""
    try:
        # Debug information
        print(f"Looking for screenshot at: {OMNIPARSER_SCREENSHOT_PATH}")
        print(f"Will save to: {LOCAL_SCREENSHOT_PATH}")
        
        # Check if the OmniParser screenshot exists
        if os.path.exists(OMNIPARSER_SCREENSHOT_PATH):
            # Get file stats for debugging
            stats = os.stat(OMNIPARSER_SCREENSHOT_PATH)
            size = stats.st_size
            last_modified = os.path.getmtime(OMNIPARSER_SCREENSHOT_PATH)
            print(f"Found screenshot: {size} bytes, last modified: {last_modified}")
            
            # Make sure target directory exists
            os.makedirs(os.path.dirname(LOCAL_SCREENSHOT_PATH), exist_ok=True)
            
            # Copy the file to static for serving
            shutil.copy2(OMNIPARSER_SCREENSHOT_PATH, LOCAL_SCREENSHOT_PATH)
            print(f"Screenshot copied to {LOCAL_SCREENSHOT_PATH}")
            
            # Verify the copy worked
            if os.path.exists(LOCAL_SCREENSHOT_PATH):
                copy_size = os.stat(LOCAL_SCREENSHOT_PATH).st_size
                print(f"Copy verified: {copy_size} bytes")
                
                # Return the path to the screenshot with a cache-busting query string
                screenshot_url = f"/static/processed_screenshot.png?t={last_modified}"
                print(f"Returning URL: {screenshot_url}")
                return {"status": "success", "screenshotUrl": screenshot_url}
            else:
                print("Copy failed: Destination file not found")
                return {"status": "error", "message": "Screenshot copy failed"}
        else:
            print(f"Screenshot not found at {OMNIPARSER_SCREENSHOT_PATH}")
            # As a fallback, check if we have a previous copy in static
            if os.path.exists(LOCAL_SCREENSHOT_PATH):
                print("Using previously saved screenshot instead")
                last_modified = os.path.getmtime(LOCAL_SCREENSHOT_PATH)
                return {"status": "success", "screenshotUrl": f"/static/processed_screenshot.png?t={last_modified}"}
            return {"status": "error", "message": "Screenshot not found"}
    except Exception as e:
        print(f"Error in get_latest_screenshot: {str(e)}")
        return {"status": "error", "message": str(e)}

# Create and start the AutomoyOperator in background
operator = AutomoyOperator()

@app.on_event("startup")
async def start_operator():
    # Start the operator loop in background
    asyncio.create_task(operator.startup_sequence())
    asyncio.create_task(operator.operate_loop())

# Endpoint to get operator state
@app.get("/operator_state")
async def get_operator_state():
    return {
        "objective": operator.objective,
        "last_action": operator.last_action,
        "current_screenshot": operator.current_screenshot,
        "coords": operator.coords,
    }

# Function to check if the GUI is already running
def is_gui_running():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        result = s.connect_ex(('127.0.0.1', 8000))
        if result == 0:
            print("[DEBUG] Port 8000 is already in use.")
        else:
            print("[DEBUG] Port 8000 is free.")
        return result == 0

# Prevent reinitialization if the GUI is already running
if is_gui_running():
    print("[GUI] Web GUI is already running. Exiting...")
    sys.exit(0)

# Ensure no browser is launched when the server starts
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False, log_level="info")
