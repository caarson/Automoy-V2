import sys
import pathlib
import os
import subprocess
import platform
import importlib.util

# Dynamically load evaluations/check_cuda.py as module 'check_cuda'
script_dir = pathlib.Path(__file__).parent.resolve()
eval_file = script_dir.parent / "evaluations" / "check_cuda.py"
spec = importlib.util.spec_from_file_location("check_cuda", str(eval_file))
check_cuda = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_cuda)

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

def is_env_created(env_name):
    """Check if the Conda environment exists."""
    conda_exe = find_conda()
    if not conda_exe:
        return False
    # Again we use a list for subprocess => safe if path has spaces
    result = subprocess.run([conda_exe, "env", "list"], capture_output=True, text=True)
    return env_name in result.stdout

def install_anaconda():
    """Download and launch the Anaconda installer for the user to install manually."""
    if is_conda_installed():
        print("✅ Anaconda is already installed.")
        return

    print("🔍 Anaconda not found. Installing full Anaconda...")
    installer_path = os.path.join(installer_dir, "Anaconda3-2024.02-1-Windows-x86_64.exe")

    if not os.path.exists(installer_path):
        print("🌍 Downloading Anaconda installer using aria2c...")
        # If aria2c_path has spaces, this is safe because we pass a list with shell=False
        subprocess.run([aria2c_path, "-x", "16", "-s", "16", "-j", "16",
                        "-d", installer_dir,
                        "-o", "Anaconda3-2024.02-1-Windows-x86_64.exe",
                        ANACONDA_URL], check=True)
    
    print("🛠️ Launching Anaconda installer... Follow the setup instructions.")
    # If the installer path has spaces, this is still safe because we pass a list with shell=False
    subprocess.run([installer_path], check=True)
    print("✅ Anaconda installation complete! Please restart your terminal if needed.")

def create_conda_env(env_name="automoy_env"):
    """Create a new Conda environment if it does not already exist."""
    conda_exe = find_conda()
    if not conda_exe:
        print("❌ Conda executable not found. Aborting.")
        return
    
    if is_env_created(env_name):
        print(f"✅ Conda environment {env_name} already exists.")
        return

    print(f"🔧 Creating Conda environment: {env_name}...")
    subprocess.run([conda_exe, "create", "--name", env_name, "python=3.12", "-y"], check=True)
    print(f"✅ Conda environment {env_name} created successfully!")

def install_pytorch(env_name="automoy_env"):
    """Install PyTorch with the correct CUDA version in the Conda environment using pip."""
    conda_exe = find_conda()
    if not conda_exe:
        print("❌ Conda executable not found. Aborting.")
        return

    print("🔍 Checking CUDA installation...")
    cuda_version = check_cuda.get_installed_cuda_version()
    
    print(f"📦 Installing PyTorch in Conda environment {env_name}...")

    # Determine the correct PyTorch installation command
    if cuda_version:
        # Convert CUDA version to the expected format for PyTorch's pip index (e.g., 11.8 -> cu118)
        cuda_pip_version = f"cu{cuda_version.replace('.', '')}"
        print(f"✅ CUDA {cuda_version} detected, installing PyTorch with {cuda_pip_version} support...")

        pytorch_command = [
            conda_exe, "run", "-n", env_name, "pip", "install",
            "torch", "torchvision", "torchaudio",
            "--index-url", f"https://download.pytorch.org/whl/{cuda_pip_version}",
            "--timeout", "300"  # 5 minute timeout for large downloads
        ]
    else:
        print("⚠️ No supported CUDA detected, installing PyTorch CPU version...")
        pytorch_command = [
            conda_exe, "run", "-n", env_name, "pip", "install",
            "torch", "torchvision", "torchaudio", 
            "--index-url", "https://download.pytorch.org/whl/cpu",
            "--timeout", "300"
        ]
    
    # Try pip installation with retries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"🔄 PyTorch installation attempt {attempt + 1}/{max_retries}...")
            subprocess.run(pytorch_command, check=True, timeout=600)  # 10 minute timeout
            print("✅ PyTorch installation successful!")
            
            # Verify PyTorch installation
            verify_cmd = [
                conda_exe, "run", "-n", env_name, "python", "-c",
                "import torch; print(f'PyTorch {torch.__version__} installed successfully'); print(f'CUDA available: {torch.cuda.is_available()}')"
            ]
            subprocess.run(verify_cmd, check=True)
            return
            
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"❌ PyTorch installation attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                print("⚠️ All pip installation attempts failed. Trying conda fallback...")
                break
            else:
                print("🔄 Retrying in 5 seconds...")
                import time
                time.sleep(5)
    
    # Fallback: use conda install instead
    print("🔄 Attempting conda-based PyTorch installation...")
    try:
        if cuda_version:
            cudatoolkit_pkg = f"cudatoolkit={cuda_version}"
            conda_pkg_cmd = [
                conda_exe, "install", "-n", env_name, "-y", "-c", "pytorch", "-c", "conda-forge",
                "pytorch", "torchvision", "torchaudio", cudatoolkit_pkg
            ]
        else:
            conda_pkg_cmd = [
                conda_exe, "install", "-n", env_name, "-y", "-c", "pytorch", "-c", "conda-forge",
                "pytorch", "torchvision", "torchaudio", "cpuonly"
            ]
        subprocess.run(conda_pkg_cmd, check=True, timeout=600)
        print("✅ PyTorch installation via conda successful!")
        
        # Verify conda installation
        verify_cmd = [
            conda_exe, "run", "-n", env_name, "python", "-c",
            "import torch; print(f'PyTorch {torch.__version__} installed successfully'); print(f'CUDA available: {torch.cuda.is_available()}')"
        ]
        subprocess.run(verify_cmd, check=True)
        
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"❌ Conda PyTorch installation also failed: {e}")
        print("💡 You may need to install PyTorch manually after the setup completes.")
        print("💡 Visit https://pytorch.org/get-started/locally/ for manual installation instructions.")

def install_requirements(env_name="automoy_env"):
    """
    Install dependencies from requirements.txt using Conda, 
    then install packages from force_install.txt if present.
    """
    conda_exe = find_conda()
    if not conda_exe:
        print("❌ Conda executable not found. Aborting.")
        return
    
    print(f"📄 Installing dependencies in Conda environment {env_name}...")

    # Figure out where your requirements.txt is located
    # This example assumes it is in the same folder as this script: 'installer/requirements.txt'
    requirements_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    
    if os.path.isfile(requirements_path):
        print(f"🔎 Found requirements at: {requirements_path}")
        try:
            subprocess.run([
                conda_exe, "run", "-n", env_name, "pip", "install", 
                "-r", requirements_path, "--timeout", "300"
            ], check=True, timeout=900)  # 15 minute timeout for all packages
            print("✅ Requirements installation successful!")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"⚠️ Some packages in requirements.txt failed to install: {e}")
            print("🔄 Continuing with individual package installations...")
    else:
        print("⚠️ No 'requirements.txt' found, skipping that step.")

    # Step 2: Force install items in force_install.txt (if it exists)
    force_install_file = os.path.join(os.path.dirname(__file__), "force_install.txt")
    
    if os.path.exists(force_install_file):
        try:
            with open(force_install_file, "r") as f:
                force_packages = [
                    pkg.strip() 
                    for pkg in f.readlines() 
                    if pkg.strip() and not pkg.startswith("#")
                ]
            
            if force_packages:
                print(f"🔄 Force reinstalling: {', '.join(force_packages)}")
                for package in force_packages:
                    try:
                        print(f"📦 Forcing install of {package}...")
                        subprocess.run([
                            conda_exe, "run", "-n", env_name, 
                            "pip", "install", "--force-reinstall", package,
                            "--timeout", "120"
                        ], check=True, timeout=300)
                        print(f"✅ Successfully force installed: {package}")
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                        print(f"⚠️ Failed to install {package}: {e}")
                        print("🔄 Continuing with next package...")
            else:
                print("⚠️ No packages found in force_install.txt.")
        except Exception as e:
            print(f"❌ Error reading force_install.txt: {e}")
    else:
        print("No force_install.txt found; skipping force installs.")

    print("🚀 All installations complete!")

def main():
    print("🚀 Automoy-V2 Conda Installer Starting...")
    
    install_anaconda()
    
    env_name = "automoy_env"
    create_conda_env(env_name)
    install_pytorch(env_name)
    install_requirements(env_name)
    
    print(f"✅ Installation Complete! Activate your environment with: conda activate {env_name}")

if __name__ == "__main__":
    main()
