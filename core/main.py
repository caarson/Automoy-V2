import sys
import os
import asyncio
import json
import signal
import subprocess
import threading
import time
import webview
import requests
import httpx
import logging
import logging.handlers
import platform
import atexit

from typing import Any, Dict, Optional, List, Union, TYPE_CHECKING

# Adjust sys.path to include the project root
PROJECT_ROOT_FOR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT_FOR_PATH not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_FOR_PATH)

# Configuration and utility imports
import config.config as app_config

from core.operate import AutomoyOperator
from core.data_models import AutomoyStatus, OperatorState
from core.utils.operating_system.process_utils import is_process_running_on_port, kill_process_on_port

if TYPE_CHECKING:
    from core.operate import AutomoyOperator
    from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager

# Global variables
gui_process: Optional[subprocess.Popen] = None
webview_window_global: Optional[webview.Window] = None
current_gui_visibility: bool = False
operator: 'AutomoyOperator' = None
omniparser_manager: Optional['OmniParserServerManager' ] = None  # Track OmniParser server manager

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


def on_window_closed():
    """Handler for when the webview window is closed."""
    logger.info("PyWebview window closed by user - initiating cleanup...")
    # Call cleanup immediately when window is closed
    cleanup_processes()

def start_gui_and_create_webview_window():
    global gui_process, webview_window_global
    gui_script_path = os.path.join(PROJECT_ROOT, "gui", "gui.py") 
    
    if not os.path.exists(gui_script_path):
        logger.error(f"GUI script not found at {gui_script_path}")
        return False

    try:
        if is_process_running_on_port(app_config.GUI_PORT):
            logger.warning(f"Process already running on port {app_config.GUI_PORT}. Attempting to kill it.")
            if kill_process_on_port(app_config.GUI_PORT):
                logger.info(f"Successfully killed existing process on port {app_config.GUI_PORT}.")
                time.sleep(1) 
            else:
                logger.error(f"Failed to kill existing process on port {app_config.GUI_PORT}. GUI start might fail.")
        
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW
        
        logger.info(f'Starting GUI: "{sys.executable}" "{gui_script_path}" --host {app_config.GUI_HOST} --port {app_config.GUI_PORT}')
        gui_process = subprocess.Popen([
            sys.executable, 
            gui_script_path, 
            "--host", app_config.GUI_HOST,
            "--port", str(app_config.GUI_PORT)
        ], creationflags=creation_flags)
        logger.info(f"GUI process started with PID: {gui_process.pid}. Waiting for it to be healthy...")

        max_wait_time = 60 
        start_time = time.time()
        gui_ready = False
        while time.time() - start_time < max_wait_time:
            try:
                response = requests.get(f"http://{app_config.GUI_HOST}:{app_config.GUI_PORT}/health", timeout=2)
                if response.status_code == 200:
                    logger.info("GUI is healthy and responsive.")
                    gui_ready = True
                    break
                else:
                    logger.warning(f"GUI health check returned status {response.status_code}, retrying...")
            except requests.exceptions.ConnectionError:
                logger.warning("GUI not ready yet (connection error), retrying...")
            except requests.exceptions.Timeout:
                logger.warning("GUI health check timed out, retrying...")
            except requests.RequestException as e:
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
                    logger.warning("GUI process did not terminate gracefully, killing...")
                    gui_process.kill()
            gui_process = None
            return False

        logger.info("GUI subprocess started and reported healthy.")
        logger.info("Attempting to create PyWebview window object for the GUI...")
        gui_url = f"http://{app_config.GUI_HOST}:{app_config.GUI_PORT}"
        window_title = f"{app_config.AUTOMOY_GUI_TITLE_PREFIX} {gui_url}"
        
        webview_window_global = webview.create_window(
            window_title,
            gui_url,
            width=1088,  # 15% smaller than 1280 (1280 * 0.85)
            height=680,  # 15% smaller than 800 (800 * 0.85)
            resizable=True,
            frameless=True,  # Make window borderless
            easy_drag=True,
            min_size=(510, 340),  # 15% smaller min size
            js_api=None,  # We'll add zoom control after window creation
            on_top=False,
            shadow=True
        )
        if webview_window_global:
             logger.info(f"PyWebview window object '{window_title}' created successfully. It will be started on the main thread.")
             return True
        else:
             logger.error(f"PyWebview window object creation returned None.")
             return False

    except Exception as e:
        logger.error(f"Failed to start GUI or create PyWebview window object: {e}", exc_info=True)
        if gui_process and gui_process.poll() is None:
            gui_process.kill()
        gui_process = None
        webview_window_global = None
        return False

async def set_webview_zoom(zoom_level: float = 0.7):
    """Set zoom level for the webview window and ensure content fills the entire window."""
    global webview_window_global
    if webview_window_global:
        try:
            # Wait for page to be fully loaded first
            await asyncio.sleep(1)
            
            # Apply proper CSS scaling that makes content fill the window completely
            zoom_js = f"""
            try {{
                // Wait for page to be ready
                if (document.readyState !== 'complete') {{
                    window.addEventListener('load', function() {{
                        applyZoom();
                    }});
                }} else {{
                    applyZoom();
                }}
                
                function applyZoom() {{
                    console.log('Applying Automoy zoom: {zoom_level}');
                    
                    // Get the actual window dimensions
                    const windowWidth = window.innerWidth;
                    const windowHeight = window.innerHeight;
                    
                    // Calculate the inverse scale to make content fill the scaled space
                    const inverseScale = 1 / {zoom_level};
                    
                    // Remove existing zoom styles first
                    const existingStyle = document.getElementById('automoy-zoom-style');
                    if (existingStyle) {{
                        existingStyle.remove();
                    }}
                    
                    // Create comprehensive zoom styles
                    const style = document.createElement('style');
                    style.id = 'automoy-zoom-style';
                    style.textContent = `
                        html {{
                            margin: 0 !important;
                            padding: 0 !important;
                            width: 100% !important;
                            height: 100% !important;
                            overflow: hidden !important;
                            box-sizing: border-box !important;
                        }}
                        
                        body {{
                            margin: 0 !important;
                            padding: 0 !important;
                            transform-origin: top left !important;
                            transform: scale({zoom_level}) !important;
                            width: ${{windowWidth * inverseScale}}px !important;
                            height: ${{windowHeight * inverseScale}}px !important;
                            overflow: auto !important;
                            box-sizing: border-box !important;
                        }}
                        
                        * {{
                            box-sizing: border-box !important;
                        }}
                        
                        .main-flex, .top-nav {{
                            width: 100% !important;
                        }}
                        
                        .left-panel, .right-panel {{
                            min-height: 100% !important;
                        }}
                    `;
                    
                    document.head.appendChild(style);
                    
                    // Force layout recalculation
                    document.body.offsetHeight;
                    
                    console.log('Automoy zoom applied successfully: ' + {zoom_level} + 'x scale');
                    console.log('Body dimensions: ' + document.body.style.width + ' x ' + document.body.style.height);
                }}
            }} catch (e) {{
                console.error('Error applying zoom:', e);
            }}
            """
              # Execute the zoom JavaScript
            webview_window_global.evaluate_js(zoom_js)
            logger.info(f"Set webview zoom level to {zoom_level} with improved scaling and error handling")
              # Give it another moment and try again to ensure it sticks
            await asyncio.sleep(0.5)
            webview_window_global.evaluate_js(f"console.log('Zoom check: body scale is', getComputedStyle(document.body).transform);")
            
            # Dispatch UI zoom completion event for loading screen AFTER zoom verification
            zoom_complete_js = """
            try {
                // Check if zoom was actually applied before dispatching
                function checkAndDispatchZoom() {
                    const body = document.body;
                    const computedStyle = getComputedStyle(body);
                    const transform = computedStyle.transform;
                    
                    console.log('Checking zoom application - transform:', transform);
                    console.log('Body computed style transform:', transform);
                    
                    // Force layout recalculation to ensure styles are applied
                    document.body.offsetHeight;
                      // Check if transform contains scale (matrix format means transform is applied)
                    if (transform && transform !== 'none' && transform.includes('matrix')) {
                        console.log('✅ Zoom confirmed to be applied - dispatching ui-zoomed event');
                        // Add a substantial visual confirmation delay to ensure the zoom effect is visually complete
                        setTimeout(() => {
                            window.dispatchEvent(new CustomEvent('ui-zoomed'));
                            console.log('🎯 UI zoom event dispatched after extended visual confirmation delay');
                        }, 3000); // 3 second delay to ensure visual effect is definitely complete
                        return true;
                    } else {
                        console.log('❌ Zoom not yet applied, waiting... (transform=' + transform + ')');
                        return false;
                    }
                }
                
                // Try to verify zoom application, with retries
                let retryCount = 0;
                const maxRetries = 30; // 15 seconds total (30 * 500ms)
                
                function verifyZoomWithRetry() {
                    console.log(`🔍 Zoom verification attempt ${retryCount + 1}/${maxRetries}`);
                    if (checkAndDispatchZoom()) {
                        console.log('UI zoom completion event will be dispatched after visual delay');
                    } else if (retryCount < maxRetries) {
                        retryCount++;
                        setTimeout(verifyZoomWithRetry, 500); // Check every 500ms
                    } else {
                        console.warn('⚠️ Zoom verification timeout - dispatching event anyway');
                        window.dispatchEvent(new CustomEvent('ui-zoomed'));
                    }
                }
                
                // Wait a bit longer before starting verification to allow CSS to be applied
                setTimeout(() => {
                    console.log('🚀 Starting zoom verification process...');
                    verifyZoomWithRetry();
                }, 1500); // Wait 1.5 seconds before starting verification
                
            } catch (e) {
                console.error('Error in zoom verification:', e);
                // Fallback - dispatch event anyway
                window.dispatchEvent(new CustomEvent('ui-zoomed'));
            }
            """
            webview_window_global.evaluate_js(zoom_complete_js)
        except Exception as e:
            logger.warning(f"Failed to set webview zoom: {e}")
            # Fallback: try a simpler zoom approach
            try:
                simple_zoom = f"document.body.style.zoom = '{zoom_level}';"
                webview_window_global.evaluate_js(simple_zoom)
                logger.info(f"Applied fallback zoom: {zoom_level}")                # Dispatch UI zoom completion event for fallback zoom with verification
                zoom_complete_js = """
                try {
                    // Check if fallback zoom was actually applied
                    function checkFallbackZoom() {
                        const body = document.body;
                        const zoom = body.style.zoom;
                        
                        console.log('Checking fallback zoom application - zoom:', zoom);
                        
                        // Force layout recalculation
                        document.body.offsetHeight;
                          if (zoom && zoom !== '1' && zoom !== '') {
                            console.log('✅ Fallback zoom confirmed - dispatching ui-zoomed event');
                            // Add substantial visual confirmation delay
                            setTimeout(() => {
                                window.dispatchEvent(new CustomEvent('ui-zoomed'));
                                console.log('🎯 UI zoom event dispatched (fallback) after extended visual confirmation delay');
                            }, 3000); // 3 second delay for fallback too
                            return true;
                        } else {
                            console.log('❌ Fallback zoom not yet applied, waiting...');
                            return false;
                        }
                    }
                    
                    // Try to verify fallback zoom with retries
                    let retryCount = 0;
                    const maxRetries = 20; // 10 seconds total
                    
                    function verifyFallbackZoomWithRetry() {
                        console.log(`🔍 Fallback zoom verification attempt ${retryCount + 1}/${maxRetries}`);
                        if (checkFallbackZoom()) {
                            console.log('UI zoom completion event will be dispatched (fallback) after visual delay');
                        } else if (retryCount < maxRetries) {
                            retryCount++;
                            setTimeout(verifyFallbackZoomWithRetry, 500);
                        } else {
                            console.warn('⚠️ Fallback zoom verification timeout - dispatching event anyway');
                            window.dispatchEvent(new CustomEvent('ui-zoomed'));
                        }
                    }
                    
                    // Wait before starting fallback verification
                    setTimeout(() => {
                        console.log('🚀 Starting fallback zoom verification process...');
                        verifyFallbackZoomWithRetry();
                    }, 1500);
                    
                } catch (e) {
                    console.error('Error in fallback zoom verification:', e);
                    window.dispatchEvent(new CustomEvent('ui-zoomed'));
                }
                """
                webview_window_global.evaluate_js(zoom_complete_js)
            except Exception as e2:
                logger.error(f"Fallback zoom also failed: {e2}")

async def dispatch_system_ready_event():
    """Dispatch system-ready event to indicate all initialization is complete."""
    global webview_window_global
    if webview_window_global:
        try:
            system_ready_js = """
            try {
                // Dispatch system-ready event to indicate all initialization is complete
                window.dispatchEvent(new CustomEvent('system-ready'));
                console.log('System-ready event dispatched - all initialization complete');
            } catch (e) {
                console.error('Error dispatching system-ready event:', e);
            }
            """
            webview_window_global.evaluate_js(system_ready_js)
            logger.info("System-ready event dispatched to GUI")
        except Exception as e:
            logger.warning(f"Failed to dispatch system-ready event: {e}")

async def async_manage_automoy_gui_visibility(target_visibility: bool):
    global current_gui_visibility
    # PyWebview windows are visible by default when created and shown
    # We can't easily hide/show them programmatically without custom API
    # For now, just log the request and update the state
    logger.debug(f"Request to change GUI visibility to: {'visible' if target_visibility else 'hidden'}")
    current_gui_visibility = target_visibility
    logger.debug(f"GUI visibility state updated to: {'visible' if target_visibility else 'hidden'}")


# Global flag to prevent double cleanup
_cleanup_called = False

def cleanup_processes():
    global gui_process, webview_window_global, operator, async_main_task, main_loop, stop_event, omniparser_manager, _cleanup_called

    # Make cleanup idempotent to prevent issues with double calls
    if _cleanup_called:
        logger.debug("Cleanup already called, skipping duplicate cleanup")
        return
    
    _cleanup_called = True
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
    
    # PyWebview window destruction should happen on the main thread,
    # typically by webview.start() exits naturally.
    if webview_window_global:
        logger.info("PyWebview window will be destroyed when webview.start() exits")
        webview_window_global = None

    if gui_process and gui_process.poll() is None:
        logger.info(f"Terminating GUI subprocess (PID: {gui_process.pid})...")
        try:
            gui_process.terminate()
            gui_process.wait(timeout=5)
            logger.info("GUI subprocess terminated.")
        except subprocess.TimeoutExpired:
            logger.warning("GUI process did not terminate gracefully, killing...")
            gui_process.kill()
            gui_process.wait(timeout=2) 
            logger.info("GUI subprocess killed.")
        except Exception as e:
            logger.error(f"Error terminating GUI process: {e}", exc_info=True)
        gui_process = None
    
    if operator and hasattr(operator, 'stop_gracefully'):
        logger.info("Stopping AutomoyOperator...")
        try:
            operator.stop_gracefully() 
            logger.info("AutomoyOperator stopped.")
        except Exception as e:
            logger.error(f"Error stopping AutomoyOperator: {e}", exc_info=True)
    
    # Cleanup OmniParser server if we started it
    if omniparser_manager:
        logger.info("Stopping OmniParser server...")
        try:
            omniparser_manager.stop_server()
            logger.info("OmniParser server stopped.")
        except Exception as e:
            logger.error(f"Error stopping OmniParser server: {e}", exc_info=True)
        omniparser_manager = None
    
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
            url_endpoint = f"/state/{endpoint}" # Default to /state/ if not a full path
        else:
            url_endpoint = endpoint

        # MODIFIED: Use app_config for GUI_HOST and GUI_PORT
        url = f"http://{app_config.GUI_HOST}:{app_config.GUI_PORT}{url_endpoint}"
        
        # Ensure payload is not None, default to empty dict if it is
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(url, json=payload if payload is not None else {})
        
        if response.status_code == 200:
            logger.debug(f"[GUI_UPDATE] Successfully sent payload to {url}.")
        else:
            # For 422 errors, log more of the response to see validation details
            if response.status_code == 422:
                logger.warning(f"[GUI_UPDATE] Failed to send payload to {url}. Response status: {response.status_code}, text: {response.text}")
            else:
                logger.warning(f"[GUI_UPDATE] Failed to send payload to {url}. Response status: {response.status_code}, text: {response.text[:200] if response.text else 'N/A'}")
            
    except httpx.RequestError as e:
        logger.warning(f"Failed to update GUI state at {url} (RequestError): {e}")
    except Exception as e:
        logger.error(f"Unexpected error in async_update_gui_state sending to {url}: {e}", exc_info=True)

async def main_async_operations():
    global operator_state_lock, current_operator_state, operator, stop_event, omniparser_manager
    
    logger.debug("main_async_operations() coroutine entered.")
    
    if stop_event is None: 
        stop_event = asyncio.Event()
    
    omniparser_port = app_config.OMNIPARSER_PORT
    omniparser_base_url = f"http://localhost:{omniparser_port}"
    
    # Check if OmniParser server is running
    omniparser_running = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{omniparser_base_url}/probe/")
        if response.status_code == 200:
            logger.info("OmniParser server is already running.")
            omniparser_running = True
        else:
            logger.info(f"OmniParser server probe returned status {response.status_code}.")
    except httpx.RequestError:
        logger.info("OmniParser server is not running or not responding. Attempting to start it automatically...")
      # Auto-start OmniParser server if not running
    if not omniparser_running:
        try:
            from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
            logger.info("Starting OmniParser server automatically...")
            omniparser_manager = OmniParserServerManager(server_url=omniparser_base_url)
            
            # Start the server (this is a blocking operation that spawns the server)
            server_process = omniparser_manager.start_server('automoy_env')
            
            if server_process:
                logger.info("OmniParser server started successfully. Waiting for it to be ready...")
                # Wait for server to be ready (with a reasonable timeout)
                server_ready = omniparser_manager.wait_for_server(timeout=45)
                if server_ready:
                    logger.info("OmniParser server is now ready!")
                    omniparser_running = True
                else:
                    logger.error("OmniParser server failed to become ready within timeout.")
            else:
                logger.error("Failed to start OmniParser server automatically.")
        except Exception as e:
            logger.error(f"Exception occurred while auto-starting OmniParser server: {e}", exc_info=True)
    
    if not omniparser_running:
        logger.warning("OmniParser server is not available. Visual analysis will not work properly.")    # Initialize OmniParser interface
    try:
        from core.utils.omniparser.omniparser_interface import OmniParserInterface
        omniparser = OmniParserInterface(server_url=omniparser_base_url)
        logger.info("OmniParser interface initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize OmniParser interface: {e}", exc_info=True)
        if stop_event: 
            stop_event.set()
        return

    # Create pause event for the operator
    pause_event = asyncio.Event()
    pause_event.set()  # Start unpaused

    try:
        # Initialize AutomoyOperator with all required parameters
        operator = AutomoyOperator(
            objective="",  # Will be set later when user provides a goal
            manage_gui_window_func=async_manage_gui_window,
            omniparser=omniparser,
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
      # Set zoom level to make GUI smaller/more compact
    await asyncio.sleep(3)  # Longer delay to ensure window and DOM are fully ready
    logger.info("Applying zoom level...")
    await set_webview_zoom(0.7)  # 70% zoom - adjusted for more compact view
    logger.info("Zoom application completed - zoom verification is now running in JavaScript")
    
    # Wait a moment for the JavaScript zoom verification to complete
    logger.info("Waiting for JavaScript zoom verification to complete...")
    await asyncio.sleep(2)  # Brief delay to allow JS verification to start
    
    # Dispatch system-ready event to indicate all initialization is complete
    logger.info("ALL INITIALIZATION COMPLETE - dispatching system-ready event...")
    await dispatch_system_ready_event()
    logger.info("System-ready event dispatched - loading screen should now hide when BOTH zoom verification AND system ready are complete")
    
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
                new_goal = new_state_data.get("goal")
                  # Update our local state
                async with operator_state_lock:
                    current_operator_state.goal = new_goal or current_operator_state.goal
                    
                    # Parse status with error handling
                    status_value = new_state_data.get("status", current_operator_state.status.value)
                    try:
                        # Handle status messages that contain "Failed:" prefix
                        if isinstance(status_value, str) and status_value.startswith("Failed:"):
                            current_operator_state.status = AutomoyStatus.FAILED
                        else:
                            current_operator_state.status = AutomoyStatus(status_value)
                    except ValueError:
                        logger.warning(f"Invalid status value received: '{status_value}', defaulting to ERROR")
                        current_operator_state.status = AutomoyStatus.ERROR
                    
                    current_operator_state.objective = new_state_data.get("objective")
                    current_operator_state.parsed_steps = new_state_data.get("parsed_steps")
                    current_operator_state.current_step_index = new_state_data.get("current_step_index", -1)
                    current_operator_state.errors = new_state_data.get("errors", [])                # Check if we have a new goal to process
                if new_goal and new_goal != current_goal and not operator_running:
                    logger.info(f"New goal received: '{new_goal}'. Formulating objective...")
                    current_goal = new_goal
                    operator_running = True
                    
                    # Formulate objective from user goal using LLM
                    try:
                        from core.prompts.prompts import FORMULATE_OBJECTIVE_SYSTEM_PROMPT, FORMULATE_OBJECTIVE_USER_PROMPT_TEMPLATE
                        from core.lm.lm_interface import MainInterface, handle_llm_response
                        
                        # Create LLM interface for objective formulation
                        lm_interface = MainInterface()
                        
                        # Format the objective formulation prompt
                        objective_prompt = FORMULATE_OBJECTIVE_USER_PROMPT_TEMPLATE.format(
                            user_goal=new_goal
                        )
                        logger.info("Sending objective formulation request to LLM...")
                        
                        # Create messages for LLM request
                        messages = [
                            {"role": "system", "content": FORMULATE_OBJECTIVE_SYSTEM_PROMPT},
                            {"role": "user", "content": objective_prompt}
                        ]
                        
                        # Make LLM request using the correct method
                        raw_response, thinking_output, error = await lm_interface.get_llm_response(
                            model=lm_interface.config.get_model(),
                            messages=messages,
                            objective="Formulate clear objective from user goal",
                            session_id="objective_formulation",
                            response_format_type="default"                        )
                        
                        if error:
                            logger.error(f"LLM request failed: {error}")
                            formulated_objective = new_goal
                        elif raw_response and raw_response.strip():
                            # Process the raw response to remove <think> tags and clean it
                            cleaned_response = handle_llm_response(
                                raw_response, 
                                "objective_formulation", 
                                is_json=False
                            )
                            formulated_objective = cleaned_response.strip() if cleaned_response else new_goal
                            logger.info(f"Objective formulated: '{formulated_objective}'")
                            
                            # Update GUI with formulated objective
                            await async_update_gui_state("/set_formulated_objective", {"objective": formulated_objective})
                            
                            # Update operator with formulated objective
                            operator.objective = formulated_objective
                        else:
                            logger.warning("LLM returned empty response for objective formulation. Using original goal.")
                            formulated_objective = new_goal
                            operator.objective = new_goal
                            
                    except Exception as e:
                        logger.error(f"Error during objective formulation: {e}", exc_info=True)
                        logger.info("Using original user goal as objective.")
                        formulated_objective = new_goal
                        operator.objective = new_goal
                    
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
    if stop_event and main_loop and main_loop.is_running():
        main_loop.call_soon_threadsafe(stop_event.set)
    # cleanup_processes will be called by atexit.
    # Forcing another call here might be redundant or cause issues if not fully idempotent.
    # If PyWebview is blocking the main thread, this signal handler (on main thread)
    # might need to call webview.destroy_window() directly if atexit doesn't fire soon enough
    # or if webview doesn't handle the signal itself to break its loop.
    # For now, rely on atexit and webview's own signal handling.


if __name__ == "__main__":
    print("=== AUTOMOY V2 STARTING ===")
    print("Setting up logging...")    # Setup logging as the very first step
    setup_logging()
    print("Logging setup complete.")
    logger.debug(f"Script execution started in __main__ block. Main thread ID: {threading.get_ident()}")
    print(f"Main thread ID: {threading.get_ident()}")
    
    print("Registering cleanup function...")
    # Register cleanup function
    atexit.register(cleanup_processes)
    
    print("Setting up signal handlers...")
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if platform.system() != "Windows":
        signal.signal(signal.SIGHUP, signal_handler)
        signal.signal(signal.SIGQUIT, signal_handler)

    print("Initializing stop event...")
    stop_event = asyncio.Event() # Initialize the global stop_event

    print("Starting GUI and creating webview window...")
    if not start_gui_and_create_webview_window(): # This is synchronous
        print("ERROR: Failed to initialize GUI!")
        logger.error("Failed to initialize GUI and/or PyWebview window object. Automoy cannot start.")
        sys.exit(1)

    logger.info("GUI process started and PyWebview window object created.")
    logger.info("Starting asyncio operations in a separate thread...")
    
    async_thread = threading.Thread(target=run_async_operations_in_thread, name="AsyncioOperationsThread", daemon=True)
    async_thread.start()

    try:
        logger.info("Starting PyWebview event loop on the main thread... (This will block)")        # Pass the created window object to webview.start() if it's not already the default
        # However, webview.start() uses all created windows if not specified.
        webview.start(debug=False)  # Set debug=False to disable DevTools
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

        # Explicitly call cleanup when window is closed to ensure immediate OmniParser cleanup
        logger.info("Calling cleanup_processes explicitly since GUI window was closed...")
        cleanup_processes()

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
                      # atexit will run before full termination.
