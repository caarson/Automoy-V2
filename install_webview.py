import subprocess
import sys

# Install pywebview
print("Installing pywebview...")
result = subprocess.run([sys.executable, "-m", "pip", "install", "pywebview"], capture_output=True, text=True)

if result.returncode == 0:
    print("SUCCESS: pywebview installed!")
    print(result.stdout)
else:
    print("ERROR installing pywebview:")
    print(result.stderr)

# Test import
try:
    import pywebview
    print(f"SUCCESS: pywebview {pywebview.__version__} is ready!")
except ImportError as e:
    print(f"ERROR: pywebview still not available: {e}")
