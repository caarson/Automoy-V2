import sys
import os
import time
import asyncio
import json
import pathlib
from operate import operate_loop

sys.path.append(str(pathlib.Path(__file__).parent.parent / "evaluations"))
import check_cuda
import check_pytorch

sys.path.append(str(pathlib.Path(__file__).parent.parent / "gui"))
import gui

# Load configuration
config = Config()

def main():
    """
    Entry point for Automoy.
    - Launches the GUI for user interaction.
    - Handles LLM interaction for autonomous operations.
    """
    print("Starting Automoy...")
    
    # Step 1: Check CUDA availability
    if not check_pytorch.check_pytorch():
        print("PyTorch does not have CUDA acceleration!")
        sys.exit(1)
    print("PyTorch is successfully initialized and CUDA acceleration enabled! \nStartup...")
    
    # Step 2: Start GUI
    gui.start_gui()
    
    # Step 3: Start autonomous operation loop
    asyncio.run(operate_loop())

if __name__ == "__main__":
    main()
