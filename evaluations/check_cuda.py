import os
import subprocess
import shutil

def check_cuda():
    """
    Checks whether CUDA (nvcc) is installed by:
      1) Attempting 'nvcc --version' in a fresh 'cmd /c' call.
      2) If not found, scanning typical install folders like 
         C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\vXX.X\\bin\\nvcc.exe
         and directly calling them with 'cmd /c'.
    Returns the parsed version string (e.g., '11.8') or None if not found.
    Prints stdout/stderr inline, so logs appear in the same console.
    """

    print("Running 'nvcc --version' in a fresh CMD context...")

    # 1) Try PATH-based detection in a fresh 'cmd /c'
    cmd_line = 'cmd /c "nvcc --version"'
    nvcc_proc = subprocess.run(cmd_line, shell=True, capture_output=True, text=True)

    # Show the outputs in the current console
    if nvcc_proc.stdout:
        print("[nvcc stdout]:")
        print(nvcc_proc.stdout)
    if nvcc_proc.stderr:
        print("[nvcc stderr]:")
        print(nvcc_proc.stderr)

    if nvcc_proc.returncode == 0:
        # Parse out the version
        for line in nvcc_proc.stdout.splitlines():
            if "release" in line:
                parts = line.strip().split("release")
                if len(parts) > 1:
                    version = parts[1].split(",")[0].strip()
                    print(f"✅ Detected CUDA version: {version}")
                    return version
        print("⚠️ 'nvcc --version' ran, but no 'release' keyword found.")
        return None
    else:
        print("❌ 'nvcc --version' command failed (not on PATH or error).")

    # 2) If PATH-based detection fails, check fallback directories
    fallback_paths = []
    base_dir = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"
    if os.path.isdir(base_dir):
        for folder_name in os.listdir(base_dir):
            candidate = os.path.join(base_dir, folder_name, "bin", "nvcc.exe")
            if os.path.isfile(candidate):
                fallback_paths.append(candidate)

    # Add known versions
    known_versions = ["11.8", "12.1", "12.4"]  # Adjust as needed
    for ver in known_versions:
        candidate = rf"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v{ver}\bin\nvcc.exe"
        if os.path.isfile(candidate) and candidate not in fallback_paths:
            fallback_paths.append(candidate)

    # 3) Direct-call each fallback path
    for path_to_nvcc in fallback_paths:
        print(f"Attempting direct call to: {path_to_nvcc}")
        direct_cmd = f'cmd /c "{path_to_nvcc} --version"'
        proc = subprocess.run(direct_cmd, shell=True, capture_output=True, text=True)

        if proc.stdout:
            print("[nvcc stdout]:")
            print(proc.stdout)
        if proc.stderr:
            print("[nvcc stderr]:")
            print(proc.stderr)

        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if "release" in line:
                    parts = line.strip().split("release")
                    if len(parts) > 1:
                        version = parts[1].split(",")[0].strip()
                        print(f"✅ Found CUDA version: {version} (via {path_to_nvcc})")
                        return version
        else:
            print(f"Command failed for {path_to_nvcc}. Returncode: {proc.returncode}")

    print("❌ Could not detect CUDA version. Possibly needs a reboot or wasn't installed in default path.")
    return None

def is_cuda_installed():
    """Return True if we can parse a version from 'nvcc --version' or fallback paths."""
    return bool(check_cuda())

if __name__ == "__main__":
    ver = check_cuda()
    if ver:
        print(f"Final Detected CUDA version: {ver}")
    else:
        print("No CUDA detected.")
