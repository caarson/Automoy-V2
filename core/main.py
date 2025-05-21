import os
import sys
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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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
from utils.omniparser.omniparser_interface import OmniParserInterface

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

        async def manage_gui_window(action):
            """Manage the GUI window state (minimize or restore)."""
            try:
                windows = [w for w in gw.getWindowsWithTitle("Automoy") if w.title == "Automoy"]
                if not windows:
                    print("[WARNING] Automoy GUI window not found.")
                    return

                gui_window = windows[0] # Get the current window reference

                if action == "hide":
                    print(f"[INFO] Attempting to hide GUI window '{gui_window.title}'. Initial state: minimized={gui_window.isMinimized}, visible={gui_window.visible}, active={gui_window.isActive}, pos=({gui_window.left},{gui_window.top}))")
                    
                    if not gui_window.isMinimized:
                        print("[INFO] Sending minimize command...")
                        gui_window.minimize()
                        time.sleep(0.3) # Allow time for minimize
                        # Re-check minimized state for logging
                        current_windows_check = gw.getWindowsWithTitle("Automoy")
                        if current_windows_check and len(current_windows_check) > 0:
                             print(f"[INFO] After minimize attempt, state: minimized={current_windows_check[0].isMinimized}")
                        else:
                            print("[WARNING] GUI window not found after minimize attempt for re-check.")
                            # If window is gone, we can't move it.

                    # Always move it off-screen as an additional measure, even if reported as minimized.
                    # This helps if minimize isn't enough or if the window is restored by something.
                    # Ensure window object is still valid if previous check failed to find it.
                    if gw.getWindowsWithTitle("Automoy"): # Check if window still exists before moving
                        print("[INFO] Sending move-off-screen command (-3000, -2000)...")
                        gui_window.moveTo(-3000, -2000) # Use the initially fetched gui_window ref for action
                        time.sleep(1.0) # Increased delay: Allow more time for move to complete visually
                    else:
                        print("[INFO] GUI window was not found before move-off-screen attempt. Skipping move.")

                    print("[INFO] GUI hide actions (minimize + move off-screen) completed.")

                elif action == "show":
                    print(f"[INFO] Attempting to show GUI window '{gui_window.title}'. Initial state: minimized={gui_window.isMinimized}, visible={gui_window.visible}, pos=({gui_window.left},{gui_window.top}))")

                    if gui_window.isMinimized:
                        print("[INFO] Window is minimized, sending restore command...")
                        gui_window.restore()
                        time.sleep(0.3) # Allow time for restore

                    print("[INFO] Sending move-to-(0,0) command...")
                    gui_window.moveTo(0, 0)
                    time.sleep(0.2) # Allow time for move

                    current_windows_after_move = gw.getWindowsWithTitle("Automoy")
                    if not current_windows_after_move:
                        print("[WARNING] Automoy GUI window lost after move/restore.")
                        return
                    
                    active_gui_window = current_windows_after_move[0]

                    print(f"[INFO] After move/restore, GUI at ({active_gui_window.left},{active_gui_window.top}), minimized={active_gui_window.isMinimized}")

                    if not active_gui_window.isMinimized and active_gui_window.left == 0 and active_gui_window.top == 0:
                        print(f"[INFO] Clicking at screen coordinates (10,10) to activate GUI window.")
                        pyautogui.click(10, 10)
                        time.sleep(0.3)

                        active_win_after_click = gw.getActiveWindow()
                        if active_win_after_click and active_win_after_click.title == "Automoy":
                            print("[INFO] GUI window appears to be active after click.")
                        else:
                            current_active_title = active_win_after_click.title if active_win_after_click else "None"
                            print(f"[WARNING] GUI window may not be active after click. Current active: {current_active_title}")
                    elif active_gui_window.isMinimized:
                        print("[WARNING] GUI window is minimized after show attempt, cannot click.")
                    else:
                        print(f"[WARNING] GUI window not at (0,0) after moveTo (is at {active_gui_window.left},{active_gui_window.top}). Skipping click.")
                    
                    print("[INFO] GUI window show process finished.")
            
            except Exception as e:
                print(f"[ERROR] Failed to manage GUI window: {e}")

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
        # Minimize GUI just before taking screenshot
        asyncio.run(manage_gui_window("hide"))

        # Anchor to desktop before screenshot for clean background (conditional on config)
        if cfg.get("DESKTOP_ANCHOR_POINT", False):
            try:
                from core.environmental.anchor.desktop_anchor_point import show_desktop
                print("[ANCHOR] Showing desktop for clean screenshot...")
                show_desktop()
                # time.sleep(1)  # REMOVED: allow desktop to render - This will be handled by a consolidated delay
            except Exception as e:
                print(f"[ANCHOR] Failed to show desktop: {e}")

        # Consolidated delay to ensure GUI is hidden and desktop is settled
        PRE_SCREENSHOT_DELAY = 1.5  # seconds
        print(f"[INFO] Waiting {PRE_SCREENSHOT_DELAY}s before screenshot to ensure GUI is hidden and desktop settled.")
        time.sleep(PRE_SCREENSHOT_DELAY)

        # Fetch and save processed screenshot from OmniParser
        # GUI is already hidden; ensure it gets restored afterward
        print("[INFO] Requesting processed screenshot from OmniParser...")
        try:
            resp = requests.get("http://127.0.0.1:8111/processed_screenshot.png", timeout=10)
            if resp.status_code == 200:
                screenshot_source = PROJECT_ROOT / "core" / "utils" / "omniparser" / "processed_screenshot.png"
                with open(screenshot_source, "wb") as f:
                    f.write(resp.content)
                # Copy into GUI static folder for display
                gui_static_dest = PROJECT_ROOT / "gui" / "static" / "processed_screenshot.png"
                shutil.copy2(screenshot_source, gui_static_dest)
                print("[INFO] Saved and copied processed screenshot for GUI display.")
            else:
                print(f"[WARNING] Could not fetch processed screenshot: {resp.status_code}")
        except Exception as e:
            print(f"[ERROR] Fetch processed screenshot failed: {e}")
        finally:
            # Restore only the PyWebView GUI window after screenshot
            asyncio.run(manage_gui_window("show"))

        # Continue with operation loop
        asyncio.run(operate_loop(objective=args.objective))
    else:
        print("❌ OmniParser server failed to launch.")
