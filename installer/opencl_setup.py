import sys
import subprocess
import os
import urllib.request
import tempfile
import shutil
import pathlib
import winshell
import win32com.client

def is_oneapi_installed():
    """
    Checks if Intel oneAPI Base Toolkit is already installed.
    Returns True if installed, False otherwise.
    """
    # Check for the presence of oneAPI environment variables or installation directory
    oneapi_env_var = os.environ.get('ONEAPI_ROOT')
    oneapi_install_path = pathlib.Path("C:/Program Files (x86)/Intel/oneAPI")

    if oneapi_env_var or oneapi_install_path.exists():
        print("Intel oneAPI Base Toolkit is already installed.")
        return True

    return False

def install_oneapi():
    print("Downloading Intel oneAPI Base Toolkit offline installer...")
    downloads_dir = os.path.join(os.path.dirname(__file__), "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    oneapi_url = "https://registrationcenter-download.intel.com/akdlm/IRC_NAS/e5785fb3-b5a7-4b97-89bc-918adab1f77d/intel-oneapi-base-toolkit-2025.1.3.8_offline.exe"
    installer_path = os.path.join(downloads_dir, "intel-oneapi-base-toolkit-2025.1.3.8_offline.exe")
    extract_dir = os.path.join(downloads_dir, "oneapi_extracted")
    aria2c_path = os.path.join(os.path.dirname(__file__), "aria2c.exe")
    if not os.path.isfile(installer_path):
        try:
            print(f"Downloading from {oneapi_url} using aria2c ...")
            subprocess.run([
                aria2c_path,
                "-x", "16",
                "-s", "16",
                "-d", downloads_dir,
                "-o", "intel-oneapi-base-toolkit-2025.1.3.8_offline.exe",
                oneapi_url
            ], check=True)
            print(f"Downloaded Intel oneAPI installer to {installer_path}")
        except Exception as e:
            print(f"Intel oneAPI download failed: {e}")
            print("Please download and install Intel oneAPI Base Toolkit manually from: https://www.intel.com/content/www/us/en/developer/tools/oneapi/base-toolkit-download.html")
            return False
    else:
        print(f"Intel oneAPI installer already exists at {installer_path}")
    # Step 1: Extract the offline installer
    if not os.path.isdir(extract_dir) or not os.path.isfile(os.path.join(extract_dir, "bootstrapper.exe")):
        try:
            print(f"Extracting offline installer to {extract_dir} ...")
            subprocess.run([
                installer_path,
                "--extract-folder", extract_dir,
                "--extract-only"
            ], check=True)
            print(f"Extraction complete.")
        except Exception as e:
            print(f"Extraction failed: {e}")
            print("Please extract and install Intel oneAPI Base Toolkit manually.")
            return False
    else:
        print(f"Installer already extracted at {extract_dir}")
    # Step 2: Run bootstrapper.exe with supported silent install argument and EULA acceptance
    bootstrapper_path = os.path.join(extract_dir, "bootstrapper.exe")
    try:
        print("Running Intel oneAPI Base Toolkit bootstrapper (silent mode)...")
        subprocess.run([
            bootstrapper_path,
            "--silent",
            "--eula=accept"
        ], check=True)
        print("Intel oneAPI Base Toolkit installation complete.")
        return True
    except Exception as e:
        print(f"Intel oneAPI install failed: {e}")
        print(f"Please run the bootstrapper manually from {bootstrapper_path} or check for errors.")
        return False

def install_build_tools():
    print("Installing build tools and dependencies for PyTorch SYCL fork...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "cmake", "ninja", "pyyaml", "mkl", "mkl-include", "setuptools", "cffi", "typing_extensions", "future", "six", "requests", "dataclasses"], check=True)
        print("Python build dependencies installed.")
    except Exception as e:
        print(f"Python build dependencies install failed: {e}")
        sys.exit(1)
    # Recommend Visual Studio Build Tools for C++
    print("Please ensure you have Visual Studio 2019 or newer with C++ Desktop Development tools installed.")

def check_vs_build_tools_prerequisites():
    print("Checking prerequisites for Visual Studio Build Tools installation...")
    # Check for internet connection
    import socket
    try:
        socket.create_connection(("www.microsoft.com", 80), timeout=5)
        print("Internet connection: OK")
    except Exception:
        print("Warning: No internet connection detected. Visual Studio Build Tools installer may fail.")
    # Check for admin rights
    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("Warning: Script is not running as administrator. Installation may fail.")

def has_required_vs_components():
    """
    Uses vswhere.exe to check for required Visual Studio Build Tools workloads/components by ID and checks for binaries under the detected installationPath.
    Returns True if all required components are present, False otherwise.
    """
    import glob
    import shutil
    vswhere_path = r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
    required_components = [
        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",  # MSVC
        "Microsoft.VisualStudio.Component.Windows10SDK.19041",  # Windows 10 SDK
        "Microsoft.VisualStudio.Component.VC.CMake.Project"  # CMake tools
    ]
    if os.path.isfile(vswhere_path):
        try:
            # Get the installation path
            result = subprocess.run([
                vswhere_path,
                "-latest",
                "-products", "*",
                "-property", "installationPath"
            ], capture_output=True, text=True, check=True)
            install_path = result.stdout.strip()
            if not install_path:
                print("[VS Detection] No Visual Studio Build Tools installation found.")
                return False
            # Check for binaries under the detected install_path
            cl_paths = glob.glob(os.path.join(install_path, "VC", "Tools", "MSVC", "*", "bin", "Hostx64", "x64", "cl.exe"))
            cmake_paths = glob.glob(os.path.join(install_path, "Common7", "IDE", "CommonExtensions", "Microsoft", "CMake", "CMake", "bin", "cmake.exe"))
            sdk_glob = r"C:\Program Files (x86)\Windows Kits\10\bin\*\x64\rc.exe"
            sdk_paths = glob.glob(sdk_glob)
            found_msvc = bool(cl_paths)
            found_cmake = bool(cmake_paths)
            found_sdk = bool(sdk_paths)
            print(f"[VS Detection] install_path: {install_path}")
            print(f"[VS Detection] MSVC: {found_msvc}, Windows 10 SDK: {found_sdk}, CMake: {found_cmake}")
            return found_msvc and found_sdk and found_cmake
        except Exception as e:
            print(f"vswhere.exe detection failed: {e}")
            return False
    else:
        print("vswhere.exe not found, falling back to binary checks (may be unreliable)...")
        # Fallback to previous method
        import glob
        vs_base = r"C:\Program Files (x86)\Microsoft Visual Studio\2022"
        editions = ["BuildTools", "Community", "Professional", "Enterprise"]
        found_msvc = found_sdk = found_cmake = False
        for edition in editions:
            msvc_glob = os.path.join(vs_base, edition, "VC", "Tools", "MSVC", "*", "bin", "Hostx64", "x64", "cl.exe")
            if glob.glob(msvc_glob):
                found_msvc = True
            cmake_glob = os.path.join(vs_base, edition, "Common7", "IDE", "CommonExtensions", "Microsoft", "CMake", "CMake", "bin", "cmake.exe")
            if glob.glob(cmake_glob):
                found_cmake = True
        sdk_glob = r"C:\Program Files (x86)\Windows Kits\10\bin\*\x64\rc.exe"
        if glob.glob(sdk_glob):
            found_sdk = True
        print(f"[VS Detection] MSVC: {found_msvc}, Windows 10 SDK: {found_sdk}, CMake: {found_cmake}")
        return found_msvc and found_sdk and found_cmake


def install_vs_build_tools():
    check_vs_build_tools_prerequisites()
    print("Checking for Visual Studio Build Tools (C++ components)...")
    vswhere_path = r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
    if os.path.isfile(vswhere_path):
        try:
            result = subprocess.run([
                vswhere_path,
                "-latest",
                "-products", "*",
                "-property", "installationPath"
            ], capture_output=True, text=True, check=True)
            install_path = result.stdout.strip()
            if install_path:
                # Now check for required components using the improved function
                if has_required_vs_components():
                    print("Required C++ components are installed. Proceeding...")
                    return True
                else:
                    print("Visual Studio Build Tools are installed, but required C++ components are missing.")
                    print("Please click 'Modify' in the Visual Studio Installer, and ensure the following are checked:")
                    print("  - Desktop development with C++")
                    print("  - Windows 10 SDK")
                    print("  - CMake tools for Windows")
                    input("After modifying and completing the installation, press Enter to continue...")
                    if has_required_vs_components():
                        print("Required C++ components are now installed. Proceeding...")
                        return True
                    else:
                        print("Required C++ components are still missing. Please try again or install manually.")
                        return False
            else:
                print("No Visual Studio Build Tools installation found.")
        except Exception as e:
            print(f"vswhere.exe detection failed: {e}")
    # If we get here, treat as not found and prompt for install
    print("Visual Studio Build Tools not found. Downloading and launching installer for user interaction...")
    vs_url = "https://aka.ms/vs/17/release/vs_BuildTools.exe"
    downloads_dir = os.path.join(os.path.dirname(__file__), "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    installer_path = os.path.join(downloads_dir, "vs_BuildTools.exe")
    try:
        import urllib.request
        urllib.request.urlretrieve(vs_url, installer_path)
        print(f"Downloaded Visual Studio Build Tools installer to {installer_path}")
        print("\nIMPORTANT: In the Visual Studio Installer, select the following before clicking Install:")
        print("  - Desktop development with C++")
        print("  - Windows 10 SDK")
        print("  - CMake tools for Windows\n")
        print("Launching Visual Studio Build Tools installer. Please complete the installation in the window that appears.")
        print("After installation is complete, return to this window and press Enter to continue.")
        subprocess.run([installer_path], check=False)
        input("Press Enter to continue after you have finished the Visual Studio Build Tools installation...")
        if has_required_vs_components():
            print("Required C++ components are now installed. Proceeding...")
            return True
        else:
            print("Required C++ components are still missing. Please try again or install manually.")
            return False
    except Exception as e:
        print(f"Visual Studio Build Tools install failed: {e}")
    print("Please install Visual Studio Build Tools with C++ components manually from: https://visualstudio.microsoft.com/visual-cpp-build-tools/")
    print("Retry the installation after ensuring all prerequisites are met.")
    return False

def clone_and_build_pytorch_sycl():
    print("Cloning Intel's SYCL fork of PyTorch...")
    repo_url = "https://github.com/intel/pytorch.git"
    branch = "sycl"
    clone_dir = os.path.abspath("pytorch_sycl_build")
    if not os.path.exists(clone_dir):
        try:
            subprocess.run(["git", "clone", "--recursive", "-b", branch, repo_url, clone_dir], check=True)
        except Exception as e:
            print(f"Failed to clone PyTorch SYCL fork: {e}")
            sys.exit(1)
    else:
        print(f"PyTorch SYCL fork already cloned at {clone_dir}")
    print("Building PyTorch SYCL fork (this may take a long time)...")
    try:
        subprocess.run([sys.executable, "tools\build_pytorch_libs.py"], cwd=clone_dir, check=True)
        subprocess.run([sys.executable, "setup.py", "install"], cwd=clone_dir, check=True)
        print("PyTorch SYCL fork built and installed.")
    except Exception as e:
        print(f"PyTorch SYCL fork build/install failed: {e}")
        sys.exit(1)

def pause_and_report():
    print("\nAn error occurred during the SYCL/OpenCL (Intel oneAPI/PyTorch SYCL) installation.")
    print("Please report this issue with the error message above to the Automoy-V2 maintainers.")
    input("Press Enter to exit and report the issue...")
    sys.exit(1)

def validate_oneapi_installation():
    """
    Validates that the Intel oneAPI Base Toolkit is correctly installed and accessible.
    Automatically sets the ONEAPI_ROOT environment variable if missing.
    Returns True if validation passes, False otherwise.
    """
    oneapi_env_var = os.environ.get('ONEAPI_ROOT')
    oneapi_setvars_path = pathlib.Path("C:/Program Files (x86)/Intel/oneAPI/setvars.bat")
    oneapi_compiler_path = pathlib.Path("C:/Program Files (x86)/Intel/oneAPI/compiler/latest")

    print("Debug: Checking Intel oneAPI installation...")
    print(f"Debug: ONEAPI_ROOT environment variable: {oneapi_env_var}")
    print(f"Debug: setvars.bat path exists: {oneapi_setvars_path.exists()}")
    print(f"Debug: Compiler directory path exists: {oneapi_compiler_path.exists()}")

    if not oneapi_env_var and oneapi_setvars_path.exists() and oneapi_compiler_path.exists():
        print("ONEAPI_ROOT environment variable is not set. Attempting to set it automatically...")
        try:
            os.environ['ONEAPI_ROOT'] = str(oneapi_setvars_path.parent)
            subprocess.run(["setx", "ONEAPI_ROOT", str(oneapi_setvars_path.parent), "/M"], check=True)
            print("ONEAPI_ROOT environment variable set successfully.")
        except Exception as e:
            print(f"Failed to set ONEAPI_ROOT environment variable: {e}")
            return False

    # Revalidate after setting the environment variable
    oneapi_env_var = os.environ.get('ONEAPI_ROOT')
    if oneapi_env_var and oneapi_setvars_path.exists() and oneapi_compiler_path.exists():
        print("Intel oneAPI Base Toolkit installation validated successfully.")
        return True

    print("Intel oneAPI Base Toolkit validation failed.")
    print("Ensure the toolkit is installed and the following are correctly set:")
    print("  1. Environment variable 'ONEAPI_ROOT' is defined.")
    print("  2. File 'setvars.bat' exists at 'C:/Program Files (x86)/Intel/oneAPI/'.")
    print("  3. Compiler directory exists at 'C:/Program Files (x86)/Intel/oneAPI/compiler/latest/'.")
    print("You may need to reinstall the toolkit or manually set the environment variables.")
    return False

def run_setvars_bat():
    setvars_path = r"C:\Program Files (x86)\Intel\oneAPI\setvars.bat"
    if os.path.exists(setvars_path):
        print("Launching setvars.bat in a new command prompt window...")
        subprocess.Popen(["cmd.exe", "/k", setvars_path])
        print("A new command prompt with oneAPI environment will remain open for you to use.")
    else:
        print(f"setvars.bat not found at {setvars_path}. Please set up the environment manually.")

def run_setvars_bat_persistent():
    setvars_path = r"C:\Program Files (x86)\Intel\oneAPI\setvars.bat"
    if os.path.exists(setvars_path):
        print("Launching a persistent command prompt with oneAPI environment set up. This window will remain open for future SYCL/PyTorch work.")
        subprocess.Popen(["cmd.exe", "/k", setvars_path])
        print("A new command prompt with oneAPI environment will remain open for you to use at any time.")
    else:
        print(f"setvars.bat not found at {setvars_path}. Please set up the environment manually.")

def add_setvars_to_startup():
    """
    Adds a shortcut to setvars.bat in the user's Startup folder so that the oneAPI environment is set up automatically on login.
    """
    setvars_path = r"C:\Program Files (x86)\Intel\oneAPI\setvars.bat"
    if not os.path.exists(setvars_path):
        print(f"setvars.bat not found at {setvars_path}. Cannot add to Startup.")
        return False
    startup_dir = winshell.startup()
    shortcut_path = os.path.join(startup_dir, "oneAPI_setvars.lnk")
    shell = win32com.client.Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = "cmd.exe"
    shortcut.Arguments = f'/k "{setvars_path}"'
    shortcut.WorkingDirectory = os.path.dirname(setvars_path)
    shortcut.IconLocation = setvars_path
    shortcut.save()
    print(f"Shortcut to setvars.bat added to Startup folder: {shortcut_path}")
    return True

def main():
    if is_oneapi_installed():
        print("Skipping Intel oneAPI installation as it is already installed.")
    else:
        if not install_oneapi():
            print("Intel oneAPI installation failed.")
            pause_and_report()

    if not validate_oneapi_installation():
        print("Post-installation validation failed.")
        pause_and_report()

    install_build_tools()

    if not install_vs_build_tools():
        print("Visual Studio Build Tools installation failed.")
        pause_and_report()

    try:
        clone_and_build_pytorch_sycl()
    except Exception as e:
        print(f"PyTorch SYCL fork build/install failed: {e}")
        pause_and_report()

    print("\nPyTorch SYCL fork installation complete!\n")
    print("To use PyTorch with SYCL, Intel oneAPI environment variables must be set.")
    print("If you answer 'Y' below, the oneAPI environment will be set up automatically and persistently on every login (a command prompt will open with oneAPI ready).\n")
    print("You can remove this behavior at any time by deleting the 'oneAPI_setvars.lnk' shortcut from your Startup folder.")
    print("You can also open a new oneAPI-enabled prompt manually by running:\n  \"C:\\Program Files (x86)\\Intel\\oneAPI\\setvars.bat\"")
    answer = input("Would you like to set up the oneAPI environment to launch automatically on login? (Y/N): ").strip().lower()
    if answer == 'y':
        if add_setvars_to_startup():
            print("oneAPI environment will now be set up automatically on every login. A command prompt will open with oneAPI ready.")
        else:
            print("Failed to add setvars.bat to Startup. You can do this manually if needed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
