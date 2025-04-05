import os
import sys
import time
import requests
import subprocess
import threading

class OmniParserInterface:
    def __init__(self, server_url="http://localhost:8111"):
        """Initialize the OmniParser client interface."""
        self.server_url = server_url
        self.server_process = None  # We'll store the Popen handle here

    def launch_server(
        self,
        conda_path=r"C:\Users\YourName\Anaconda3\condabin\conda.bat",
        conda_env="automoy_env",
        omiparser_module="omnitool.omniparserserver.omniparserserver",
        cwd=r"C:\path\to\OmniParser-master\omnitool\omniparserserver",
        port=8111,
        model_path=r"C:\path\to\OmniParser-master\weights\icon_detect\model.pt",
        caption_model_dir=r"C:\path\to\OmniParser-master\weights\icon_caption_florence"
    ):
        """
        Launch the OmniParser server in a background process.

        :param conda_path: Path to conda.bat or conda.exe
        :param conda_env: Name of the Conda environment to run in
        :param omiparser_module: Python module for the OmniParser server
        :param cwd: Working directory (omnitool/omniparserserver)
        :param port: Which port to bind on localhost
        :param model_path: YOLO model path (icon_detect/model.pt)
        :param caption_model_dir: Path to the icon_caption_florence folder
        """
        # Prepare environment variables
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        # Add the OmniParser folder to PYTHONPATH if needed:
        # env["PYTHONPATH"] = r"C:\path\to\OmniParser-master"

        # Build the command
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

        # Start the server
        self.server_process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Optional: Real-time output from the server
        def _read_output():
            while True:
                line = self.server_process.stdout.readline()
                if not line and self.server_process.poll() is not None:
                    break
                if line:
                    print("[Server]", line.rstrip())
        threading.Thread(target=_read_output, daemon=True).start()

        # Wait up to 2 minutes for the server to come online
        timeout_sec = 120
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            if self.server_process.poll() is not None:
                # The server process died prematurely
                print("❌ OmniParser server exited before it was ready.")
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
        """Check if the server /probe/ endpoint returns 200 OK."""
        try:
            resp = requests.get(f"http://localhost:{port}/probe/", timeout=3)
            return resp.status_code == 200
        except:
            return False

    def stop_server(self):
        """Terminate the OmniParser server process if it's running."""
        if self.server_process and self.server_process.poll() is None:
            print("Stopping OmniParser server...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print("Forcing kill on server process...")
                self.server_process.kill()
            self.server_process = None

    def parse_screenshot(self, image_path):
        """
        Sends an image to the OmniParser server for analysis.

        :param image_path: Path to the image file
        :return: Parsed response from the server (dict) or None on error
        """
        url = f"{self.server_url}/parse"
        files = {"file": open(image_path, "rb")}
        
        try:
            response = requests.post(url, files=files)
            response.raise_for_status()  # Raise error for non-2xx responses
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ OmniParser request failed: {e}")
            return None


# Example usage
if __name__ == "__main__":
    # 1) Initialize
    omniparser = OmniParserInterface()

    # 2) Launch the server (sample paths -- update for your environment)
    launched = omniparser.launch_server(
        conda_path=r"C:\Users\YourName\Anaconda3\condabin\conda.bat",
        conda_env="automoy_env",
        cwd=r"C:\path\to\OmniParser-master\omnitool\omniparserserver",
        port=8111,
        model_path=r"C:\path\to\OmniParser-master\weights\icon_detect\model.pt",
        caption_model_dir=r"C:\path\to\OmniParser-master\weights\icon_caption_florence"
    )

    if launched:
        # 3) Send a test image
        result = omniparser.parse_screenshot("sample_screenshot.png")
        print("🔍 Parsed Data:", result)

        # 4) Optionally stop the server
        omniparser.stop_server()
    else:
        print("OmniParser server did not launch correctly.")
