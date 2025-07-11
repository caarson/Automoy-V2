import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio

# --- Constants ---
GUI_PORT = 8001
LOG_DIR_GUI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "debug", "logs", "gui")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gui_state.json") # File in project root to match backend
GOAL_REQUEST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "goal_request.json") # File in project root to match backend

# --- Logging Setup ---
os.makedirs(LOG_DIR_GUI, exist_ok=True)
LOG_FILE_GUI = os.path.join(LOG_DIR_GUI, "gui_output.log")

# --- Basic print for early diagnostics ---
print(f"[GUI_SCRIPT_START] gui.py execution started. Log file target: {LOG_FILE_GUI}")

# --- Configure logging ---
logger = logging.getLogger("GUI")
logger.setLevel(logging.DEBUG)

if logger.hasHandlers():
    logger.handlers.clear()

# File handler
fh = logging.FileHandler(LOG_FILE_GUI, mode='w')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

# Console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

logger.info("GUI Logging initialized.")

# --- Pydantic Models ---
class GoalData(BaseModel):
    goal: str

# --- State Management Functions (GUI is now mostly a reader) ---
def read_state():
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            # Ensure all required fields exist with proper defaults
            defaults = {
                "operator_status": "initializing",
                "objective": "Waiting for backend...",
                "current_step_details": "Backend is starting...",
                "thinking": "System initializing...",  # Replace visual with thinking
                "operations_log": [],
                "operation": "No operations yet",  # This maps to Current Operation  
                "past_operation": "No operations yet",  # This maps to Past Operation
                "step": "Waiting for goal...",
                "status": "idle",
                "goal": ""
            }
            # Merge defaults with actual state, giving priority to actual state
            for key, default_value in defaults.items():
                if key not in state or not state[key]:
                    state[key] = default_value
            return state
    except (FileNotFoundError, json.JSONDecodeError):
        # Return a complete default structure if file doesn't exist or is corrupt
        return {
            "operator_status": "initializing",
            "objective": "Waiting for backend...",
            "current_step_details": "Backend is starting...",
            "thinking": "System initializing...",  # Replace visual with thinking
            "operations_log": [],
            "operation": "No operations yet", 
            "past_operation": "No operations yet",
            "step": "Waiting for goal...",
            "status": "idle",
            "goal": ""
        }

# --- FastAPI Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Clean up old request file on startup
    if os.path.exists(GOAL_REQUEST_FILE):
        os.remove(GOAL_REQUEST_FILE)
    yield
    print("[GUI_LIFESPAN] GUI shutting down.")

# --- FastAPI App ---
app = FastAPI(lifespan=lifespan)
script_dir = os.path.dirname(__file__)
static_files_path = os.path.join(script_dir, "static")
app.mount("/static", StaticFiles(directory=static_files_path), name="static")

# --- API Endpoints ---
@app.post("/set_goal")
async def set_goal(goal_data: GoalData):
    try:
        goal_text = goal_data.goal.strip()
        if not goal_text:
            return JSONResponse(status_code=400, content={"error": "Goal cannot be empty"})

        # Write the goal to the request file for the backend to pick up
        request_payload = {
            "goal": goal_text,
            "timestamp": time.time()
        }
        with open(GOAL_REQUEST_FILE, 'w') as f:
            json.dump(request_payload, f)

        return JSONResponse(content={"message": "Goal submitted for processing"})
    except Exception as e:
        logger.error(f"Error writing goal request file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to submit goal: {e}")

@app.get("/stream_operator_updates")
async def stream_operator_updates(request: Request):
    async def event_generator():
        last_state = {}
        while True:
            if await request.is_disconnected():
                logger.info("[GUI /stream] Client disconnected.")
                break

            current_state = read_state()
            if current_state != last_state:
                yield f"data: {json.dumps(current_state)}\n\n"
                last_state = current_state
            
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/", response_class=HTMLResponse)
async def get_root(request: Request):
    try:
        with open(os.path.join(script_dir, "templates", "index.html"), "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        logger.error(f"HTML file not found at {os.path.join(script_dir, 'templates', 'index.html')}")
        raise HTTPException(status_code=500, detail="Internal server error: UI file not found.")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

def run_gui(host="127.0.0.1", port=8001):
    logger.info(f"Attempting to start Uvicorn on {host}:{port} with 1 worker")
    print(f"[GUI_RUN_GUI_PRINT] Attempting to start Uvicorn on {host}:{port} with 1 worker")
    try:
        uvicorn.run(app, host=host, port=port, workers=1, log_config=None) 
        logger.info(f"Uvicorn server started successfully on {host}:{port}")
        print(f"[GUI_RUN_GUI_PRINT] Uvicorn server started successfully on {host}:{port}")
    except Exception as e:
        logger.error(f"Failed to start Uvicorn: {e}", exc_info=True)
        print(f"[GUI_RUN_GUI_PRINT] Failed to start Uvicorn: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Automoy GUI")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for the GUI server")
    parser.add_argument("--port", type=int, default=8001, help="Port for the GUI server")
    args = parser.parse_args()

    logger.info(f"Starting GUI script directly with args: {args}")
    print(f"[GUI_MAIN_PRINT] Starting GUI script directly with args: {args}")
    run_gui(host=args.host, port=args.port)
