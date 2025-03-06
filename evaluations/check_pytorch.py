import torch
import subprocess
import os

SUPPORTED_CUDA_VERSIONS = ["11.8", "12.1", "12.4"]

def check_pytorch():
    """
    Checks if PyTorch is installed and using a supported CUDA version.
    
    Returns:
        bool: True if PyTorch is installed and using a compatible CUDA version.
    """
    print("🔍 Checking PyTorch installation...")

    try:
        import torch
        torch_version = torch.__version__
        cuda_version = torch.version.cuda

        if cuda_version is None:
            print("❌ PyTorch is installed but does NOT have CUDA support.")
            return False

        print(f"✅ PyTorch Version: {torch_version}")
        print(f"✅ PyTorch CUDA Version: {cuda_version}")

        # Ensure PyTorch is using a supported CUDA version
        if cuda_version in SUPPORTED_CUDA_VERSIONS:
            print("✅ PyTorch is correctly configured with a supported CUDA version.")
            return True
        else:
            print("⚠️ PyTorch is using an unsupported CUDA version.")
            return False

    except ImportError:
        print("❌ PyTorch is not installed.")
        return False

if __name__ == "__main__":
    print("🚀 Checking PyTorch Configuration...")

    if check_pytorch():
        print("✅ PyTorch installation verified successfully.")
    else:
        print("❌ PyTorch is either missing or not configured correctly for CUDA.")

    print("👉 If you need to install PyTorch, run:")
    print("   pip install torch==2.5.1+cu124 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124")
