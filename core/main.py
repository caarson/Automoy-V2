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


gui_process = None
omniparser_server_process = None # To keep track of the OmniParser server process

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
        print(f"[MAIN_GUI_CTRL] pygetwindow: Restoring, resizing, and moving window '{window.title}'.")
        if window.isMinimized:
            window.restore()
        
        if not window.visible:
            window.show()
            print(f"[MAIN_GUI_CTRL] pygetwindow: Window '{window.title}' was not visible, called show().")
         
        window.activate()
        window.resizeTo(1228, 691) 
        window.moveTo(0, 0)        
        window.activate()
        print(f"[MAIN_GUI_CTRL] pygetwindow: Window '{window.title}' shown and positioned at (0,0) with size 1228x691.")
    else:
        print("[MAIN_GUI_CTRL] pygetwindow: Window not provided for show_and_position.")

async def async_manage_automoy_gui_visibility(action: str, window_title: str = AUTOMOY_GUI_TITLE_PREFIX) -> bool:
    # Normalize action and handle minimize (hide) directly via pygetwindow
    normalized = action.lower()
    if normalized in ('hide', 'minimize'):
        print(f"[MAIN_GUI_CTRL] Minimizing Automoy GUI ('{window_title}') via pygetwindow.")
        window = find_automoy_gui_window()
        if not window:
            print(f"[MAIN_GUI_CTRL] No GUI window found with prefix '{window_title}' to minimize.")
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


async def main():
    global gui_process, omniparser_server_process 
    config = Config()
    initial_objective = config.get("DEFAULT_OBJECTIVE", "No objective set in environment.txt")
    print(f"Initial Objective: {initial_objective}")

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

    operator = AutomoyOperator(
        objective=initial_objective,
        manage_gui_window_func=functools.partial(async_manage_automoy_gui_visibility, window_title=AUTOMOY_GUI_TITLE_PREFIX),
        omniparser=omniparser_manager.get_interface() 
    )

    if config.get("DESKTOP_ANCHOR_POINT", False):
        print("[MAIN] Applying desktop anchor point...")
        from core.environmental.anchor.desktop_anchor_point import show_desktop
        show_desktop() 
        await asyncio.sleep(0.5)

    # Initial screenshot and parse sequence
    try:
        print("[MAIN] Performing initial screen capture and parse.")
        await _update_gui_state("objective", {"text": initial_objective}) 
        await _update_gui_state("current_operation", {"text": "Initializing... Taking first screenshot."}) 
        await hide_gui_for_screenshot(AUTOMOY_GUI_TITLE_PREFIX)

        desktop_utils.set_desktop_background_solid_color(0, 0, 0) 
        await asyncio.sleep(0.2)

        initial_screenshot_path = operator.os_interface.take_screenshot("initial_automoy_screenshot.png")
        print(f"[MAIN] Initial screenshot saved to {initial_screenshot_path}")

    except Exception as e:
        print(f"[MAIN][ERROR] Error during initial screenshot sequence: {e}")
        await _update_gui_state("current_operation", {"text": f"Error during init: {e}"})
    finally:
        desktop_utils.restore_desktop_background_settings()
        await show_gui_after_screenshot(AUTOMOY_GUI_TITLE_PREFIX)
        print("[MAIN] Initial screenshot process complete. Desktop and GUI restored.")

    # Start the main operation loop
    try:
        await operator.operate_loop()
    except KeyboardInterrupt:
        print("[MAIN] KeyboardInterrupt received. Shutting down...")
    except Exception as e:
        print(f"[MAIN][ERROR] Unhandled exception in operator.operate_loop: {e}")
    finally:
        print("[MAIN] Main operation loop finished or interrupted. Cleaning up...")
        if hasattr(omniparser_manager, 'stop_server'): omniparser_manager.stop_server()
        cleanup_processes() # This will also try to clean up GUI and any other OmniParser processes
        print("[MAIN] Automoy has shut down.")

if __name__ == "__main__":
    # Setup signal handlers for graceful shutdown on SIGINT/SIGTERM
    # Note: Windows handles SIGINT (Ctrl+C) differently for console apps vs subprocesses.
    # This setup is more common for Unix-like systems but good practice.
    # The primary KeyboardInterrupt handling is within main() and the asyncio.run() wrapper.
    
    # loop = asyncio.get_event_loop()
    # signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    # for s in signals:
    #     loop.add_signal_handler(
    #         s, lambda s=s: asyncio.create_task(shutdown(s, loop))
    #     )

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[MAIN_ASYNC_RUNNER] KeyboardInterrupt received at top level. Ensuring cleanup...")
    # No specific handling for other exceptions here, as main() should handle its own.
    finally:
        # This final cleanup is a last resort.
        # It's crucial that `main()` and `cleanup_processes()` are robust.
        print("[MAIN_ASYNC_RUNNER] Ensuring final cleanup...")
        # Call cleanup_processes directly, as the loop might be stopped.
        # It's important that cleanup_processes is synchronous or manages its own async tasks carefully if any.
        cleanup_processes() # Ensure this is robust and handles already cleaned states.
        print("[MAIN_ASYNC_RUNNER] Final cleanup attempt complete. Exiting.")
