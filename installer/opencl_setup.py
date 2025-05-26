import os
import sys
import time
import shutil
import pathlib
import subprocess
import stat
import errno
import importlib

def handle_remove_readonly(func, path, exc):
    """Handler for removing read-only files"""
    excvalue = exc[1]
    if func in (os.rmdir, os.remove, os.unlink) and excvalue.errno == errno.EACCES:
        os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        func(path)
    else:
        raise excvalue

def verify_directory_empty(path, retries=5, delay=1):
    """Verify that a directory is empty or doesn't exist, with retries."""
    for i in range(retries):
        if not os.path.exists(path):
            return True
        
        try:
            with os.scandir(path) as it:
                has_entries = any(True for _ in it)
                if not has_entries:
                    return True
        except Exception as e:
            print(f"Scan attempt {i+1} failed: {e}")
        
        print(f"Directory not empty, waiting {delay} seconds...")
        time.sleep(delay)
    
    return False

def remove_directory_safe(path, max_retries=3):
    """Enhanced directory removal with multiple fallback methods."""
    if not os.path.exists(path):
        return True

    print(f"Attempting to remove directory: {path}")
    
    # Try 1: Basic rmtree with readonly handler
    try:
        shutil.rmtree(path, onerror=handle_remove_readonly)
        print("Directory removed successfully using standard method")
        return True
    except Exception as e:
        print(f"Standard removal failed: {e}")

    # Try 2: Force with robocopy (Windows only)
    empty_dir = os.path.join(os.path.dirname(path), "empty_temp_dir")
    try:
        os.makedirs(empty_dir, exist_ok=True)
        subprocess.run(
            ["robocopy", empty_dir, path, "/MIR"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False
        )
        os.rmdir(empty_dir)
        if os.path.exists(path):
            os.rmdir(path)
        print("Directory removed successfully using robocopy method")
        return True
    except Exception as e:
        print(f"Robocopy removal failed: {e}")
    finally:
        if os.path.exists(empty_dir):
            try:
                os.rmdir(empty_dir)
            except:
                pass
    
    # Try 3: Force delete using PowerShell
    try:
        ps_command = f'Remove-Item -Path "{path}" -Recurse -Force'
        subprocess.run(
            ["powershell", "-Command", ps_command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        print("Directory removed successfully using PowerShell method")
        return True
    except Exception as e:
        print(f"PowerShell removal failed: {e}")

    print(f"Failed to remove directory {path} after all attempts")
    return False

def clone_and_build_pytorch_sycl():
    """Clone and build PyTorch with SYCL support."""
    print("Setting up build environment...")
    
    # Get clean environment without MSVC/Windows SDK
    build_env = {}
    for key in ['SYSTEMROOT', 'TEMP', 'TMP', 'USERNAME', 'USERPROFILE', 'COMPUTERNAME', 'PATH']:
        if key in os.environ:
            build_env[key] = os.environ[key]
            
    # Set up Intel environment only
    print("Setting up Intel oneAPI environment...")
    setvars_path = pathlib.Path("C:/Program Files (x86)/Intel/oneAPI/setvars.bat")
    if not setvars_path.exists():
        print("Error: Intel oneAPI installation not found!")
        sys.exit(1)
        
    temp_base = os.path.join(os.getenv('TEMP', os.path.expanduser('~')), 'pt_build')
    os.makedirs(temp_base, exist_ok=True)
    
    # Create temporary batch file to capture environment
    temp_bat = os.path.join(temp_base, "temp_setvars.bat")
    with open(temp_bat, 'w') as f:
        f.write(f'call "{setvars_path}" > nul 2>&1\ncall set > "{temp_base}\\env.txt"')
    
    subprocess.run([temp_bat], shell=True, check=True)
    
    # Parse environment variables
    with open(os.path.join(temp_base, "env.txt"), 'r') as f:
        for line in f:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                build_env[key] = value
    
    # Get Intel compiler paths
    icx_path, icpx_path = get_intel_compiler_paths()
    if not icx_path or not icpx_path:
        print("Error: Intel ICX/ICPX compilers not found!")
        sys.exit(1)
    
    # Set up directories
    clone_dir = os.path.join(temp_base, "pytorch")
    build_dir = os.path.join(clone_dir, "build")
    
    # Clean up existing directory using our enhanced removal functions
    if os.path.exists(clone_dir):
        print(f"Removing existing directory: {clone_dir}")
        if not remove_directory_safe(clone_dir):
            print("Failed to remove directory using all available methods")
            print("Please manually remove the directory and try again")
            sys.exit(1)
        
        # Verify directory is actually empty/gone
        if not verify_directory_empty(clone_dir):
            print("Directory cleanup verification failed")
            sys.exit(1)
    
    # Create fresh directories
    print("Creating build directories...")
    os.makedirs(clone_dir, exist_ok=True)
    os.makedirs(build_dir, exist_ok=True)

    # Clone repository with enhanced retries and cleanup
    print(f"Cloning PyTorch to {clone_dir}...")
    max_retries = 3
    retry_delay = 5  # seconds between retries
    success = False
    
    for attempt in range(max_retries):
        try:
            # Clean directory before each attempt
            if os.path.exists(clone_dir):
                if not remove_directory_safe(clone_dir):
                    print(f"Failed to clean directory before clone attempt {attempt + 1}")
                    continue
                if not verify_directory_empty(clone_dir):
                    print(f"Directory not empty before clone attempt {attempt + 1}")
                    continue
            
            os.makedirs(clone_dir, exist_ok=True)
            
            # Try the clone with progress
            process = subprocess.Popen(
                ["git", "clone", "--depth", "1", "https://github.com/pytorch/pytorch.git", clone_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Monitor the clone process
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(output.strip())
            
            # Get the return code
            return_code = process.poll()
            if return_code == 0:
                success = True
                print("Repository cloned successfully")
                break
            else:
                stderr = process.stderr.read()
                print(f"Clone attempt {attempt + 1} failed with code {return_code}:")
                print(stderr)
                
            if attempt < max_retries - 1:
                print(f"Retrying after {retry_delay} seconds...")
                time.sleep(retry_delay)
                
        except Exception as e:
            print(f"Clone attempt {attempt + 1} failed with exception:")
            print(f"Error: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Retrying after {retry_delay} seconds...")
                time.sleep(retry_delay)
    
    if not success:
        print("Failed to clone repository after all attempts")
        sys.exit(1)

    print("Initializing submodules...")
    try:
        # Initialize submodules with progress
        process = subprocess.Popen(
            ["git", "submodule", "update", "--init", "--recursive"],
            cwd=clone_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
        
        if process.poll() != 0:
            stderr = process.stderr.read()
            print(f"Failed to initialize submodules: {stderr}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Failed to initialize submodules: {e}")
        sys.exit(1)

    print("Building PyTorch with SYCL support...")
    try:
        # First verify the Intel compiler works
        print("Verifying Intel compiler...")
        result = subprocess.run([icpx_path, "--version"], 
                              env=build_env, 
                              capture_output=True, 
                              text=True)
        if result.returncode != 0:
            print(f"Error: Intel compiler test failed: {result.stderr}")
            sys.exit(1)
        print(f"Intel compiler version: {result.stdout.strip()}")
        
        # Create our own toolchain file with explicit GNU-style compilation settings
        toolchain_file = os.path.join(build_dir, "intel_toolchain.cmake")
        with open(toolchain_file, 'w') as f:
            f.write("""
set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_C_COMPILER_ID "GNU")
set(CMAKE_CXX_COMPILER_ID "GNU")
set(CMAKE_C_COMPILER_FORCED TRUE)
set(CMAKE_CXX_COMPILER_FORCED TRUE)
set(CMAKE_C_COMPILER_WORKS TRUE)
set(CMAKE_CXX_COMPILER_WORKS TRUE)
set(CMAKE_C_FLAGS_INIT "-march=native -O2 -fPIC -fno-ms-extensions")
set(CMAKE_CXX_FLAGS_INIT "-march=native -O2 -std=c++17 -fPIC -fno-ms-extensions")
set(CMAKE_SHARED_LINKER_FLAGS_INIT "-Wl,--export-all-symbols")
set(CMAKE_EXE_LINKER_FLAGS_INIT "-Wl,--export-all-symbols")
""")

        print("Installing build requirements...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      cwd=clone_dir, env=build_env, check=True)

        # Run CMake configure step with enhanced error checking
        print("Configuring CMake build...")
        cmake_args = [
            "-GNinja",
            f"-DCMAKE_TOOLCHAIN_FILE={toolchain_file}",
            f"-DCMAKE_C_COMPILER={icx_path}",
            f"-DCMAKE_CXX_COMPILER={icpx_path}",
            "-DBUILD_SHARED_LIBS=ON",
            "-DCMAKE_BUILD_TYPE=Release",
            f"-DPYTHON_EXECUTABLE={sys.executable}",
            "-DUSE_CUDA=OFF",
            "-DUSE_ROCM=OFF",
            "-DUSE_XPU=ON",
            "-DUSE_SYCL=ON",
            "-DUSE_OPENMP=ON",
            "-DUSE_MKLDNN=ON",
            "-DUSE_ITT=ON",
            "-DBUILD_TEST=OFF",
            "-DBUILD_PYTHON=True",
            "-DUSE_NUMPY=True",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"
        ]
        
        process = subprocess.Popen(
            ["cmake", ".."] + cmake_args,
            cwd=build_dir,
            env=build_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Monitor CMake output
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
        
        if process.poll() != 0:
            stderr = process.stderr.read()
            print(f"CMake configuration failed: {stderr}")
            sys.exit(1)

        print("Building PyTorch...")
        process = subprocess.Popen(
            ["cmake", "--build", ".", "--config", "Release"],
            cwd=build_dir,
            env=build_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
        
        if process.poll() != 0:
            stderr = process.stderr.read()
            print(f"Build failed: {stderr}")
            sys.exit(1)

        print("Installing PyTorch...")
        process = subprocess.Popen(
            ["cmake", "--install", "."],
            cwd=build_dir,
            env=build_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
        
        if process.poll() != 0:
            stderr = process.stderr.read()
            print(f"Installation failed: {stderr}")
            sys.exit(1)

        print("PyTorch built and installed successfully with SYCL support.")
    except Exception as e:
        print(f"PyTorch build/install failed: {e}")
        print("\nTroubleshooting information:")
        print("1. Verify Intel oneAPI is properly installed")
        print("2. Check environment variables:")
        for env_var in ['PATH', 'LIB', 'INCLUDE']:
            print(f"   {env_var}={build_env.get(env_var, '')}")
        print("3. Check CMake configuration logs in build directory")
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
    # Check for required modules
    if not ensure_module('winshell'):
        print("Could not set up automatic startup - winshell module not available")
        return False
    
    if not ensure_module('win32com.client', 'pywin32'):
        print("Could not set up automatic startup - pywin32 module not available")
        return False

    try:
        # Now that we know the modules are available, import them
        import winshell
        import win32com.client

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
    except Exception as e:
        print(f"Failed to create startup shortcut: {e}")
        return False

# Ensure winshell and pywin32 are installed for shortcut creation
import importlib
import subprocess

def ensure_module(module_name, pip_name=None):
    try:
        return importlib.import_module(module_name)
    except ImportError:
        print(f"Module '{module_name}' not found. Attempting to install...")
        pip_pkg = pip_name if pip_name else module_name
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', pip_pkg])
        return importlib.import_module(module_name)

# Try to import winshell and win32com.client, install if missing
try:
    winshell = ensure_module('winshell')
    win32com = ensure_module('win32com')
    win32com_client = ensure_module('win32com.client')
except Exception as e:
    print(f"Could not import or install required modules for persistent oneAPI shortcut: {e}")
    winshell = None
    win32com_client = None

def is_oneapi_installed():
    """
    Check if Intel oneAPI is already installed by looking for key components.
    Returns True if oneAPI is detected, False otherwise.
    """
    print("Checking for Intel oneAPI installation...")
    
    # Check for key paths
    setvars_path = pathlib.Path("C:/Program Files (x86)/Intel/oneAPI/setvars.bat")
    compiler_path = pathlib.Path("C:/Program Files (x86)/Intel/oneAPI/compiler/latest/windows/bin/intel64/icx.exe")
    
    if setvars_path.exists() and compiler_path.exists():
        print("Intel oneAPI appears to be installed.")
        return True
    
    print("Intel oneAPI installation not detected.")
    return False

def install_oneapi():
    """
    Install Intel oneAPI Base Toolkit.
    Returns True if installation succeeds, False otherwise.
    """
    print("Installing Intel oneAPI Base Toolkit...")
    
    # Create downloads directory if it doesn't exist
    downloads_dir = pathlib.Path(__file__).parent / "downloads"
    downloads_dir.mkdir(exist_ok=True)
    
    # First, download the web installer
    installer_url = "https://registrationcenter-download.intel.com/akdlm/IRC_NAS/992857e9-c93d-45a9-8d23-e4b8f31479c8/w_BaseKit_p_2024.0.0.49563_offline.exe"
    installer_path = downloads_dir / "w_BaseKit_offline.exe"
    
    if not installer_path.exists():
        print("Downloading Intel oneAPI Base Toolkit installer...")
        try:
            # Use aria2c for faster download with progress
            aria2c_path = pathlib.Path(__file__).parent / "aria2c.exe"
            if not aria2c_path.exists():
                print("aria2c.exe not found. Using standard download method.")
                subprocess.run([
                    "powershell",
                    "-Command",
                    f"(New-Object Net.WebClient).DownloadFile('{installer_url}', '{installer_path}')"
                ], check=True)
            else:
                subprocess.run([
                    str(aria2c_path),
                    "--allow-overwrite=true",
                    "--auto-file-renaming=false",
                    "-c",
                    "-x", "16",
                    "-s", "16",
                    "-j", "16",
                    installer_url,
                    "-d", str(downloads_dir),
                    "-o", "w_BaseKit_offline.exe"
                ], check=True)
        except Exception as e:
            print(f"Failed to download oneAPI installer: {e}")
            return False
    
    # Run the installer silently
    print("Running Intel oneAPI installer (this may take a while)...")
    try:
        # Create config file for silent install
        config_file = downloads_dir / "installer_config.txt"
        config_file.write_text("""
ACCEPT_EULA=accept
CONTINUE_WITH_OPTIONAL_ERROR=yes
PSET_INSTALL_DIR=C:\\Program Files (x86)\\Intel\\oneAPI
CONTINUE_WITH_INSTALLDIR_OVERWRITE=yes
COMPONENTS=ALL
ARCH_SELECTED=ALL
COMPONENTS_COMPILER_FORTRAN_COMMON_0=1
COMPONENTS_COMPILER_CPP_COMMON_0=1
COMPONENTS_COMPILER_DPCPP_0=1
COMPONENTS_VTUNE_PROFILER_0=1
COMPONENTS_PERFORMANCE_PRIMITIVES_0=1
COMPONENTS_PERFORMANCE_LIBRARIES_0=0
COMPONENTS_MKLMAT_CORE_0=1
COMPONENTS_COMP_DOC_0=1
INSTALL_MODE=NONRPM
""")
        
        # Run installer with config
        result = subprocess.run([
            str(installer_path),
            "-s",
            "--log-dir", str(downloads_dir),
            "--ignore-errors",
            "-x",
            "--components=intel.oneapi.win.dpcpp-compiler:intel.oneapi.win.cpp-compiler",
            "-a", f"--silent --log {downloads_dir / 'oneapi_install.log'}"
        ], check=True)
        
        if result.returncode != 0:
            print(f"oneAPI installer failed with return code {result.returncode}")
            return False
        
        print("Intel oneAPI installation completed.")
        return True
        
    except Exception as e:
        print(f"Failed to install Intel oneAPI: {e}")
        return False

def install_build_tools():
    """Install required build tools for PyTorch SYCL compilation."""
    print("Installing required build tools...")
    
    try:
        # Install Python requirements
        subprocess.run([
            sys.executable, "-m", "pip", "install",
            "ninja", "cmake>=3.22", "setuptools", "wheel",
            "--upgrade"
        ], check=True)
        print("Python build requirements installed successfully.")
        return True
    except Exception as e:
        print(f"Failed to install Python build requirements: {e}")
        return False

def install_vs_build_tools():
    """
    Install Visual Studio Build Tools required for PyTorch SYCL compilation.
    Returns True if installation succeeds, False otherwise.
    """
    print("Installing Visual Studio Build Tools...")
    
    # Create downloads directory if it doesn't exist
    downloads_dir = pathlib.Path(__file__).parent / "downloads"
    downloads_dir.mkdir(exist_ok=True)
    
    # Download VS Build Tools bootstrapper if not present
    vs_installer = downloads_dir / "vs_BuildTools.exe"
    if not vs_installer.exists():
        print("Downloading Visual Studio Build Tools installer...")
        try:
            url = "https://aka.ms/vs/17/release/vs_BuildTools.exe"
            subprocess.run([
                "powershell",
                "-Command",
                f"(New-Object Net.WebClient).DownloadFile('{url}', '{vs_installer}')"
            ], check=True)
        except Exception as e:
            print(f"Failed to download VS Build Tools installer: {e}")
            return False
    
    try:
        # Run the installer with required workloads
        print("Running Visual Studio Build Tools installer (this may take a while)...")
        result = subprocess.run([
            str(vs_installer),
            "--quiet", "--wait", "--norestart",
            "--nocache",
            "--installPath", "C:\\BuildTools",
            "--add", "Microsoft.VisualStudio.Workload.VCTools",
            "--add", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "--add", "Microsoft.VisualStudio.Component.Windows10SDK.19041",
            "--includeRecommended"
        ], check=True)
        
        if result.returncode != 0:
            print(f"VS Build Tools installer failed with return code {result.returncode}")
            return False
        
        print("Visual Studio Build Tools installation completed.")
        return True
        
    except Exception as e:
        print(f"Failed to install Visual Studio Build Tools: {e}")
        return False

def main():
    # First check for Intel oneAPI installation
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
    print("You can set up the oneAPI environment in two ways:")
    print("1. Automatically on login (requires additional setup)")
    print("2. Manually by running: C:\\Program Files (x86)\\Intel\\oneAPI\\setvars.bat")
    
    answer = input("\nWould you like to set up automatic oneAPI environment initialization? (Y/N): ").strip().lower()
    if answer == 'y':
        if add_setvars_to_startup():
            print("\noneAPI environment will now be set up automatically on every login.")
            print("A command prompt will open with oneAPI ready when you log in.")
        else:
            print("\nAutomatic setup failed. You can still use oneAPI by running:")
            print('  "C:\\Program Files (x86)\\Intel\\oneAPI\\setvars.bat"')
    
    sys.exit(0)

if __name__ == "__main__":
    main()
