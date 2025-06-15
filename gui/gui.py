import os
import sys
import pathlib
from pathlib import Path
import json
print(f"[GUI_LOAD] gui.py script started. Python version: {sys.version}", flush=True) # Very early print

# Add project root to sys.path so `import core.operate` works
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
print(f"[GUI_LOAD] Project root added to sys.path: {PROJECT_ROOT}", flush=True)

import logging
import logging.handlers
# Ensure this sys import is available for the logger if not already imported above
# import sys 

# Determine project root to correctly path to logs directory
# PROJECT_ROOT is already defined above
GUI_LOG_FILE_PATH = os.path.join(PROJECT_ROOT, "debug", "logs", "gui", "gui_output.log")

def setup_gui_logging():
    log_dir = os.path.dirname(GUI_LOG_FILE_PATH)
    os.makedirs(log_dir, exist_ok=True)

    gui_logger = logging.getLogger("GUI") # Specific logger for GUI
    
    # Clear existing handlers for this logger to avoid duplication
    if gui_logger.hasHandlers():
        gui_logger.handlers.clear()

    gui_logger.setLevel(logging.DEBUG) 

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')

    # File Handler for GUI logs
    fh = logging.FileHandler(GUI_LOG_FILE_PATH, mode='w') # Changed mode to 'w'
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    gui_logger.addHandler(fh)

    # Console Handler for GUI logs
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO) 
    ch.setFormatter(formatter)
    gui_logger.addHandler(ch)
    
    gui_logger.info(f"GUI Logging initialized. Log file: {GUI_LOG_FILE_PATH}. Console level: INFO, File level: DEBUG.")

# Call setup_logging() once, early in the script.
setup_gui_logging()
logger = logging.getLogger("GUI") # Use the GUI-specific logger

# Now continue with other imports
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
from typing import List, Dict, Any, Optional # ADDED Optional
# from core.operate import AutomoyOperator 
import subprocess
import time
import asyncio # Ensure asyncio is imported
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import uvicorn  # add uvicorn import
from contextlib import asynccontextmanager # Add this import
import logging
import logging.handlers
import sys
import argparse # ADDED
import config.config as app_config

print(f"[GUI_LOAD] Imports completed.", flush=True)

# --- Pydantic Models ---
class GoalData(BaseModel):    
    goal: str

class ObjectiveData(BaseModel):    
    objective: str

class LogMessage(BaseModel):
    message: str
    level: str = "INFO"

class StateUpdateText(BaseModel):
    text: str

class StateUpdateSteps(BaseModel):
    steps: List[str] # This was List[str] before, but /state/steps_generated endpoint now expects List[Dict[str, Any]]
                    # Let's keep it List[str] here if it's for a different purpose or update if it's for the same.
                    # For now, assuming it might be used by a different, simpler text-based step update.
                    # If it's for the same endpoint that now takes List[Dict], this model needs an update.

class StateUpdateDict(BaseModel):    
    json: Dict[str, Any] # Changed from json_data to json

class LLMStreamChunk(BaseModel):
    content: str
    event_type: str # e.g., "thought", "action_json", "status"

# New Pydantic models for updated endpoints
class OperatorStatusUpdateRequest(BaseModel):
    text: str # Changed from status to text to match core/operate.py

class ScreenshotUpdateRequest(BaseModel):
    path: str # Expecting a file path string

class ProcessedScreenshotNotif(BaseModel):
    # This can be an empty model if it's just a notification
    pass 

class VisualAnalysisUpdateRequest(BaseModel):
    text: str # Expecting the analysis string or error message

# Model for the /state/steps_generated endpoint that expects a list of dictionaries
class StateUpdateComplexSteps(BaseModel):
    steps: List[Dict[str, Any]] 
    error: Optional[str] = None

# Model for the /state/operations_generated endpoint
class StateUpdateOperations(BaseModel):
    operations: List[Dict[str, Any]] 
    thinking_process: Optional[str] = None

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
# window_global_ref: webview.Window = None

# --- Define Event Handlers ---
# def apply_window_settings(window):
#     """Applies settings to the window once its content is loaded."""
#     if window:
#         print(f"[GUI Event - Loaded] Applying settings to window: {window.title if hasattr(window, 'title') else 'N/A'}", flush=True)
#         # Apply 70% zoom
#         window.evaluate_js("document.body.style.zoom = '70%';")
#         print("[GUI Event - Loaded] Zoom to 70% applied via JS.", flush=True)
#         # You can add other settings here, e.g., window.move, window.resize
#     else:
#         print("[GUI Event - Loaded][WARN] apply_window_settings called with no window object.", flush=True)

# def on_closing():
#     """Handler for when the window is about to close."""
#     print("[GUI Event - Closing] Window is closing.", flush=True)
#     # Perform any cleanup here if needed before the window actually closes
#     # For example, signal other threads to stop
#     return True # Return True to allow closing, False to prevent

# def on_closed():
#     """Handler for when the window has been closed."""
#     print("[GUI Event - Closed] Window has been closed.", flush=True)
#     # Perform cleanup after the window is gone
#     # Note: Uvicorn server might still be running; main.py should handle its shutdown.
#     global uvicorn_thread_global # Access the global Uvicorn thread reference
#     if uvicorn_thread_global and uvicorn_thread_global.is_alive():
#         print("[GUI Event - Closed] Uvicorn thread is still alive. Main process should handle its termination.", flush=True)
#     # Attempt to gracefully stop the Uvicorn server if it's managed here
#     # This is tricky as server.should_exit needs to be set from the server's thread usually.
#     # For now, we rely on main.py to terminate the subprocess.

# Global reference for the Uvicorn thread
# uvicorn_thread_global = None

# Function to start the Uvicorn server in a separate thread
# def _start_uvicorn_server(app, host, port):  # Ensure all three parameters are accepted
#     """Starts the Uvicorn server."""
#     # Add a print statement to confirm parameters
#     print(f"[UVICORN_THREAD] Initializing Uvicorn server with host='{host}', port={port}")
#     try:
#         config = uvicorn.Config(app, host=host, port=port, log_level="info")
#         server = uvicorn.Server(config)
#         print("[UVICORN_THREAD] Uvicorn server configured. Starting server.run()...")
#         server.run()
#         print("[UVICORN_THREAD] Uvicorn server.run() completed.") # Should not be reached if server runs indefinitely
#     except Exception as e:
#         print(f"[UVICORN_THREAD][ERROR] Uvicorn server failed to start or crashed: {e}")
        # Optionally, re-raise or handle more gracefully if needed by the main app
        # For now, just printing the error from within the thread.

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # global window_global_ref # REMOVED global
    print("[GUI Lifespan] Starting up...", flush=True)
    yield
    print("[GUI Lifespan] Shutting down...", flush=True)
    # REMOVED window destruction logic
    # if window_global_ref:
    #     print("[GUI Lifespan] Destroying PyWebView window.", flush=True)
    #     try:
    #         window_global_ref.destroy()
    #     except Exception as e:
    #         print(f"[GUI Lifespan][ERROR] Error destroying PyWebView window: {e}", flush=True)
    print("[GUI Lifespan] Shutdown complete.", flush=True)

app = FastAPI(lifespan=lifespan)
logger.info("FastAPI app created with lifespan.") # Example log after app creation

# --- Templates and Static Files Setup ---
BASE_DIR = Path(__file__).resolve().parent
templates_dir = BASE_DIR / "templates"
static_dir = BASE_DIR / "static"

# Ensure directories exist
templates_dir.mkdir(parents=True, exist_ok=True)
static_dir.mkdir(parents=True, exist_ok=True)

# Pass auto_reload=True to Jinja2Templates for development
templates = Jinja2Templates(directory=str(templates_dir), auto_reload=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health") # ADDED health check endpoint
async def health_check():
    logger.info("[GUI /health] Health check endpoint called successfully.")
    return {"status": "healthy"}

@app.get("/operator_state") # ADDED operator state endpoint
async def get_operator_state():
    # Return current GUI state for core polling
    return {
        "user_goal": current_user_goal,
        "status": operator_status,
        "objective": current_formulated_objective,
        "parsed_steps": current_steps_generated,
        "current_step_index": None,
        "errors": []
    }

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    print("[GUI FastAPI] Root path / requested. Serving index.html.", flush=True)
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/set_goal")
async def set_goal(data: GoalData):
    # Receive new user goal: store and notify via SSE
    global current_user_goal, current_formulated_objective, current_steps_generated
    current_user_goal = data.goal
    current_formulated_objective = ""
    current_steps_generated = []
    await llm_stream_queue.put({"type": "goal", "data": current_user_goal})
    return {"message": "Goal received"}

@app.post("/state/objective")
async def update_objective_state(data: StateUpdateText):
    global current_formulated_objective
    current_formulated_objective = data.text
    await llm_stream_queue.put({"type": "objective", "data": data.text})
    return {"message": "Objective state updated"}

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


@app.post("/state/visual")
async def update_visual_state(data: StateUpdateText):
    await llm_stream_queue.put({"type": "visual", "data": data.text})
    return {"message": "Visual state updated"}

@app.post("/state/thinking") # Added endpoint
async def update_thinking_state(data: StateUpdateText):
    await llm_stream_queue.put({"type": "thinking", "data": data.text})
    return {"message": "Thinking state updated"}

@app.post("/state/steps_generated") # Added endpoint
async def update_steps_state(data: StateUpdateComplexSteps):    
    # Steps generation update
    await llm_stream_queue.put({"type": "steps", "data": data.steps})
    return {"message": "Steps state updated"}

@app.post("/state/operations_generated") # Added endpoint
async def update_operations_state(data: StateUpdateOperations):    
    await llm_stream_queue.put({"type": "operations_generated", "data": data.operations})
    if data.thinking_process:
        await llm_stream_queue.put({"type": "thinking", "data": data.thinking_process})
    return {"message": "Operations state updated"}

@app.post("/state/current_operation") # Added endpoint
async def update_current_operation_state(data: StateUpdateText):    
    await llm_stream_queue.put({"type": "current_operation", "data": data.text})
    return {"message": "Current operation state updated"}

@app.post("/state/last_action_result") # Added endpoint
async def update_last_action_result_state(data: StateUpdateText):    
    # Treat last action result as past operation
    await llm_stream_queue.put({"type": "past_operation", "data": data.text})
    return {"message": "Last action result updated"}

@app.post("/state/screenshot") 
async def update_screenshot_state(payload: ScreenshotUpdateRequest):    
    # Notify that a new screenshot is available
    await llm_stream_queue.put({"type": "screenshot", "data": payload.path})
    return {"message": "Screenshot path updated"}

@app.post("/state/screenshot_processed")
async def screenshot_processed_notification(_: ProcessedScreenshotNotif):    
    await llm_stream_queue.put({"type": "processed_screenshot", "data": True})
    return {"message": "Processed screenshot notification received"}

@app.post("/state/visual_analysis") # ADDED (or corrected if it was /state/visual before)
async def update_visual_analysis_state(data: VisualAnalysisUpdateRequest):    
    await llm_stream_queue.put({"type": "visual_analysis", "data": data.text})
    return {"message": "Visual analysis state updated"}

@app.post("/state/operator_status")
async def update_operator_status(data: OperatorStatusUpdateRequest):    
    await llm_stream_queue.put({"type": "operator_status", "data": data.text})
    return {"message": "Operator status updated"}

# This endpoint is already defined above, removed duplicate

@app.get("/processed_screenshot.png") # ADDED endpoint for processed screenshot
async def get_processed_screenshot(request: Request):
    processed_image_static_path = Path(BASE_DIR) / "static" / "processed_screenshot.png"
    logger.debug(f"[GUI /processed_screenshot.png] Attempting to serve: {processed_image_static_path}")
    if not processed_image_static_path.exists():
        logger.warning(f"[GUI /processed_screenshot.png][ERROR] Processed screenshot not found at {processed_image_static_path}")
        raise HTTPException(status_code=404, detail="Processed screenshot (static/processed_screenshot.png) not found.")
    return FileResponse(str(processed_image_static_path), media_type="image/png", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.get("/automoy_current.png")
async def get_current_screenshot(request: Request):
    raw_screenshot_static_path = Path(BASE_DIR) / "static" / "automoy_current.png"
    logger.debug(f"[GUI /automoy_current.png] Attempting to serve: {raw_screenshot_static_path}")
    if not raw_screenshot_static_path.exists():
        logger.warning(f"[GUI /automoy_current.png][ERROR] Raw screenshot not found at {raw_screenshot_static_path}")
        raise HTTPException(status_code=404, detail="Raw screenshot (static/automoy_current.png) not found.")
    return FileResponse(str(raw_screenshot_static_path), media_type="image/png", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

# --- SSE endpoint for streaming operator state updates ---
@app.get("/stream_operator_updates")
async def stream_operator_updates():
    # Server-Sent Events endpoint
    async def event_generator():
        while True:
            msg = await llm_stream_queue.get()
            yield f"data: {json.dumps(msg)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Ensure other state update endpoints or comments follow
# class StateUpdateSteps(BaseModel):
#     steps: List[Dict[str, Any]] # Expecting a list of step objects (e.g. {"description": "..."})
#     error: Optional[str] = None

# @app.post("/state/steps_generated")
# async def update_steps_state(data: StateUpdateSteps): # Corrected from List[str] to List[Dict[str,Any]]
#     global current_steps_generated
#     logger.info(f"[GUI /state/steps_generated] Received steps update: {len(data.steps)} steps. Error: {data.error}")
#     if data.error:
#         current_steps_generated = [{"description": f"Error generating steps: {data.error}"}] # Show error as a step
#     else:
#         current_steps_generated = data.steps # Store the list of step objects
#     return {"message": "Steps generated state updated"}

# Ensure StateUpdateDict for /state/operations_generated is appropriate
# class StateUpdateOperations(BaseModel):
#     operations: List[Dict[str, Any]] # Expecting a list of operation objects
#     thinking_process: Optional[str] = None

# @app.post("/state/operations_generated") 
# async def update_operations_state(data: StateUpdateOperations): # MODIFIED to use new Pydantic model
#     global current_operations_generated, current_thinking_process
#     logger.info(f"[GUI /state/operations_generated] Received operations update: {data.operations}")
#     current_operations_generated = {"operations": data.operations} # Store as a dict with 'operations' key as expected by JS
#     if data.thinking_process:
#         current_thinking_process = data.thinking_process # Update thinking process if provided
#     return {"message": "Operations generated state updated"}

# ADDED main execution block
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run FastAPI GUI server")
    parser.add_argument("--host", default="127.0.0.1", help="Host for the GUI server")
    parser.add_argument("--port", type=int, default=8000, help="Port for the GUI server")
    args = parser.parse_args()
    import uvicorn
    uvicorn.run("gui:app", host=args.host, port=args.port, log_level="info")
# End of main execution block

import asyncio
import logging # Added
from fastapi import FastAPI, Request, HTTPException # Added Request
from fastapi.responses import HTMLResponse, FileResponse # Added FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
import uvicorn
import os
from pathlib import Path # Added Path

# Assuming AutomoyStatus and ObjectiveStore are correctly imported/defined elsewhere or here
# from core.data_models import AutomoyStatus # Make sure this path is correct

# Placeholder for AutomoyStatus if not imported (ensure it's properly available)
class AutomoyStatus:
    IDLE = "idle"
    THINKING = "thinking"
    OPERATING = "operating"
    SUCCESS = "success"
    ERROR = "error"
    PENDING_USER_INPUT = "pending_user_input"

# ObjectiveStore to manage the objective state
class ObjectiveStore:
    def __init__(self):
        self._objective = "Formulated Objective:" # Initial state as per requirements
        self.lock = asyncio.Lock()

    async def set_objective(self, objective: str):
        async with self.lock:
            self._objective = objective
        # After setting, immediately push an update for the objective
        await send_operator_update({"objective": objective})


    async def get_objective(self):
        async with self.lock:
            return self._objective

current_objective_store = ObjectiveStore()


# Configure basic logging for gui.py
# Using a basic config, assuming Automoy's logger might not be easily accessible here
# or to ensure these logs are distinctly identifiable.
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
gui_logger = logging.getLogger("AutomoyGUI")

# Global state variables
current_user_goal: str = ""
gui_logger.info(f"Module-level: current_user_goal initialized to '{current_user_goal}'")

current_thinking_process: str = "" # Initialize empty, updated by backend
current_visual_summary: str = ""   # Initialize empty
current_steps_taken: list = []     # Initialize empty
current_generated_operations: list = [] # Initialize empty
current_automoy_status: AutomoyStatus = AutomoyStatus.IDLE


app = FastAPI()

# Determine base path for static files and templates
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

sse_queue = asyncio.Queue()

async def send_operator_update(update: dict):
    """Helper function to put updates onto the SSE queue."""
    try:
        await sse_queue.put(update)
    except Exception as e:
        gui_logger.error(f"Error putting update onto SSE queue: {e}")

@app.on_event("startup")
async def startup_event():
    gui_logger.info(f"FastAPI app startup: current_user_goal is '{current_user_goal}'")
    initial_objective = await current_objective_store.get_objective()
    gui_logger.info(f"FastAPI app startup: initial objective from store is '{initial_objective}'")
    # Send initial state to clients connecting at startup
    # This ensures the GUI starts with the correct "Formulated Objective:"
    await send_operator_update({
        "objective": initial_objective,
        "goal": current_user_goal, # Should be ""
        "thinking": current_thinking_process,
        "visual_summary": current_visual_summary,
        "steps_taken": current_steps_taken,
        "generated_operations": current_generated_operations,
        "status": current_automoy_status # Use the enum member directly if client handles it, or .value
    })


class Goal(BaseModel):
    goal: str

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = TEMPLATES_DIR / "index.html"
    if not index_path.is_file():
        gui_logger.error(f"index.html not found at {index_path}")
        raise HTTPException(status_code=500, detail="index.html not found")
    return FileResponse(index_path)

@app.post("/set_goal")
async def set_goal(goal_data: Goal, request: Request): # Added request: Request
    global current_user_goal, current_thinking_process, current_visual_summary, current_steps_taken, current_generated_operations, current_automoy_status
    
    previous_goal = current_user_goal
    gui_logger.info(f"/set_goal called. Previous goal: '{previous_goal}'. Received new goal: '{goal_data.goal}'. Client: {request.client}")
    
    current_user_goal = goal_data.goal
    
    # Reset other states when a new goal is set
    current_thinking_process = "Thinking..." # Reset to initial thinking message
    current_visual_summary = ""
    current_steps_taken = []
    current_generated_operations = []
    current_automoy_status = AutomoyStatus.THINKING # Change status to thinking

    await current_objective_store.set_objective("Formulating objective...") # Show "Formulating..."
    
    gui_logger.info(f"/set_goal updated current_user_goal to: '{current_user_goal}' and reset related states.")
    
    # Push full state update
    await send_operator_update({
        "goal": current_user_goal,
        "objective": await current_objective_store.get_objective(),
        "thinking": current_thinking_process,
        "visual_summary": current_visual_summary,
        "steps_taken": current_steps_taken,
        "generated_operations": current_generated_operations,
        "status": current_automoy_status
    })
    return {"message": "Goal set successfully", "current_goal": current_user_goal}

@app.get("/state/goal")
async def get_goal_state():
    gui_logger.info(f"/state/goal called. Returning goal: '{current_user_goal}'")
    return {"goal": current_user_goal}

@app.get("/state/objective")
async def get_objective_state():
    obj = await current_objective_store.get_objective()
    gui_logger.info(f"/state/objective called. Returning objective: '{obj}'")
    return {"objective": obj}

@app.get("/operator_state")
async def get_operator_state():
    obj = await current_objective_store.get_objective()
    # status_val = current_automoy_status.value if hasattr(current_automoy_status, 'value') else current_automoy_status
    gui_logger.info(f"/operator_state called. Goal: '{current_user_goal}', Objective: '{obj}', Status: '{current_automoy_status}'")
    return {
        "goal": current_user_goal,
        "objective": obj,
        "thinking": current_thinking_process,
        "visual_summary": current_visual_summary,
        "steps_taken": current_steps_taken,
        "generated_operations": current_generated_operations,
        "status": current_automoy_status, # Send enum member or .value depending on client
    }

async def sse_event_publisher():
    while True:
        try:
            update = await sse_queue.get()
            yield {"data": json.dumps(update)} # Ensure json is imported
        except asyncio.CancelledError:
            gui_logger.info("SSE publisher task cancelled.")
            break
        except Exception as e:
            gui_logger.error(f"Error in SSE publisher: {e}")
            # Avoid breaking the loop for other errors, maybe add a small delay
            await asyncio.sleep(0.1)


@app.get("/stream_operator_updates")
async def stream_operator_updates_endpoint(request: Request): # Added request
    # Need to import json for dumps
    import json
    # Also, the publisher should yield dicts that EventSourceResponse can serialize,
    # or strings directly. If json.dumps is used, it should be `data: json.dumps(update)`.
