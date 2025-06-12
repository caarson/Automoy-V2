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

@app.get("/health") # ADDED health check endpoint
async def health_check():
    logger.info("[GUI /health] Health check endpoint called successfully.")
    return {"status": "healthy"}

@app.get("/operator_state") # ADDED operator state endpoint
async def get_operator_state():
    logger.debug(f"[GUI /operator_state] Requested. Current state: user_goal='{current_user_goal}', formulated_objective='{current_formulated_objective}', operator_status='{operator_status}', is_paused={is_paused}")
    return {
        "user_goal": current_user_goal,
        "formulated_objective": current_formulated_objective,
        "operator_status": operator_status,
        "is_paused": is_paused,
        "current_visual_analysis": current_visual_analysis,
        "current_thinking_process": current_thinking_process,
        "current_steps_generated": current_steps_generated,
        "current_operations_generated": current_operations_generated,
        "current_operation_display": current_operation_display,
        "past_operation_display": past_operation_display,
        "processed_screenshot_available": processed_screenshot_available,
        "llm_stream_content": llm_stream_content 
    }

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    print("[GUI FastAPI] Root path / requested. Serving index.html.", flush=True)
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/set_goal")
async def set_goal(data: GoalData):
    global current_user_goal, operator_status, current_formulated_objective
    logger.info(f"[GUI /set_goal] Received new goal: {data.goal}")
    current_user_goal = data.goal
    operator_status = "Processing Goal" # Or some other initial status
    current_formulated_objective = "" # Clear previous formulated objective
    # Potentially trigger some backend processing if needed immediately
    # For now, main.py's loop will pick up this new goal via /operator_state
    return {
        "message": "Goal received successfully", 
        "goal": current_user_goal,
        "operator_status": operator_status
    }

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
async def update_steps_state(data: StateUpdateComplexSteps): # Changed to use StateUpdateComplexSteps
    global current_steps_generated
    logger.info(f"[GUI /state/steps_generated] Received steps update: {len(data.steps)} steps. Error: {data.error}")
    if data.error:
        current_steps_generated = [{"description": f"Error generating steps: {data.error}"}] 
    else:
        current_steps_generated = data.steps 
    return {"message": "Steps generated state updated"}

@app.post("/state/operations_generated") # Added endpoint
async def update_operations_state(data: StateUpdateOperations): # Changed to use StateUpdateOperations
    global current_operations_generated, current_thinking_process
    logger.info(f"[GUI /state/operations_generated] Received operations update: {data.operations}") 
    current_operations_generated = {"operations": data.operations} 
    if data.thinking_process:
        current_thinking_process = data.thinking_process 
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

@app.post("/state/screenshot") 
async def update_screenshot_state(payload: ScreenshotUpdateRequest): # MODIFIED to use Pydantic model
    global processed_screenshot_available # REMOVED window_global_ref
    logger.info(f"[GUI /state/screenshot] Received screenshot update notification with path: {payload.path}")
    
    new_screenshot_abs_path_str = payload.path # MODIFIED
    # Ensure BASE_DIR is defined correctly, usually os.path.dirname(__file__)
    static_destination_path = Path(BASE_DIR) / "static" / "automoy_current.png" # Changed to automoy_current.png
    
    if new_screenshot_abs_path_str:
        source_path = Path(new_screenshot_abs_path_str)
        static_destination_path = Path(BASE_DIR) / "static" / "automoy_current.png" # Changed to automoy_current.png
        
        if source_path.exists():
            try:
                os.makedirs(static_destination_path.parent, exist_ok=True)
                shutil.copy(str(source_path), str(static_destination_path))
                logger.info(f"[GUI /state/screenshot] Copied screenshot from {source_path} to {static_destination_path}")
                # This endpoint is for the RAW screenshot. GUI will refresh it via /automoy_current.png?t=timestamp
                # The processed_screenshot_available flag is for the *processed* one.
                # We can trigger a generic refresh if needed, or let the frontend poll/refresh specific images.
                # REMOVED JS evaluation call
                # if window_global_ref:
                #     try:
                #         # Call refreshScreenshot in JS, which should now handle both raw and processed based on availability
                #         js_command = "if (typeof refreshScreenshot === 'function') { refreshScreenshot('raw'); console.log('[GUI /state/screenshot] JS refreshScreenshot(\\'raw\\') called.'); } else { console.error('[GUI /state/screenshot] refreshScreenshot function not defined in JS.'); }"
                #         window_global_ref.evaluate_js(js_command)
                #         logger.info(f"[GUI /state/screenshot] Executed JS command: {js_command}")
                #     except Exception as e:
                #         logger.error(f"[GUI /state/screenshot][ERROR] Failed to execute JS for screenshot refresh: {e}")
            except Exception as e:
                logger.error(f"[GUI /state/screenshot] Error copying screenshot to static folder: {e}")
        else:
            logger.warning(f"[GUI /state/screenshot] Source screenshot path does not exist: {source_path}")
    else:
        logger.warning("[GUI /state/screenshot] Screenshot update notification received, but no path provided in payload.")
        
    return {"message": "Raw screenshot path received and copied to static/automoy_current.png"}

@app.post("/state/screenshot_processed")
async def screenshot_processed_notification(_: ProcessedScreenshotNotif): # MODIFIED to use Pydantic model
    global processed_screenshot_available # REMOVED window_global_ref
    processed_screenshot_available = True
    logger.info("[GUI /state/screenshot_processed] Processed screenshot notification received.") # Simplified log
    # REMOVED JS evaluation call
    # if window_global_ref:
    #     try:
    #         js_command = "if (typeof refreshScreenshot === 'function') { refreshScreenshot('processed'); console.log('[GUI /state/screenshot_processed] JS refreshScreenshot(\\'processed\\') called.'); } else { console.error('[GUI /state/screenshot_processed] refreshScreenshot function not defined in JS.'); }"
    #         window_global_ref.evaluate_js(js_command)
    #         logger.info(f"[GUI /state/screenshot_processed] Executed JS command: {js_command}")
    #     except Exception as e:
    #         logger.error(f"[GUI /state/screenshot_processed][ERROR] Failed to execute JS for screenshot refresh: {e}")
    # else:
    #     logger.warning("[GUI /state/screenshot_processed][WARN] window_global_ref not available to trigger JS screenshot refresh.")
    return {"message": "Processed screenshot notification received"}

@app.post("/state/visual_analysis") # ADDED (or corrected if it was /state/visual before)
async def update_visual_analysis_state(data: VisualAnalysisUpdateRequest): # MODIFIED
    global current_visual_analysis
    logger.info(f"[GUI /state/visual_analysis] Received visual analysis update: {data.text[:100]}...") # MODIFIED
    current_visual_analysis = data.text # MODIFIED
    return {"message": "Visual analysis state updated"}

@app.post("/state/operator_status")
async def update_operator_status(data: OperatorStatusUpdateRequest): # MODIFIED
    global operator_status
    logger.info(f"[GUI /state/operator_status] Received status update: {data.text}") # MODIFIED
    operator_status = data.text # MODIFIED
    return {"message": "Operator status updated"}

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
    """Server-Sent Events endpoint to stream real-time operator state to the frontend"""
    async def event_generator():
        while True:
            # Prepare comprehensive state snapshot
            state = {
                "user_goal": current_user_goal,
                "formulated_objective": current_formulated_objective,
                "operator_status": operator_status,
                "is_paused": is_paused,
                "current_visual_analysis": current_visual_analysis,
                "current_thinking_process": current_thinking_process,
                "current_steps_generated": current_steps_generated,
                "current_operations_generated": current_operations_generated,
                "current_operation_display": current_operation_display,
                "past_operation_display": past_operation_display,
                "processed_screenshot_available": processed_screenshot_available,
                "llm_stream_content": llm_stream_content
            }
            yield f"data: {json.dumps(state, default=str)}\n\n"
            await asyncio.sleep(0.5)  # adjust interval as needed
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
