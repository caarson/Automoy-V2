
import subprocess
import sys
import os

def get_conda_env_python_executable(env_name):
    """
    Get the Python executable path for a given conda environment.
    """
    try:
        # Get the path to the conda executable
        conda_exe = "conda.exe"  # For Windows
        
        # Get the info about the conda environments
        result = subprocess.run([conda_exe, "info", "--envs", "--json"], capture_output=True, text=True, check=True)
        import json
        envs = json.loads(result.stdout)
        
        # Find the path for the specified environment
        for env in envs['envs']:
            if env.endswith(env_name):
                python_exe = os.path.join(env, "python.exe")
                if os.path.exists(python_exe):
                    return python_exe
    except Exception as e:
        print(f"Error finding Python executable for conda env {env_name}: {e}")
        return None
    
    return None

def main():
    """
    Main function to run Automoy.
    """
    # Get the absolute path to the directory containing this script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Define the paths to the main and GUI scripts
    core_main_path = os.path.join(script_dir, "core", "main.py")
    gui_main_path = os.path.join(script_dir, "gui", "gui.py")

    # Get the python executable from the automoy_env conda environment
    python_executable = get_conda_env_python_executable("automoy_env")

    if not python_executable:
        print("Could not find the python executable for the 'automoy_env' conda environment.")
        print("Please make sure that the 'automoy_env' is created and activated.")
        sys.exit(1)

    # Start the backend
    print(f"Starting backend with {python_executable}...")
    backend_process = subprocess.Popen([python_executable, core_main_path])

    # Start the GUI
    print(f"Starting GUI with {python_executable}...")
    gui_process = subprocess.Popen([python_executable, gui_main_path])

    # Wait for both processes to complete
    backend_process.wait()
    gui_process.wait()

if __name__ == "__main__":
    main()
