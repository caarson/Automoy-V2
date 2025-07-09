import json
import os

# Create goal request file with proper encoding
goal_data = {"goal": "open calculator"}

goal_file_path = "goal_request.json"
with open(goal_file_path, 'w', encoding='utf-8') as f:
    json.dump(goal_data, f)

print(f"Created goal request file: {goal_file_path}")

# Verify the file
with open(goal_file_path, 'r', encoding='utf-8') as f:
    content = f.read()
    print(f"File content: {content}")
    print(f"File size: {len(content)} characters")
