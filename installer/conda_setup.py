import sys
import pathlib
import os
import subprocess
import platform

sys.path.append(str(pathlib.Path(__file__).parent.parent / "evaluations"))
import check_cuda

# Define the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Define installer directory
installer_dir = os.path.join(project_root, "installer", "downloads")
os.makedirs(installer_dir, exist_ok=True)

# Path to aria2c executable (assumed to be in the same directory as this script)
aria2c_path = os.path.join(os.path.dirname(__file__), "aria2c.exe")

# Possible locations for Conda
CONDA_PATHS = [
    os.path.join(os.environ.get("PROGRAMFILES", ""), "Anaconda3", "condabin", "conda.bat"),
    os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Anaconda3", "condabin", "conda.bat"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Anaconda3", "condabin", "conda.bat"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Continuum", "anaconda3", "condabin", "conda.bat"),
    os.path.join(os.environ.get("USERPROFILE", ""), "miniconda3", "condabin", "conda.bat")
]

ANACONDA_URL = "https://repo.anaconda.com/archive/Anaconda3-2024.06-1-Windows-x86_64.exe"

def find_conda():
    """Find the Conda executable."""
    for path in CONDA_PATHS:
        if os.path.exists(path):
            return path
    return None

def is_conda_installed():
    """Check if Conda is installed by looking for the executable."""
    return find_conda() is not None

def install_anaconda():
    """Download and launch the Anaconda installer for the user to install manually."""
    if is_conda_installed():
        print("✅ Anaconda is already installed.")
        return

    print("🔍 Anaconda not found. Installing full Anaconda...")
    installer_path = os.path.join(installer_dir, "Anaconda3-2024.02-1-Windows-x86_64.exe")

    if not os.path.exists(installer_path):
        print("🌍 Downloading Anaconda installer using aria2c...")
        subprocess.run([aria2c_path, "-x", "16", "-s", "16", "-j", "16", "-d", installer_dir, "-o", "Anaconda3-2024.02-1-Windows-x86_64.exe", ANACONDA_URL], check=True)
    
    print("🛠️ Launching Anaconda installer... Follow the setup instructions.")
    subprocess.run([installer_path], check=True)

    print("✅ Anaconda installation complete! Please restart your terminal if needed.")

def create_conda_env(env_name="automoy_env"):
    """Create a new Conda environment for Automoy-V2."""
    conda_exe = find_conda()
    if not conda_exe:
        print("❌ Conda executable not found. Aborting.")
        return
    
    print(f"🔧 Creating Conda environment: {env_name}...")
    subprocess.run([conda_exe, "create", "--name", env_name, "python=3.12", "-y"], check=True)
    print(f"✅ Conda environment {env_name} created successfully!")

def install_pytorch(env_name="automoy_env"):
    """Install PyTorch with the correct CUDA version in the Conda environment."""
    conda_exe = find_conda()
    if not conda_exe:
        print("❌ Conda executable not found. Aborting.")
        return
    
    print("🔍 Checking CUDA installation...")
    cuda_version = check_cuda.get_installed_cuda_version()
    
    print(f"📦 Installing PyTorch in Conda environment {env_name}...")
    if cuda_version:
        pytorch_command = [
            conda_exe, "install", "-n", env_name, "-c", "pytorch", "torch", "torchvision", "torchaudio",
            f"pytorch-cuda={cuda_version}", "-y"
        ]
    else:
        print("⚠️ No supported CUDA detected, installing PyTorch CPU version...")
        pytorch_command = [conda_exe, "install", "-n", env_name, "-c", "pytorch", "torch", "torchvision", "torchaudio", "cpuonly", "-y"]
    subprocess.run(pytorch_command, check=True)

def install_requirements(env_name="automoy_env"):
    """Install all dependencies in requirements.txt using Conda."""
    conda_exe = find_conda()
    if not conda_exe:
        print("❌ Conda executable not found. Aborting.")
        return
    
    print(f"📄 Installing dependencies from requirements.txt in Conda environment {env_name}...")
    subprocess.run([conda_exe, "run", "-n", env_name, "pip", "install", "-r", "installer/requirements.txt"], check=True)

def install_anaconda_navigator():
    """Ensure Anaconda Navigator is installed."""
    conda_exe = find_conda()
    if not conda_exe:
        print("❌ Conda executable not found. Aborting.")
        return
    
    print("📦 Installing Anaconda Navigator...")
    subprocess.run([conda_exe, "install", "-y", "anaconda-navigator"], check=True)
    print("✅ Anaconda Navigator installation complete!")

def main():
    print("🚀 Automoy-V2 Conda Installer Starting...")
    
    install_anaconda()
    
    env_name = "automoy_env"
    create_conda_env(env_name)
    install_pytorch(env_name)
    install_requirements(env_name)
    install_anaconda_navigator()
    
    print(f"✅ Installation Complete! Activate your environment with: conda activate {env_name}")

if __name__ == "__main__":
    main()
