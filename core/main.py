import sys
import os
import time
import asyncio
import json
import pathlib

from operate import operate_loop

# Add these lines to import your PyTorch check and GUI
sys.path.append(str(pathlib.Path(__file__).parent.parent / "evaluations"))
import check_pytorch

sys.path.append(str(pathlib.Path(__file__).parent.parent / "gui"))
import gui

# Add this import for OmniParserInterface
from omniparser_interface import OmniParserInterface

# If you have a Config class (not shown in snippet):
# config = Config()

def main():
    """
    Entry point for Automoy.
    - Checks CUDA / PyTorch
    - Launches OmniParser server
    - Starts the GUI
    - Runs the asynchronous 'operate_loop'
    """
    print("Starting Automoy...")

    # Step 1: Check CUDA availability
    if not check_pytorch.check_pytorch():
        print("CRITICAL HALT: PyTorch does not have CUDA acceleration!")
        sys.exit(1)
    print("PyTorch is successfully initialized and CUDA acceleration enabled!\nStartup...")

    # Step 2: Launch OmniParser server (optional if your system needs it)
    omni = OmniParserInterface(server_url="http://localhost:8111")

    launched = omni.launch_server(
        conda_path=r"C:\Users\YourName\Anaconda3\condabin\conda.bat",  # Adjust path
        conda_env="automoy_env",
        cwd=r"C:\path\to\OmniParser-master\omnitool\omniparserserver",  # Adjust path
        port=8111,
        model_path=r"C:\path\to\OmniParser-master\weights\icon_detect\model.pt",
        caption_model_dir=r"C:\path\to\OmniParser-master\weights\icon_caption_florence"
    )
    if not launched:
        print("OmniParser server failed to launch. Exiting.")
        sys.exit(1)

    # Step 3: Start GUI
    gui.start_gui()

    # Step 4: Start autonomous operation loop
    asyncio.run(operate_loop())

    # (Optionally) Stop the OmniParser server on shutdown
    # omni.stop_server()

if __name__ == "__main__":
    main()
