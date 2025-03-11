import os
import sys
import subprocess
import pathlib
import zipfile
import time
import urllib.request

# Import conda_setup.py from the same directory
try:
    import conda_setup
except ImportError:
    print("❌ Could not import conda_setup. Ensure conda_setup.py is in the same directory.")
    sys.exit(1)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Paths
DEPENDENCIES_DIR = pathlib.Path(__file__).parent.parent / "dependencies"
OMNIPARSER_ZIP = DEPENDENCIES_DIR / "OmniParser-master.zip"
OMNIPARSER_DIR = DEPENDENCIES_DIR / "OmniParser-master"

# OmniParser server module path:
# File location: OmniParser-master/omnitool/omniparserserver/omniparserserver.py
OMNIPARSER_MODULE = "omnitool.omniparserserver.omniparserserver"

# We want the working directory (for relative paths) to be:
SERVER_CWD = OMNIPARSER_DIR / "omnitool" / "omniparserserver"

# Model weights folder paths
WEIGHTS_DIR = OMNIPARSER_DIR / "weights"
ICON_DETECT_DIR = WEIGHTS_DIR / "icon_detect"
ICON_CAPTION_DIR = WEIGHTS_DIR / "icon_caption_florence"

# Model weight files (icon_detect)
YOLO_MODEL_FILE = ICON_DETECT_DIR / "model.pt"
TRAIN_ARGS_FILE = ICON_DETECT_DIR / "train_args.yaml"
MODEL_YAML_FILE = ICON_DETECT_DIR / "model.yaml"

# Model weight files (icon_caption_florence)
ICON_CAPTION_FILE = ICON_CAPTION_DIR / "model.safetensors"
ICON_CAPTION_CONFIG = ICON_CAPTION_DIR / "config.json"
ICON_CAPTION_GEN_CONFIG = ICON_CAPTION_DIR / "generation_config.json"

# Conda environment settings
CONDA_ENV = "automoy_env"

# Desired server port
SERVER_PORT = 8111

# Minimal FastAPI server code (only created if the file is missing)
MINIMAL_FASTAPI_SERVER = f'''"""
Minimal OmniParser server using FastAPI.

Exposes /probe/ (health check) and a placeholder /parse/ endpoint.
"""
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/probe/")
def probe():
    return {{"status": "ok"}}

@app.post("/parse/")
def parse_image():
    # Placeholder for parsing logic (e.g., load models, process image)
    return {{"screen_info": "Parsed screen info goes here"}}

if __name__ == "__main__":
    uvicorn.run("{OMNIPARSER_MODULE}:app", host="0.0.0.0", port={SERVER_PORT}, reload=False)
'''

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def extract_omniparser():
    """Extracts OmniParser from the ZIP if not already extracted."""
    if not OMNIPARSER_DIR.exists():
        print(f"📦 Extracting OmniParser from {OMNIPARSER_ZIP}...")
        try:
            with zipfile.ZipFile(OMNIPARSER_ZIP, 'r') as zip_ref:
                zip_ref.extractall(DEPENDENCIES_DIR)
            print("✅ OmniParser extracted successfully!")
        except Exception as e:
            print(f"❌ Error extracting OmniParser: {e}")
            sys.exit(1)
    else:
        print("✅ OmniParser is already extracted.")

def ensure_directory_exists(directory: pathlib.Path):
    """Creates a directory if it doesn't exist."""
    if not directory.exists():
        print(f"📁 Creating missing directory: {directory}")
        directory.mkdir(parents=True, exist_ok=True)

def download_file(url: str, destination: pathlib.Path):
    """Downloads a file from a given URL to the destination."""
    if destination.exists():
        print(f"✅ Already downloaded: {destination}")
        return
    try:
        print(f"📥 Downloading {destination}...")
        urllib.request.urlretrieve(url, destination)
        print(f"✅ Downloaded {destination}")
    except Exception as e:
        print(f"❌ Failed to download {destination}: {e}")
        sys.exit(1)

def download_required_models():
    """Downloads all required model weights and configuration files."""
    print("🔍 Checking for required model weights...")
    ensure_directory_exists(ICON_DETECT_DIR)
    ensure_directory_exists(ICON_CAPTION_DIR)

    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_detect/train_args.yaml", TRAIN_ARGS_FILE)
    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_detect/model.yaml", MODEL_YAML_FILE)
    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_detect/model.pt", YOLO_MODEL_FILE)

    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_caption/model.safetensors", ICON_CAPTION_FILE)
    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_caption/config.json", ICON_CAPTION_CONFIG)
    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_caption/generation_config.json", ICON_CAPTION_GEN_CONFIG)

def ensure_omniparser_server_file():
    """
    Ensures that the OmniParser server file exists at:
      OmniParser-master/omnitool/omniparserserver/omniparserserver.py
    If missing, creates the folder (and an empty __init__.py) and writes minimal server code.
    """
    server_dir = OMNIPARSER_DIR / "omnitool" / "omniparserserver"
    init_file = server_dir / "__init__.py"
    server_py = server_dir / "omniparserserver.py"

    if not server_dir.exists():
        print(f"📂 Creating folder {server_dir} for the OmniParser server.")
        server_dir.mkdir(parents=True, exist_ok=True)

    if not init_file.exists():
        print(f"📄 Creating empty {init_file}")
        init_file.write_text("", encoding="utf-8")

    if not server_py.exists():
        print(f"📄 Creating {server_py} with minimal server code (port {SERVER_PORT}).")
        server_py.write_text(MINIMAL_FASTAPI_SERVER, encoding="utf-8")
    else:
        print(f"✅ {server_py} already exists; not overwriting.")

def validate_server_module():
    """
    Validates that the server module can be imported by running a simple import test.
    The working directory is set to SERVER_CWD so that relative paths resolve correctly.
    """
    print(f"🔎 Validating server module: {OMNIPARSER_MODULE}")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(OMNIPARSER_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    
    conda_exe = conda_setup.find_conda()
    if not conda_exe:
        print("❌ Could not find Conda. Aborting.")
        sys.exit(1)

    try:
        result = subprocess.run(
            [
                conda_exe, "run", "-n", CONDA_ENV,
                "python", "-c", f"import {OMNIPARSER_MODULE}"
            ],
            env=env,
            cwd=str(SERVER_CWD),
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print("❌ Server module validation failed")
            print("--- stdout ---\n", result.stdout)
            print("--- stderr ---\n", result.stderr)
            sys.exit(1)
        print("✅ Server module is valid")
    except Exception as e:
        print(f"❌ Validation error: {e}")
        sys.exit(1)

def start_omniparser_server():
    """Starts the OmniParser server on port 8111 (SERVER_PORT) with logging."""
    print("🚀 Starting OmniParser server...")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(OMNIPARSER_DIR)
    env["PYTHONUNBUFFERED"] = "1"

    conda_exe = conda_setup.find_conda()
    if not conda_exe:
        print("❌ Could not find Conda. Aborting.")
        sys.exit(1)

    try:
        server_process = subprocess.Popen(
            [
                conda_exe, "run", "-n", CONDA_ENV,
                "python", "-m", OMNIPARSER_MODULE,
                "--som_model_path", str(YOLO_MODEL_FILE),
                "--caption_model_name", "florence2",
                "--caption_model_path", str(ICON_CAPTION_DIR),
                "--device", "cuda",
                "--BOX_TRESHOLD", "0.05",
                "--port", str(SERVER_PORT)
            ],
            cwd=str(SERVER_CWD),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Start a thread to print the server's stdout in real time
        import threading
        def output_reader():
            while True:
                line = server_process.stdout.readline()
                if not line and server_process.poll() is not None:
                    break
                if line:
                    print("[Server] " + line.strip())
        threading.Thread(target=output_reader, daemon=True).start()

        print(f"⏳ Waiting for server startup (up to 2 minutes) on port {SERVER_PORT}...")
        start_time = time.time()
        while time.time() - start_time < 120:
            if server_process.poll() is not None:
                print("❌ Server process exited prematurely!")
                sys.exit(1)
            if check_server_status():
                print(f"✅ Server started successfully on port {SERVER_PORT}! (Took {int(time.time()-start_time)}s)")
                print(f"🔗 API available at http://localhost:{SERVER_PORT}")
                return
            time.sleep(5)

        print("❌ Server failed to start within timeout.")
        server_process.terminate()
        sys.exit(1)

    except Exception as e:
        print(f"❌ Server startup failed: {e}")
        sys.exit(1)

def check_server_status() -> bool:
    """Checks the health endpoint at http://localhost:8111/probe/."""
    try:
        import requests
        response = requests.get(f"http://localhost:{SERVER_PORT}/probe/", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("\n🔧 OmniParser Setup Utility 🔧\n")

    # 2) Extract OmniParser if needed
    extract_omniparser()

    # 3) Ensure the server file exists in omnitool/omniparserserver/
    ensure_omniparser_server_file()

    # 4) Download model weights
    download_required_models()

    # 5) Validate the server module (by attempting to import it)
    validate_server_module()

    # 6) Start the OmniParser server on port 8111
    start_omniparser_server()
    
    print("\n✅ Setup completed successfully!\n")
