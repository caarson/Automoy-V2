import os
import sys
import pathlib
# Add project root to sys.path so `import core.operate` works
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import webbrowser
import threading
import shutil
from pathlib import Path
import socket
from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from core.operate import AutomoyOperator
import subprocess
import time
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import uvicorn  # add uvicorn import
import webview  # for borderless GUI window

# Add the parent directory to sys.path to resolve imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Define base directory (where this script lives)
BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.txt")

app = FastAPI()

# Mount static files (CSS/JS) and HTML templates
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static"), html=False, check_dir=True),
    name="static",
)
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

@app.get("/processed_screenshot.png")
async def processed_screenshot():  # corrected signature
    """Serve the latest processed screenshot with debug info."""
    file_path = PROJECT_ROOT / "core" / "utils" / "omniparser" / "processed_screenshot.png"
    exists = file_path.exists()
    print(f"[DEBUG] processed_screenshot endpoint called. Path: {file_path}, exists: {exists}")
    if exists:
        print("[DEBUG] Serving updated processed_screenshot.png")
        # Prevent caching to ensure fresh frames
        return FileResponse(
            str(file_path),
            media_type="image/png",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )
    else:
        return JSONResponse({"status": "not_found"}, status_code=404)

@app.get("/get_latest_screenshot")
async def get_latest_screenshot():
    """Return JSON with screenshotUrl and debug info."""
    file_path = PROJECT_ROOT / "core" / "utils" / "omniparser" / "processed_screenshot.png"
    exists = file_path.exists()
    print(f"[DEBUG] get_latest_screenshot called. Path: {file_path}, exists: {exists}")
    if exists:
        return JSONResponse({"status": "success", "screenshotUrl": "/processed_screenshot.png"})
    else:
        return JSONResponse({"status": "no_screenshot", "message": "No screenshot available"})

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

# Add an endpoint to set the objective
@app.post("/set_objective")
async def set_objective(data: dict):
    objective = data.get("objective")
    if objective:
        operator.objective = objective
        print(f"[INFO] Objective set to: {objective}")
        return {"status": "success", "objective": objective}
    return {"status": "error", "message": "No objective provided"}

# Health check endpoint to confirm GUI is running
@app.get("/health")
async def health():
    return {"status": "ok"}

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

# Helper to get local LAN IP for display in borderless window
def _get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

# Server binds to all interfaces; display window uses the LAN IP
SERVER_HOST = "0.0.0.0"
DISPLAY_HOST = _get_local_ip()

# Launch server and open a frameless desktop window via PyWebView
def launch_gui():
    # Start Uvicorn server on all interfaces
    def start_server():
        uvicorn.run(app, host="0.0.0.0", port=8000, reload=False, log_level="info")
    threading.Thread(target=start_server, daemon=True).start()
    # Wait for server to be ready
    import requests
    while True:
        try:
            resp = requests.get("http://127.0.0.1:8000/health", timeout=1)
            if resp.status_code == 200:
                break
        except Exception:
            time.sleep(0.5)
    # Build URL using local IP so the same server is reachable remotely
    url = f"http://{DISPLAY_HOST}:8000"
    print(f"[GUI] Opening borderless window on: {url}")
    # Create a PyWebView window
    # Assign the created window to a variable that on_loaded can access
    created_window_ref = webview.create_window(
        "Automoy",
        "http://127.0.0.1:8000",
        width=1024,  # Reduced from 1280
        height=576,  # Reduced from 720
        frameless=True,
        easy_drag=True,
        text_select=True
    )

    def on_loaded():
        print("[INFO] Webview DOM loaded. Applying zoom...")
        # Now created_window_ref should be accessible here
        if created_window_ref: 
            created_window_ref.evaluate_js("document.body.style.zoom = '70%'")

    if created_window_ref: 
        created_window_ref.events.loaded += on_loaded

    webview.start(debug=False)  # Changed debug to False

if __name__ == "__main__":
    launch_gui()

# Watcher to sync processed_screenshot into GUI static folder
class ScreenshotEventHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('processed_screenshot.png'):
            try:
                target = PROJECT_ROOT / 'gui' / 'static' / 'processed_screenshot.png'
                shutil.copy2(event.src_path, target)
                print(f"[DEBUG] Detected new processed image, copied to GUI static: {target}")
            except Exception as e:
                print(f"[ERROR] Failed to copy processed screenshot: {e}")

# Start the watcher before launching the server
watch_dir = PROJECT_ROOT / 'core' / 'utils' / 'omniparser'
observer = Observer()
observer.schedule(ScreenshotEventHandler(), path=str(watch_dir), recursive=False)
observer.daemon = True
observer.start()

# Ensure no browser is launched when the server starts
if __name__ == "__main__":
    launch_gui()
