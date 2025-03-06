import sys
import os
import platform
import subprocess
import importlib.util
import requests
import ctypes  # Required for admin privileges on Windows
import pathlib
import time

sys.path.append(str(pathlib.Path(__file__).parent.parent / "evaluations"))
import check_cuda

# Define the project root and installer directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
installer_dir = os.path.join(project_root, "installer", "downloads")
os.makedirs(installer_dir, exist_ok=True)

# Supported CUDA versions with download links
CUDA_SUPPORTED_VERSIONS = {
    "11.8": "https://developer.download.nvidia.com/compute/cuda/11.8.0/network_installers/cuda_11.8.0_windows_network.exe",
    "12.1": "https://developer.download.nvidia.com/compute/cuda/12.1.1/network_installers/cuda_12.1.1_windows_network.exe",
    "12.4": "https://developer.download.nvidia.com/compute/cuda/12.4.0/network_installers/cuda_12.4.0_windows_network.exe"
}

def is_user_admin():
    """Check if the script is running with administrative privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """Re-run the script with administrative privileges."""
    if not is_user_admin():
        print("Administrative privileges required. Re-running as administrator...")
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, ' '.join(sys.argv), None, 1)
        sys.exit()

def wait_for_cuda_installer():
    """Wait until the NVIDIA CUDA installer has fully completed."""
    while True:
        if check_cuda.get_installed_cuda_version():
            break
        print("Waiting for CUDA installation to complete...")
        time.sleep(10)  # Check every 10 seconds

def install_cuda():
    """Main function to handle the CUDA installation process."""
    if platform.system() == "Windows":
        run_as_admin()
        print("Checking CUDA installation...")
        installed_cuda_version = check_cuda.get_installed_cuda_version()
        if installed_cuda_version:
            print(f"CUDA {installed_cuda_version} is already installed!")
            return
        else:
            print("No compatible CUDA installation detected.")

        cuda_version = ask_user_cuda_version()
        if cuda_version not in CUDA_SUPPORTED_VERSIONS:
            print("Selected CUDA version is not supported. Only versions 11.8 - 12.4 are allowed.")
            return
        
        installer_path = os.path.join(installer_dir, f"cuda_{cuda_version}_installer.exe")
        download_url = CUDA_SUPPORTED_VERSIONS[cuda_version]

        download_installer(download_url, installer_path)

        print("Launching CUDA installer... Follow the installation steps.")
        subprocess.Popen([installer_path], shell=True)
        
        # Wait for CUDA to be properly installed
        wait_for_cuda_installer()
        
        print(f"CUDA {cuda_version} installation completed!")
    else:
        print("Unsupported OS for automatic CUDA installation. Please install CUDA manually.")

def ask_user_cuda_version():
    """Prompt the user to select a CUDA version to install."""
    print("\nAvailable CUDA versions for installation:")
    for idx, version in enumerate(CUDA_SUPPORTED_VERSIONS.keys(), start=1):
        print(f"{idx}. CUDA {version}")
    while True:
        choice = input("Enter the number of the CUDA version you want to install: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(CUDA_SUPPORTED_VERSIONS):
            return list(CUDA_SUPPORTED_VERSIONS.keys())[int(choice) - 1]
        print("Invalid selection. Please enter a valid number.")

def download_installer(url, dest_path):
    """Download the CUDA installer."""
    print(f"Downloading CUDA installer from {url}...")
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"Installer downloaded successfully: {dest_path}")

if __name__ == "__main__":
    install_cuda()
