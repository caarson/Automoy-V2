import json
import re
from utils.region.mapper import map_elements_to_coords

def handle_llm_response(response, os_interface, parsed_ui=None, screenshot_path=None):
    try:
        # Extract the JSON from the code block
        code_block = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if not code_block:
            print("⚠️ Could not extract a valid JSON action from LLM response.")
            return

        action_list = json.loads(code_block.group(1))
        action = action_list[0]
        op_type = action.get("operation")

        if op_type == "press":
            keys = action.get("keys", [])
            for key in keys:
                os_interface.press(key)
            print(f"⌨️ Simulated Key Press: {keys}")

        elif op_type == "click":
            text = action.get("text")
            if not text or not parsed_ui:
                print(f"🖱️ Would click: {action}")
                return

            coords = map_elements_to_coords(parsed_ui, screenshot_path)
            match = coords.get(text)
            if match:
                x, y = match
                os_interface.click(x, y)
                print(f"🖱️ Clicked on '{text}' at ({x}, {y})")
            else:
                print(f"⚠️ Couldn't find coordinates for '{text}'")

        elif op_type == "write":
            text = action.get("text", "")
            os_interface.write(text)
            print(f"⌨️ Typed: {text}")

        elif op_type == "take_screenshot":
            print("📸 Would take a new screenshot")

        elif op_type == "done":
            print("✅ Task complete.")

    except Exception as e:
        print(f"❌ Error parsing or executing LLM response: {e}")
