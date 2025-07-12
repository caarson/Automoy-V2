import sys
import os
import json

# Add project root to path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

# Test JSON parsing directly
test_json_array = '''[
  {
    "step_number": 1,
    "description": "Open the Windows Start Menu by clicking the Start button or pressing the Windows key",
    "action_type": "key",
    "target": "win",
    "verification": "Confirm Start Menu is visible"
  },
  {
    "step_number": 2,
    "description": "Type 'Calculator' in the search box to find the Calculator app",
    "action_type": "type",
    "target": "calculator",
    "verification": "Calculator appears in search results"
  }
]'''

print("Testing JSON parsing...")
try:
    parsed = json.loads(test_json_array)
    print(f"✓ Parsed successfully: {type(parsed)} with {len(parsed)} items")
    print(f"First item: {parsed[0]}")
    print(f"Has step_number: {'step_number' in parsed[0]}")
except Exception as e:
    print(f"✗ Failed to parse: {e}")

# Test LMStudio handler detection logic
print("\nTesting detection logic...")
if isinstance(parsed, list) and len(parsed) > 0:
    if "step_number" in parsed[0]:
        print("✓ Would be detected as step array")
    else:
        print("✗ Would be detected as action array")
else:
    print("✗ Not detected as list")
