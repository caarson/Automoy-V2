"""
Test the improved keyboard functionality in Automoy
"""

import sys
import os
import time

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.operate import ActionExecutor

def test_keyboard_actions():
    print("=== TESTING IMPROVED KEYBOARD FUNCTIONALITY ===")
    print("Make sure to have a text editor or notepad open!")
    print("Starting tests in 3 seconds...")
    time.sleep(3)
    
    # Create action executor
    executor = ActionExecutor()
    
    # Test individual keys
    test_actions = [
        {"type": "key", "key": "a"},
        {"type": "key", "key": "space"},
        {"type": "key", "key": "b"},
        {"type": "key", "key": "space"},
        {"type": "key", "key": "c"},
        {"type": "key", "key": "enter"},
        {"type": "type", "text": "Hello World!"},
        {"type": "key", "key": "enter"},
        {"type": "key_sequence", "keys": ["ctrl", "a"]},
        {"type": "key", "key": "delete"},
    ]
    
    print("Executing test actions...")
    for i, action in enumerate(test_actions, 1):
        print(f"Test {i}: {action}")
        try:
            result = executor.execute(action)
            print(f"   Result: {result}")
        except Exception as e:
            print(f"   ERROR: {e}")
        time.sleep(0.5)  # Brief pause between actions
    
    print("\n=== TESTING COMPLETE ===")
    print("Check your text editor to see if the keys worked properly!")

if __name__ == "__main__":
    test_keyboard_actions()
