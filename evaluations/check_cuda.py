import os
import subprocess
import shutil

# Adjust if you want to match the same versions from cuda_setup.py
CUDA_SUPPORTED_VERSIONS = [
    "11.8",
    "12.1",
    "12.4"
]

# If you have extra versions like 12.6, add them.
EXTRA_KNOWN_VERSIONS = []

def find_nvcc_in_standard_paths():
    """
    Returns the absolute path to nvcc.exe if found in standard CUDA directories,
    or None if not found.
    """
    base_dir = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"
    possible_paths = []

    if os.path.isdir(base_dir):
        for folder_name in os.listdir(base_dir):
            candidate = os.path.join(base_dir, folder_name, "bin", "nvcc.exe")
            if os.path.isfile(candidate):
                possible_paths.append(candidate)

    all_versions = CUDA_SUPPORTED_VERSIONS + EXTRA_KNOWN_VERSIONS
    for v in all_versions:
        candidate = rf"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v{v}\bin\nvcc.exe"
        if os.path.isfile(candidate):
            possible_paths.append(candidate)

    for p in possible_paths:
        if os.path.exists(p):
            return p
    return None

def direct_call_to_nvcc(nvcc_path):
    """
    Directly call e.g. 'C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.1\\bin\\nvcc.exe --version'
    and parse out the version. Return version string or None.
    """
    try:
        result = subprocess.run([nvcc_path, "--version"], capture_output=True, text=True, check=True)
        output = result.stdout
        for line in output.splitlines():
            if "release" in line.lower():
                # line might be: 'Cuda compilation tools, release 11.8, V11.8.89'
                parts = line.lower().split("release")
                if len(parts) > 1:
                    return parts[1].split(",")[0].strip()
    except Exception as e:
        print(f"Error calling {nvcc_path}: {e}")
    return None

def get_installed_cuda_version():
    """
    1. If 'nvcc' is on PATH, call 'nvcc --version' to parse version.
    2. Else if physically found in standard path, call it directly there.
    3. Return version string or None.
    """
    if shutil.which("nvcc"):
        # Try PATH-based detection
        try:
            cmd = ["nvcc", "--version"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            for line in result.stdout.splitlines():
                if "release" in line:
                    parts = line.split("release")
                    if len(parts) > 1:
                        return parts[1].split(",")[0].strip()
        except Exception as e:
            print(f"Error calling 'nvcc --version': {e}")

    # If PATH-based detection fails or PATH not updated, do direct call in standard path
    local_nvcc = find_nvcc_in_standard_paths()
    if local_nvcc:
        ver = direct_call_to_nvcc(local_nvcc)
        if ver:
            return ver

    return None

def is_cuda_installed():
    """
    Simple boolean check. Returns True if we can parse a CUDA version.
    """
    version = get_installed_cuda_version()
    return bool(version)

if __name__ == "__main__":
    v = get_installed_cuda_version()
    if v:
        print(f"Detected CUDA version: {v}")
    else:
        print("No CUDA detected.")
