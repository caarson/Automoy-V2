# --- Global Imports ---
# Standard library imports
import asyncio
import json
import logging.handlers
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
import urllib.request
from typing import Any, Dict, Optional

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Third-party imports
import httpx
import socket

# Optional GUI imports
try:
    import webview as pywebview  # Import webview module and alias it as pywebview for compatibility
    PYWEBVIEW_AVAILABLE = True
except ImportError:
    pywebview = None
    PYWEBVIEW_AVAILABLE = False

# --- Project-specific Imports ---
from config.config import (
    VERSION, DEBUG_MODE, GUI_HOST, GUI_PORT, GUI_WIDTH, GUI_HEIGHT,
    GUI_RESIZABLE, GUI_ON_TOP, OMNIPARSER_BASE_URL, AUTOMOY_APP_NAME,
    LOG_FILE_PATH, LOG_FILE_CORE, MAIN_LOOP_SLEEP_INTERVAL, MAX_LOG_FILE_SIZE, LOG_BACKUP_COUNT
)
from core.data_models import (
    AutomoyState, 
    OperatorState, 
    GUIState, 
    ExecutionState, 
    get_initial_state, 
    read_state, 
    write_state, 
    GOAL_REQUEST_FILE
)
from core.lm.lm_interface import MainInterface # CHANGED
from core.operate import AutomoyOperator
# Removed debug_utils imports that were causing issues
# from core.utils.debug_utils import (
#     log_system_info,
#     log_process_and_thread_info,
#     get_caller_info
# )

# --- Configuration & Constants ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")) # ADDED BACK

# --- Helper Functions ---
def wait_for_gui_health(host: str, port: int, timeout: int = 30, health_endpoint: str = "/health") -> bool:
    """Waits for the GUI server to become healthy."""
    start_time = time.time()
    url = f"http://{host}:{port}{health_endpoint}"
    while time.time() - start_time < timeout:
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False

def is_process_running_on_port(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
        except socket.error:
            return True
        return False

def kill_process_on_port(port: int):
    try:
        if os.name == 'nt': 
            command = f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr ":{port}"\') do taskkill /F /PID %a'
            subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        else: 
            command = f"lsof -ti tcp:{port} | xargs kill -9"
            subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
    except Exception:
        pass

class JSBridge:
    """Bridge for JavaScript to Python communication."""
    def __init__(self, stop_event: threading.Event, gui_host: str, gui_port: int):
        self._stop_event = stop_event
        self._gui_host = gui_host
        self._gui_port = gui_port

    def shutdown(self):
        """Called from JS to initiate a graceful shutdown."""
        # logger.info("JSBridge: Shutdown requested from GUI.")  # logger might not be defined yet
        if not self._stop_event.is_set():
            self._stop_event.set()

# --- Global Variables ---
webview_window_global = None  # Will be set to pywebview.Window when pywebview is imported
current_gui_visibility: bool = False
operator: 'AutomoyOperator' = None
gui_process_global: Optional[subprocess.Popen] = None

# Lock for thread-safe access to current_operator_state
operator_state_lock = asyncio.Lock()
current_state = OperatorState() # Initialize with OperatorState

# --- Logging Setup ---
logger = logging.getLogger(AUTOMOY_APP_NAME) # Use imported AUTOMOY_APP_NAME

def setup_logging(console_level=logging.INFO, file_level=logging.DEBUG):
    logger.setLevel(min(console_level, file_level))
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(threadName)s - %(levelname)s - %(message)s')

    # Clear existing handlers to prevent duplicate logging
    if logger.hasHandlers():
        logger.handlers.clear()

    # Console Handler
    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Handler (Rotating)
    log_dir = os.path.dirname(LOG_FILE_PATH) # Use imported LOG_FILE_PATH
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except OSError as e:
            print(f"Could not create log directory {log_dir}: {e}", file=sys.stderr)
            return
    
    # Delete existing log file before setting up new handler
    if log_dir and os.path.exists(LOG_FILE_PATH):
        try:
            os.remove(LOG_FILE_PATH)
            print(f"Deleted existing core log file: {LOG_FILE_PATH}", file=sys.stderr) # Use print for early messages
        except OSError as e:
            print(f"Could not delete core log file {LOG_FILE_PATH}: {e}", file=sys.stderr)
    
    try:
        fh = logging.handlers.RotatingFileHandler(
            LOG_FILE_PATH, maxBytes=MAX_LOG_FILE_SIZE, backupCount=LOG_BACKUP_COUNT
        )
        fh.setLevel(file_level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception as e:
        print(f"Failed to set up file logging: {e}", file=sys.stderr)
        # Continue without file logging

def start_gui_and_create_webview_window(gui_host_local: str, gui_port_local: int, stop_event_local: threading.Event):
    global gui_process_global, webview_window_global # Removed app_config from global as it's not used here directly
    
    logger.info("Starting GUI and creating webview window...")
    if PYWEBVIEW_AVAILABLE:
        logger.info("pywebview is available and will be used for native window")
    else:
        logger.warning("pywebview is not available - GUI will only be accessible via browser")
    
    # --- Pre-launch: Kill any process on the GUI port ---
    logger.info(f"Checking for existing process on GUI port {gui_port_local}...")
    if is_process_running_on_port(gui_port_local):
        logger.warning(f"Port {gui_port_local} is in use. Attempting to terminate the process.")
        kill_process_on_port(gui_port_local)
        time.sleep(1.5) # Give a moment to the port to be released
        if is_process_running_on_port(gui_port_local):
            logger.error(f"Failed to free up port {gui_port_local}. The GUI cannot start. Shutting down.")
            return False 
        else:
            logger.info(f"Successfully terminated process on port {gui_port_local}.")
    else:
        logger.info(f"Port {gui_port_local} is free.")
    # --- End Pre-launch ---

    # Ensure GUI process is started first
    gui_script_path = os.path.join(os.path.dirname(__file__), "..", "gui", "gui.py")
    # Use the imported GUI_HOST and GUI_PORT for consistency, though gui_host_local/gui_port_local are passed
    gui_command = [sys.executable, "-u", gui_script_path, "--host", gui_host_local, "--port", str(gui_port_local)]

    logger.info(f"Starting GUI subprocess: {' '.join(gui_command)}")
    try:
        # Redirect stdout and stderr to PIPE to allow logging them from main process if needed
        # Or, if gui.py handles its own logging to a file, this might not be strictly necessary
        # but can be useful for capturing early startup errors from the GUI script.
        gui_process_global = subprocess.Popen(gui_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        logger.info(f"GUI subprocess started with PID: {gui_process_global.pid}")
        # Optional: Start threads to log GUI stdout/stderr if not handled by gui.py itself
        # threading.Thread(target=log_subprocess_output, args=(gui_process_global.stdout, "GUI_STDOUT"), daemon=True).start()
        # threading.Thread(target=log_subprocess_output, args=(gui_process_global.stderr, "GUI_STDERR"), daemon=True).start()

    except Exception as e:
        logger.error(f"Failed to start GUI subprocess: {e}", exc_info=True)
        return False # Indicate failure

    # Wait for GUI to be healthy
    if not wait_for_gui_health(gui_host_local, gui_port_local, timeout=30):
        logger.error("GUI did not become healthy in time. Aborting.")
        # Attempt to terminate the GUI process if it started but didn't become healthy
        if gui_process_global:
            try:
                gui_process_global.terminate()
                gui_process_global.wait(timeout=5) # Wait for termination
            except Exception as e_term:
                logger.error(f"Error terminating GUI process during health check failure: {e_term}", exc_info=True)
                # Fallback to kill if terminate fails or times out
                if gui_process_global and gui_process_global.poll() is None: # Check if still running
                    gui_process_global.kill()
                    logger.warning("GUI process killed due to health check failure and termination issues.")
        return False # Indicate failure

    logger.info("GUI is healthy and responsive.")

    # --- Ensure original URL and title are used ---
    gui_url = f"http://{gui_host_local}:{gui_port_local}" # THIS IS THE CORRECT URL
    # Use the directly imported VERSION variable
    window_title = f"Automoy GUI @ {VERSION} - {gui_url}" # THIS IS THE CORRECT TITLE
    # --- End URL and title section ---
    logger.info(f"Attempting to create PyWebview window with title: '{window_title}' and URL: '{gui_url}'")
    
    if not PYWEBVIEW_AVAILABLE:
        logger.warning("pywebview is not available (PYWEBVIEW_AVAILABLE=False). Skipping window creation.")
        logger.info(f"You can access the GUI by opening this URL in your browser: {gui_url}")
        webview_window_global = None
        return True  # Consider this successful since the GUI server is running
        
    if pywebview is None:
        logger.warning("pywebview module is None. Skipping window creation.")
        logger.info(f"You can access the GUI by opening this URL in your browser: {gui_url}")
        webview_window_global = None
        return True  # Consider this successful since the GUI server is running
        
    try:
        logger.info("Creating pywebview window...")
        logger.info(f"Window config: width={GUI_WIDTH}, height={GUI_HEIGHT}, resizable={GUI_RESIZABLE}, on_top={GUI_ON_TOP}")
        
        webview_window_global = pywebview.create_window(
            title=window_title,
            url=gui_url,
            width=GUI_WIDTH, # Use imported config
            height=GUI_HEIGHT, # Use imported config
            resizable=GUI_RESIZABLE, # Use imported config
            on_top=GUI_ON_TOP, # Use imported config
            frameless=False, # Changed to False for better visibility during testing
            js_api=JSBridge(stop_event_local, gui_host_local, gui_port_local) # Pass necessary args
        )
        logger.info(f"PyWebview window '{window_title}' created successfully. Type: {type(webview_window_global)}")
        logger.info(f"Window object: {webview_window_global}")
    except Exception as e:
        logger.error(f"Failed to create PyWebview window: {e}", exc_info=True)
        logger.info(f"You can access the GUI by opening this URL in your browser: {gui_url}")
        webview_window_global = None
        return False

    if webview_window_global:
        logger.info(f"PyWebview window '{window_title}' created successfully (using test parameters). Global webview_window_global is set.")
    else:
        logger.error(f"PyWebview window creation FAILED for title '{window_title}' (using test_parameters). webview.create_window returned None. webview_window_global is None.")
        return False

    return True

async def async_manage_automoy_gui_visibility(target_visibility: bool):
    global current_gui_visibility
    if current_gui_visibility == target_visibility:
        logger.debug(f"GUI visibility already set to: {'visible' if target_visibility else 'hidden'}")
        return

    logger.debug(f"Request to change GUI visibility to: {'visible' if target_visibility else 'hidden'}")

    if webview_window_global:
        try:
            if target_visibility:
                logger.info("Showing PyWebview window via Python API.")
                webview_window_global.show()
            else:
                logger.info("Hiding PyWebview window via Python API.")
                webview_window_global.hide()
            current_gui_visibility = target_visibility
            logger.debug(f"GUI visibility change completed to: {'visible' if target_visibility else 'hidden'}")
        except Exception as e:
            logger.warning(f"Error changing PyWebview window visibility: {e}")
            logger.debug(f"Webview visibility change failed, but this won't prevent core operations.")
            # Don't raise the exception - just log it and continue
    else:
        logger.warning("PyWebview window (webview_window_global) not available. Cannot manage GUI visibility directly.")


def cleanup_processes():
    global webview_window_global

    logger.info("Initiating Automoy core processes cleanup (cleanup_processes)...")
    
    # Destroy PyWebview window (this is also in the main cleanup() function, but can be here for robustness)
    if webview_window_global: # Check if it exists
        logger.info("cleanup_processes: Requesting PyWebview window destruction (if not already done)...")
        try:
            if hasattr(webview_window_global, 'destroy'): 
                webview_window_global.destroy()
                logger.info("cleanup_processes: PyWebview window.destroy() called.")
        except Exception as e:
            logger.error(f"cleanup_processes: Error during PyWebview window destruction: {e}", exc_info=True)
    
    # Stop embedded Uvicorn server / AutomoyOperator
    if operator and hasattr(operator, 'stop_gracefully'):
        logger.info("cleanup_processes: Stopping AutomoyOperator...")
        try:
            operator.stop_gracefully() 
            logger.info("cleanup_processes: AutomoyOperator stopped.")
        except Exception as e:
            logger.error(f"cleanup_processes: Error stopping AutomoyOperator: {e}", exc_info=True)
    
    logger.info("Automoy core processes cleanup (cleanup_processes) finished.")

async def async_manage_gui_window(action: str) -> bool:
    """GUI window management function for AutomoyOperator."""
    logger.debug(f"Managing GUI window: {action}")
    try:
        if action == "show":
            await async_manage_automoy_gui_visibility(True)
            return True
        elif action == "hide":
            await async_manage_automoy_gui_visibility(False)
            return True
        else:
            logger.warning(f"Unknown GUI window action: {action}")
            return False
    except Exception as e:
        logger.error(f"Error managing GUI window ({action}): {e}", exc_info=True)
        return False

async def update_gui_state(updates: Dict[str, Any]):
    """Reads the current state from the file, applies updates, and writes it back."""
    try:
        # This function is called from the single-threaded async loop,
        # so a lock isn't strictly necessary unless another thread modifies the file.
        current_state = read_state()
        current_state.update(updates)
        write_state(current_state)
        logger.debug(f"Updated GUI state file with: {updates}")
    except Exception as e:
        logger.error(f"Failed to update GUI state file: {e}", exc_info=True)

async def main_async_operations(stop_event: asyncio.Event):
    global webview_window_global, gui_process_global

    logger.info(f"main_async_operations started.")

    gui_host_local = GUI_HOST
    gui_port_local = GUI_PORT
    
    # Initialize OmniParser for visual analysis
    logger.info("Initializing OmniParser for visual analysis...")
    try:
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        omniparser_manager = OmniParserServerManager()
        
        # Check if server is already running
        if omniparser_manager.is_server_ready():
            logger.info("OmniParser server is already running")
            omniparser = omniparser_manager.get_interface()
        else:
            logger.info("Starting OmniParser server...")
            server_process = omniparser_manager.start_server()
            if server_process:
                if omniparser_manager.wait_for_server(timeout=60):
                    logger.info("OmniParser server started successfully")
                    omniparser = omniparser_manager.get_interface()
                else:
                    logger.error("OmniParser server failed to become ready within timeout")
                    omniparser = None
            else:
                logger.error("Failed to start OmniParser server")
                omniparser = None
    except Exception as e:
        logger.error(f"Error initializing OmniParser: {e}", exc_info=True)
        omniparser = None
    
    if omniparser:
        logger.info("OmniParser initialized successfully for visual analysis")
    else:
        logger.warning("OmniParser initialization failed - visual analysis will be limited")
            
    pause_event = asyncio.Event()
    pause_event.set()  # Start unpaused

    logger.info("Initializing GUI state file at startup.")
    write_state(get_initial_state())

    # Initialize AutomoyOperator
    try:
        global operator
        logger.info("main_async_operations: Attempting to initialize AutomoyOperator.")
        
        # Create an async wrapper for the GUI state update function
        async def async_update_gui_state_wrapper(endpoint, payload):
            # Handle endpoint-based updates for different state aspects
            if endpoint == "/state/thinking":
                # Update thinking field specifically
                if isinstance(payload, dict) and "text" in payload:
                    await update_gui_state({"thinking": payload["text"]})
                else:
                    await update_gui_state({"thinking": str(payload)})
            elif endpoint == "/state/current_operation":
                # Update current operation
                if isinstance(payload, dict) and "text" in payload:
                    await update_gui_state({"operation": payload["text"]})
                else:
                    await update_gui_state({"operation": str(payload)})
            elif endpoint == "/state/past_operation":
                # Update past operation
                if isinstance(payload, dict) and "text" in payload:
                    await update_gui_state({"past_operation": payload["text"]})
                else:
                    await update_gui_state({"past_operation": str(payload)})
            elif endpoint == "/state/operator_status":
                # Update operator status
                if isinstance(payload, dict) and "text" in payload:
                    await update_gui_state({"operator_status": payload["text"]})
                else:
                    await update_gui_state({"operator_status": str(payload)})
            else:
                # For all other endpoints, use the payload directly
                await update_gui_state(payload)
        
        operator = AutomoyOperator(
            objective="", # Initial objective is empty until set by user
            manage_gui_window_func=async_manage_gui_window,
            omniparser=omniparser,  # Restored visual analysis capability
            pause_event=pause_event,
            update_gui_state_func=async_update_gui_state_wrapper
        )
        
        # Set additional attributes after initialization
        operator._update_gui_state_func = async_update_gui_state_wrapper
        operator.webview_window = webview_window_global
        operator.gui_host = gui_host_local
        operator.gui_port = gui_port_local
        operator.stop_event = stop_event
        
        # Initialize desktop utilities for screen interaction
        try:
            from core.utils.operating_system.desktop_utils import DesktopUtils
            operator.desktop_utils = DesktopUtils()
            logger.info("Desktop utilities initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing desktop utilities: {e}", exc_info=True)
            operator.desktop_utils = None
        
        # Verify dependencies are properly set
        logger.info(f"Operator dependencies set - omniparser: {omniparser is not None}, "
                   f"manage_gui_window_func: {operator.manage_gui_window_func is not None}, "
                   f"_update_gui_state_func: {operator._update_gui_state_func is not None}, "
                   f"desktop_utils: {operator.desktop_utils is not None}")
        
        logger.info("main_async_operations: AutomoyOperator initialized successfully.")
    except Exception as e:
        logger.error(f"main_async_operations: Failed to initialize AutomoyOperator: {e}", exc_info=True)
        if stop_event: stop_event.set()
        return

    # Wait a brief moment for webview window to potentially be shown by main thread
    await asyncio.sleep(1)
    
    # Try to set GUI visibility but don't let it block the main operations
    try:
        await asyncio.wait_for(async_manage_automoy_gui_visibility(True), timeout=5.0)
        logger.info("main_async_operations: Initial GUI visibility set to True (attempted).")
    except asyncio.TimeoutError:
        logger.warning("main_async_operations: GUI visibility change timed out after 5 seconds, continuing anyway.")
    except Exception as e:
        logger.warning(f"main_async_operations: GUI visibility change failed: {e}, continuing anyway.")
    
    # Update state to idle after successful initialization
    logger.info("Initialization complete. Setting GUI state to idle.")
    write_state({
        "operator_status": "idle",
        "gui_status": "ready",
        "current_step_details": "System initialized and ready for goals.",
        "thinking": "System ready - waiting for goal input",
        "goal": ""
    })
    
    logger.info("Entering main polling loop to monitor for goal requests.")

    while not stop_event.is_set():
        try:
            # Debug: Log polling activity every 10 iterations
            polling_counter = getattr(main_async_operations, 'polling_counter', 0)
            polling_counter += 1
            main_async_operations.polling_counter = polling_counter
            
            if polling_counter % 20 == 0:  # Every 10 seconds (20 * 0.5s)
                logger.debug(f"Polling loop iteration #{polling_counter}, checking for goals...")
            
            if os.path.exists(GOAL_REQUEST_FILE):
                logger.info(f"Detected goal request file: {GOAL_REQUEST_FILE}")
                user_goal = None
                
                # Add retries to handle race conditions and file locking
                max_retries = 3
                retry_delay = 0.1
                
                for attempt in range(max_retries):
                    try:
                        # Check if file has content before trying to read
                        if os.path.getsize(GOAL_REQUEST_FILE) == 0:
                            logger.warning(f"Goal request file is empty on attempt {attempt + 1}, retrying...")
                            await asyncio.sleep(retry_delay)
                            continue
                        
                        # Try different encodings to handle various file formats
                        content = None
                        for encoding in ['utf-8-sig', 'utf-8', 'utf-16', 'cp1252']:
                            try:
                                with open(GOAL_REQUEST_FILE, 'r', encoding=encoding) as f:
                                    content = f.read().strip()
                                    break
                            except UnicodeDecodeError:
                                continue
                        
                        if not content:
                            logger.warning(f"Goal request file could not be decoded or is empty on attempt {attempt + 1}, retrying...")
                            await asyncio.sleep(retry_delay)
                            continue
                            
                        request_data = json.loads(content)
                        user_goal = request_data.get("goal")
                            
                        # Successfully read the file, now remove it
                        os.remove(GOAL_REQUEST_FILE)
                        logger.info(f"Successfully read and removed goal request file on attempt {attempt + 1}")
                        break
                        
                    except (json.JSONDecodeError, IOError, OSError) as e:
                        logger.warning(f"Error reading goal request file on attempt {attempt + 1}: {e}")
                        if attempt == max_retries - 1:
                            logger.error(f"Failed to read goal request file after {max_retries} attempts, removing it")
                            try:
                                os.remove(GOAL_REQUEST_FILE)
                            except:
                                pass
                            continue
                        await asyncio.sleep(retry_delay)

                if not user_goal:
                    logger.warning("Goal request file was empty or invalid after all retries. Ignoring.")
                    continue

                logger.info(f"New goal received: '{user_goal}'")
                write_state({
                    "operator_status": "thinking",
                    "goal": user_goal,  # Store the original goal in GUI state
                    "objective": "Formulating objective...",
                    "current_step_details": f"Processing goal: {user_goal}",
                    "current_operation": "Analyzing goal and formulating strategy",
                    "thinking": "Breaking down the goal into actionable steps...",
                    "operations_log": [],
                    "llm_error_message": None
                })

                # --- Objective Formulation & Execution ---
                try:
                    logger.info("Instantiating MainInterface to formulate objective.")
                    llm_interface = MainInterface() # Correct class from the import
                    logger.info(f"Successfully instantiated llm_interface. Type: {type(llm_interface)}")
                    logger.info("Calling formulate_objective on llm_interface...")
                    
                    # Add timeout wrapper to prevent infinite hanging
                    try:
                        objective_task = asyncio.create_task(
                            llm_interface.formulate_objective(
                                goal=user_goal,
                                session_id=str(uuid.uuid4())
                            )
                        )
                        objective_text, error = await asyncio.wait_for(objective_task, timeout=60.0)
                        logger.info(f"formulate_objective returned: objective_text={objective_text}, error={error}")
                    except asyncio.TimeoutError:
                        logger.error("Objective formulation timed out after 60 seconds")
                        write_state({
                            "operator_status": "error",
                            "goal": user_goal,
                            "objective": "Failed to formulate objective - timeout.",
                            "current_step_details": "LLM call timed out after 60 seconds. Check LMStudio connection.",
                            "thinking": "LLM service timed out - check if LMStudio is running and accessible",
                            "llm_error_message": "Objective formulation timed out. LLM service may be unavailable."
                        })
                        continue

                    if error:
                        logger.error(f"Error formulating objective: {error}")
                        write_state({
                            "operator_status": "error",
                            "goal": user_goal,  # Keep the goal even on error
                            "objective": "Failed to formulate objective.",
                            "current_step_details": str(error),
                            "thinking": f"LLM error during objective formulation: {str(error)}",
                            "llm_error_message": str(error)
                        })
                        continue
                    elif objective_text:
                        # Extract the final objective from the LLM response
                        # The LLM often includes reasoning followed by the actual objective
                        lines = objective_text.strip().split('\n')
                        final_objective = lines[-1].strip() if lines else objective_text.strip()
                        
                        logger.info(f"Successfully formulated objective: {final_objective}")
                        write_state({
                            "operator_status": "running",
                            "goal": user_goal,  # Keep the original goal in GUI state
                            "objective": final_objective,
                            "current_step_details": "Objective formulated. Starting dynamic operation loop...",
                            "current_operation": "Initializing operation sequence",
                            "thinking": f"Ready to execute: {final_objective}",
                            "llm_error_message": None
                        })
                        if operator:
                            logger.info(f"Starting dynamic operator execution for objective: {final_objective}")
                            try:
                                # Store the original goal in the operator for reference
                                operator.original_goal = user_goal
                                operator.set_objective(final_objective)
                                logger.info("operator.set_objective() called successfully with dynamic loop.")
                            except Exception as op_exec_err:
                                logger.error(f"Exception during operator.set_objective: {op_exec_err}", exc_info=True)
                                write_state({
                                    "operator_status": "error",
                                    "goal": user_goal,  # Keep the goal even on error
                                    "objective": "Operator execution failed.",
                                    "current_step_details": str(op_exec_err),
                                    "llm_error_message": str(op_exec_err)
                                })
                        else:
                            logger.error("Operator not initialized, cannot execute objective.")
                            write_state({
                                "operator_status": "error",
                                "goal": user_goal,  # Keep the goal even on error
                                "objective": "Operator not initialized.",
                                "current_step_details": "Cannot execute objective.",
                            })
                    else:
                        logger.error("Failed to formulate objective: LLM returned an empty response.")
                        write_state({
                            "operator_status": "error",
                            "goal": user_goal,  # Keep the goal even on error
                            "objective": "Failed to formulate objective.",
                            "current_step_details": "LLM returned an empty or invalid response.",
                            "thinking": "LLM provided empty response - check model configuration and connectivity",
                            "llm_error_message": "LLM returned an empty or invalid response."
                        })
                        continue

                except AttributeError as ae:
                    logger.error(f"AttributeError during objective formulation: {ae}", exc_info=True)
                    write_state({
                        "operator_status": "error",
                        "goal": user_goal,  # Keep the goal even on error
                        "objective": "An unexpected attribute error occurred.",
                        "current_step_details": f"AttributeError: {str(ae)}",
                        "llm_error_message": "An internal attribute error stopped the process."
                    })
                    continue
                except Exception as e:
                    logger.error(f"An error occurred during operation in main.py: {e}", exc_info=True)
                    write_state({
                        "operator_status": "error",
                        "goal": user_goal,  # Keep the goal even on error
                        "objective": "An unexpected error occurred.",
                        "current_step_details": f"CAUGHT_IN_MAIN_PY: {str(e)}",
                        "operations_log": [],
                        "llm_error_message": "An internal error stopped the process."
                    })
                    continue
            await asyncio.sleep(MAIN_LOOP_SLEEP_INTERVAL)

        except Exception as e:
            logger.critical(f"Critical error in main async loop: {e}", exc_info=True)
            write_state({"operator_status": "error", "current_step_details": "A critical error occurred in the main loop."})
            await asyncio.sleep(5)

    logger.info("main_async_operations loop has exited.")

def signal_handler(sig, frame):
    global gui_process_global 
    logger.info("Signal received, initiating shutdown...")
    if gui_process_global:
        logger.info(f"Terminating GUI subprocess (PID: {gui_process_global.pid})...")
        gui_process_global.terminate()
        try:
            gui_process_global.wait(timeout=5) 
        except subprocess.TimeoutExpired:
            logger.warning("GUI subprocess did not terminate gracefully, killing.")
            gui_process_global.kill()
        logger.info("GUI subprocess terminated.")

def setup_signal_handlers(stop_event_local: threading.Event):
    """Sets up signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f'Signal {signum} received, initiating shutdown...') # Use logger
        if not stop_event_local.is_set():
            stop_event_local.set() # Signal all parts of the application to stop

    # Register signal handlers for SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, signal_handler) # Use signal.SIGINT
    signal.signal(signal.SIGTERM, signal_handler) # Use signal.SIGTERM
    logger.info("Signal handlers for SIGINT and SIGTERM registered.") # Use logger

def main():
    print(">>>>>>>>> CORE/MAIN.PY: MAIN FUNCTION STARTED <<<<<<<<<<")
    global gui_process_global, webview_window_global

    setup_logging()

    print("\n==== AUTOMOY MAIN FUNCTION STARTED ====")
    print(f"Version: {VERSION}, Debug Mode: {DEBUG_MODE}")
    print(f"GUI Host: {GUI_HOST}, Port: {GUI_PORT}")
    print(f"Log File: {LOG_FILE_CORE}")

    # Initialize global stop event (threading.Event)
    stop_event_threading = threading.Event()
    logger.info("Global stop_event_threading initialized in main().")
    print("Global stop_event initialized.")

    # Setup signal handlers for graceful shutdown
    setup_signal_handlers(stop_event_threading)
    print("Signal handlers set up for graceful shutdown.")

    # Start the GUI and create the PyWebview window
    print("\n==== STARTING GUI AND WEBVIEW ====")
    if not start_gui_and_create_webview_window(GUI_HOST, GUI_PORT, stop_event_threading):
        logger.error("main: Failed to start GUI or create webview window. Exiting.")
        print("CRITICAL ERROR: Failed to start GUI or create webview window. Exiting.")
        cleanup() # Ensure cleanup is called
        return

    print(f"GUI process started successfully (PID: {gui_process_global.pid if gui_process_global else 'Unknown'})")
    print("Webview window created successfully.")
    
    if PYWEBVIEW_AVAILABLE:
        print("✓ PyWebView is available - native window will be displayed")
    else:
        print("⚠ PyWebView not available - using Microsoft Edge app mode for native-like window")
    
    logger.info(f"main: GUI process started (PID: {gui_process_global.pid if gui_process_global else 'Unknown'}) and webview_window_global created.")

    def signal_handler_main(sig, frame):
        logger.info("Signal received in main, initiating shutdown...")
        if not stop_event_threading.is_set():
            stop_event_threading.set()

    signal.signal(signal.SIGINT, signal_handler_main)
    signal.signal(signal.SIGTERM, signal_handler_main)
    logger.info("main: Signal handlers registered.")
    logger.info("main: Starting asyncio operations in a separate thread...")
    loop = asyncio.new_event_loop()
    async_thread = threading.Thread(target=run_async_operations_in_thread, args=(stop_event_threading, loop), daemon=True, name="AsyncOpsThread")
    async_thread.start()
    logger.info(f"main: Asyncio operations thread '{async_thread.name}' started (ID: {async_thread.ident}).")
    
    # Give async thread a moment to start, but don't wait too long
    time.sleep(2)
    logger.info("main: Proceeding to webview window display...")

    # ADDED: Check window object before starting webview
    if webview_window_global:
        logger.info(f"main: webview_window_global is set. Proceeding to call pywebview.start(). Window title: '{webview_window_global.title}'")
        logger.info(f"main: Window properties - Width: {getattr(webview_window_global, 'width', 'Unknown')}, Height: {getattr(webview_window_global, 'height', 'Unknown')}")
    else:
        logger.warning("main: webview_window_global is NONE. This may happen if pywebview is not available.")
        logger.info(f"main: GUI is accessible via browser at: http://{GUI_HOST}:{GUI_PORT}")
        
    # Debug: Print pywebview status
    logger.info(f"main: PYWEBVIEW_AVAILABLE = {PYWEBVIEW_AVAILABLE}")
    logger.info(f"main: pywebview module = {pywebview}")
    logger.info(f"main: webview_window_global = {webview_window_global}")

    try:
        logger.info("main: >>>>>>> CALLING pywebview.start() NOW <<<<<<<") # ADDED PROMINENT LOG
        if PYWEBVIEW_AVAILABLE and pywebview and webview_window_global:
            logger.info("main: Starting pywebview with native window...")
            pywebview.start(debug=DEBUG_MODE, private_mode=False)
            logger.info("main: pywebview.start() has returned. GUI window was likely closed by the user.")
        elif PYWEBVIEW_AVAILABLE and pywebview:
            logger.warning("main: pywebview is available but no window was created. GUI accessible via browser only.")
            logger.info(f"main: GUI URL: http://{GUI_HOST}:{GUI_PORT}")
            # Keep the application running even without webview
            while not stop_event_threading.is_set():
                time.sleep(1)
        else:
            logger.warning("main: pywebview is not available. Trying alternative native window method...")
            
            # Try alternative native window method
            gui_url = f"http://{GUI_HOST}:{GUI_PORT}"
            if open_native_window_alternative(gui_url, f"Automoy GUI @ {VERSION}"):
                logger.info("main: Alternative native window opened successfully")
                # Keep the application running while the alternative window is open
                while not stop_event_threading.is_set():
                    time.sleep(1)
            else:
                logger.info(f"main: GUI accessible via browser only at: http://{GUI_HOST}:{GUI_PORT}")
                # Keep the application running even without webview
                while not stop_event_threading.is_set():
                    time.sleep(1)
    except Exception as e:
        logger.error(f"main: Error during PyWebview start: {e}", exc_info=True)
    finally:
        logger.info("main: PyWebview event loop section finished. Initiating shutdown sequence.")
        if not stop_event_threading.is_set(): # Ensure it's set if not already
            logger.info("main: Signaling stop_event for async operations post-webview.")
            stop_event_threading.set()
        
        logger.info(f"main: Waiting for asyncio operations thread ('{async_thread.name}') to complete...")
        async_thread.join(timeout=10)
        if async_thread.is_alive():
            logger.warning(f"main: Asyncio operations thread ('{async_thread.name}') did not terminate gracefully after 10s.")
        else:
            logger.info(f"main: Asyncio operations thread ('{async_thread.name}') has completed.")

        cleanup() # Call the modified cleanup
        logger.info("main: Automoy application shutdown complete.")
        logging.shutdown() # Ensure all log handlers are flushed and closed

def run_async_operations_in_thread(stop_event_threading: threading.Event, loop: asyncio.AbstractEventLoop):
    """Target function for the asyncio operations thread."""
    thread_name = threading.current_thread().name
    thread_id = threading.get_ident()
    logger.info(f"Async operations thread ({thread_name}, ID: {thread_id}) started. Setting event loop.")
    asyncio.set_event_loop(loop)
    
    # Create an asyncio.Event from the threading.Event
    stop_event_async = asyncio.Event()
    
    async def monitor_threading_event():
        """Monitor the threading event and set the asyncio event when needed."""
        while not stop_event_threading.is_set():
            await asyncio.sleep(0.1)
        stop_event_async.set()
    
    logger.info(f"Async operations thread ({thread_name}): About to run main_async_operations() until complete.")
    try:
        # Start monitoring the threading event
        loop.create_task(monitor_threading_event())
        # Run main async operations with the asyncio event
        loop.run_until_complete(main_async_operations(stop_event_async))
        logger.info(f"Async operations thread ({thread_name}): main_async_operations() completed.")
    except Exception as e:
        logger.error(f"Async operations thread ({thread_name}): Exception during main_async_operations() or its management: {e}", exc_info=True)
        if stop_event_async: # Ensure stop_event_async is not None before setting
            stop_event_async.set() # Signal main thread to stop if async ops fail critically
    finally:
        logger.info(f"Async operations thread ({thread_name}): Closing asyncio event loop.")
        loop.close()
        logger.info(f"Async operations thread ({thread_name}): Asyncio event loop closed.")
    logger.info(f"Async operations thread ({thread_name}) finished execution.")

def cleanup():
    logger.info("Initiating Automoy full cleanup (cleanup function)...")
    global gui_process_global, webview_window_global

    # 1. Destroy PyWebview window first, if it exists
    if webview_window_global:
        try:
            logger.info("cleanup: Requesting PyWebview window destruction...")
            webview_window_global.destroy()
            logger.info("cleanup: PyWebview window.destroy() called.")
        except Exception as e:
            logger.error(f"cleanup: Error destroying PyWebview window: {e}", exc_info=True)
        webview_window_global = None # Clear the global reference
    else:
        logger.info("cleanup: No PyWebview window (webview_window_global) to destroy.")
    
    # 2. Terminate GUI subprocess
    if gui_process_global and gui_process_global.poll() is None: 
        logger.info(f"cleanup: Terminating GUI subprocess (PID: {gui_process_global.pid})...")
        gui_process_global.terminate()
        try:
            gui_process_global.wait(timeout=5)
            logger.info("cleanup: GUI subprocess terminated gracefully.")
        except subprocess.TimeoutExpired:
            logger.warning("cleanup: GUI subprocess did not terminate gracefully, killing.")
            gui_process_global.kill()
        except Exception as e:
            logger.error(f"cleanup: Error terminating GUI subprocess: {e}", exc_info=True)
    elif gui_process_global:
        logger.info(f"cleanup: GUI subprocess (PID: {gui_process_global.pid}) already terminated (exit code: {gui_process_global.poll()}).")
    else:
        logger.info("cleanup: No GUI subprocess to terminate.")
    gui_process_global = None # Clear the global reference

    # 3. Call cleanup_processes for operator and other async-related cleanup
    # This is called after GUI process and window are handled to ensure stop_event propagation
    # and operator shutdown occur cleanly.
    logger.info("cleanup: Calling cleanup_processes for core async components...")
    cleanup_processes()

    logger.info("Automoy full cleanup (cleanup function) finished.")

# Alternative native window methods for when pywebview is not available
def open_native_window_alternative(url: str, title: str = "Automoy GUI") -> bool:
    """Open a native-looking window using Microsoft Edge app mode."""
    logger.info(f"Attempting to open native window alternative for: {url}")
    
    try:
        # Find Microsoft Edge executable
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        ]
        
        edge_exe = None
        for path in edge_paths:
            if os.path.exists(path):
                edge_exe = path
                break
                
        if edge_exe:
            logger.info(f"Found Microsoft Edge at: {edge_exe}")
            cmd = [
                edge_exe,
                f"--app={url}",
                f"--window-size={GUI_WIDTH},{GUI_HEIGHT}",
                f"--window-position=100,100",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding"
            ]
            
            # Start Edge in app mode
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            logger.info("✓ Opened GUI in Microsoft Edge app mode (native-like window)")
            return True
        else:
            logger.warning("Microsoft Edge not found in standard locations")
            return False
            
    except Exception as e:
        logger.error(f"Failed to open Edge app mode: {e}", exc_info=True)
        return False

# --- Main Execution ---
if __name__ == "__main__":
    main()