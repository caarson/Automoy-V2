import os
import sys
import ctypes
import subprocess
import pathlib
import shutil

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
    That console won't close on Ctrl+C or error.
    """
    if not is_user_admin():
        print("Re-launching as administrator in a new console that won't close on error or Ctrl+C.")

        exe_path = os.path.normpath(sys.executable)
        script_path = os.path.normpath(os.path.abspath(sys.argv[0]))

        # Build the command that we want cmd.exe to run
        cmd_parts = [exe_path, script_path] + sys.argv[1:]
        command_in_cmd = subprocess.list2cmdline(cmd_parts)

        # /k => keep CMD window open after the command finishes
        params_for_cmd = f'/k {command_in_cmd}'

        # Elevate: run cmd.exe as admin with the /k ...
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

if __name__ == "__main__":
    print("Automoy-V2 Full Installer Starting...")

    # 1) Elevate if needed (opens new admin console with /k)
    ensure_admin()

    # 2) CUDA
    run_cuda_setup()

    # 3) Conda
    run_conda_setup()

    # 4) OmniParser
    run_omnispaper_setup()

    print("All installations complete! Automoy-V2 is now ready to use.")
