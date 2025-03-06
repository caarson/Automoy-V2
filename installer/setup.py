import os
import subprocess
import sys
import time
import pathlib

sys.path.append(str(pathlib.Path(__file__).parent.parent / "evaluations"))
import check_cuda

def is_nvidia_installer_running():
    """Check if the NVIDIA CUDA installer is running."""
    try:
        result = subprocess.run(["tasklist"], capture_output=True, text=True)
        return "setup.exe" in result.stdout.lower() or "cuda_installer" in result.stdout.lower()
    except Exception as e:
        print(f"Error checking running processes: {e}")
    return False

def is_cuda_installed():
    """Check if CUDA installation is complete by verifying if nvcc reports a version."""
    try:
        cuda_version = check_cuda.get_installed_cuda_version()
        if cuda_version:
            print(f"Detected CUDA version: {cuda_version}")
            return True
    except Exception as e:
        print(f"Error checking CUDA version: {e}")
    return False

def run_cuda_setup():
    """Runs the CUDA setup script to install CUDA and waits for completion."""
    print("Starting CUDA installation...")
    try:
        cuda_process = subprocess.Popen([sys.executable, "installer/cuda_setup.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        while is_nvidia_installer_running() or not is_cuda_installed():
            print("nvcc not detected! \nWaiting for CUDA installation to complete...")
            time.sleep(10)  # Check every 10 seconds
        
        stdout, stderr = cuda_process.communicate()
        print(stdout)
        print(stderr)
        
        if cuda_process.returncode == 0 and is_cuda_installed():
            print("CUDA installation complete!")
        else:
            print("CUDA installation failed. Please check logs.")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        print("CUDA installation encountered an error:")
        print(e.output)
        sys.exit(1)

def run_conda_setup():
    """Runs the Conda setup script to install and configure Conda."""
    print("Starting Conda installation and environment setup...")
    try:
        subprocess.run([sys.executable, "installer/conda_setup.py"], check=True)
        print("Conda setup complete!")
    except subprocess.CalledProcessError:
        print("Conda setup failed. Please check logs.")
        sys.exit(1)

if __name__ == "__main__":
    print("Automoy-V2 Full Installer Starting...")

    # Step 1: Install CUDA and wait for it to finish
    run_cuda_setup()

    # Step 2: Install Conda and setup environment
    run_conda_setup()

    print("All installations complete! Automoy-V2 is now ready to use.")
