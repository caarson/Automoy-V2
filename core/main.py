import asyncio
import os
import signal
import subprocess
import sys # sys needs to be imported before use
import time
import webbrowser
from contextlib import contextmanager
import shutil # Add this import
import re # Add re module for regex operations
import pygetwindow as gw # Added for find_automoy_gui_window
import functools # Added for functools.partial
import httpx # Added for async API calls
import psutil # Added for process cleanup
import requests # Added for synchronous health check

# Add project root to sys.path BEFORE attempting to import from core or config
# This ensures that modules like 'core' and 'config' can be found.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Now import project-specific modules
from core.utils.operating_system.desktop_utils import DesktopUtils
from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
from core.operate import AutomoyOperator, _update_gui_state 
from config import Config
from core.lm.lm_interface import MainInterface
from core.prompts.prompts import FORMULATE_OBJECTIVE_SYSTEM_PROMPT, FORMULATE_OBJECTIVE_USER_PROMPT_TEMPLATE

import logging
import logging.handlers

LOG_FILE_PATH = os.path.join(PROJECT_ROOT, "debug", "logs", "core", "output.log") # Updated path

def setup_logging():
    log_dir = os.path.dirname(LOG_FILE_PATH)
    os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger()
    
    # Clear existing handlers to avoid duplication if this function is called multiple times
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.setLevel(logging.DEBUG) 

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')

    # File Handler for detailed debug logs
    fh = logging.FileHandler(LOG_FILE_PATH, mode='w') # Changed mode to 'w'
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    root_logger.addHandler(fh)

    # Console Handler for general info logs
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO) 
    ch.setFormatter(formatter)
    root_logger.addHandler(ch)
    
    # Use the root logger for the initial message, or a specific logger if preferred
    logging.info(f"Logging initialized. Log file: {LOG_FILE_PATH}. Console level: INFO, File level: DEBUG.")

# Call setup_logging() once, early in the script.
setup_logging()
logger = logging.getLogger(__name__) # Logger for this module

logger.debug("Script execution started.")

# Define the prefix for the Automoy GUI window title
AUTOMOY_GUI_TITLE_PREFIX = "Automoy - Access via"

gui_process = None
omniparser_server_process = None 
pause_event = asyncio.Event() 

# Function to find the Automoy GUI window (using the corrected title prefix)
def find_automoy_gui_window():
    prefix = AUTOMOY_GUI_TITLE_PREFIX
    try:
        for w in gw.getAllWindows():
            if w.title and w.title.startswith(prefix):
                return w
        return None
    except Exception as e:
        logger.error(f"Error finding Automoy GUI window: {e}")
        return None

def start_gui_subprocess():
    global gui_process
    # Correctly determine the project root and gui_script_path
    # PROJECT_ROOT is already defined globally
    gui_script_path = os.path.join(PROJECT_ROOT, "gui", "gui.py")

    if not os.path.exists(gui_script_path):
        logger.error(f"GUI script not found at {gui_script_path}")
        return None

    try:
        # Determine creation flags for subprocess.Popen
        creation_flags = 0
        if sys.platform == "win32":
            # This will open a new console window for the gui.py process,
            # allowing its stdout/stderr (prints, errors) to be visible.
            creation_flags = subprocess.CREATE_NEW_CONSOLE
        
        logger.info(f"Starting GUI: {sys.executable} \\\"{gui_script_path}\\\"")
        # CREATE_NO_WINDOW can be added back for production if GUI console is not needed
        # creationflags = subprocess.CREATE_NO_WINDOW 
        # Ensure gui.py runs in a new console window to see its output
        creationflags = subprocess.CREATE_NEW_CONSOLE
        gui_process = subprocess.Popen([sys.executable, gui_script_path], creationflags=creationflags)
        logger.info(f"GUI process started with PID: {gui_process.pid}. Waiting for it to be healthy...")

        max_wait_time = 30  # seconds
        start_time = time.time()
        gui_ready = False
        while time.time() - start_time < max_wait_time:
            try:
                # Standard requests for synchronous health check
                response = requests.get("http://127.0.0.1:8000/health", timeout=2)
                if response.status_code == 200:
                    content = response.json()
                    if content.get("status") == "healthy":
                        logger.info("GUI is healthy and responsive.")
                        gui_ready = True
                        break
                    else:
                        logger.warning(f"GUI health check status not healthy: {content.get('status')}, retrying...")
                else:
                    logger.warning(f"GUI health check failed with status {response.status_code}, retrying...")
            except requests.exceptions.ConnectionError:
                logger.warning("GUI not ready yet (connection error), retrying...")
            except requests.exceptions.Timeout:
                logger.warning("GUI health check timed out, retrying...")
            except Exception as e:
                logger.error(f"Error checking GUI health: {e}, retrying...")
            time.sleep(1)

        if not gui_ready:
            logger.error("GUI did not become healthy within the timeout period.")
            if gui_process and gui_process.poll() is None:
                logger.info("Terminating unresponsive GUI process.")
                gui_process.terminate()
                try:
                    gui_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("GUI process did not terminate gracefully, killing.")
                    gui_process.kill()
            gui_process = None
            return None

        logger.info("GUI subprocess started and reported healthy.")
        return gui_process
    except Exception as e:
        logger.error(f"Failed to start GUI subprocess: {e}")
        if gui_process and gui_process.poll() is None:
            gui_process.kill() # Ensure it's killed if something went wrong after Popen
        gui_process = None
        return None

async def _control_gui_window_api(action: str, retries=3, delay=1) -> bool:
    if not gui_process:
        logger.error(f"GUI process not available. Cannot {action} window.")
        return False

    gui_base_url = "http://127.0.0.1:8000"
    url = f"{gui_base_url}/control/window/{action}"
    logger.info(f"Attempting to {action} GUI window via API: {url}")

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, timeout=10) # Increased timeout slightly

            if response.status_code == 200:
                logger.info(f"Successfully sent {action} command to GUI API. Response: {response.text}")
                return True
            else:
                logger.error(f"Failed to {action} GUI window via API. Attempt {attempt + 1}/{retries}. Status: {response.status_code}, Response: {response.text}")
        except httpx.RequestError as e:
            logger.error(f"httpx.RequestError on attempt {attempt + 1}/{retries} when trying to {action} GUI: {e}")
        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1}/{retries} when trying to {action} GUI: {e}")
        
        if attempt < retries - 1:
            logger.info(f"Retrying in {delay}s...")
            await asyncio.sleep(delay)
        else:
            logger.error(f"Failed to {action} GUI window via API after {retries} attempts.")
    return False

def _pygetwindow_show_and_position(window):
    if window:
        logger.info(f"pygetwindow: Restoring and activating window '{window.title}'.")
        if window.isMinimized:
            window.restore()
        
        if not window.visible:
            window.show()
            logger.info(f"pygetwindow: Window '{window.title}' was not visible, called show().")
         
        try:
            window.activate()
        except gw.PyGetWindowException as e: # Assuming 'import pygetwindow as gw' is at the top
            if "Error code from Windows: 0" in str(e):
                logger.warning(f"pygetwindow.activate() raised known benign exception (error code 0): {e}. Continuing.")
            else:
                logger.error(f"pygetwindow.activate() failed: {e}")
                raise # Re-raise other pygetwindow exceptions
        logger.info(f"pygetwindow: Window '{window.title}' shown and activated.")
    else:
        logger.warning("pygetwindow: Window not provided for show_and_position.")

async def async_manage_automoy_gui_visibility(action: str, window_title: str = AUTOMOY_GUI_TITLE_PREFIX) -> bool:
    normalized = action.lower()
    if normalized in ('hide', 'minimize'):
        logger.info(f"Minimizing Automoy GUI ('{window_title}') via pygetwindow.")
        window = None
        for _ in range(10):  # 10 x 0.3s = 3s
            window = find_automoy_gui_window()
            if window:
                break
            await asyncio.sleep(0.3)
        if not window:
            logger.warning(f"Timeout: No GUI window found with prefix '{window_title}' to minimize.")
            return False
        try:
            window.minimize()
            await asyncio.sleep(1.0)  # ensure window is hidden
            logger.info(f"GUI window '{window.title}' minimized via pygetwindow.")
            return True
        except Exception as e:
            logger.error(f"Error minimizing window '{window.title}' via pygetwindow: {e}")
            return False
            
    logger.info(f"Attempting to show Automoy GUI ('{window_title}') via API.")
    if await _control_gui_window_api('show'):
        await asyncio.sleep(0.5)  # allow show to complete
        return True
    logger.warning(f"API show failed for '{window_title}', falling back to pygetwindow.")
    window = find_automoy_gui_window()
    if not window:
        logger.warning(f"No GUI window found with prefix '{window_title}' to show via pygetwindow fallback.")
        return False
    _pygetwindow_show_and_position(window)
    return True

async def hide_gui_for_screenshot(window_title: str = AUTOMOY_GUI_TITLE_PREFIX):
    logger.info(f"Preparing to minimize GUI ('{window_title}') for screenshot.")
    minimized_successfully = await async_manage_automoy_gui_visibility("minimize", window_title)

    if minimized_successfully:
        logger.info(f"GUI ('{window_title}') minimization attempt completed.")
    else:
        logger.warning(f"Failed to minimize GUI ('{window_title}'). Screenshot might capture the GUI.")

async def show_gui_after_screenshot(window_title: str = AUTOMOY_GUI_TITLE_PREFIX):
    logger.info(f"Preparing to show GUI ('{window_title}') after screenshot.")
    shown_successfully = await async_manage_automoy_gui_visibility("show", window_title)

    if shown_successfully:
        logger.info(f"GUI ('{window_title}') show attempt completed.")
    else:
        logger.warning(f"Failed to show GUI ('{window_title}').")

def cleanup_processes():
    global gui_process, omniparser_server_process
    logger.info("Cleaning up processes...")

    if gui_process:
        logger.info(f"Terminating GUI process (PID: {gui_process.pid})...")
        if gui_process.poll() is None: # Check if process is still running
            # Try to terminate gracefully first
            if sys.platform == "win32":
                # Send CTRL_BREAK_EVENT to the process group on Windows to allow graceful FastAPI shutdown
                # This requires starting the subprocess with creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                # For now, using terminate() which sends SIGTERM (or TerminateProcess on Windows)
                gui_process.terminate()
            else:
                # For non-Windows, send SIGTERM to the process group if Popen started it with one.
                # If not, gui_process.terminate() sends SIGTERM to the process itself.
                # os.killpg(os.getpgid(gui_process.pid), signal.SIGTERM) # Use if process group is managed
                gui_process.terminate()

            try:
                gui_process.wait(timeout=10) # Wait for graceful termination
                logger.info("GUI process terminated gracefully.")
            except subprocess.TimeoutExpired:
                logger.warning("GUI process did not terminate gracefully, killing...")
                gui_process.kill() # Force kill if it doesn't terminate
                try:
                    gui_process.wait(timeout=5) # Wait for kill
                except subprocess.TimeoutExpired:
                    logger.error("GUI process kill command timed out.")
            except Exception as e: # Catch other potential errors during termination
                logger.error(f"Error during GUI process termination: {e}")
        else:
            logger.info("GUI process already terminated.")
        gui_process = None

    if omniparser_server_process and omniparser_server_process.poll() is None:
        logger.info(f"Terminating OmniParser server process (PID: {omniparser_server_process.pid})...")
        omniparser_server_process.terminate()
        try:
            omniparser_server_process.wait(timeout=5)
            logger.info("OmniParser server process terminated.")
        except subprocess.TimeoutExpired:
            logger.warning("OmniParser server process did not terminate gracefully, killing...")
            omniparser_server_process.kill()
            try:
                omniparser_server_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logger.error("OmniParser server process kill command timed out.")
        omniparser_server_process = None
    elif omniparser_server_process: # Process exists but poll() is not None (already terminated)
        logger.info(f"OmniParser server process (PID: {omniparser_server_process.pid if hasattr(omniparser_server_process, 'pid') else 'unknown'}) already terminated.")
        omniparser_server_process = None
    
    # Additional cleanup for any OmniParser server processes that might have been missed
    # This is a more aggressive cleanup based on process name, use with caution
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            # Adjust "omniparser_script_name.py" to the actual script name if different
            # Or check for a unique part of the command line arguments
            if proc.info['name'] and proc.info['name'].lower() in ('python.exe', 'python'): # Check if it's a python process
                 cmdline = proc.info['cmdline']
                 if cmdline and any("omniparser" in arg.lower() for arg in cmdline): # Heuristic
                    logger.info(f"Found lingering OmniParser-related process: PID {proc.info['pid']}, Cmd: {' '.join(cmdline)}. Terminating.")
                    try:
                        p = psutil.Process(proc.info['pid'])
                        p.terminate() # or p.kill()
                        p.wait(timeout=3)
                    except psutil.NoSuchProcess:
                        logger.info(f"Process {proc.info['pid']} already terminated.")
                    except Exception as e:
                        logger.error(f"Failed to terminate lingering OmniParser process {proc.info['pid']}: {e}")
    except Exception as e:
        logger.error(f"Error during psutil cleanup for OmniParser: {e}")
    logger.info("Process cleanup finished.")

async def manage_pause_event_concurrently(pause_event_ref: asyncio.Event):
    logger.info("Pause manager task started.")
    while True:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("http://127.0.0.1:8000/operator_state", timeout=2)

            if resp.status_code == 200:
                state = resp.json()
                is_gui_paused = state.get("is_paused", False)

                if is_gui_paused: # GUI wants to pause
                    if pause_event_ref.is_set(): # Operator is currently running
                        logger.info("GUI requests PAUSE. Clearing asyncio.Event (pausing operator).")
                        pause_event_ref.clear()
                else: # GUI wants to run (not paused)
                    if not pause_event_ref.is_set(): # Operator is currently paused
                        logger.info("GUI requests RESUME. Setting asyncio.Event (resuming operator).")
                        pause_event_ref.set()
            else: # Optional: log if GUI state cannot be fetched
                logger.warning(f"Could not get operator_state from GUI (status: {resp.status_code}). Retrying.")

        except httpx.RequestError as e_httpx: # More specific exception for network issues with httpx
            logger.warning(f"HTTP Error polling GUI state: {e_httpx}. Retrying.")
            # Removed flush=True as it's not a valid argument for logger methods
        except Exception as e: # Catch other unexpected errors
            logger.error(f"Unexpected error in pause manager: {e}. Retrying.")
            # Removed flush=True
        
        await asyncio.sleep(0.2) # Poll interval (e.g., 0.2 seconds)

async def main():
    logger.debug("main() coroutine entered.")
    global gui_process, omniparser_server_process, pause_event 
    
    try:
        config = Config()
    except Exception as e:
        logger.critical(f"Failed to initialize Config: {e}", exc_info=True)
        return # Cannot proceed without config

    try:
        desktop_utils = DesktopUtils() 
    except Exception as e:
        logger.critical(f"Failed to initialize DesktopUtils: {e}", exc_info=True)
        return

    try:
        omniparser_manager = OmniParserServerManager()
        if not omniparser_manager.is_server_ready():
            logger.info("OmniParser server is not running. Attempting to start...")
            omniparser_server_process = omniparser_manager.start_server()
            if not omniparser_server_process or not omniparser_manager.wait_for_server(timeout=30):
                logger.error("OmniParser server failed to start or become ready. Exiting.")
                cleanup_processes() 
                if hasattr(omniparser_manager, 'stop_server'): omniparser_manager.stop_server()
                return
            logger.info("OmniParser server started and ready.")
        else:
            logger.info("OmniParser server is already running or started successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize or start OmniParserServerManager: {e}", exc_info=True)
        cleanup_processes()
        return

    gui_process = start_gui_subprocess()  
    if not gui_process:  
        logger.error("GUI process failed to start. Exiting.")  
        cleanup_processes()   
        if hasattr(omniparser_manager, 'stop_server'): omniparser_manager.stop_server()  
        return  

    pause_event.set() # Ensure Automoy is not paused by default when starting

    # Start the concurrent task for managing the pause event
    # This task will run alongside the objective formulation and operator loop
    pause_manager_task = asyncio.create_task(manage_pause_event_concurrently(pause_event))

    # Wait for the user to set a goal via the GUI
    logger.info("Waiting for user to set a goal via the GUI...")
    user_goal = None
    formulated_objective = None
    initial_objective_for_operator = None
    
    # This loop is now only for objective formulation, not pause management.
    while True:
        try:
            # Use httpx for async GET request
            async with httpx.AsyncClient() as client:
                resp = await client.get("http://127.0.0.1:8000/operator_state", timeout=2)

            if resp.status_code == 200:
                state = resp.json()
                current_gui_goal = state.get("user_goal", "").strip()
                current_gui_formulated_objective = state.get("formulated_objective", "").strip()
                operator_status = state.get("operator_status", "Idle")
                # is_gui_paused = state.get("is_paused", False) # Pause state is handled by pause_manager_task

                if current_gui_goal and not user_goal:
                    user_goal = current_gui_goal
                    logger.info(f"User Goal received from GUI: {user_goal}")
                    
                    logger.info(f"Requesting AI to formulate objective for goal: {user_goal}")
                    llm_interface = MainInterface()
                    formulation_messages = [
                        {"role": "system", "content": FORMULATE_OBJECTIVE_SYSTEM_PROMPT},
                        {"role": "user", "content": FORMULATE_OBJECTIVE_USER_PROMPT_TEMPLATE.format(user_goal=user_goal)}
                    ]
                    try:
                        cfg = Config() # Ensure Config is instantiated if used here
                        model_for_formulation = cfg.get_model()
                        response_text, _, _ = await llm_interface.get_next_action(
                            model=model_for_formulation,
                            messages=formulation_messages,
                            objective="Formulate a detailed objective from the user\'s goal.",
                            session_id="automoy-objective-formulation",
                            screenshot_path=None
                        )
                        # Strip <think> tags and content before sending it to the GUI and using it for the operator
                        raw_formulated_objective = response_text.strip()
                        # Use re.DOTALL flag to make . match newlines
                        formulated_objective_for_gui = re.sub(r"<think>.*?</think>", "", raw_formulated_objective, flags=re.DOTALL).strip()
                        
                        if not formulated_objective_for_gui: # Check if stripping resulted in empty string
                            logger.error("AI failed to formulate a valid objective after stripping tags. Using a fallback.")
                            formulated_objective_for_gui = f"Fallback objective: Complete user goal \'{user_goal}\'"
                        
                        # Log the version that will be used by the operator (could be with or without think tags, depending on choice)
                        # For now, let's assume the operator should also get the cleaned version.
                        formulated_objective = formulated_objective_for_gui

                    except Exception as e_formulate:
                        logger.error(f"Error during AI objective formulation: {e_formulate}")
                        formulated_objective = f"Error fallback objective for: {user_goal}" # This will be sent to GUI

                    logger.info(f"AI Formulated Objective (for GUI): {formulated_objective}")
                    
                    async with httpx.AsyncClient() as client_post_obj: # Use a different name for this client
                        await client_post_obj.post("http://127.0.0.1:8000/state/formulated_objective", 
                                          json={"objective": formulated_objective}, timeout=5) # Send the cleaned version
                
                if user_goal and formulated_objective and current_gui_formulated_objective == formulated_objective and operator_status == "ObjectiveFormulated":
                    initial_objective_for_operator = formulated_objective # Use the cleaned version for the operator too
                    logger.info(f"Confirmed AI formulated objective (for operator): {initial_objective_for_operator}")
                    break # Exit loop once objective is formulated and confirmed

        except httpx.RequestError: # Catch httpx specific errors
            # print(f"[MAIN] Error polling GUI state during objective setup: {e_httpx_obj}") # Can be noisy
            pass 
        except Exception as e_obj_loop: # Catch other errors in this loop
            logger.error(f"Unexpected error polling GUI state during objective setup: {e_obj_loop}")
        await asyncio.sleep(0.1) # Poll every 0.1 seconds for objective setup
    
    logger.info(f"Proceeding with AI Formulated Objective: {initial_objective_for_operator}")

    try:
        operator = AutomoyOperator(
            objective=initial_objective_for_operator, 
            manage_gui_window_func=functools.partial(async_manage_automoy_gui_visibility, window_title=AUTOMOY_GUI_TITLE_PREFIX),
            omniparser=omniparser_manager.get_interface(), # Ensure this returns a valid interface
            pause_event=pause_event 
        )
    except Exception as e:
        logger.critical(f"Failed to initialize AutomoyOperator: {e}", exc_info=True)
        cleanup_processes()
        if hasattr(omniparser_manager, 'stop_server'): omniparser_manager.stop_server()
        # Cancel pause manager task if it was started
        if 'pause_manager_task' in locals() and pause_manager_task and not pause_manager_task.done():
            pause_manager_task.cancel()
        return

    logger.info(f"Starting operator with objective: {initial_objective_for_operator}")
    try:
        await operator.operate_loop()
    except Exception as e_op_loop:
        logger.error(f"Error during operator.operate_loop: {e_op_loop}", exc_info=True)
    finally:
        logger.info("Operator loop finished or an error occurred. Cancelling pause manager task.")
        if pause_manager_task and not pause_manager_task.done():
            pause_manager_task.cancel()
            try:
                await pause_manager_task
            except asyncio.CancelledError:
                logger.info("Pause manager task successfully cancelled.")
            except Exception as e_task_cleanup:
                logger.error(f"Exception during pause manager task cleanup: {e_task_cleanup}", exc_info=True)
        else:
            logger.info("Pause manager task was already done or not initialized.")

if __name__ == "__main__":
    logger.debug("Inside __main__ block, before asyncio.run.")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user (Ctrl+C).")
    except Exception as e:
        logger.critical(f"An unhandled exception occurred at the top level: {e}", exc_info=True)
    finally:
        logger.info("Starting final cleanup...")
        cleanup_processes()
        logger.info("Application shutdown complete.")
