import os
import sys
import ctypes
import subprocess
import pathlib
import shutil

def install_basic_dependencies():
    """Install basic dependencies needed for the installer scripts."""
    print("Installing basic dependencies for installer...")
    try:
        # Install requests, which is needed by cuda_setup.py
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        print("✓ Basic dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install basic dependencies: {e}")
        return False

def is_user_admin():
    """
    Returns True if the current process is running with admin privileges.
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def ensure_admin():
    """
    If not running as admin, re-launch this script in a new CMD console (with /k).
    That console won't close on Ctrl+C or error, and includes proper quoting for paths.
    """
    if not is_user_admin():
        print("Re-launching as administrator in a new console that won't close on error or Ctrl+C.")

        exe_path = os.path.normpath(sys.executable)  # e.g. "C:\\Users\\Declan Smith\\python.exe"
        script_path = os.path.normpath(os.path.abspath(sys.argv[0]))  # e.g. "C:\\Some Folder\\Automoy\\setup.py"

        # Build the argument list, then convert to a single command line string:
        cmd_parts = [exe_path, script_path] + sys.argv[1:]
        command_in_cmd = subprocess.list2cmdline(cmd_parts)

        # /k => keep CMD window open after finishing; we add an extra set of quotes around the entire command
        params_for_cmd = f'/k \"{command_in_cmd}\"'

        # Elevate: run cmd.exe as admin with those parameters
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            "cmd.exe",
            params_for_cmd,
            None,
            1
        )
        sys.exit(0)

def run_cuda_setup():
    print("Starting CUDA installation...")

    # If setup.py is in the same folder as cuda_setup.py:
    script_dir = pathlib.Path(__file__).parent.resolve()
    cuda_setup_script = script_dir / "cuda_setup.py"

    # We'll run python cuda_setup.py with shell=False and a list of args, so spaces won't break
    result = subprocess.run([sys.executable, str(cuda_setup_script)], check=False)
    if result.returncode == 0:
        print("CUDA installation complete!")
    else:
        print("CUDA installation failed or timed out. Please check logs.")
        sys.exit(result.returncode)

def run_conda_setup():
    print("Starting Conda installation and environment setup...")

    script_dir = pathlib.Path(__file__).parent.resolve()
    conda_setup_script = script_dir / "conda_setup.py"

    rc = subprocess.run([sys.executable, str(conda_setup_script)], check=False)
    if rc.returncode == 0:
        print("Conda setup complete!")
    else:
        print("Conda setup failed. Please check logs.")
        sys.exit(1)

def run_omnispaper_setup():
    print("Starting OmniParser setup...")

    script_dir = pathlib.Path(__file__).parent.resolve()
    omniparser_setup_script = script_dir / "omniparser_setup.py"

    rc = subprocess.run([sys.executable, str(omniparser_setup_script)], check=False)
    if rc.returncode == 0:
        print("OmniParser setup complete!")
    else:
        print("OmniParser setup failed. Please check logs.")
        sys.exit(1)

def is_cuda_available():
    """
    Uses evaluations/check_cuda.py to determine if CUDA is installed.
    Returns True if CUDA is detected, False otherwise.
    """
    script_dir = pathlib.Path(__file__).parent.parent.resolve()
    check_cuda_script = script_dir / "evaluations" / "check_cuda.py"
    result = subprocess.run([sys.executable, str(check_cuda_script)], capture_output=True, text=True)
    # If the script prints a version, it's detected
    return "Final Detected CUDA version" in result.stdout or "✅ Detected CUDA version" in result.stdout or "✅ Found CUDA version" in result.stdout

def has_nvidia_gpu():
    """
    Return True if an NVIDIA GPU is present.
    """
    # check for nvidia-smi on PATH
    if shutil.which("nvidia-smi"):
        return True
    # fallback to WMI query
    try:
        output = subprocess.check_output(
            'wmic path win32_VideoController get name', shell=True
        ).decode(errors="ignore")
        for line in output.splitlines():
            if "NVIDIA" in line.upper():
                return True
    except Exception:
        pass
    return False

def run_cuda_or_sycl_setup():
    print("Checking for NVIDIA GPU...")
    if has_nvidia_gpu():
        print("NVIDIA GPU detected. Proceeding with CUDA installation...")
        run_cuda_setup()
    else:
        print("No NVIDIA GPU found. Proceeding with SYCL/OpenCL installation...")
        run_opencl_setup()

def run_opencl_setup():
    print("Starting SYCL/OpenCL installation...")
    script_dir = pathlib.Path(__file__).parent.resolve()
    opencl_setup_script = script_dir / "opencl_setup.py"
    rc = subprocess.run([sys.executable, str(opencl_setup_script)], check=False)
    if rc.returncode == 0:
        print("SYCL/OpenCL setup complete!")
    else:
        print("SYCL/OpenCL setup failed. Please check logs.")
        sys.exit(1)

if __name__ == "__main__":
    print("Automoy-V2 Full Installer Starting...")

    # 1) Elevate if needed (opens new admin console with /k + quotes)
    ensure_admin()

    # 2) Install basic dependencies for installer scripts
    if not install_basic_dependencies():
        print("Failed to install basic dependencies. Cannot continue.")
        sys.exit(1)

    # 3) CUDA or SYCL/OpenCL
    run_cuda_or_sycl_setup()

    # 4) Conda
    run_conda_setup()

    # 5) OmniParser
    run_omnispaper_setup()

    print("All installations complete! Automoy-V2 is now ready to use.")
