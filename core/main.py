import os, sys  # add at the very top
# Ensure the project root (workspace) is on sys.path so core package is resolvable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import asyncio
import json
import signal
import threading
import time
import webview
import requests
import httpx  # Added for async_update_gui_state
import logging
import logging.handlers
import platform
import atexit
import subprocess
import re  # Added for objective extraction patterns
from typing import Any, Dict, Optional, List, Union, TYPE_CHECKING

# Import process_utils after adjusting sys.path
from core.utils.operating_system.process_utils import is_process_running_on_port, kill_process_on_port
from core.operate import AutomoyOperator
from core.data_models import AutomoyStatus, OperatorState
from core.prompts.prompts import FORMULATE_OBJECTIVE_SYSTEM_PROMPT, FORMULATE_OBJECTIVE_USER_PROMPT_TEMPLATE

if TYPE_CHECKING:
    from core.operate import AutomoyOperator

# Load application configuration
import config.config as app_config

# Global variables
webview_window_global: Optional[webview.Window] = None
current_gui_visibility: bool = False
operator: 'AutomoyOperator' = None
# Global for GUI subprocess
gui_process: Optional[subprocess.Popen] = None

# For managing the asyncio event loop in a dedicated thread
main_loop: Optional[asyncio.AbstractEventLoop] = None
async_main_task: Optional[asyncio.Task] = None

# --- Configuration & Constants ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Event for signaling graceful shutdown
stop_event: Optional[asyncio.Event] = None

# Lock for thread-safe access to current_operator_state
operator_state_lock = asyncio.Lock()
current_operator_state = OperatorState() 

# Setup logger
logger = logging.getLogger(app_config.AUTOMOY_APP_NAME)

def setup_logging(console_level=logging.INFO, file_level=logging.DEBUG):
    logger.setLevel(min(console_level, file_level))
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(threadName)s - %(levelname)s - %(message)s')

    # Console Handler
    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Handler (Rotating)
    log_dir = os.path.dirname(app_config.LOG_FILE_PATH) 
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except OSError as e:
            print(f"Could not create log directory {log_dir}: {e}", file=sys.stderr)
            return
    
    if log_dir: 
        fh = logging.handlers.RotatingFileHandler(
            app_config.LOG_FILE_PATH, maxBytes=app_config.MAX_LOG_FILE_SIZE, backupCount=app_config.LOG_BACKUP_COUNT
        )
        fh.setLevel(file_level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    
    logger.info("Logging setup complete.")


def start_gui_and_create_webview_window():
    """Launch the FastAPI GUI app as a uvicorn subprocess and create a PyWebview window."""
    global gui_process, webview_window_global
    # Kill existing GUI port usage
    if is_process_running_on_port(app_config.GUI_PORT):
        logger.info(f"Port {app_config.GUI_PORT} busy, killing existing process...")
        kill_process_on_port(app_config.GUI_PORT)
        time.sleep(1)
    # Launch gui.py script (handles uvicorn itself) with host and port args
    gui_script = os.path.join(PROJECT_ROOT, "gui", "gui.py")
    cmd = [sys.executable, "-u", gui_script, "--host", app_config.GUI_HOST, "--port", str(app_config.GUI_PORT)]
    logger.info(f"Starting GUI subprocess: {' '.join(cmd)}")
    gui_process = subprocess.Popen(cmd, cwd=PROJECT_ROOT)
    # Wait for health endpoint
    timeout = getattr(app_config, 'GUI_START_TIMEOUT', 60)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"http://{app_config.GUI_HOST}:{app_config.GUI_PORT}/health", timeout=2)
            if r.status_code == 200:
                logger.info("GUI is healthy and responsive.")
                break
        except requests.RequestException:
            time.sleep(1)
    else:
        logger.error("GUI did not become healthy within the timeout period.")
        gui_process.terminate()
        return False
    # Create the PyWebview window
    gui_url = f"http://{app_config.GUI_HOST}:{app_config.GUI_PORT}"
    window_title = f"{app_config.AUTOMOY_GUI_TITLE_PREFIX} {gui_url}"
    webview_window_global = webview.create_window(
        window_title,
        gui_url,
        width=1280,
        height=800,
        frameless=True,
        easy_drag=True
    )

    # The loading screen is part of index.html and will be shown by default.
    # We will hide it from the main_async_operations after OmniParser is ready.

    # Inject JS to zoom out after window loads (and after loading screen is hidden)
    # This will be chained after hiding the loading screen.
    # def _set_zoom():
    #     time.sleep(1) # Ensure loading screen is hidden first
    #     try:
    #         webview_window_global.evaluate_js("document.body.style.zoom='80%'")
    #     except Exception as _:
    #         pass
    # threading.Thread(target=_set_zoom, daemon=True).start()
    logger.info(f"PyWebview window '{window_title}' created successfully. Loading screen should be visible.")
    return True

async def async_manage_automoy_gui_visibility(target_visibility: bool):
    global current_gui_visibility
    if current_gui_visibility == target_visibility and webview_window_global and webview_window_global.shown == target_visibility:
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
            logger.debug(f"GUI visibility change requested to: {'visible' if target_visibility else 'hidden'}")
        except Exception as e:
            logger.error(f"Error changing PyWebview window visibility via evaluate_js: {e}", exc_info=True)
    else:
        logger.warning("PyWebview window (webview_window_global) not available. Cannot manage GUI visibility directly.")


def cleanup_processes():
    global webview_window_global, async_main_task, main_loop, stop_event

    logger.info("Initiating Automoy cleanup...")

    if stop_event and not stop_event.is_set():
        logger.info("Signaling async tasks to stop via stop_event...")
        if main_loop and main_loop.is_running():
             main_loop.call_soon_threadsafe(stop_event.set)
        else: 
            stop_event.set()

    if async_main_task and not async_main_task.done():
        logger.info("Cancelling main async task...")
        if main_loop and main_loop.is_running():
             main_loop.call_soon_threadsafe(async_main_task.cancel)
        else:
            async_main_task.cancel()
    
    # Destroy PyWebview window
    if webview_window_global:
        logger.info("Requesting PyWebview window destruction...")
        try:
            # Correct method is destroy(), not destroy_window()
            if hasattr(webview_window_global, 'destroy'): 
                webview_window_global.destroy()
                logger.info("PyWebview window.destroy() called.")
            else:
                logger.warning("Webview window does not have a destroy() method. Attempting hide().")
                if hasattr(webview_window_global, 'hide'):
                    webview_window_global.hide()
                    logger.info("PyWebview window.hide() called as fallback.")
                else:
                    logger.warning("Webview window has neither destroy() nor hide() methods.")
        except Exception as e:
            logger.error(f"Error during PyWebview window destruction/hiding: {e}", exc_info=True)
        webview_window_global = None

    # Stop embedded Uvicorn server if thread is alive
    if operator and hasattr(operator, 'stop_gracefully'):
        logger.info("Stopping AutomoyOperator...")
        try:
            operator.stop_gracefully() 
            logger.info("AutomoyOperator stopped.")
        except Exception as e:
            logger.error(f"Error stopping AutomoyOperator: {e}", exc_info=True)
    
    logger.info("Automoy cleanup sequence finished.")


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

async def async_update_gui_state(endpoint: str, payload: dict):
    """GUI state update function for AutomoyOperator."""
    try:
        # Ensure the endpoint starts with a slash
        if not endpoint.startswith("/"):
            url_endpoint = "/" + endpoint
        else:
            url_endpoint = endpoint

        # Build full URL for GUI state update
        url = f"http://{app_config.GUI_HOST}:{app_config.GUI_PORT}{url_endpoint}"

        # Send the state update as JSON payload
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(url, json=payload)

        if response.status_code == 200:
            logger.debug(f"Successfully updated GUI state at {url}")
        else:
            logger.warning(f"Failed to update GUI state at {url}, status code: {response.status_code}")
    except httpx.RequestError as e:
        logger.warning(f"Failed to update GUI state at {url} (RequestError): {e}")
    except Exception as e:
        logger.error(f"Unexpected error in async_update_gui_state sending to {url}: {e}", exc_info=True)

async def main_async_operations():
    global operator_state_lock, current_operator_state, operator, stop_event, webview_window_global
    
    logger.debug("main_async_operations() coroutine entered.")
    
    if stop_event is None: 
        stop_event = asyncio.Event()

    # Attempt to import OmniParserInterface locally within the function
    try:
        from core.utils.omniparser.omniparser_interface import OmniParserInterface
    except ImportError as e:
        logger.error(f"Failed to import OmniParserInterface: {e}", exc_info=True)
        if stop_event: 
            stop_event.set()
        return

    # --- OmniParser Initialization ---
    omniparser_port = app_config.OMNIPARSER_PORT
    omniparser_base_url = f"http://localhost:{omniparser_port}"
    # Use getattr to safely get config with a default
    omniparser_conda_env = getattr(app_config, 'OMNIPARSER_CONDA_ENV_NAME', 'automoy_env') 
    omniparser_model_path = getattr(app_config, 'OMNIPARSER_MODEL_PATH', None) 
    omniparser_caption_model_dir = getattr(app_config, 'OMNIPARSER_CAPTION_MODEL_DIR', None)

    logger.info(f"Initializing OmniParser interface for URL: {omniparser_base_url}")
    omniparser = OmniParserInterface(server_url=omniparser_base_url) 

    logger.info("Checking OmniParser server status...")
    if not omniparser._check_server_ready(): 
        logger.info(f"OmniParser server not detected at {omniparser_base_url}. Attempting to launch...")
        
        launch_args = {
            "port": omniparser_port,
            "conda_env": omniparser_conda_env
        }
        if omniparser_model_path:
            launch_args["model_path"] = omniparser_model_path
        if omniparser_caption_model_dir:
            launch_args["caption_model_dir"] = omniparser_caption_model_dir
        
        # launch_server is synchronous.
        if omniparser.launch_server(**launch_args):
            logger.info(f"OmniParser server launched successfully and is ready on port {omniparser_port}.")
        else:
            logger.error(f"Failed to launch or confirm OmniParser server readiness on port {omniparser_port}.")
            # Optionally, make this fatal:
            # logger.error("OmniParser is critical. Shutting down.")
            # if stop_event: stop_event.set()
            # return 
    else:
        logger.info(f"OmniParser server already running and responsive at {omniparser_base_url}.")

    # OmniParser is now confirmed or launched. Hide loading screen and apply zoom.
    if webview_window_global:
        try:
            logger.info("OmniParser ready. Hiding loading screen and applying zoom via PyWebview JS evaluation...")
            webview_window_global.evaluate_js("hideLoadingScreen(); document.body.style.zoom='80%';")
            logger.info("Loading screen hidden and zoom applied.")
        except Exception as e:
            logger.error(f"Error hiding loading screen or applying zoom: {e}", exc_info=True)

    # Create pause event for the operator
    pause_event = asyncio.Event()
    pause_event.set()  # Start unpaused

    try:
        # Initialize AutomoyOperator with all required parameters
        operator = AutomoyOperator(
            objective="",  # Will be set later when user provides a goal
            manage_gui_window_func=async_manage_gui_window,
            omniparser=omniparser, # Use the initialized omniparser instance
            pause_event=pause_event,
            update_gui_state_func=async_update_gui_state
        )
        logger.info("AutomoyOperator initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize AutomoyOperator: {e}", exc_info=True)
        if stop_event: 
            stop_event.set()
        return

    # Wait a brief moment for webview window to potentially be shown by main thread
    await asyncio.sleep(1)
    await async_manage_automoy_gui_visibility(True)
    logger.info("Initial GUI visibility set to True (attempted).")
    
    logger.info("Waiting for user to set a goal via the GUI...")

    # Main loop - wait for user goal and run operator
    current_goal = None
    operator_running = False

    while not stop_event.is_set():
        try:
            # Check for new goal from GUI
            operator_state_url = f"http://{app_config.GUI_HOST}:{app_config.GUI_PORT}/operator_state"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(operator_state_url)
            
            if response.status_code == 200:
                new_state_data = response.json()
                new_goal = new_state_data.get("user_goal")
                logger.info(f"[MAIN_LOOP_DEBUG] Fetched new_goal from GUI: '{new_goal}' (type: {type(new_goal)})")
                logger.info(f"[MAIN_LOOP_DEBUG] current_goal before check: '{current_goal}'")
                logger.info(f"[MAIN_LOOP_DEBUG] operator_running before check: {operator_running}")

                if new_goal and new_goal != current_goal and not operator_running:
                    logger.info(f"[MAIN_LOOP_DEBUG] Condition MET. Processing new_goal: '{new_goal}'")
                    logger.info(f"New goal received: '{new_goal}'. Starting operation...")
                    current_goal = new_goal
                    operator_running = True                    # Generate a clear objective from the user's goal
                    # Formulate a clear objective via direct LLM call
                    objective_text = ""
                    try:
                        # Prepare messages for objective formulation
                        system_prompt = FORMULATE_OBJECTIVE_SYSTEM_PROMPT
                        user_prompt = FORMULATE_OBJECTIVE_USER_PROMPT_TEMPLATE.format(user_goal=new_goal)
                        
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ]
                        
                        logger.info(f"Calling LLM to formulate objective from goal: '{new_goal}'")
                          # Try a forced direct approach to generate an objective instead of relying on the LLM directly
                        # If the goal is relatively short, we'll create a detailed objective ourselves
                        goal_words = new_goal.split()
                        create_objective_locally = len(goal_words) <= 10
                        
                        if create_objective_locally:
                            logger.info(f"Goal is short enough to create objective locally without calling LLM")
                            raw_obj = f"Complete the task of {new_goal} by systematically identifying the appropriate application or website, navigating through its interface, and performing all necessary actions to achieve the desired outcome efficiently and accurately."
                            obj_error = None
                            logger.debug(f"Locally created objective: {raw_obj}")
                        else:                            # Use get_llm_response to generate objective
                            try:
                                raw_obj, _, obj_error = await operator.llm_interface.get_llm_response(
                                    operator.config.get_model(), messages, new_goal, operator.session_id, response_format_type="objective_generation"
                                )
                                logger.debug(f"Raw objective from LLM: {raw_obj}")
                                logger.info(f"Got raw objective from LLM (length: {len(raw_obj) if raw_obj else 0})")
                            except Exception as llm_error:
                                logger.error(f"Failed to communicate with LLM server: {llm_error}")
                                # Explicitly set raw_obj to None or an empty string if LLM fails
                                raw_obj = "" # Or None, depending on how it's handled below
                                obj_error = f"LLM server communication error: {llm_error}"
                                # Fallback objective when LLM is down
                                objective_text = f"Complete the task of {new_goal} systematically, efficiently, and accurately."


                        # Process the raw LLM response to extract the objective
                        if raw_obj and not obj_error:                            # Try to extract just the formulated objective from raw_obj
                            # Look for common patterns in LLM responses
                            formulation_patterns = [
                                r"Formulated Objective:\s*(.*?)(?:\n\n|$)",  # Match after "Formulated Objective:" label
                                r"(?:Based on this goal, )?(?:the )?(?:formulated|detailed) objective(?:s)? (?:is|are|would be):\s*(.*?)(?:\n\n|$)",  # Common LLM output patterns
                                r"(?i)objective:\s*(.*?)(?:\n\n|$)",  # Case-insensitive "Objective:" label
                                r"(?i)formulated objective for[^:]*:\s*(.*?)(?:\n\n|$)",  # Another common pattern
                                r"^\"(.*)\"$",  # Match quoted text (entire response)
                                r"^(.*?)$"  # Just use the first line if nothing else matches
                            ]
                              # Debug print for raw objective
                            print(f"\n[OBJECTIVE_EXTRACTION] Raw objective: {raw_obj[:500]}")
                            
                            extracted_objective = None
                            for pattern in formulation_patterns:
                                match = re.search(pattern, raw_obj.strip(), re.DOTALL | re.MULTILINE)
                                if match:
                                    extracted_objective = match.group(1).strip()
                                    logger.info(f"Extracted objective using pattern '{pattern}': {extracted_objective}")
                                    print(f"[OBJECTIVE_EXTRACTION] Matched pattern: {pattern}")
                                    print(f"[OBJECTIVE_EXTRACTION] Extracted objective: {extracted_objective}")
                                    break
                                else:
                                    print(f"[OBJECTIVE_EXTRACTION] Pattern did not match: {pattern}")
                            
                            # Use the extracted objective if we found one, otherwise use the raw response
                            objective_text = extracted_objective if extracted_objective else raw_obj.strip()
                              # Ensure we're not just echoing the goal
                            if objective_text.lower() == new_goal.lower():
                                logger.warning("LLM echoed back the goal as objective. Using raw response instead.")
                                print(f"[OBJECTIVE_EXTRACTION] WARNING: Objective matches goal exactly!")
                                objective_text = raw_obj.strip()  # Use unprocessed response as fallback
                            
                            # Final validation - if objective is still too similar to goal or too short, add a prefix
                            if len(objective_text) < 20 or objective_text.lower() == new_goal.lower():
                                print(f"[OBJECTIVE_EXTRACTION] Objective too short or matches goal, enhancing it")
                                objective_text = f"Detailed objective: {raw_obj.strip()}"
                            
                            logger.info(f"Original goal: '{new_goal}'")
                            logger.info(f"Formulated objective: '{objective_text}'")
                        else:
                            # Fallback to user goal if error or empty/None response from LLM
                            logger.warning(f"Using goal as objective due to error or empty LLM response. Error: {obj_error if obj_error else 'No response from LLM'}")
                            objective_text = new_goal # Fallback to the original goal
                            if not obj_error: # If obj_error wasn't set by LLM communication failure, set a generic one
                                obj_error = "LLM did not return a usable objective."
                    except Exception as e:
                        logger.error(f"Objective formulation failed: {e}", exc_info=True)
                        objective_text = new_goal
                        logger.warning(f"Using original goal as fallback due to objective formulation failure: '{objective_text}'")                    # CRITICAL FIX: If we still don't have a proper objective formulation,
                    # force a transformation of the goal to make it clearly different and more detailed
                    # Also, ensure obj_error reflects LLM status if it was the cause
                    if not objective_text or objective_text.lower().strip() == new_goal.lower().strip():
                        logger.warning("[CRITICAL] Objective still matches goal or is empty! Forcing a transformation...")
                        
                        # Create a more detailed objective manually from the goal
                        goal_words = new_goal.split()
                        
                        if len(goal_words) <= 3:
                            # Very short goal needs expansion
                            objective_text = f"Complete the following detailed task on the computer: {new_goal}. This involves finding the appropriate application or website, navigating its interface efficiently, and performing all necessary steps to achieve the desired outcome."
                        else:
                            # Add detail and structure to longer goals
                            objective_text = f"Perform the following operation methodically: {new_goal}. Break this down into logical steps, navigating through relevant applications or websites as needed, and ensure all required subtasks are completed."
                        
                        # Add note about LLM server issue if an error occurred
                        if obj_error:
                            logger.warning("Using manually generated objective due to LLM server issues")
                        
                        print(f"[CRITICAL] Forced objective transformation: '{objective_text}'")                    # Format the objective for the GUI
                    # Check if there was an error with the LLM (obj_error should be set if LLM failed)
                    if obj_error or not raw_obj: # Check raw_obj as well, if it's None/empty after LLM call
                        # Ensure the error message is clear about LLM server being offline
                        error_message_detail = str(obj_error) if obj_error else "LLM server offline or did not respond."
                        formatted_objective = f"[ERROR]: {error_message_detail} Formulated Objective: {objective_text}"
                    else:
                        formatted_objective = f"Formulated Objective: {objective_text}"
                    
                    logger.info(f"Formatted objective being sent to GUI: '{formatted_objective}'")

                    # Notify GUI of generated objective
                    await async_update_gui_state("/state/objective", {"text": formatted_objective})
                    
                    # Keep the raw objective for internal use (without prefix)
                    operator.objective = objective_text
                    
                    try:
                        # Run the operator's main loop
                        await operator.operate_loop()
                        logger.info("Operator loop completed successfully.")
                    except Exception as e:
                        logger.error(f"Error in operator loop: {e}", exc_info=True)
                        await async_update_gui_state("/state/operator_status", {"text": f"Error: {str(e)}"})
                    finally:
                        operator_running = False
                        logger.info("Operator is ready for next goal.")

            elif response.status_code == 204:
                logger.debug("No new goal set by the user yet (204 No Content from /operator_state).")
            else:
                logger.error(f"Failed to get operator state from GUI. Status: {response.status_code}, Response: {response.text}")

            # Sleep between checks
            await asyncio.sleep(app_config.MAIN_LOOP_SLEEP_INTERVAL) 

        except httpx.RequestError as e:
            logger.error(f"HTTP request error in main loop: {e}. Check if GUI server is running.", exc_info=False)
            await asyncio.sleep(5) 
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error processing operator state: {e}. Response: {response.text if 'response' in locals() else 'N/A'}", exc_info=True)
        except asyncio.CancelledError:
            logger.info("Main loop cancelled.")
            break 
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            async with operator_state_lock:
                current_operator_state.status = AutomoyStatus.ERROR
                current_operator_state.errors.append(f"Core loop error: {str(e)}")
            await asyncio.sleep(app_config.MAIN_LOOP_ERROR_SLEEP_INTERVAL)

    logger.info("main_async_operations() finished or was stopped.")


def run_async_operations_in_thread():
    global main_loop, async_main_task, stop_event
    
    logger.info("Async operations thread started.")
    if stop_event is None:
        stop_event = asyncio.Event()

    main_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(main_loop)
    
    try:
        async_main_task = main_loop.create_task(main_async_operations())
        main_loop.run_until_complete(async_main_task)
    except asyncio.CancelledError:
        logger.info("Main async task was cancelled externally.")
    except Exception as e:
        logger.error(f"Exception in async operations thread: {e}", exc_info=True)
    finally:
        logger.info("Shutting down asyncio event loop in async thread...")
        
        # Ensure OmniParser is stopped if it was launched by this process
        if operator and operator.omniparser and operator.omniparser.server_process:
            logger.info("Attempting to stop OmniParser server from async thread cleanup...")
            operator.omniparser.stop_server()
            logger.info("OmniParser server stop command issued.")

        if main_loop.is_running():
            tasks = [t for t in asyncio.all_tasks(loop=main_loop) if t is not asyncio.current_task(loop=main_loop)]
            if tasks:
                logger.info(f"Cancelling {len(tasks)} outstanding asyncio tasks...")
                for task in tasks:
                    task.cancel()
                try:
                    main_loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                    logger.info("Outstanding asyncio tasks cancelled/completed.")
                except Exception as e_gather:
                    logger.error(f"Error during gathering of cancelled tasks: {e_gather}", exc_info=True)
            
            logger.info("Stopping asyncio event loop...")
            main_loop.stop() 
            
        if not main_loop.is_closed():
            logger.info("Closing asyncio event loop...")
            main_loop.close()
        logger.info("Asyncio event loop closed.")
        logger.info("Async operations thread finished.")

def signal_handler(signum, frame):
    logger.warning(f"Signal {signal.Signals(signum).name} received. Initiating shutdown...")
    # Ensure OmniParser is stopped if it was launched by this process
    # This is a bit redundant if cleanup_processes also handles it, but good for direct signals.
    if operator and operator.omniparser and operator.omniparser.server_process:
        logger.info("Attempting to stop OmniParser server from signal_handler...")
        operator.omniparser.stop_server() # This is synchronous
        logger.info("OmniParser server stop command issued from signal_handler.")

    if stop_event and main_loop and main_loop.is_running():
        main_loop.call_soon_threadsafe(stop_event.set)
    # cleanup_processes will be called by atexit.
    # Forcing another call here might be redundant or cause issues if not fully idempotent.
    # If PyWebview is blocking the main thread, this signal handler (on main thread)
    # might need to call webview.destroy_window() directly if atexit doesn't fire soon enough
    # or if webview doesn't handle the signal itself to break its loop.
    # For now, rely on atexit and webview's own signal handling.


if __name__ == "__main__":
    # Setup logging as the very first step
    setup_logging() 
    logger.debug(f"Script execution started in __main__ block. Main thread ID: {threading.get_ident()}")

    # Register cleanup_processes to be called on exit, including OmniParser shutdown
    atexit.register(cleanup_processes)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if platform.system() != "Windows":
        signal.signal(signal.SIGHUP, signal_handler)
        signal.signal(signal.SIGQUIT, signal_handler)

    stop_event = asyncio.Event() # Initialize the global stop_event

    if not start_gui_and_create_webview_window(): # This is synchronous
        logger.error("Failed to initialize GUI and/or PyWebview window object. Automoy cannot start.")
        sys.exit(1) 

    logger.info("GUI process started and PyWebview window object created.")
    logger.info("Starting asyncio operations in a separate thread...")
    
    async_thread = threading.Thread(target=run_async_operations_in_thread, name="AsyncioOperationsThread", daemon=True)
    async_thread.start()

    try:
        logger.info("Starting PyWebview event loop on the main thread... (This will block)")
        # Pass the created window object to webview.start() if it's not already the default
        # However, webview.start() uses all created windows if not specified.
        webview.start(debug=False)
        logger.info("PyWebview event loop finished.")
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt on main thread (webview.start). Relying on signal_handler and atexit.")
    except Exception as e:
        logger.error(f"Unhandled exception in PyWebview event loop (main thread): {e}", exc_info=True)
    finally:
        logger.info("Main thread's PyWebview loop has ended. Initiating final cleanup sequence...")
        if stop_event and not stop_event.is_set(): # Ensure async thread is signaled to stop
            logger.info("Main thread explicitly signaling stop_event for async operations post-webview.")
            if main_loop and main_loop.is_running(): # Check if loop is available and running
                main_loop.call_soon_threadsafe(stop_event.set)
            else: # Fallback if loop is not running or not available
                stop_event.set()

        # cleanup_processes() is registered with atexit.
        # Explicitly calling it here might be okay if it's idempotent.
        # For now, let atexit handle it to avoid potential double-cleanup issues.

        if async_thread.is_alive():
            logger.info("Waiting for asyncio operations thread to complete...")
            async_thread.join(timeout=15) 
            if async_thread.is_alive():
                logger.warning("Asyncio operations thread did not complete in the allocated time.")
            else:
                logger.info("Asyncio operations thread has completed.")
        else:
            logger.info("Asyncio operations thread has already completed.")
            
        # MODIFIED: Use app_config
        logger.info(f"{app_config.AUTOMOY_APP_NAME} application shutdown complete.")
        # sys.exit(0) # Let the script exit naturally after main thread finishes.
