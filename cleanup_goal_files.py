import os
import sys

# Add project root to path
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

from core.data_models import GOAL_REQUEST_FILE

# Files to clean up
files_to_clean = [
    GOAL_REQUEST_FILE,
    os.path.join("debug", "logs", "gui", "goal_request.json"),
    "goal_request.json"  # In case there's one at root
]

print("Cleaning up goal request files...")
for file_path in files_to_clean:
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"✓ Removed: {file_path}")
        except Exception as e:
            print(f"✗ Failed to remove {file_path}: {e}")
    else:
        print(f"- Not found: {file_path}")

print("Cleanup complete!")
