import json

goal_data = {
    "goal": "Take a screenshot and analyze what's on the screen"
}

with open('goal_request.json', 'w') as f:
    json.dump(goal_data, f, indent=2)

print("Goal submitted: Take a screenshot and analyze what's on the screen")
