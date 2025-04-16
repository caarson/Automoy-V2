import os
import sys
import argparse
import pathlib
import time
import requests
import threading
import atexit
import signal

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
from operate import operate_loop
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
if __name__ == "__main__":
    if launched:
        import asyncio
        print("✅ OmniParser launched. Running Automoy...")
        asyncio.run(operate_loop(objective=args.objective))
    else:
        print("❌ OmniParser server failed to launch.")
