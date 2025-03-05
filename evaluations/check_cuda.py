import subprocess
import os
import re

# Supported CUDA versions for Automoy
SUPPORTED_CUDA_VERSIONS = ["11.8", "12.1", "12.4"]

def get_installed_cuda_version():
    """
    Detects installed CUDA versions using `nvcc --version`.
    Returns:
        str: Detected CUDA version or None if no supported CUDA is found.
    """
    try:
        # Run `nvcc --version` and extract the actual installed CUDA version
        result = subprocess.run(["nvcc", "--version"], capture_output=True, text=True)
        match = re.search(r"release (\d+\.\d+)", result.stdout)

        if match:
            detected_version = match.group(1)
            print(f"🔍 Detected installed CUDA version via NVCC: {detected_version}")

            # Check if the detected version is in the supported range
            if detected_version in SUPPORTED_CUDA_VERSIONS:
                print("✅ Installed CUDA version is supported.")
                return detected_version
            else:
                print("⚠️ Installed CUDA version is outside the supported range.")
                return None
    except FileNotFoundError:
        print("⚠️ `nvcc` is not installed or not found. Falling back to NVIDIA-SMI.")


def check_cuda():
    """
    Checks if a supported CUDA version is installed.
    
    Returns:
        bool: True if a supported CUDA version is detected.
    """
    print("🔍 Checking CUDA installation...")

    # Check system CUDA version using NVCC
    installed_cuda = get_installed_cuda_version()
    if not installed_cuda:
        print("❌ No compatible CUDA installation found.")
        return False

    return True

def run_nvidia_smi():
    """
    Runs the 'nvidia-smi' command to display GPU details.
    """
    try:
        print("🔍 Running 'nvidia-smi' for additional diagnostics...")
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        print(result.stdout)

    except FileNotFoundError:
        print("⚠️ 'nvidia-smi' is not installed or not found. Ensure you have NVIDIA drivers installed.")

    return result

if __name__ == "__main__":
    print("🚀 Checking System CUDA Version...")

    if check_cuda():
        print("✅ CUDA installation verified successfully.")
    else:
        print("❌ No supported CUDA version found. Please install a supported version (11.8, 12.1, 12.4).")