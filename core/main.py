import os
import sys
import subprocess
import pathlib
import time
import requests
import threading
import atexit
import signal

REQUIRED_ENV_NAME = "automoy_env"

# --- Helper function to auto-find conda ---
def auto_find_conda():
    import pathlib
    user_home = pathlib.Path.home()
    possible_paths = [
        os.environ.get("CONDA_EXE"),
        user_home / "anaconda3" / "condabin" / "conda.bat",
        user_home / "miniconda3" / "condabin" / "conda.bat",
        user_home / "anaconda3" / "Scripts" / "conda.exe",
        user_home / "miniconda3" / "Scripts" / "conda.exe"
    ]
    for path in possible_paths:
        if path and os.path.isfile(path):
            return str(path)
    return None

# Relaunch if not inside automoy_env
if os.environ.get("CONDA_DEFAULT_ENV") != REQUIRED_ENV_NAME:
    conda_exe = auto_find_conda()
    if not conda_exe:
        print("❌ Could not locate conda executable. Please check your Anaconda installation.")
        sys.exit(1)

    print(f"🔁 Relaunching in conda env: {REQUIRED_ENV_NAME}")
    subprocess.run([
        conda_exe, "run", "-n", REQUIRED_ENV_NAME,
        "python", os.path.abspath(__file__)
    ])
    sys.exit()

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
    conda_path=auto_find_conda(),
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
        asyncio.run(operate_loop())
    else:
        print("❌ OmniParser server failed to launch.")
