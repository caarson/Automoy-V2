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
                windows = gw.getWindowsWithTitle("Automoy GUI")
                if windows:
                    gui_window = windows[0]
                    if action == "hide":
                        gui_window.minimize()
                        print("[INFO] GUI window minimized for screenshot.")
                    elif action == "show":
                        gui_window.restore()
                        gui_window.moveTo(0, 0)
                        print("[INFO] GUI window restored at top-left.")
            except Exception as e:
                print(f"[ERROR] Failed to manage GUI window: {e}")

        asyncio.run(wait_for_objective())
        asyncio.run(manage_gui_window("hide"))

        # Fetch and save processed screenshot from OmniParser
        try:
            resp = requests.get("http://127.0.0.1:8111/processed_screenshot.png", timeout=10)
            if resp.status_code == 200:
                screenshot_source = PROJECT_ROOT / "core" / "utils" / "omniparser" / "processed_screenshot.png"
                with open(screenshot_source, "wb") as f:
                    f.write(resp.content)
                # Also copy to GUI static directory for serving as static resource
                gui_static_dest = PROJECT_ROOT / "gui" / "static" / "processed_screenshot.png"
                shutil.copy2(screenshot_source, gui_static_dest)
                print("[INFO] Saved and copied processed screenshot for GUI display.")
            else:
                print(f"[WARNING] Could not fetch processed screenshot: {resp.status_code}")
        except Exception as e:
            print(f"[ERROR] Fetch processed screenshot failed: {e}")

        asyncio.run(manage_gui_window("show"))
        asyncio.run(operate_loop(objective=args.objective))
    else:
        print("❌ OmniParser server failed to launch.")
