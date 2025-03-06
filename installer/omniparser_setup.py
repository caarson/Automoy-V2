import os
import sys
import subprocess
import pathlib
import zipfile
import time

# Define paths
DEPENDENCIES_DIR = pathlib.Path(__file__).parent.parent / "dependencies"
OMNIPARSER_ZIP = DEPENDENCIES_DIR / "OmniParser-master.zip"
OMNIPARSER_DIR = DEPENDENCIES_DIR / "OmniParser-master"

# OmniParser server module (use `-m` to run)
OMNIPARSER_MODULE = "omnitool.omniparserserver.omniparserserver"

# Required model weights (ensure they're downloaded)
WEIGHTS_DIR = OMNIPARSER_DIR / "weights"
ICON_DETECT_MODEL = WEIGHTS_DIR / "icon_detect/model.pt"
ICON_CAPTION_MODEL = WEIGHTS_DIR / "icon_caption_florence"

# Conda environment settings
CONDA_ENV = "automoy_env"
CONDA_EXE = r"C:\Users\imitr\anaconda3\Scripts\conda.exe"  # Adjust if needed

def extract_omniparser():
    """Extracts OmniParser if it's still in a ZIP file."""
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

def install_dependencies():
    """Installs necessary dependencies for OmniParser inside Conda."""
    requirements_path = OMNIPARSER_DIR / "requirements.txt"
    if requirements_path.exists():
        print(f"📦 Installing dependencies inside Conda environment: {CONDA_ENV}...")
        try:
            result = subprocess.run(
                [CONDA_EXE, "run", "-n", CONDA_ENV, "python", "-m", "pip", "install", "-r", str(requirements_path)],
                capture_output=True, text=True, check=True
            )
            print("✅ Dependencies installed successfully in Conda environment!")
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            print(e.stderr)
            sys.exit(1)
    else:
        print("⚠️ No requirements.txt found, skipping dependency installation.")

def start_omniparser_server():
    """Starts the OmniParser server inside Conda."""
    print("🚀 Starting OmniParser server inside Conda...")

    try:
        server_process = subprocess.Popen(
            [
                CONDA_EXE, "run", "-n", CONDA_ENV, "python", "-m", OMNIPARSER_MODULE,
                "--som_model_path", str(ICON_DETECT_MODEL),
                "--caption_model_name", "florence2",
                "--caption_model_path", str(ICON_CAPTION_MODEL),
                "--device", "cuda",
                "--BOX_TRESHOLD", "0.05"
            ],
            cwd=OMNIPARSER_DIR,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        # Wait for server to start
        time.sleep(5)

        # Check if server is running
        server_running = check_server_status()
        if server_running:
            print("✅ OmniParser server started successfully!")
        else:
            print("❌ OmniParser server failed to start. Check logs below:")
            stdout, stderr = server_process.communicate()
            print(stdout)
            print(stderr)
            sys.exit(1)

    except Exception as e:
        print(f"❌ Error starting OmniParser server: {e}")
        sys.exit(1)

def check_server_status():
    """Check if the server is running on port 8000."""
    try:
        import requests
        response = requests.get("http://localhost:8000/probe/")
        return response.status_code == 200
    except:
        return False

if __name__ == "__main__":
    print("🔧 Setting up OmniParser...")

    # Step 1: Extract OmniParser if needed
    extract_omniparser()

    # Step 2: Install dependencies inside Conda
    install_dependencies()

    # Step 3: Start the OmniParser server
    start_omniparser_server()

    print("✅ OmniParser setup complete!")
