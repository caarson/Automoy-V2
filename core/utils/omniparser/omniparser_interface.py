import os
import sys
import time
import requests
import subprocess
import threading
import pathlib

# --- Helper function to auto-find conda ---
def auto_find_conda():
    """Attempt to locate the conda executable automatically."""
    conda_exe = os.environ.get("CONDA_EXE")
    if conda_exe and os.path.isfile(conda_exe):
        return conda_exe
    try:
        output = subprocess.check_output(["where", "conda"], shell=True, text=True)
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if lines:
            return lines[0]
    except Exception:
        pass
    return None

# --- Compute the project root based on file location ---
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.parent.resolve()

# --- Default paths for OmniParser ---
DEFAULT_SERVER_CWD = str(PROJECT_ROOT / "dependencies" / "OmniParser-master" / "omnitool" / "omniparserserver")
DEFAULT_MODEL_PATH = str(PROJECT_ROOT / "dependencies" / "OmniParser-master" / "weights" / "icon_detect" / "model.pt")
DEFAULT_CAPTION_MODEL_DIR = str(PROJECT_ROOT / "dependencies" / "OmniParser-master" / "weights" / "icon_caption_florence")

class OmniParserInterface:
    def __init__(self, server_url="http://localhost:8111"):
        self.server_url = server_url
        self.server_process = None

    def launch_server(self,
                      conda_path=None,
                      conda_env="automoy_env",
                      omiparser_module="omnitool.omniparserserver.omniparserserver",
                      cwd=None,
                      port=8111,
                      model_path=None,
                      caption_model_dir=None):

        if conda_path is None:
            conda_path = auto_find_conda()
            if not conda_path:
                print("❌ Could not auto-locate conda executable.")
                return False

        if cwd is None:
            cwd = DEFAULT_SERVER_CWD
        if model_path is None:
            model_path = DEFAULT_MODEL_PATH
        if caption_model_dir is None:
            caption_model_dir = DEFAULT_CAPTION_MODEL_DIR

        if not os.path.isdir(cwd):
            print(f"❌ Error: The provided working directory '{cwd}' is invalid or does not exist.")
            return False

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        command = [
            conda_path, "run", "-n", conda_env,
            "python", "-m", omiparser_module,
            "--som_model_path", model_path,
            "--caption_model_name", "florence2",
            "--caption_model_path", caption_model_dir,
            "--device", "cuda",
            "--BOX_TRESHOLD", "0.05",
            "--port", str(port)
        ]

        print(f"🚀 Launching OmniParser server on port {port}...")
        print(f"Using working directory: {cwd}")

        try:
            self.server_process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
        except Exception as e:
            print(f"❌ Failed to launch server process: {e}")
            return False

        def _read_output():
            while True:
                line = self.server_process.stdout.readline()
                if not line and self.server_process.poll() is not None:
                    break
                if line:
                    print("[Server]", line.rstrip())

        threading.Thread(target=_read_output, daemon=True).start()

        timeout_sec = 120
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            if self.server_process.poll() is not None:
                print("❌ OmniParser server exited prematurely!")
                self.server_process = None
                return False
            if self._check_server_ready(port):
                print(f"✅ OmniParser server is ready at http://localhost:{port}")
                return True
            time.sleep(5)

        print("❌ OmniParser server did not become ready within 2 minutes.")
        self.server_process.terminate()
        self.server_process = None
        return False

    def _check_server_ready(self, port=8111):
        try:
            resp = requests.get(f"http://localhost:{port}/probe/", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def stop_server(self):
        if self.server_process and self.server_process.poll() is None:
            print("Stopping OmniParser server...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print("Server did not terminate in time; forcing kill.")
                self.server_process.kill()
            self.server_process = None

    def parse_screenshot(self, image_path):
        url = f"{self.server_url}/parse"
        try:
            with open(image_path, "rb") as f:
                files = {"file": f}
                response = requests.post(url, files=files)
                response.raise_for_status()
                return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ OmniParser request failed: {e}")
            return None

if __name__ == "__main__":
    omniparser = OmniParserInterface()
    launched = omniparser.launch_server(
        conda_path=None,
        conda_env="automoy_env",
        cwd=DEFAULT_SERVER_CWD,
        port=8111,
        model_path=None,
        caption_model_dir=None
    )

    if launched:
        result = omniparser.parse_screenshot("sample_screenshot.png")
        print("🔍 Parsed Data:", result)
        omniparser.stop_server()
    else:
        print("OmniParser server did not launch correctly.")
