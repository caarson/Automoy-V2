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
from fastapi import FastAPI, Request, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
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

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Mount static files and templates ---
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static"), html=False, check_dir=True), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# --- Global state for Automoy GUI ---
current_objective: str = ""
operator_status: str = "Idle" # Idle, Running, Paused, Error
gui_log_messages: List[str] = [] # For general logs in GUI

# New state variables for multi-stage reasoning display
current_visual_analysis: str = "Waiting for visual analysis..."
current_thinking_process: str = "Waiting for thinking process..."
current_steps_generated: List[str] = [] # Store as a list of strings
current_operation_display: str = "No operation active."
past_operation_display: str = "No past operations yet."
processed_screenshot_available: bool = False


class ObjectiveData(BaseModel):
    objective: str

class LogMessage(BaseModel):
    message: str

class StateUpdateText(BaseModel):
    text: str

class StateUpdateSteps(BaseModel):
    steps: List[str]

@app.post("/set_objective")
async def set_objective_endpoint(data: ObjectiveData):
    global current_objective, operator_status
    global current_visual_analysis, current_thinking_process, current_steps_generated
    global current_operation_display, past_operation_display, processed_screenshot_available

    current_objective = data.objective
    operator_status = "Running" # Assume it starts running once objective is set
    
    # Clear previous state when a new objective is set
    current_visual_analysis = "Processing new objective..."
    current_thinking_process = ""
    current_steps_generated = []
    current_operation_display = "Initiating..."
    past_operation_display = "" # Clear past operations for new objective
    processed_screenshot_available = False # Reset screenshot status

    print(f"[GUI] Objective received: {current_objective}")
    return {"message": "Objective set and state cleared", "objective": current_objective}

@app.post("/state/visual")
async def update_visual_state(data: StateUpdateText):
    global current_visual_analysis
    current_visual_analysis = data.text
    return {"message": "Visual analysis updated"}

@app.post("/state/thinking")
async def update_thinking_state(data: StateUpdateText):
    global current_thinking_process
    current_thinking_process = data.text
    return {"message": "Thinking process updated"}

@app.post("/state/steps")
async def update_steps_state(data: StateUpdateSteps):
    global current_steps_generated
    current_steps_generated = data.steps
    return {"message": "Steps updated"}

@app.post("/state/current_operation")
async def update_current_operation_state(data: StateUpdateText):
    global current_operation_display, past_operation_display
    # When a new current operation comes in, the old current becomes the new past.
    past_operation_display = current_operation_display 
    current_operation_display = data.text
    return {"message": "Current and past operations updated"}

# This specific endpoint for past_operation might be redundant if current_operation updates past_operation.
# However, keeping it allows explicit setting of past_operation if needed for some reason.
@app.post("/state/past_operation")
async def update_past_operation_state(data: StateUpdateText):
    global past_operation_display
    past_operation_display = data.text
    return {"message": "Past operation updated"}

@app.post("/state/screenshot_processed")
async def screenshot_processed_notification():
    global processed_screenshot_available
    processed_screenshot_available = True
    return {"message": "Screenshot processed and available"}

@app.post("/state/clear_all_operational_data")
async def clear_all_operational_data():
    global current_visual_analysis, current_thinking_process, current_steps_generated
    global current_operation_display, past_operation_display, processed_screenshot_available
    current_visual_analysis = "Waiting for visual analysis..."
    current_thinking_process = "Waiting for thinking process..."
    current_steps_generated = []
    current_operation_display = "No operation active."
    past_operation_display = "No past operations yet."
    processed_screenshot_available = False
    # current_objective and operator_status might be preserved or reset based on desired logic
    # For now, this focuses on the operational display fields.
    return {"message": "Operational display data cleared"}


@app.get("/operator_state")
async def get_operator_state():
    global processed_screenshot_available
    screenshot_path = os.path.join(BASE_DIR, "static", "processed_screenshot.png")
    if os.path.exists(screenshot_path) and os.path.getsize(screenshot_path) > 0:
        processed_screenshot_available = True
    else:
        processed_screenshot_available = False
        
    return {
        "objective": current_objective,
        "status": operator_status,
        "log_messages": gui_log_messages[-20:],  # Return last 20 log messages
        "visual_analysis": current_visual_analysis,
        "thinking_process": current_thinking_process,
        "steps_generated": current_steps_generated,
        "current_operation": current_operation_display,
        "past_operation": past_operation_display,
        "screenshot_available": processed_screenshot_available
    }

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

# Health check endpoint to confirm GUI is running
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Serve index.html
@app.get("/")
async def serve_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

def get_local_ip():
    """Attempt to get the local IP address."""
    try:
        # Connect to an external host (doesn't actually send data)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(("8.8.8.8", 80)) # Google DNS
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1" # Fallback

# Store the window reference globally so on_loaded can access it
created_window_ref = None

def run_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    server.run()

def start_gui():
    global created_window_ref
    local_ip = get_local_ip()
    window_title = f"Automoy - Access via http://{local_ip}:8000 or http://127.0.0.1:8000"

    uvicorn_thread = threading.Thread(target=run_server, daemon=True)
    uvicorn_thread.start()

    created_window_ref = webview.create_window(
        window_title, # Use dynamic title
        "http://127.0.0.1:8000", # PyWebView always targets local server instance
        width=1024,
        height=576,
        frameless=True,
        easy_drag=True,
        text_select=True
    )

    def on_loaded():
        print("[INFO] Webview DOM loaded. Applying zoom...")
        if created_window_ref:
            created_window_ref.evaluate_js("document.body.style.zoom = '70%'")

    if created_window_ref:
        created_window_ref.events.loaded += on_loaded

    webview.start(debug=False)

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

# Ensure this is the only call to start_gui when script is run directly
if __name__ == "__main__":
    start_gui()

async def manage_gui_window(action: str):
    """Hide or show the PyWebView window using PyWebView's methods."""
    print(f"[GUI_MANAGE_INTERNAL] Attempting to {action} Automoy GUI window via PyWebView.")
    
    pywebview_window = None
    if not hasattr(webview, 'windows') or not webview.windows:
        print("[GUI_MANAGE_INTERNAL][WARNING] webview.windows is not available or empty. Cannot manage GUI window.")
        return False # Indicate failure

    # Assuming the main Automoy GUI is the first window, or find by title
    found_window = False
    for w in webview.windows:
        try:
            # CORRECTED TITLE CHECK:
            if hasattr(w, 'title') and w.title and w.title.startswith("Automoy - Access via"):
                pywebview_window = w
                found_window = True
                break
        except Exception as e:
            print(f"[GUI_MANAGE_INTERNAL][ERROR] Error accessing window title: {e}")
            continue
    
    if not found_window and webview.windows: # Fallback if title match fails but windows exist
        print("[GUI_MANAGE_INTERNAL][WARNING] Automoy GUI window not found by title, attempting to use first window.")
        pywebview_window = webview.windows[0] # Less reliable, but a fallback
    elif not webview.windows:
        print(f"[GUI_MANAGE_INTERNAL][WARNING] No PyWebView windows found. Action '{action}' skipped.")
        return False


    if not pywebview_window:
        print(f"[GUI_MANAGE_INTERNAL][WARNING] Automoy GUI window object could not be obtained. Action '{action}' skipped.")
        if hasattr(webview, 'windows') and webview.windows:
            try:
                titles = [str(getattr(win, 'title', 'N/A')) for win in webview.windows]
                print(f"[GUI_MANAGE_INTERNAL][DEBUG] Available window titles: {titles}")
            except Exception as e:
                print(f"[GUI_MANAGE_INTERNAL][DEBUG] Error listing window titles: {e}")
        return False

    try:
        current_title = getattr(pywebview_window, 'title', 'Unknown Title')
        if action == "hide":
            print(f"[GUI_MANAGE_INTERNAL] Hiding window: {current_title}")
            pywebview_window.hide()
            print(f"[GUI_MANAGE_INTERNAL] Window '{current_title}' hide() called via PyWebView.")
        elif action == "show":
            print(f"[GUI_MANAGE_INTERNAL] Showing window: {current_title}")
            pywebview_window.show()
            # PyWebView's show should make it visible. Activation/positioning handled by main.py's pygetwindow part.
            print(f"[GUI_MANAGE_INTERNAL] Window '{current_title}' show() called via PyWebView.")
        return True # Indicate success
    except Exception as e:
        print(f"[GUI_MANAGE_INTERNAL][ERROR] Error during PyWebView window action '{action}' on '{current_title}': {e}")
        return False

@app.post("/control/window/{action}")
async def control_window_endpoint(action: str):
    print(f"[GUI_API] Received request to {action} window.")
    if action not in ["hide", "show"]:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'hide' or 'show'.")
    
    # Ensure webview has been started and windows are available
    # The manage_gui_window function checks webview.windows
    if not (hasattr(webview, 'windows') and webview.windows):
        # This might indicate the window isn't fully initialized yet or pywebview hasn't started.
        # Schedule the task if webview is available but windows list is empty (might be too early)
        if hasattr(webview, 'create_window') and not webview.windows: # webview object exists but no windows yet
             print("[GUI_API][WARNING] webview.windows is empty. Deferring action slightly.")
             await asyncio.sleep(0.5) # Brief delay and retry, hoping window initializes

    success = await manage_gui_window(action)
    if success:
        return JSONResponse(content={"status": f"action '{action}' processed for Automoy GUI."}, status_code=200)
    else:
        # If manage_gui_window returned False, it means it couldn't perform the action.
        # It would have printed its own warnings/errors.
        raise HTTPException(status_code=500, detail=f"Failed to execute '{action}' on Automoy GUI window. Check GUI logs.")

# ... existing FastAPI app setup, routes, and webview.start() call ...
# Make sure 'webview' is the global instance used by pywebview.start()
# Example:
# if __name__ == "__main__":
#     # ... setup api, app ...
#     window = webview.create_window("Automoy GUI...", app, ...)
#     webview.start(debug=True) # Or however it's started
