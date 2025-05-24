print("[MAIN_PY_DEBUG] Script execution started.")
import asyncio
import os
import signal
import subprocess
import sys # sys needs to be imported before use
import time
import webbrowser
from contextlib import contextmanager
import shutil # Add this import
import pygetwindow as gw
import functools

# Define the prefix for the Automoy GUI window title
AUTOMOY_GUI_TITLE_PREFIX = "Automoy - Access via"

# Add project root to sys.path BEFORE attempting to import from core or config
# This ensures that modules like 'core' and 'config' can be found.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Define the GUI window title prefix for hide/show operations
AUTOMOY_GUI_TITLE_PREFIX = "Automoy - Access via"

import psutil
import requests
import httpx # Added for async API calls

from core.utils.operating_system.desktop_utils import DesktopUtils
from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
from core.operate import AutomoyOperator, _update_gui_state 
from config import Config
# Import necessary for LLM call
from core.lm.lm_interface import MainInterface
from core.prompts.prompts import FORMULATE_OBJECTIVE_SYSTEM_PROMPT, FORMULATE_OBJECTIVE_USER_PROMPT_TEMPLATE

gui_process = None
omniparser_server_process = None # To keep track of the OmniParser server process
pause_event = asyncio.Event() # Create a global pause event

# Function to find the Automoy GUI window (using the corrected title prefix)
def find_automoy_gui_window():
    prefix = AUTOMOY_GUI_TITLE_PREFIX
    try:
        for w in gw.getAllWindows():
            if w.title and w.title.startswith(prefix):
                return w
        return None
    except Exception as e:
        print(f"[PYGETWINDOW_FIND][ERROR] Error finding Automoy GUI window: {e}")
        return None

def start_gui_subprocess():
    global gui_process
    # Correctly determine the project root and gui_script_path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    gui_script_path = os.path.join(project_root, "gui", "gui.py")

    if not os.path.exists(gui_script_path):
        print(f"[MAIN][ERROR] GUI script not found at {gui_script_path}")
        return None

    try:
        # Determine creation flags for subprocess.Popen
        creation_flags = 0
        if sys.platform == "win32":
            # This will open a new console window for the gui.py process,
            # allowing its stdout/stderr (prints, errors) to be visible.
            creation_flags = subprocess.CREATE_NEW_CONSOLE
        
        # Log the command and flags being used
        # The existing print statement for the command is good.
        print(f"[MAIN] Starting GUI: {sys.executable} \\\"{gui_script_path}\\\"") # Corrected: Escape backslashes for quotes
        # CREATE_NO_WINDOW can be added back for production if GUI console is not needed
        # creationflags = subprocess.CREATE_NO_WINDOW 
        # Ensure gui.py runs in a new console window to see its output
        creationflags = subprocess.CREATE_NEW_CONSOLE
        gui_process = subprocess.Popen([sys.executable, gui_script_path], creationflags=creationflags)
        print(f"[MAIN] GUI process started with PID: {gui_process.pid}. Waiting for it to be healthy...")

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
                        print("[MAIN] GUI is healthy and responsive.")
                        gui_ready = True
                        break
                    else:
                        print(f"[MAIN] GUI health check status not healthy: {content.get('status')}, retrying...")
                else:
                    print(f"[MAIN] GUI health check failed with status {response.status_code}, retrying...")
            except requests.exceptions.ConnectionError:
                print("[MAIN] GUI not ready yet (connection error), retrying...")
            except requests.exceptions.Timeout:
                print("[MAIN] GUI health check timed out, retrying...")
            except Exception as e:
                print(f"[MAIN] Error checking GUI health: {e}, retrying...")
            time.sleep(1)

        if not gui_ready:
            print("[MAIN][ERROR] GUI did not become healthy within the timeout period.")
            if gui_process and gui_process.poll() is None:
                print("[MAIN] Terminating unresponsive GUI process.")
                gui_process.terminate()
                try:
                    gui_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print("[MAIN] GUI process did not terminate gracefully, killing.")
                    gui_process.kill()
            gui_process = None
            return None

        print("[MAIN] GUI subprocess started and reported healthy.")
        return gui_process
    except Exception as e:
        print(f"[MAIN][ERROR] Failed to start GUI subprocess: {e}")
        if gui_process and gui_process.poll() is None:
            gui_process.kill() # Ensure it's killed if something went wrong after Popen
        gui_process = None
        return None

async def _control_gui_window_api(action: str, retries=3, delay=1) -> bool:
    if not gui_process:
        print(f"[API_CALL][ERROR] GUI process not available. Cannot {action} window.")
        return False

    gui_base_url = "http://127.0.0.1:8000"
    url = f"{gui_base_url}/control/window/{action}"
    print(f"[API_CALL] Attempting to {action} GUI window via API: {url}")

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, timeout=10) # Increased timeout slightly

            if response.status_code == 200:
                print(f"[API_CALL] Successfully sent {action} command to GUI API. Response: {response.text}")
                return True
            else:
                print(f"[API_CALL][ERROR] Failed to {action} GUI window via API. Attempt {attempt + 1}/{retries}. Status: {response.status_code}, Response: {response.text}")
        except httpx.RequestError as e:
            print(f"[API_CALL][ERROR] httpx.RequestError on attempt {attempt + 1}/{retries} when trying to {action} GUI: {e}")
        except Exception as e:
            print(f"[API_CALL][ERROR] Unexpected error on attempt {attempt + 1}/{retries} when trying to {action} GUI: {e}")
        
        if attempt < retries - 1:
            print(f"Retrying in {delay}s...")
            await asyncio.sleep(delay)
        else:
            print(f"[API_CALL] Failed to {action} GUI window via API after {retries} attempts.")
    return False

def _pygetwindow_show_and_position(window):
    if window:
        print(f"[MAIN_GUI_CTRL] pygetwindow: Restoring and activating window '{window.title}'.") # Modified log
        if window.isMinimized:
            window.restore()
        
        if not window.visible:
            window.show()
            print(f"[MAIN_GUI_CTRL] pygetwindow: Window '{window.title}' was not visible, called show().")
         
        window.activate()
        # window.resizeTo(1228, 691) # Removed resize
        # window.moveTo(0, 0)        # Removed move
        print(f"[MAIN_GUI_CTRL] pygetwindow: Window '{window.title}' shown and activated.") # Modified log
    else:
        print("[MAIN_GUI_CTRL] pygetwindow: Window not provided for show_and_position.")

async def async_manage_automoy_gui_visibility(action: str, window_title: str = AUTOMOY_GUI_TITLE_PREFIX) -> bool:
    # Normalize action and handle minimize (hide) directly via pygetwindow
    normalized = action.lower()
    if normalized in ('hide', 'minimize'):
        print(f"[MAIN_GUI_CTRL] Minimizing Automoy GUI ('{window_title}') via pygetwindow.")
        # Wait for the window to be created (up to 3s)
        window = None
        for _ in range(10):  # 10 x 0.3s = 3s
            window = find_automoy_gui_window()
            if window:
                break
            await asyncio.sleep(0.3)
        if not window:
            print(f"[MAIN_GUI_CTRL] Timeout: No GUI window found with prefix '{window_title}' to minimize.")
            return False
        window.minimize()
        await asyncio.sleep(1.0)  # ensure window is hidden
        return True
    
    # Show action: try API first, then fallback
    print(f"[MAIN_GUI_CTRL] Attempting to show Automoy GUI via API.")
    if await _control_gui_window_api('show'):
        await asyncio.sleep(0.5)  # allow show to complete
        return True
    print(f"[MAIN_GUI_CTRL] API show failed, falling back to pygetwindow.")
    window = find_automoy_gui_window()
    if not window:
        print(f"[MAIN_GUI_CTRL] No GUI window found with prefix '{window_title}' to show.")
        return False
    _pygetwindow_show_and_position(window)
    return True

async def hide_gui_for_screenshot(window_title: str = AUTOMOY_GUI_TITLE_PREFIX):
    print(f"[MAIN_GUI_CTRL] Preparing to minimize GUI ('{window_title}') for screenshot.")
    minimized_successfully = await async_manage_automoy_gui_visibility("minimize", window_title)

    if minimized_successfully:
        print(f"[MAIN_GUI_CTRL] GUI ('{window_title}') minimization attempt completed (API or pygetwindow).")
    else:
        print(f"[MAIN_GUI_CTRL] Failed to minimize GUI ('{window_title}') via API and pygetwindow fallback. Screenshot might capture the GUI.")

async def show_gui_after_screenshot(window_title: str = AUTOMOY_GUI_TITLE_PREFIX):
    print(f"[MAIN_GUI_CTRL] Preparing to show GUI ('{window_title}') after screenshot.")
    shown_successfully = await async_manage_automoy_gui_visibility("show", window_title)

    if shown_successfully:
        print(f"[MAIN_GUI_CTRL] GUI ('{window_title}') show attempt completed (API or pygetwindow).")
    else:
        print(f"[MAIN_GUI_CTRL] Failed to show GUI ('{window_title}') via API and pygetwindow fallback.")

def cleanup_processes():
    global gui_process, omniparser_server_process
    print("[CLEANUP] Cleaning up processes...")

    # Terminate GUI process
    if gui_process:
        print(f"[CLEANUP] Terminating GUI process (PID: {gui_process.pid})...")
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
                print("[CLEANUP] GUI process terminated gracefully.")
            except subprocess.TimeoutExpired:
                print("[CLEANUP] GUI process did not terminate gracefully, killing...")
                gui_process.kill() # Force kill if it doesn't terminate
                try:
                    gui_process.wait(timeout=5) # Wait for kill
                except subprocess.TimeoutExpired:
                    print("[CLEANUP] GUI process kill command timed out.")
            except Exception as e: # Catch other potential errors during termination
                print(f"[CLEANUP][ERROR] Error during GUI process termination: {e}")
        else:
            print("[CLEANUP] GUI process already terminated.")
        gui_process = None

    # Terminate OmniParser server process (if managed by main.py via OmniParserServerManager)
    # The OmniParserServerManager instance should handle its own process termination ideally.
    # This is a fallback / direct management if omniparser_server_process is the Popen object.
    if omniparser_server_process and omniparser_server_process.poll() is None:
        print(f"[CLEANUP] Terminating OmniParser server process (PID: {omniparser_server_process.pid})...")
        omniparser_server_process.terminate()
        try:
            omniparser_server_process.wait(timeout=5)
            print("[CLEANUP] OmniParser server process terminated.")
        except subprocess.TimeoutExpired:
            print("[CLEANUP] OmniParser server process did not terminate gracefully, killing...")
            omniparser_server_process.kill()
            try:
                omniparser_server_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                print("[CLEANUP] OmniParser server process kill command timed out.")
        omniparser_server_process = None
    elif omniparser_server_process: # Process exists but poll() is not None (already terminated)
        print(f"[CLEANUP] OmniParser server process (PID: {omniparser_server_process.pid if hasattr(omniparser_server_process, 'pid') else 'unknown'}) already terminated.")
        omniparser_server_process = None
    
    # Additional cleanup for any OmniParser server processes that might have been missed
    # This is a more aggressive cleanup based on process name, use with caution
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            # Adjust "omniparser_script_name.py" to the actual script name if different
            # Or check for a unique part of the command line arguments
            if proc.info['name'] and proc.info['name'].lower() == 'python.exe' or proc.info['name'].lower() == 'python': # Check if it's a python process
                 cmdline = proc.info['cmdline']
                 if cmdline and any("omniparser" in arg.lower() for arg in cmdline): # Heuristic
                    print(f"[CLEANUP] Found lingering OmniParser-related process: PID {proc.info['pid']}, Cmd: {' '.join(cmdline)}. Terminating.")
                    try:
                        p = psutil.Process(proc.info['pid'])
                        p.terminate() # or p.kill()
                        p.wait(timeout=3)
                    except psutil.NoSuchProcess:
                        print(f"[CLEANUP] Process {proc.info['pid']} already terminated.")
                    except Exception as e:
                        print(f"[CLEANUP][ERROR] Failed to terminate lingering OmniParser process {proc.info['pid']}: {e}")
    except Exception as e:
        print(f"[CLEANUP][ERROR] Error during psutil cleanup for OmniParser: {e}")

    print("[CLEANUP] Process cleanup finished.")


async def manage_pause_event_concurrently(pause_event_ref: asyncio.Event):
    """Polls GUI for pause state and updates the pause_event accordingly. Runs concurrently."""
    print("[PAUSE_MANAGER_TASK] Started.")
    while True:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("http://127.0.0.1:8000/operator_state", timeout=2)

            if resp.status_code == 200:
                state = resp.json()
                is_gui_paused = state.get("is_paused", False)

                # Minimal logging to reduce noise, can be enabled for deep debugging
                # print(f"[PAUSE_MANAGER_TASK] GUI says: {{'is_paused': {is_paused}}}. Event is_set: {pause_event_ref.is_set()}")

                if is_gui_paused: # GUI wants to pause
                    if pause_event_ref.is_set(): # Operator is currently running
                        print("[PAUSE_MANAGER_TASK] GUI requests PAUSE. Clearing asyncio.Event (pausing operator).", flush=True) # Log
                        pause_event_ref.clear()
                    # else: # Operator already paused, GUI agrees
                        # print("[PAUSE_MANAGER_TASK] GUI confirms PAUSE. Event already clear.", flush=True) # Log - can be noisy
                else: # GUI wants to run (not paused)
                    if not pause_event_ref.is_set(): # Operator is currently paused
                        print("[PAUSE_MANAGER_TASK] GUI requests RESUME. Setting asyncio.Event (resuming operator).", flush=True) # Log
                        pause_event_ref.set()
                    # else: # Operator already running, GUI agrees
                        # print("[PAUSE_MANAGER_TASK] GUI confirms RESUME. Event already set.", flush=True) # Log - can be noisy
            else: # Optional: log if GUI state cannot be fetched
                print(f"[PAUSE_MANAGER_TASK] Warning: Could not get operator_state from GUI (status: {resp.status_code}). Retrying.", flush=True) # Log

        except httpx.RequestError as e_httpx: # More specific exception for network issues with httpx
            print(f"[PAUSE_MANAGER_TASK] HTTP Error polling GUI state: {e_httpx}. Retrying.", flush=True) # Log
            pass
        except Exception as e: # Catch other unexpected errors
            print(f"[PAUSE_MANAGER_TASK] Unexpected error: {e}. Retrying.", flush=True) # Log
        
        await asyncio.sleep(0.2) # Poll interval (e.g., 0.2 seconds)

async def main():
    print("[MAIN_PY_DEBUG] main() coroutine entered.")
    global gui_process, omniparser_server_process, pause_event 
    config = Config()
    # Default objective is not used initially, user goal is primary
    # initial_objective = config.get("DEFAULT_OBJECTIVE", "No objective set in environment.txt")
    # print(f"Initial Objective: {initial_objective}")

    # Initialize DesktopUtils
    desktop_utils = DesktopUtils() 

    # Start OmniParser Server
    omniparser_manager = OmniParserServerManager()
    if not omniparser_manager.is_server_ready():
        print("[MAIN] OmniParser server is not running. Attempting to start...")
        omniparser_server_process = omniparser_manager.start_server()
        if not omniparser_server_process or not omniparser_manager.wait_for_server(timeout=30):
            print("[MAIN][ERROR] OmniParser server failed to start or become ready. Exiting.")
            cleanup_processes() 
            if hasattr(omniparser_manager, 'stop_server'): omniparser_manager.stop_server()
            return
        print("[MAIN] OmniParser server started and ready.")
    else:
        print("[MAIN] OmniParser server is already running or started successfully.")

    # Start GUI
    gui_process = start_gui_subprocess()  
    if not gui_process:  
        print("[MAIN][ERROR] GUI process failed to start. Exiting.")  
        cleanup_processes()   
        if hasattr(omniparser_manager, 'stop_server'): omniparser_manager.stop_server()  
        return  

    pause_event.set() # Ensure Automoy is not paused by default when starting

    # Start the concurrent task for managing the pause event
    # This task will run alongside the objective formulation and operator loop
    pause_manager_task = asyncio.create_task(manage_pause_event_concurrently(pause_event))

    # Wait for the user to set a goal via the GUI
    print("[MAIN] Waiting for user to set a goal via the GUI...")
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

                # REMOVED PAUSE LOGIC and [MAIN_PAUSE_DEBUG] logs from this loop

                if current_gui_goal and not user_goal:
                    user_goal = current_gui_goal
                    print(f"[MAIN] User Goal received from GUI: {user_goal}")
                    
                    print(f"[MAIN] Requesting AI to formulate objective for goal: {user_goal}")
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
                            objective="Formulate a detailed objective from the user's goal.",
                            session_id="automoy-objective-formulation",
                            screenshot_path=None
                        )
                        formulated_objective = response_text.strip()
                        if not formulated_objective:
                            print("[MAIN][ERROR] AI failed to formulate an objective. Using a fallback.")
                            formulated_objective = f"Fallback objective: Complete user goal '{user_goal}'"
                    except Exception as e_formulate:
                        print(f"[MAIN][ERROR] Error during AI objective formulation: {e_formulate}")
                        formulated_objective = f"Error fallback objective for: {user_goal}"

                    print(f"[MAIN] AI Formulated Objective: {formulated_objective}")
                    
                    async with httpx.AsyncClient() as client_post_obj: # Use a different name for this client
                        await client_post_obj.post("http://127.0.0.1:8000/state/formulated_objective", 
                                          json={"objective": formulated_objective}, timeout=5)
                
                if user_goal and formulated_objective and current_gui_formulated_objective == formulated_objective and operator_status == "ObjectiveFormulated":
                    initial_objective_for_operator = formulated_objective
                    print(f"[MAIN] Confirmed AI formulated objective: {initial_objective_for_operator}")
                    break # Exit loop once objective is formulated and confirmed

        except httpx.RequestError: # Catch httpx specific errors
            # print(f"[MAIN] Error polling GUI state during objective setup: {e_httpx_obj}") # Can be noisy
            pass 
        except Exception as e_obj_loop: # Catch other errors in this loop
            print(f"[MAIN] Unexpected error polling GUI state during objective setup: {e_obj_loop}")
        await asyncio.sleep(0.1) # Poll every 0.1 seconds for objective setup
    
    print(f"[MAIN] Proceeding with AI Formulated Objective: {initial_objective_for_operator}")

    operator = AutomoyOperator(
        objective=initial_objective_for_operator, 
        manage_gui_window_func=functools.partial(async_manage_automoy_gui_visibility, window_title=AUTOMOY_GUI_TITLE_PREFIX),
        omniparser=omniparser_manager.get_interface(),
        pause_event=pause_event 
    )

    print(f"[MAIN] Starting operator with objective: {initial_objective_for_operator}")
    try:
        await operator.operate_loop()
    finally:
        # Clean up the pause manager task when operate_loop finishes or if an error occurs
        print("[MAIN] Operator loop finished or an error occurred. Cancelling pause manager task.")
        if pause_manager_task and not pause_manager_task.done():
            pause_manager_task.cancel()
            try:
                await pause_manager_task
            except asyncio.CancelledError:
                print("[MAIN] Pause manager task successfully cancelled.")
            except Exception as e_task_cleanup:
                print(f"[MAIN][ERROR] Exception during pause manager task cleanup: {e_task_cleanup}")
        else:
            print("[MAIN] Pause manager task was already done or not initialized.")


if __name__ == "__main__":
    print("[MAIN_PY_DEBUG] Inside __main__ block, before asyncio.run.")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[MAIN] Process interrupted by user (Ctrl+C).")
    except Exception as e:
        print(f"[MAIN][CRITICAL] An unhandled exception occurred at the top level: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[MAIN] Starting final cleanup...")
        cleanup_processes()
        print("[MAIN] Application shutdown complete.")
