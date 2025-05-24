import os
import sys
import pathlib
import json
print(f"[GUI_LOAD] gui.py script started. Python version: {sys.version}", flush=True) # Very early print

# Add project root to sys.path so `import core.operate` works
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
print(f"[GUI_LOAD] Project root added to sys.path: {PROJECT_ROOT}", flush=True)

import webbrowser
import threading
import shutil
from pathlib import Path
import socket
from fastapi import FastAPI, Request, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
# from core.operate import AutomoyOperator 
import subprocess
import time
import asyncio # Ensure asyncio is imported
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import uvicorn  # add uvicorn import
import webview  # for borderless GUI window
from contextlib import asynccontextmanager # Add this import
import threading # Ensure threading is imported

print(f"[GUI_LOAD] Imports completed.", flush=True)


# Add the parent directory to sys.path to resolve imports
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) # This is redundant due to PROJECT_ROOT

# Define base directory (where this script lives)
BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.txt")
print(f"[GUI_LOAD] BASE_DIR: {BASE_DIR}", flush=True)

# Define path for the processed screenshot, relative to project root
PROCESSED_SCREENSHOT_PATH_FROM_ROOT = Path("core") / "utils" / "omniparser" / "processed_screenshot.png"

# AutomoyOperator is NOT initialized or managed by gui.py
# operator: AutomoyOperator | None = None # REMOVE THIS
# Global variable to hold the window instance, initialized to None
window_global_ref: webview.Window = None

# --- Define Event Handlers ---
def apply_window_settings(window):
    """Applies settings to the window once its content is loaded."""
    if window:
        print(f"[GUI Event - Loaded] Applying settings to window: {window.title if hasattr(window, 'title') else 'N/A'}", flush=True)
        # Apply 70% zoom
        window.evaluate_js("document.body.style.zoom = '70%';")
        print("[GUI Event - Loaded] Zoom to 70% applied via JS.", flush=True)
        # You can add other settings here, e.g., window.move, window.resize
    else:
        print("[GUI Event - Loaded][WARN] apply_window_settings called with no window object.", flush=True)

def on_closing():
    """Handler for when the window is about to close."""
    print("[GUI Event - Closing] Window is closing.", flush=True)
    # Perform any cleanup here if needed before the window actually closes
    # For example, signal other threads to stop
    return True # Return True to allow closing, False to prevent

def on_closed():
    """Handler for when the window has been closed."""
    print("[GUI Event - Closed] Window has been closed.", flush=True)
    # Perform cleanup after the window is gone
    # Note: Uvicorn server might still be running; main.py should handle its shutdown.
    global uvicorn_thread_global # Access the global Uvicorn thread reference
    if uvicorn_thread_global and uvicorn_thread_global.is_alive():
        print("[GUI Event - Closed] Uvicorn thread is still alive. Main process should handle its termination.", flush=True)
    # Attempt to gracefully stop the Uvicorn server if it's managed here
    # This is tricky as server.should_exit needs to be set from the server's thread usually.
    # For now, we rely on main.py to terminate the subprocess.

# Global reference for the Uvicorn thread
uvicorn_thread_global = None

# Function to start the Uvicorn server in a separate thread
def _start_uvicorn_server(app, host, port):  # Ensure all three parameters are accepted
    """Starts the Uvicorn server."""
    # Add a print statement to confirm parameters
    print(f"[UVICORN_THREAD] Initializing Uvicorn server with host='{host}', port={port}")
    try:
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        print("[UVICORN_THREAD] Uvicorn server configured. Starting server.run()...")
        server.run()
        print("[UVICORN_THREAD] Uvicorn server.run() completed.") # Should not be reached if server runs indefinitely
    except Exception as e:
        print(f"[UVICORN_THREAD][ERROR] Uvicorn server failed to start or crashed: {e}")
        # Optionally, re-raise or handle more gracefully if needed by the main app
        # For now, just printing the error from within the thread.

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    global window_global_ref 
    print("[GUI Lifespan] Starting up...", flush=True)
    yield
    print("[GUI Lifespan] Shutting down...", flush=True)
    if window_global_ref:
        print("[GUI Lifespan] Destroying PyWebView window.", flush=True)
        try:
            window_global_ref.destroy()
        except Exception as e:
            print(f"[GUI Lifespan][ERROR] Error destroying PyWebView window: {e}", flush=True)
    print("[GUI Lifespan] Shutdown complete.", flush=True)

app = FastAPI(lifespan=lifespan)
print(f"[GUI_LOAD] FastAPI app created.", flush=True)

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

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    print("[GUI FastAPI] Root path / requested. Serving index.html.", flush=True)
    return templates.TemplateResponse("index.html", {"request": request})

# --- Global state for Automoy GUI ---
current_user_goal: str = "" # User's direct input
current_formulated_objective: str = "" # LLM-generated objective
operator_status: str = "Idle" # Idle, Running, Paused, Error
gui_log_messages: List[str] = [] # For general logs in GUI

# New state variables for multi-stage reasoning display
current_visual_analysis: str = "Waiting for visual analysis..."
current_thinking_process: str = "Waiting for thinking process..."
current_steps_generated: List[str] = [] # Store as a list of strings
current_operations_generated: Dict[str, Any] = {} # For the new "Operations Generated" section
current_operation_display: str = "No operation active."
past_operation_display: str = "No past operations yet."
processed_screenshot_available: bool = False
llm_stream_content: str = "" # New global variable for LLM stream

# Pause state
is_paused: bool = False

# Queue for SSE LLM stream updates
llm_stream_queue = asyncio.Queue()


class GoalData(BaseModel): # Renamed from ObjectiveData
    goal: str

class ObjectiveData(BaseModel): # For LLM-formulated objective
    objective: str

class LogMessage(BaseModel):
    message: str

class StateUpdateText(BaseModel):
    text: str

class StateUpdateSteps(BaseModel):
    list: List[str] # Changed from steps to list to match operate.py

class StateUpdateDict(BaseModel): # For operations generated
    current_operations_generated: Dict[str, Any]

class LLMStreamChunk(BaseModel):
    chunk: str

@app.post("/state/visual")
async def update_visual_state(data: StateUpdateText):
    global current_visual_analysis
    print(f"[GUI /state/visual] Received visual analysis update: {data.text[:100]}...", flush=True)
    current_visual_analysis = data.text
    return {"message": "Visual analysis state updated"}

@app.post("/state/thinking") # Added endpoint
async def update_thinking_state(data: StateUpdateText):
    global current_thinking_process
    print(f"[GUI /state/thinking] Received thinking process update: {data.text[:100]}...", flush=True)
    current_thinking_process = data.text
    return {"message": "Thinking process state updated"}

@app.post("/state/steps_generated") # Added endpoint
async def update_steps_state(data: StateUpdateSteps):
    global current_steps_generated
    print(f"[GUI /state/steps_generated] Received steps update: {data.list}", flush=True)
    current_steps_generated = data.list
    return {"message": "Steps generated state updated"}

@app.post("/state/operations_generated") # Added endpoint
async def update_operations_state(data: StateUpdateDict): # Assuming StateUpdateDict is appropriate
    global current_operations_generated
    print(f"[GUI /state/operations_generated] Received operations update: {data.current_operations_generated}", flush=True)
    current_operations_generated = data.current_operations_generated
    return {"message": "Operations generated state updated"}

@app.post("/state/current_operation") # Added endpoint
async def update_current_operation_state(data: StateUpdateText):
    global current_operation_display
    print(f"[GUI /state/current_operation] Received current operation update: {data.text}", flush=True)
    current_operation_display = data.text
    return {"message": "Current operation state updated"}

@app.post("/state/last_action_result") # Added endpoint
async def update_last_action_result_state(data: StateUpdateText): # Assuming text, adjust if it's dict
    global past_operation_display # Or a new variable if preferred
    print(f"[GUI /state/last_action_result] Received last action result: {data.text}", flush=True)
    past_operation_display = data.text # Update past_operation_display or a dedicated one
    return {"message": "Last action result updated"}

@app.post("/state/screenshot") # Added endpoint for screenshot path
async def update_screenshot_state(payload: dict): # Generic dict payload
    global processed_screenshot_available, window_global_ref # Added window_global_ref
    # Path is expected in payload.get("path")
    # Timestamp in payload.get("timestamp")
    print(f"[GUI /state/screenshot] Received screenshot update notification: {payload}", flush=True)
    new_screenshot_path = payload.get("path")
    if new_screenshot_path: # Check if a path was provided in the payload
        processed_screenshot_available = True
        # The client-side script.js already handles refreshing the image src with a timestamp
        # by calling refreshScreenshot(). We can also try to trigger it from here.
        if window_global_ref:
            try:
                # Ensure the JS function refreshScreenshot() is called
                js_command = "if (typeof refreshScreenshot === 'function') { refreshScreenshot(); console.log('[GUI /state/screenshot] JS refreshScreenshot called.'); } else { console.error('[GUI /state/screenshot] refreshScreenshot function not defined in JS.'); }"
                window_global_ref.evaluate_js(js_command)
                print(f"[GUI /state/screenshot] Executed JS command: {js_command}", flush=True)
            except Exception as e:
                print(f"[GUI /state/screenshot][ERROR] Failed to execute JS for screenshot refresh: {e}", flush=True)
        else:
            print("[GUI /state/screenshot][WARN] window_global_ref not available to trigger JS screenshot refresh.", flush=True)
    else:
        print("[GUI /state/screenshot] Screenshot update notification received, but no path provided in payload. Screenshot availability might not change.", flush=True)
        # processed_screenshot_available might remain false or its previous state if no path is given
        
    return {"message": "Screenshot state updated and JS refresh attempted if path provided"}

@app.post("/state/clear_all_operational_data")
async def clear_all_operational_data_endpoint(_: Request): # Use _ if request not directly used
    global current_user_goal, current_formulated_objective, operator_status
    global current_visual_analysis, current_thinking_process, current_steps_generated
    global current_operations_generated, current_operation_display, past_operation_display
    global processed_screenshot_available, llm_stream_content, is_paused

    print("[GUI /state/clear_all_operational_data] Clearing all operational data.", flush=True)
    # current_user_goal = "" # Keep user goal unless explicitly cleared by new goal submission
    # current_formulated_objective = "" # Keep formulated objective until new one is made
    # operator_status = "Idle" # Keep operator status, should be managed by main flow

    current_visual_analysis = "Waiting for visual analysis..."
    current_thinking_process = "Waiting for thinking process..."
    current_steps_generated = []
    current_operations_generated = {}
    current_operation_display = "No operation active."
    past_operation_display = "No past operations yet."
    processed_screenshot_available = False
    llm_stream_content = ""
    # is_paused = False # Do not reset pause state here, it's user controlled

    return {"message": "All operational display data cleared"}

@app.post("/set_goal") # Renamed from /set_objective
async def set_goal_endpoint(data: GoalData): # Was: set_objective_endpoint(data: ObjectiveData)
    global current_user_goal, current_formulated_objective, operator_status 
    global current_visual_analysis, current_thinking_process, current_steps_generated
    global current_operation_display, past_operation_display, processed_screenshot_available, llm_stream_content

    current_user_goal = data.goal
    current_formulated_objective = "AI is formulating the objective..." # Placeholder
    operator_status = "ProcessingGoal" 
    
    # Clear previous operational state when a new goal is set
    current_visual_analysis = "Waiting for objective formulation..."
    current_thinking_process = ""
    current_steps_generated = []
    current_operation_display = "Formulating objective from goal..." 
    past_operation_display = "" 
    processed_screenshot_available = False
    llm_stream_content = "" 

    print(f"[GUI] Goal received: {current_user_goal}")
    # The actual LLM call to formulate the objective will be triggered by main.py
    # after it polls /operator_state and sees a new goal.

    return {"message": "Goal set, awaiting AI objective formulation", "goal": current_user_goal, "formulated_objective": current_formulated_objective}

# New endpoint for the backend (main.py) to update the formulated objective
@app.post("/state/formulated_objective")
async def update_formulated_objective_state(data: ObjectiveData):
    global current_formulated_objective, operator_status
    current_formulated_objective = data.objective
    if operator_status == "ProcessingGoal" and current_formulated_objective:
        operator_status = "ObjectiveFormulated" # Or "ReadyToRun"
    print(f"[GUI] Formulated objective updated by backend: {current_formulated_objective}", flush=True)
    return {"message": "Formulated objective updated successfully", "formulated_objective": current_formulated_objective}

@app.post("/state/thinking")
async def update_thinking_state(data: StateUpdateText):
    global current_thinking_process
    current_thinking_process = data.text
    return {"message": "Thinking process updated"}

@app.post("/state/steps")
async def update_steps_state(data: StateUpdateSteps):
    global current_steps_generated
    current_steps_generated = data.list # Changed from data.steps
    return {"message": "Steps updated"}

@app.post("/state/operations_generated") # New endpoint
async def update_operations_generated_state(data: StateUpdateDict):
    global current_operations_generated
    current_operations_generated = data.current_operations_generated
    print(f"[GUI /state/operations_generated] Received operations: {current_operations_generated}", flush=True)
    return {"message": "Operations generated updated"}

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

@app.get("/automoy_current.png")
async def get_current_screenshot(request: Request):
    # Serve the processed screenshot that is copied to gui/static/
    # This aligns with what operate.py sets as active_screenshot_for_llm_gui
    # and what OmniParser is expected to copy.
    processed_image_in_static_abs_path = PROJECT_ROOT / "gui" / "static" / "processed_screenshot.png"
    print(f"[GUI_SCREENSHOT_ENDPOINT] Attempting to serve: {processed_image_in_static_abs_path}", flush=True)

    if not processed_image_in_static_abs_path.exists():
        print(f"[GUI_SCREENSHOT_ENDPOINT][ERROR] Processed screenshot not found at {processed_image_in_static_abs_path}", flush=True)
        # Fallback: Try to serve the raw automoy_current.png from the project root if the processed one isn\'t there
        # This fallback might be less relevant if the primary path is the one always updated.
        fallback_path = PROJECT_ROOT / "automoy_current.png" # A raw capture, if it exists
        if fallback_path.exists():
            print(f"[GUI_SCREENSHOT_ENDPOINT][FALLBACK] Serving raw screenshot: {fallback_path}", flush=True)
            return FileResponse(str(fallback_path), media_type="image/png")
        raise HTTPException(status_code=404, detail="Processed screenshot (gui/static/processed_screenshot.png) not found.")
    
    return FileResponse(str(processed_image_in_static_abs_path), media_type="image/png")

@app.post("/state/screenshot_processed")
async def screenshot_processed_notification():
    global processed_screenshot_available, window_global_ref
    processed_screenshot_available = True
    print("[GUI FastAPI] Screenshot processed notification received. Triggering JS refresh.", flush=True)
    if window_global_ref:
        try:
            # Directly call refreshScreenshot in JS
            js_command = "if (typeof refreshScreenshot === 'function') { refreshScreenshot(); console.log('JS refreshScreenshot called.'); } else { console.error('refreshScreenshot function not defined in JS.'); }"
            window_global_ref.evaluate_js(js_command)
            print(f"[GUI FastAPI] Executed JS command: {js_command}", flush=True)
        except Exception as e:
            print(f"[GUI FastAPI][ERROR] Failed to execute JS for screenshot refresh: {e}", flush=True)
    else:
        print("[GUI FastAPI][WARN] window_global_ref not available to trigger JS screenshot refresh.", flush=True)
    return {"message": "Screenshot processed, JS refresh triggered"}

@app.post("/state/clear_all_operational_data")
async def clear_all_operational_data():
    global current_visual_analysis, current_thinking_process, current_steps_generated
    global current_operation_display, past_operation_display, processed_screenshot_available
    # current_objective and operator_status might be preserved or reset based on desired logic
    # For now, this focuses on the operational display fields.
    return {"message": "Operational display data cleared"}

@app.post("/state/llm_stream_chunk")
async def receive_llm_stream_chunk(data: LLMStreamChunk):
    global llm_stream_content
    chunk_to_send = data.chunk

    if data.chunk == "__STREAM_START__":
        llm_stream_content = "" # Clear previous stream
        # Send __STREAM_START__ to SSE queue
    elif data.chunk == "__STREAM_END__":
        # Optionally, do something when stream ends, like final processing
        # For now, the content is already accumulated.
        # Send __STREAM_END__ to SSE queue
        pass
    else:
        llm_stream_content += data.chunk
    
    # Put the original chunk (could be data or signal) onto the SSE queue
    await llm_stream_queue.put(chunk_to_send)
    return {"message": "LLM stream chunk received and queued for SSE"}

@app.get("/llm_stream_updates")
async def stream_llm_updates(request: Request):
    async def event_generator():
        while True:
            # Wait for the next item from the queue.
            item = await llm_stream_queue.get()
            if item is None:  # A way to signal the end from the queue producer if needed
                break
            if await request.is_disconnected():
                print("[SSE] Client disconnected from LLM stream.")
                break
            
            # Send data strictly as JSON with a "chunk" key, or handle signals
            if item == "__STREAM_START__":
                yield f"data: {json.dumps({'signal': '__STREAM_START__'})}\\n\\n"
            elif item == "__STREAM_END__":
                yield f"data: {json.dumps({'signal': '__STREAM_END__'})}\\n\\n"
                # Optionally, could send a close signal or the server could manage connection lifecycle.
                # For now, just passing the signal.
            else:
                yield f"data: {json.dumps({'chunk': item})}\\n\\n"
            await asyncio.sleep(0.01) # Small delay to prevent tight loop issues if queue is spammed
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/health")
async def health_check():
    """Simple health check endpoint to confirm the GUI server is running."""
    return {"status": "healthy", "message": "GUI server is responsive."}

@app.get("/operator_state")
async def get_operator_state_endpoint(): # Ensure this endpoint exists and returns current_objective
    return {
        "user_goal": current_user_goal, 
        "formulated_objective": current_formulated_objective, 
        "operator_status": operator_status,
        "current_visual_analysis": current_visual_analysis,
        "current_thinking_process": current_thinking_process,
        "current_steps_generated": current_steps_generated,
        "current_operations_generated": current_operations_generated, # Added
        "current_operation": current_operation_display, 
        "past_operation": past_operation_display, 
        "llm_query": "", 
        "llm_response": "", 
        "execution_result": "", 
        "history_log": gui_log_messages, 
        "screenshot_processed": processed_screenshot_available,
        "llm_stream_content": llm_stream_content,
        "is_paused": is_paused # Added pause state
    }

@app.post("/control/toggle_pause") # New endpoint for pause
async def toggle_pause_operator():
    global is_paused # Ensure we are modifying the global variable
    is_paused = not is_paused
    status = "paused" if is_paused else "running"
    print(f"[GUI /control/toggle_pause] Pause state toggled. New state: {'paused' if is_paused else 'running'}", flush=True) # Added flush
    # The operator_status should reflect the actual operational state, not just pause.
    # For now, just return the pause status.
    return {"message": f"Operator {status}", "is_paused": is_paused}

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

# --- Window control API exposed to JavaScript ---
# Global reference to the created pywebview window
# window_global_ref is defined in the global scope of the module later or already

# API class to be exposed to JavaScript for controlling the window from the main GUI thread
class WindowControlApi:
    def __init__(self):
        self._window = None
        self._gui_ready_event = threading.Event()
        print("[WindowControlApi] Initialized.", flush=True)

    def set_window(self, window_instance):
        print(f"[WindowControlApi] Setting window instance: {window_instance}", flush=True)
        self._window = window_instance
        self._gui_ready_event.set() # Signal that the window object is available

    def _wait_for_gui_ready(self, timeout=10):
        print("[WindowControlApi] Waiting for GUI window object to be set...", flush=True)
        ready = self._gui_ready_event.wait(timeout)
        if ready:
            print("[WindowControlApi] GUI window object is set.", flush=True)
        else:
            print("[WindowControlApi][WARN] Timeout waiting for GUI window object.", flush=True)
        return ready

    def get_window(self):
        if not self._gui_ready_event.is_set():
            print("[WindowControlApi][WARN] get_window called before window was set or ready.", flush=True)
        return self._window

    # Methods intended to be called from JS via js_api
    def js_minimize_window(self):
        print("[WindowControlApi JS Call] js_minimize_window called", flush=True)
        if self._window:
            self._window.minimize()
            return True
        print("[WindowControlApi JS Call][ERROR] js_minimize_window: Window not set", flush=True)
        return False

    def js_restore_window(self):
        print("[WindowControlApi JS Call] js_restore_window called", flush=True)
        if self._window:
            self._window.restore()
            return True
        print("[WindowControlApi JS Call][ERROR] js_restore_window: Window not set", flush=True)
        return False

    def js_hide_window(self): # Pywebview doesn't have a direct 'hide' that's different from minimize for frameless
        print("[WindowControlApi JS Call] js_hide_window called (will minimize)", flush=True)
        if self._window:
            self._window.minimize() # Or implement custom logic if hide means something else
            return True
        print("[WindowControlApi JS Call][ERROR] js_hide_window: Window not set", flush=True)
        return False

    def js_show_window(self):
        print("[WindowControlApi JS Call] js_show_window called (will restore)", flush=True)
        if self._window:
            self._window.restore()
            return True
        print("[WindowControlApi JS Call][ERROR] js_show_window: Window not set", flush=True)
        return False

    # Methods intended to be called from Python (e.g., via FastAPI endpoints)
    def minimize(self):
        print("[WindowControlApi Python Call] minimize called", flush=True)
        if self._window:
            self._window.minimize()
        else:
            print("[WindowControlApi Python Call][ERROR] minimize: Window not set", flush=True)
            
    def show(self): # This should restore, resize, and move.
        print("[WindowControlApi Python Call] show called", flush=True)
        if self._window:
            self._window.restore() # Make sure it's not minimized
            print("[WindowControlApi Python Call] Window restored. Ensure it is sized and positioned as expected.", flush=True)
        else:
            print("[WindowControlApi Python Call][ERROR] show: Window not set", flush=True)

window_control_api = WindowControlApi() # Instantiate once globally
print("[GUI_LOAD] WindowControlApi instantiated globally.", flush=True)


# --- FastAPI Endpoints ---
# ... (existing FastAPI endpoints like /health, /set_objective, etc.)

@app.post("/control/window/{action}")
async def control_window_endpoint(action: str):
    print(f"[FastAPI Endpoint] /control/window/{action} called", flush=True)
    # window_control_api is globally available, check its internal _window state if needed
    # For example, if window_control_api.get_window() returns None, it means pywebview window wasn't set yet.
    if not window_control_api.get_window(): # Check if window object is available
        print(f"[FastAPI Endpoint][ERROR] Window control API not fully initialized or window not set for action: {action}", flush=True)
        raise HTTPException(status_code=503, detail="GUI window not ready for control operations.")

    if action == "minimize":
        window_control_api.minimize()
        return {"status": f"minimize action dispatched"}
    elif action == "show":
        window_control_api.show()
        return {"status": f"show action dispatched"}
    else:
        raise HTTPException(status_code=400, detail="Invalid window action")

def _start_uvicorn_server(app, host: str, port: int): # Modified to accept app, host, and port

    print(f"[Uvicorn Thread] ALIVE ({threading.current_thread().name}). Attempting to start Uvicorn on {host}:{port}... (App: {app})", flush=True)
    try:
        print(f"[Uvicorn Thread] Configuring Uvicorn...", flush=True)
        config = uvicorn.Config(app, host=host, port=port, log_level="debug", lifespan="on")
        server = uvicorn.Server(config)
        
        print(f"[Uvicorn Thread] Uvicorn Config and Server objects created. Calling server.run()...", flush=True)
        server.run() 
        print(f"[Uvicorn Thread] Uvicorn server.run() has completed.", flush=True)
    except SystemExit as se:
        print(f"[Uvicorn Thread] Uvicorn server stopped via SystemExit: {se}", flush=True)
    except Exception as e:
        print(f"[Uvicorn Thread][ERROR] Critical error in Uvicorn thread: {e}", flush=True)
        import traceback
        print(traceback.format_exc(), flush=True)
    finally:
        print(f"[Uvicorn Thread] Exiting _start_uvicorn_server function.", flush=True)

def start_gui(host="127.0.0.1", port=8000, window_title="Automoy - Access via http://127.0.0.1:8000", width=1228, height=691):
    global window_global_ref, uvicorn_thread_global # Removed js_bridge_api_global from here

    print(f"[GUI] start_gui called with host={host}, port={port}", flush=True)
    
    # Start Uvicorn server in a separate thread
    # The uvicorn_thread_global is assigned below, removing the first duplicate assignment.
    print(f"[GUI] Attempting to start Uvicorn server thread. Name: UvicornServerThread")
    # Pass app, host, and port to the thread target
    uvicorn_thread_global = threading.Thread(
        target=_start_uvicorn_server,
        args=(app, host, port),  # Ensure these match the function signature
        name="UvicornServerThread",
        daemon=False # Ensure it's not a daemon thread, so Python waits for it
    )
    uvicorn_thread_global.start()
    print(f"[GUI] Uvicorn server thread started. Name: {uvicorn_thread_global.name}. Waiting briefly for server to initialize...", flush=True)
    time.sleep(3) # Give Uvicorn a moment to initialize and start serving

    # Create the PyWebView window
    try:
        print(f"[GUI] Attempting to create PyWebView window. Title: '{window_title}' URL: http://{host}:{port}", flush=True)
        window_global_ref = webview.create_window(
            title=window_title,
            url=f"http://{host}:{port}", # URL for PyWebView to load
            width=width, # Use updated width
            height=height, # Use updated height
            resizable=True,
            frameless=True, # Set to True for a borderless window
            on_top=False,
            js_api=window_control_api # Corrected to use the instantiated window_control_api
        )
        
        if window_global_ref:
            print(f"[GUI] PyWebView window created successfully: '{window_global_ref.title if hasattr(window_global_ref, 'title') else 'N/A'}'. Global ref set.", flush=True)
            # Register event handlers AFTER window creation
            window_global_ref.events.loaded += lambda: apply_window_settings(window_global_ref)
            window_global_ref.events.closing += on_closing
            window_global_ref.events.closed += on_closed
            print("[GUI] PyWebView window event handlers registered (loaded, closing, closed).", flush=True)
        else:
            # This case implies create_window returned None without an exception, which is unusual.
            print("[GUI][ERROR] webview.create_window returned None. Window creation failed silently.", flush=True)
            # Consider cleanup for Uvicorn thread here if possible
            return # Exit start_gui if window creation failed

    except Exception as e:
        print(f"[GUI][ERROR] Failed to create PyWebView window: {e}", flush=True)
        # Consider cleanup for Uvicorn thread here if possible
        return # Exit start_gui if window creation failed

    print("[GUI] Starting PyWebView GUI event loop. This call is blocking and will not return until the window is closed.", flush=True)
    
    # Diagnostic print: Check webview.windows before starting the event loop
    print(f"[GUI] DIAGNOSTIC: About to call webview.start(). Current webview.windows: {webview.windows}", flush=True)
    if window_global_ref and webview.windows and window_global_ref in webview.windows:
        print(f"[GUI] DIAGNOSTIC: window_global_ref ('{window_global_ref.title if hasattr(window_global_ref, 'title') else 'N/A'}') IS in webview.windows.", flush=True)
    elif window_global_ref:
        print(f"[GUI] DIAGNOSTIC: window_global_ref ('{window_global_ref.title if hasattr(window_global_ref, 'title') else 'N/A'}') is NOT in webview.windows. This is the problem.", flush=True)
    else:
        print("[GUI] DIAGNOSTIC: window_global_ref is None before webview.start(). Window was not created.", flush=True)

    try:
        # Ensure a window has been created and is tracked by pywebview
        if not webview.windows:
            print("[GUI][ERROR] No windows found in webview.windows before calling webview.start(). Aborting.", flush=True)
            # Consider cleanup for Uvicorn thread here
            return
        
        webview.start(
            debug=False,          # Set to False to disable developer tools
            http_server=False,   # CRITICAL: Set to False as Uvicorn is serving content
                                 # PyWebView should load content from the Uvicorn server URL
            # func=some_function_after_loop_finishes, # Optional: function to call after event loop exits
            # private_mode=True, # Optional: enable private mode (no cache, cookies)
            # storage_path='/path/to/storage', # Optional: custom storage path
        )
    except webview.errors.WebViewException as e:
        print(f"[GUI][PYWEBVIEW_ERROR] WebViewException during webview.start(): {e}", flush=True)
        print(f"[GUI][PYWEBVIEW_ERROR] Details: webview.windows list was {webview.windows}", flush=True)
    except Exception as e:
        print(f"[GUI][ERROR] Generic exception during webview.start(): {e}", flush=True)
    finally:
        print("[GUI] PyWebView event loop has exited.", flush=True)
        # Uvicorn thread might still be running. 
        # Its lifecycle should ideally be managed by the process that started it (main.py via subprocess).
        if uvicorn_thread_global and uvicorn_thread_global.is_alive():
            print("[GUI] Uvicorn thread is still alive after PyWebView exit. Main process should handle its termination.", flush=True)

# Ensure the if __name__ == "__main__": block correctly calls start_gui()
if __name__ == "__main__":
    print("[GUI] Script executed directly. Calling start_gui().", flush=True)
    start_gui() # Add this line to actually start the GUI and server
    print("[GUI] start_gui() returned. Script will now exit if Uvicorn thread also exited.", flush=True)
