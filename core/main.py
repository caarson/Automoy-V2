import os
import sys
# Correctly position sys.path modification before custom package imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import pathlib
import time
import requests
import threading
import atexit
import signal
import pygetwindow as gw
import pyautogui # <--- Add this import
import shutil
from core.utils.operating_system.desktop_utils import DesktopUtils # Added

REQUIRED_ENV_NAME = "automoy_env"

# --- Parse command-line arguments ---
parser = argparse.ArgumentParser(description="Launch Automoy")
parser.add_argument("--objective", type=str, help="Automation objective for Automoy")
args = parser.parse_args()

# --- Verify we're in the correct Conda environment ---
if os.environ.get("CONDA_DEFAULT_ENV") != REQUIRED_ENV_NAME:
    print(f"❌ You are not in the required Conda environment: '{REQUIRED_ENV_NAME}'.")
    print("💡 Please activate the correct environment and run this script again.")
    sys.exit(1)

# --- Project imports ---
from core.operate import operate_loop
from core.utils.omniparser.omniparser_interface import OmniParserInterface

# --- Compute the project root ---
PROJECT_ROOT = pathlib.Path(__file__).parents[1].resolve()

# Load configuration (includes environment overrides)
from config.config import Config
cfg = Config()

# --- OmniParser defaults ---
DEFAULT_SERVER_CWD = str(PROJECT_ROOT / "dependencies" / "OmniParser-master" / "omnitool" / "omniparserserver")
DEFAULT_MODEL_PATH = str(PROJECT_ROOT / "dependencies" / "OmniParser-master" / "weights" / "icon_detect" / "model.pt")
DEFAULT_CAPTION_MODEL_DIR = str(PROJECT_ROOT / "dependencies" / "OmniParser-master" / "weights" / "icon_caption_florence")

# --- Initialize OmniParser ---
omniparser = OmniParserInterface()
launched = omniparser.launch_server(
    conda_path=None,
    conda_env="automoy_env",
    cwd=DEFAULT_SERVER_CWD,
    port=8111,
    model_path=None,
    caption_model_dir=None
)

# --- Clean shutdown ---
atexit.register(omniparser.stop_server)
signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
signal.signal(signal.SIGTERM, lambda sig, frame: sys.exit(0))

# --- Run Automoy ---
# Launch the GUI by running gui.py
if __name__ == "__main__":
    if launched:
        import subprocess
        print("✅ OmniParser launched. Starting GUI...")
        gui_process = subprocess.Popen([sys.executable, str(PROJECT_ROOT / "gui" / "gui.py")])

        # Ensure the GUI process is terminated when the main program exits
        atexit.register(gui_process.terminate)

        import asyncio

        async def wait_for_objective():
            retries = 0
            max_retries = 5
            while retries < max_retries:
                try:
                    # Attempt to fetch the objective from the GUI
                    response = requests.get("http://127.0.0.1:8000/health", timeout=5)
                    if response.status_code == 200:
                        print("[INFO] GUI is healthy. Waiting for objectives...")
                        return
                except requests.exceptions.RequestException as e:
                    retries += 1
                    print(f"[WARNING] GUI not reachable. Retry attempt {retries}/{max_retries}...")
                    time.sleep(2)  # Wait before retrying

            print("[ERROR] GUI is not reachable after multiple attempts. Exiting...")
            exit(1)

        async def hide_gui_for_screenshot():
            """Hides the Automoy GUI and minimizes the OmniParser console for screenshots."""
            automoy_gui_control_url = "http://127.0.0.1:8000/control/window"
            automoy_gui_title_prefix = "Automoy - Access via"
            omniparser_console_title_part = "OmniParser Server Console"
            print("[HIDE_GUI_FOR_SCREENSHOT] Starting...")

            # Hide Automoy GUI window
            print("[INFO] Attempting to hide Automoy GUI window via API.")
            try:
                response = requests.post(f"{automoy_gui_control_url}/hide", timeout=3)
                print(f"[INFO] Automoy GUI hide API response status: {response.status_code}")
                if response.status_code == 200:
                    print(f"[INFO] Automoy GUI hide request successful. Response: {response.text}")
                else:
                    print(f"[WARNING] Automoy GUI hide request failed: {response.status_code} - {response.text}")
            except requests.exceptions.RequestException as e:
                print(f"[ERROR] Failed to send hide request to Automoy GUI: {e}")
            
            print("[INFO] Giving PyWebView 0.7s to process hide command via API...")
            await asyncio.sleep(0.7)

            print("[INFO] Checking Automoy GUI visibility with pygetwindow after API hide call.")
            gui_windows = [w for w in gw.getWindowsWithTitle(automoy_gui_title_prefix) if w.title.startswith(automoy_gui_title_prefix)]
            if gui_windows:
                gui_window = gui_windows[0]
                print(f"[INFO] Found Automoy GUI window for pygetwindow check: '{gui_window.title}', isVisible: {gui_window.visible}, isMinimized: {gui_window.isMinimized}")
                if gui_window.visible and not gui_window.isMinimized:
                    print("[WARNING] Automoy GUI still visible and not minimized after API hide. Attempting pygetwindow.minimize().")
                    try:
                        gui_window.minimize()
                        await asyncio.sleep(0.5)
                        updated_gui_windows = [w for w in gw.getWindowsWithTitle(automoy_gui_title_prefix) if w.title.startswith(automoy_gui_title_prefix)]
                        if updated_gui_windows:
                            updated_gui_window = updated_gui_windows[0]
                            if updated_gui_window.isMinimized:
                                print("[INFO] Automoy GUI minimized successfully via pygetwindow.")
                            elif not updated_gui_window.visible:
                                print("[INFO] Automoy GUI became hidden after pygetwindow minimize attempt (not minimized but not visible).")
                            else:
                                print(f"[WARNING] pygetwindow minimize() failed or window still visible. isVisible: {updated_gui_window.visible}, isMinimized: {updated_gui_window.isMinimized}")
                        else:
                            print("[WARNING] Automoy GUI window lost after minimize attempt.")
                    except Exception as e_pgw_minimize:
                        print(f"[ERROR] Exception during pygetwindow minimize for Automoy GUI: {e_pgw_minimize}")
                elif gui_window.isMinimized:
                    print("[INFO] Automoy GUI already minimized according to pygetwindow.")
                else: # Not visible
                    print("[INFO] Automoy GUI reported as not visible by pygetwindow after API hide call.")
            else:
                print(f"[WARNING] Automoy GUI window not found by pygetwindow for visibility check after API hide (title prefix: '{automoy_gui_title_prefix}').")
            
            print("[INFO] Additional 0.5s wait after all Automoy GUI hide attempts.")
            await asyncio.sleep(0.5)

            # Minimize OmniParser console window
            print(f"[INFO] Attempting to minimize OmniParser Console window (title part: '{omniparser_console_title_part}').")
            all_windows = gw.getAllWindows()
            omniparser_windows = [w for w in all_windows if omniparser_console_title_part in w.title]
            if omniparser_windows:
                op_window = omniparser_windows[0]
                if not op_window.isMinimized:
                    print(f"[INFO] Minimizing OmniParser Console window '{op_window.title}'.")
                    op_window.minimize()
                    await asyncio.sleep(0.3)
                    print(f"[INFO] OmniParser Console window '{op_window.title}' minimize action completed.")
                else:
                    print(f"[INFO] OmniParser Console window '{op_window.title}' already minimized.")
            else:
                print(f"[INFO] OmniParser console window with title part '{omniparser_console_title_part}' not found for minimization.")
            print("[HIDE_GUI_FOR_SCREENSHOT] Completed.")

        async def show_gui_after_screenshot():
            """Shows and configures the Automoy GUI after a screenshot operation."""
            automoy_gui_control_url = "http://127.0.0.1:8000/control/window"
            automoy_gui_title_prefix = "Automoy - Access via"
            print("[SHOW_GUI_AFTER_SCREENSHOT] Starting...")

            print("[INFO] Attempting to show Automoy GUI window via API.")
            try:
                response = requests.post(f"{automoy_gui_control_url}/show", timeout=3)
                if response.status_code == 200:
                    print("[INFO] Automoy GUI show request successful.")
                else:
                    print(f"[WARNING] Automoy GUI show request failed: {response.status_code} - {response.text}")
            except requests.exceptions.RequestException as e:
                print(f"[ERROR] Failed to send show request to Automoy GUI: {e}")
            
            await asyncio.sleep(0.5)

            print(f"[INFO] Configuring Automoy GUI window via pygetwindow (title prefix: '{automoy_gui_title_prefix}').")
            gui_window = None
            for attempt in range(10): 
                await asyncio.sleep(0.2) 
                automoy_windows = [w for w in gw.getWindowsWithTitle(automoy_gui_title_prefix) if w.title.startswith(automoy_gui_title_prefix)]
                if automoy_windows:
                    gui_window = automoy_windows[0]
                    print(f"[INFO] Found Automoy GUI window: '{gui_window.title}' (attempt {attempt + 1}).")
                    break
                else:
                    print(f"[INFO] Automoy GUI window (prefix: '{automoy_gui_title_prefix}') not yet found by pygetwindow. Retrying... (attempt {attempt + 1})")
            
            if gui_window:
                print(f"[INFO] Configuring Automoy GUI window: '{gui_window.title}'. Current state: active={gui_window.isActive}, visible={gui_window.visible}, minimized={gui_window.isMinimized}, pos=({gui_window.left},{gui_window.top}), size=({gui_window.width}x{gui_window.height})")
                
                if gui_window.isMinimized:
                    print("[INFO] Automoy GUI is minimized. Restoring via pygetwindow.")
                    gui_window.restore()
                    await asyncio.sleep(0.3)

                if not gui_window.visible: 
                    print("[INFO] Window not visible after API show/restore, attempting pygetwindow.show()")
                    # Ensure it's not pywebview's native hide
                    try:
                        response = requests.post(f"{automoy_gui_control_url}/show", timeout=2) # Re-send API show
                        if response.status_code == 200: print("[INFO] Re-sent API show request for visibility.")
                    except: pass # Ignore if fails, pygetwindow will try
                    await asyncio.sleep(0.2)
                    gui_window.show() # pygetwindow show
                    await asyncio.sleep(0.2)
                
                print("[INFO] Activating Automoy GUI window.")
                gui_window.activate() 
                await asyncio.sleep(0.2)
                
                print("[INFO] Moving Automoy GUI window to (0,0).")
                gui_window.moveTo(0, 0)
                await asyncio.sleep(0.2)
                
                target_width = 1024
                target_height = 576
                # Re-fetch window object to get latest size before resizing
                current_gui_windows = [w for w in gw.getWindowsWithTitle(automoy_gui_title_prefix) if w.title.startswith(automoy_gui_title_prefix)]
                if current_gui_windows:
                    gui_window = current_gui_windows[0] # Update reference
                    if gui_window.width != target_width or gui_window.height != target_height:
                        print(f"[INFO] Resizing Automoy GUI window from {gui_window.width}x{gui_window.height} to {target_width}x{target_height}.")
                        gui_window.resizeTo(target_width, target_height)
                        await asyncio.sleep(0.2)
                else:
                    print("[WARNING] Automoy GUI window lost before resize attempt.")

                print("[INFO] Re-activating Automoy GUI window after move/resize.")
                gui_window.activate() 
                await asyncio.sleep(0.1)

                final_check_windows = [w for w in gw.getWindowsWithTitle(automoy_gui_title_prefix) if w.title.startswith(automoy_gui_title_prefix)]
                if final_check_windows:
                    final_gui_window = final_check_windows[0]
                    print(f"[INFO] Automoy GUI window FINAL state: active={final_gui_window.isActive}, visible={final_gui_window.visible}, minimized={final_gui_window.isMinimized}, pos=({final_gui_window.left},{final_gui_window.top}), size=({final_gui_window.width}x{final_gui_window.height})")
                else:
                    print("[WARNING] Automoy GUI window not found for final state check after show actions.")
            else:
                print(f"[WARNING] Automoy GUI window with title prefix '{automoy_gui_title_prefix}' not found by pygetwindow for show configuration.")
            print("[SHOW_GUI_AFTER_SCREENSHOT] Completed.")

        async def manage_gui_window(action):
            """Manage the GUI window state using API for Automoy GUI and pygetwindow for OmniParser console."""
            print(f"[MANAGE_GUI_WINDOW] Action: {action}")
            try:
                if action == "hide":
                    await hide_gui_for_screenshot()
                elif action == "show":
                    await show_gui_after_screenshot()
                else:
                    print(f"[WARNING] Unknown action for manage_gui_window: {action}")
            except Exception as e:
                print(f"[ERROR] Exception in manage_gui_window: {e}")
                import traceback
                print(traceback.format_exc())


        # Wait until GUI is up
        asyncio.run(wait_for_objective())

        # Wait for user to type in objective via GUI
        async def wait_for_goal():
            print("[INFO] Waiting for objective input from GUI...")
            while True:
                try:
                    resp = requests.get("http://127.0.0.1:8000/operator_state", timeout=5)
                    if resp.status_code == 200:
                        obj = resp.json().get("objective", "")
                        if obj:
                            print(f"[INFO] Objective received: {obj}")
                            return obj
                except Exception:
                    pass
                time.sleep(1)

        goal = asyncio.run(wait_for_goal())
        
        # --- Pre-Screenshot Preparations ---
        print("[INFO] Preparing for initial screenshot...")
        # asyncio.run(manage_gui_window("hide")) # Hide GUI and OmniParser console
        asyncio.run(hide_gui_for_screenshot()) # Use the new dedicated function

        if cfg.get("DESKTOP_ANCHOR_POINT", False):
            try:
                from core.environmental.anchor.desktop_anchor_point import show_desktop
                print("[ANCHOR] Showing desktop for clean screenshot...")
                show_desktop()
            except Exception as e:
                print(f"[ANCHOR] Failed to show desktop: {e}")

        PRE_SCREENSHOT_DELAY = 1.5  # seconds
        print(f"[INFO] Waiting {PRE_SCREENSHOT_DELAY}s for windows to hide/desktop to settle.")
        time.sleep(PRE_SCREENSHOT_DELAY)

        print("[INFO] Setting black background for screenshot.")
        DesktopUtils.set_desktop_background_solid_color(0, 0, 0)
        time.sleep(0.1) # Brief pause for background to apply

        # Fetch and save processed screenshot from OmniParser
        print("[INFO] Requesting processed screenshot from OmniParser...")
        screenshot_processed_successfully = False
        try:
            resp = requests.get("http://127.0.0.1:8111/processed_screenshot.png", timeout=10)
            if resp.status_code == 200:
                screenshot_source = PROJECT_ROOT / "core" / "utils" / "omniparser" / "processed_screenshot.png"
                with open(screenshot_source, "wb") as f:
                    f.write(resp.content)
                gui_static_dest = PROJECT_ROOT / "gui" / "static" / "processed_screenshot.png"
                shutil.copy2(screenshot_source, gui_static_dest)
                print("[INFO] Saved and copied processed screenshot for GUI display.")
                try:
                    requests.post("http://127.0.0.1:8000/state/screenshot_processed", timeout=5)
                    print("[INFO] Notified GUI about processed screenshot.")
                    screenshot_processed_successfully = True
                except requests.exceptions.RequestException as e:
                    print(f"[WARNING] Failed to notify GUI about processed screenshot: {e}")
            else:
                print(f"[WARNING] Could not fetch processed screenshot: {resp.status_code}")
        except Exception as e:
            print(f"[ERROR] Failed to fetch/save processed screenshot: {e}")
        finally:
            print("[INFO] Restoring desktop background after screenshot attempt.")
            DesktopUtils.restore_desktop_background_settings() # Corrected method name
            print("[INFO] Showing GUI after screenshot attempt.")
            asyncio.run(show_gui_after_screenshot()) # Use the new dedicated function

        if not screenshot_processed_successfully:
            print("[ERROR] Initial screenshot processing failed. Exiting or handling error...")
            # Potentially exit or retry, for now, we'll let it proceed to operate_loop if goal is set
            # but operate_loop might not have a valid screenshot to start with.

        # --- Start the main operation loop ---
        if goal: # Only proceed if a goal was set
            print(f"[INFO] Starting Automoy operation loop with objective: {goal}")
            # Pass the manage_gui_window function (which now calls the new sub-functions)
            operate_loop(objective=goal, omniparser=omniparser, manage_gui_window_func=manage_gui_window)
        else:
            print("[ERROR] No objective received from GUI. Exiting.")

    else:
        print("❌ OmniParser failed to launch. Exiting.")
        sys.exit(1)
