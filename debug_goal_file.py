#!/usr/bin/env python3
"""
Debug goal file reading issue
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def debug_goal_file():
    print("🔍 Debug Goal File Reading")
    print("=" * 40)
    
    # Import the same path logic as main.py
    from core.data_models import GOAL_REQUEST_FILE
    
    print(f"1. Goal file path: {GOAL_REQUEST_FILE}")
    print(f"2. Absolute path: {os.path.abspath(GOAL_REQUEST_FILE)}")
    print(f"3. File exists: {os.path.exists(GOAL_REQUEST_FILE)}")
    
    if os.path.exists(GOAL_REQUEST_FILE):
        print(f"4. File size: {os.path.getsize(GOAL_REQUEST_FILE)} bytes")
        
        # Try reading with different encodings
        for encoding in ['utf-8-sig', 'utf-8', 'utf-16', 'cp1252']:
            try:
                with open(GOAL_REQUEST_FILE, 'r', encoding=encoding) as f:
                    content = f.read().strip()
                    print(f"5. Content with {encoding}: {len(content)} chars")
                    if content:
                        print(f"   First 100 chars: {content[:100]}")
                        # Try to parse as JSON
                        import json
                        try:
                            data = json.loads(content)
                            print(f"   ✅ Valid JSON: {data}")
                            return True
                        except json.JSONDecodeError as e:
                            print(f"   ❌ JSON Error: {e}")
                    break
            except Exception as e:
                print(f"   ❌ {encoding} failed: {e}")
                continue
    else:
        print("4. ❌ File does not exist!")
    
    return False

if __name__ == "__main__":
    success = debug_goal_file()
    if not success:
        print("\n🔧 Attempting to recreate goal file...")
        goal_content = {
            "objective": "Open Google Chrome by clicking the Chrome icon",
            "steps": [
                "Take a screenshot to identify the Chrome icon on the desktop",
                "Use OmniParser to analyze the screenshot and locate Chrome icon", 
                "Click the Chrome icon to launch the browser",
                "Verify Chrome has opened successfully"
            ]
        }
        
        import json
        from core.data_models import GOAL_REQUEST_FILE
        
        try:
            with open(GOAL_REQUEST_FILE, 'w', encoding='utf-8') as f:
                json.dump(goal_content, f, indent=4)
            print(f"✅ Goal file recreated at: {GOAL_REQUEST_FILE}")
        except Exception as e:
            print(f"❌ Failed to recreate: {e}")
