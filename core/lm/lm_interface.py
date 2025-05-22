import json
import re
import pathlib
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

# Adjust imports to use absolute paths consistently
from core.utils.region.mapper import map_elements_to_coords
from .handlers.openai_handler import call_openai_model
from .handlers.lmstudio_handler import call_lmstudio_model

# Ensure the project's core folder is on sys.path for exceptions
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent / "core"))
from exceptions import ModelNotRecognizedException

# Ensure the config folder is on sys.path for Config
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent / "config"))
from config import Config


def handle_llm_response(response, os_interface, parsed_ui=None, screenshot_path=None):
    """Parse an LLM response (JSON inside a markdown code‑block) and execute the described UI action via `os_interface`."""
    try:
        # Defensive: If response is an error string, print and return
        if response.strip().startswith("[ERROR]"):
            print(response)
            return
        code_block = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if not code_block:
            print("⚠️ Could not extract a valid JSON action from LLM response.")
            print(f"[DEBUG] Raw LLM response: {response}")
            return

        action_list = json.loads(code_block.group(1))
        if not action_list:
            print("⚠️ JSON action list is empty.")
            return

        action = action_list[0]
        op_type = action.get("operation")

        if op_type == "press":
            keys = action.get("keys", [])
            if isinstance(keys, list) and len(keys) > 1:
                os_interface.press(keys)
            else:
                single = keys[0] if isinstance(keys, list) and keys else keys
                os_interface.press(single)
            print(f"⌨️ Simulated Key Press: {keys}")

        elif op_type == "click":
            target_text = action.get("text", "").strip().lower()
            if not target_text or not parsed_ui or not screenshot_path:
                print(f"🖱️ Would click: {action}")
                return

            coords_map = map_elements_to_coords(parsed_ui, screenshot_path)

            matched_coords = None
            for content_key, element in coords_map.items():
                if target_text in content_key:
                    matched_coords = element["center"]
                    print(f"🔍 Found partial match: '{element['content']}' at {matched_coords}")
                    break

            if matched_coords:
                x, y = matched_coords
                os_interface.click(x, y)
                print(f"🖱️ Clicked on '{target_text}' at ({x}, {y})")
            else:
                print(f"⚠️ Couldn't find coordinates for '{target_text}' in UI.")

        elif op_type == "write":
            text = action.get("text", "")
            os_interface.write(text)
            print(f"⌨️ Typed: {text}")

        elif op_type == "take_screenshot":
            print("📸 Would take a new screenshot (handled externally).")

        elif op_type == "done":
            print("✅ Task complete.")

    except Exception as e:
        print(f"❌ Error parsing or executing LLM response: {e}")
        print(f"[DEBUG] Raw LLM response: {response}")


class MainInterface:
    """High‑level interface for obtaining the next UI action from an LLM."""

    async def get_next_action(self, model, messages, objective, session_id, screenshot_path):
        """
        Send the `messages` conversation context to the chosen model and
        return its raw text response.

        Returns:
            tuple[str, str, None]: (response_text, session_id, None)
        """
        print(f"[MainInterface] Using model: {model}")

        config = Config()
        api_source, _ = config.get_api_source()

        if api_source == "openai":
            # call_openai_model now returns a string (either JSON string for actions, or plain text for other stages)
            response_str = await call_openai_model(messages, objective, model)
            
            # For visual, thinking, steps stages, the response_str is the direct text.
            # For action stage, response_str is a JSON string that handle_llm_response will parse.
            # The `get_next_action` in `operate.py` for non-action stages directly uses the first element of the tuple.
            # The `handle_llm_response` in `operate.py` for action stage expects the JSON to be parsed from the string.

            # No change needed here if call_openai_model returns a string as expected by callers.
            # The `DEBUG` print might show a JSON string or plain text.
            print(f"[DEBUG] OpenAI Response String: {response_str}") 
            return (response_str, session_id, None)
        elif api_source == "lmstudio":
            response = await call_lmstudio_model(messages, objective, model)
            print(f"[DEBUG] LMStudio Response: {response}")
            return (response, session_id, None)

        raise ModelNotRecognizedException(model)


# Self‑test
if __name__ == "__main__":
    import asyncio

    async def _test():
        interface = MainInterface()
        text, sid, _ = await interface.get_next_action(
            model="gpt-4",
            messages=["Hello"],
            objective="Test objective",
            session_id="session123",
            screenshot_path="dummy.png"
        )
        print("Test result:", text)

    asyncio.run(_test())
