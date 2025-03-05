import os
import subprocess
import sys
import platform

CONDA_ENV_NAME = "automoy-v2"

def create_conda_env():
    """Creates a new Conda environment for Automoy-V2."""
    print(f"🛠️ Creating Conda environment: {CONDA_ENV_NAME}...")

    try:
        subprocess.run(["conda", "create", "-n", CONDA_ENV_NAME, "python=3.12", "-y"], check=True)
        print(f"✅ Conda environment '{CONDA_ENV_NAME}' created successfully!")
    except subprocess.CalledProcessError:
        print("❌ Failed to create Conda environment. Ensure Conda is installed.")
        sys.exit(1)

def activate_and_run():
    """Activates Conda environment and runs the full setup."""
    system = platform.system()

    if system == "Windows":
        activate_command = f"conda activate {CONDA_ENV_NAME} && python installer/conda_setup.py"
        subprocess.run(["cmd", "/c", activate_command], shell=True)
    else:
        activate_command = f"source activate {CONDA_ENV_NAME} && python installer/conda_setup.py"
        subprocess.run(["bash", "-c", activate_command], shell=True)

if __name__ == "__main__":
    print("🚀 Starting Automoy-V2 Installation...")
    
    create_conda_env()
    activate_and_run()
    
    print("✅ Automoy-V2 Setup Complete!")
