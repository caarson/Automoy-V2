import sys
import os
import platform
import subprocess
import requests
import ctypes
import pathlib
import time
import shutil

# If you'd like to use the same check_cuda function in real-time, you can import it:
# from check_cuda import check_cuda

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
installer_dir = os.path.join(project_root, "installer", "downloads")
os.makedirs(installer_dir, exist_ok=True)

CUDA_SUPPORTED_VERSIONS = {
    "11.8": "https://developer.download.nvidia.com/compute/cuda/11.8.0/network_installers/cuda_11.8.0_windows_network.exe",
    "12.1": "https://developer.download.nvidia.com/compute/cuda/12.1.1/network_installers/cuda_12.1.1_windows_network.exe",
    "12.4": "https://developer.download.nvidia.com/compute/cuda/12.4.0/network_installers/cuda_12.4.0_windows_network.exe"
}

EXTRA_KNOWN_VERSIONS = []

print("\n[DEBUG] Current PATH:")
print(os.environ.get("PATH", "(No PATH found)"))

def find_nvcc_in_standard_paths():
    known_versions = list(CUDA_SUPPORTED_VERSIONS.keys()) + EXTRA_KNOWN_VERSIONS
    possible_nvcc_paths = []

    base_dir = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"
    if os.path.isdir(base_dir):
        for folder_name in os.listdir(base_dir):
            candidate = os.path.join(base_dir, folder_name, "bin", "nvcc.exe")
            if os.path.isfile(candidate):
                possible_nvcc_paths.append(candidate)

    for ver in known_versions:
        candidate = rf"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v{ver}\bin\nvcc.exe"
        if os.path.isfile(candidate):
            possible_nvcc_paths.append(candidate)

    return possible_nvcc_paths

def is_cuda_installed():
    """Check if 'nvcc' is on PATH or in known directories."""
    if shutil.which("nvcc"):
        return True
    paths = find_nvcc_in_standard_paths()
    return len(paths) > 0

def get_installed_cuda_version():
    """Quick fallback: parse 'nvcc --version' if on PATH, else parse folder name."""
    if shutil.which("nvcc"):
        temp_output = os.path.join(installer_dir, "nvcc_check.txt")
        try:
            subprocess.run(
                f'cmd /c "nvcc --version > \"{temp_output}\" 2>&1"',
                shell=True,
                check=False
            )
            if os.path.exists(temp_output):
                with open(temp_output, "r") as f:
                    output = f.read()
                    print("\n[DEBUG] nvcc --version output:")
                    print(output)
                    for line in output.splitlines():
                        if "release" in line:
                            parts = line.strip().split("release")
                            if len(parts) > 1:
                                return parts[1].split(",")[0].strip()
        except Exception as e:
            print(f"Error running nvcc: {e}")

    # If PATH-based detection fails, parse from one of the known directories
    paths = find_nvcc_in_standard_paths()
    if paths:
        # e.g. "C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.4/bin/nvcc.exe"
        # we just pick the first
        path_to_nvcc = paths[0]
        folder_name = os.path.basename(os.path.dirname(path_to_nvcc))  # 'v12.4'
        if folder_name.lower().startswith("v"):
            return folder_name[1:]
    return None

def download_installer(url, dest_path):
    print(f"Downloading CUDA installer from {url}...")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"Installer downloaded successfully: {dest_path}")

def wait_for_cuda_installer(timeout=1800):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_cuda_installed():
            ver = get_installed_cuda_version()
            if ver:
                print(f"CUDA {ver} successfully detected.")
            else:
                print("Detected CUDA but couldn't parse version.")
            return True
        print("\n⚠️ `nvcc` is not installed or not found. Waiting for install to finish...")
        time.sleep(10)
    print("Timed out waiting for CUDA installation.")
    return False

def ask_user_cuda_version():
    versions = list(CUDA_SUPPORTED_VERSIONS.keys())
    menu = ' | '.join([f"{i+1}) {v}" for i, v in enumerate(versions)])
    print(f"\nAvailable CUDA versions: {menu}")
    while True:
        choice = input("Select CUDA version number to install: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(versions):
            return versions[int(choice) - 1]
        print("Invalid input. Please choose a valid number.")

def install_cuda():
    if platform.system() != "Windows":
        print("Unsupported OS for automatic CUDA installation. Exiting.")
        sys.exit(0)

    existing_version = get_installed_cuda_version()
    if existing_version:
        print(f"CUDA {existing_version} is already installed!")
        sys.exit(0)

    print("CUDA not detected. Proceeding with installation.")
    selected_version = ask_user_cuda_version()

    if selected_version not in CUDA_SUPPORTED_VERSIONS:
        print("Selected version is not supported. Exiting.")
        sys.exit(1)

    installer_path = os.path.join(installer_dir, f"cuda_{selected_version}_installer.exe")
    download_url = CUDA_SUPPORTED_VERSIONS[selected_version]
    if not os.path.exists(installer_path):
        download_installer(download_url, installer_path)

    print(f"Launching CUDA installer at: {installer_path}")
    subprocess.run(f'start /wait "" "{installer_path}"', shell=True)

    print("Waiting for CUDA installation to complete...")
    if wait_for_cuda_installer():
        print(f"CUDA {selected_version} installation completed!")
        sys.exit(0)
    else:
        print("CUDA install timed out or was not detected.")
        sys.exit(1)

if __name__ == "__main__":
    print("Automoy-V2 Full Installer Starting...")
    install_cuda()
