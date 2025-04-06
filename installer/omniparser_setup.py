import os
import sys
import subprocess
import pathlib
import zipfile
import time
import urllib.request
import signal

# Import conda_setup.py from the same directory
try:
    import conda_setup
except ImportError:
    print("❌ Could not import conda_setup. Ensure conda_setup.py is in the same directory.")
    sys.exit(1)

# =============================================================================
# CONFIGURATION
# =============================================================================

DEPENDENCIES_DIR = pathlib.Path(__file__).parent.parent / "dependencies"
OMNIPARSER_ZIP = DEPENDENCIES_DIR / "OmniParser-master.zip"
OMNIPARSER_DIR = DEPENDENCIES_DIR / "OmniParser-master"

OMNIPARSER_MODULE = "omnitool.omniparserserver.omniparserserver"
SERVER_CWD = OMNIPARSER_DIR / "omnitool" / "omniparserserver"

WEIGHTS_DIR = OMNIPARSER_DIR / "weights"
ICON_DETECT_DIR = WEIGHTS_DIR / "icon_detect"
ICON_CAPTION_DIR = WEIGHTS_DIR / "icon_caption_florence"

YOLO_MODEL_FILE = ICON_DETECT_DIR / "model.pt"
TRAIN_ARGS_FILE = ICON_DETECT_DIR / "train_args.yaml"
MODEL_YAML_FILE = ICON_DETECT_DIR / "model.yaml"

ICON_CAPTION_FILE = ICON_CAPTION_DIR / "model.safetensors"
ICON_CAPTION_CONFIG = ICON_CAPTION_DIR / "config.json"
ICON_CAPTION_GEN_CONFIG = ICON_CAPTION_DIR / "generation_config.json"

CONDA_ENV = "automoy_env"
SERVER_PORT = 8111

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

def ensure_omniparser_server_file():
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

def download_required_models():
    print("🔍 Checking for required model weights...")
    for d in [ICON_DETECT_DIR, ICON_CAPTION_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_detect/train_args.yaml", TRAIN_ARGS_FILE)
    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_detect/model.yaml", MODEL_YAML_FILE)
    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_detect/model.pt", YOLO_MODEL_FILE)

    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_caption/model.safetensors", ICON_CAPTION_FILE)
    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_caption/config.json", ICON_CAPTION_CONFIG)
    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_caption/generation_config.json", ICON_CAPTION_GEN_CONFIG)

def download_file(url: str, destination: pathlib.Path):
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

def validate_server_module():
    print(f"🔎 Validating server module: {OMNIPARSER_MODULE}")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(OMNIPARSER_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    conda_exe = conda_setup.find_conda()
    if not conda_exe:
        print("❌ Could not find Conda. Aborting.")
        sys.exit(1)

    try:
        result = subprocess.run([
            conda_exe, "run", "-n", CONDA_ENV,
            "python", "-c", f"import {OMNIPARSER_MODULE}"
        ], env=env, cwd=str(SERVER_CWD), capture_output=True, text=True)

        if result.returncode != 0:
            print("❌ Server module validation failed")
            print("--- stdout ---\n", result.stdout)
            print("--- stderr ---\n", result.stderr)
            sys.exit(1)
        print("✅ Server module is valid")
    except Exception as e:
        print(f"❌ Validation error: {e}")
        sys.exit(1)

def check_server_status() -> bool:
    try:
        import requests
        response = requests.get(f"http://localhost:{SERVER_PORT}/probe/", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

def start_omniparser_server():
    print("🚀 Starting OmniParser server...")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(OMNIPARSER_DIR)
    env["PYTHONUNBUFFERED"] = "1"

    conda_exe = conda_setup.find_conda()
    if not conda_exe:
        print("❌ Could not find Conda. Aborting.")
        sys.exit(1)

    try:
        command = [
            conda_exe, "run", "-n", CONDA_ENV,
            "python", "-m", OMNIPARSER_MODULE,
            "--som_model_path", str(YOLO_MODEL_FILE),
            "--caption_model_name", "florence2",
            "--caption_model_path", str(ICON_CAPTION_DIR),
            "--device", "cuda",
            "--BOX_TRESHOLD", "0.05",
            "--port", str(SERVER_PORT)
        ]

        print(f"⏳ Launching server on port {SERVER_PORT}...")
        server_process = subprocess.Popen(
            command, cwd=str(SERVER_CWD), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )

        # Setup a thread to print server output as it happens
        import threading
        def output_reader():
            while True:
                line = server_process.stdout.readline()
                if not line and server_process.poll() is not None:
                    break
                if line:
                    print("[Server] " + line.rstrip())

        thread = threading.Thread(target=output_reader, daemon=True)
        thread.start()

        # Wait up to 2 minutes for /probe/ to respond
        start_time = time.time()
        while time.time() - start_time < 120:
            if server_process.poll() is not None:
                print("❌ Server process exited prematurely!")
                sys.exit(1)
            if check_server_status():
                took = time.time() - start_time
                print(f"✅ Server started successfully on port {SERVER_PORT} (in ~{int(took)}s).")
                print(f"🔗 API available at http://localhost:{SERVER_PORT}\n")
                return server_process
            time.sleep(5)

        print("❌ Server failed to start within timeout.")
        server_process.terminate()
        sys.exit(1)

    except Exception as e:
        print(f"❌ Server startup failed: {e}")
        sys.exit(1)

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("\n🔧 OmniParser Setup Utility 🔧\n")

    extract_omniparser()
    ensure_omniparser_server_file()
    download_required_models()
    validate_server_module()

    server_process = start_omniparser_server()
    if not server_process:
        sys.exit(1)

    print("OmniParser server is running.\n")
    print("Press ENTER to stop the server and allow folder cleanup, or Ctrl+C to cancel.\n")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected, stopping server...")

    print("Terminating OmniParser server process...")
    server_process.terminate()
    # Wait up to 10 seconds for it to die
    try:
        server_process.wait(10)
    except subprocess.TimeoutExpired:
        print("Server did not stop in time; forcing kill.")
        server_process.kill()

    print("✅ Server stopped. Now you can safely delete the OmniParser folder if desired (only applicable for debug! DO NOT DELETE UNLESS YOU WISH TO RECOMPILE YOUR OMNIPARSER MODULE).")
    print("Setup completed successfully!")
    sys.exit(0)
