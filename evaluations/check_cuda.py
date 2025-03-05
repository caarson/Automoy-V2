import torch
import subprocess
import os
import re

def check_cuda(min_memory_gb=2):
    """
    Checks if CUDA is available, the GPU has enough memory, and if OmniParser can leverage GPU acceleration.
    
    Args:
        min_memory_gb (int): Minimum required GPU memory in GB.
    
    Returns:
        bool: True if CUDA is available and meets the minimum memory requirement.
    """
    print("🔍 Checking CUDA and GPU availability...")

    # Check if PyTorch detects CUDA
    if not torch.cuda.is_available():
        print("❌ CUDA is not available. Please check your GPU setup.")
        return False

    # Get CUDA device info
    device_name = torch.cuda.get_device_name(0)
    total_memory = torch.cuda.get_device_properties(0).total_memory / 1e9  # Convert bytes to GB
    print(f"✅ Using device: {device_name}")
    print(f"✅ Total GPU memory: {total_memory:.2f} GB")

    if total_memory < min_memory_gb:
        print(f"⚠️ Insufficient GPU memory. Required: {min_memory_gb} GB, Available: {total_memory:.2f} GB")
        return False

    return True

def run_nvidia_smi():
    """
    Runs the 'nvidia-smi' command to get GPU details and driver information.
    """
    try:
        print("🔍 Running 'nvidia-smi' for additional diagnostics...")
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        print(result.stdout)

    except FileNotFoundError:
        print("⚠️ 'nvidia-smi' is not installed or not found. Ensure you have NVIDIA drivers installed.")

# Main test
if __name__ == "__main__":
    print("🚀 Starting CUDA Evaluation for Automoy-V2...")
    
    if check_cuda():
        print("✅ CUDA and PyTorch GPU configuration verified successfully.")
    else:
        print("❌ CUDA and/or PyTorch GPU configuration failed. Please check your setup.")

    run_nvidia_smi()
