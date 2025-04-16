import json
import re

def handle_llm_response(response, os_interface):
    try:
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
            if "location" in action:
                x, y = map(int, action["location"].split())
                os_interface.move_mouse(x, y, duration=0.3)
                os_interface.click_mouse()
                print(f"🖱️ Clicked at ({x}, {y})")
            else:
                print(f"🖱️ Text-based click requested: {action.get('text')} (not yet implemented)")

        elif op_type == "write":
            text = action.get("text", "")
            os_interface.type_text(text)
            print(f"⌨️ Typed text: {text}")

        elif op_type == "take_screenshot":
            path = os_interface.take_screenshot("automoy_screenshot.png")
            print(f"📸 Screenshot saved to: {path}")

        elif op_type == "done":
            print(f"✅ Task marked complete. Summary: {action.get('summary', '')}")

        else:
            print(f"⚠️ Unknown operation type: {op_type}")

    except Exception as e:
        print(f"❌ Error parsing or executing LLM response: {e}")
