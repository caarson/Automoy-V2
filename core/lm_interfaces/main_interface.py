import json
from .handlers.openai_handler import call_openai_model
from .handlers.lmstudio_handler import call_lmstudio_model
import pathlib
import sys

# Ensure the project's core folder is on sys.path for exceptions
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent / "core"))
from exceptions import ModelNotRecognizedException

# Ensure the config folder is on sys.path for Config
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent / "config"))
from config import Config

class MainInterface:
    async def get_next_action(self, model, messages, objective, session_id, screenshot_path):
        """
        Sends the conversation `messages` to the chosen model (either OpenAI or LMStudio)
        and returns the raw text response.
        
        Returns a tuple: (response_text, session_id, None)
        """
        print(f"[MainInterface] Using model: {model}")

        # Load configuration and determine which API source to use
        config = Config()
        api_source, _ = config.get_api_source()

        if api_source == "openai":
            response = await call_openai_model(messages, objective, model)
            print(f"[DEBUG] OpenAI Response: {response}")
            return (response, session_id, None)
        elif api_source == "lmstudio":
            response = await call_lmstudio_model(messages, objective, model)
            print(f"[DEBUG] LMStudio Response: {response}")
            return (response, session_id, None)

        raise ModelNotRecognizedException(model)

# For testing purposes:
if __name__ == "__main__":
    import asyncio

    async def test():
        interface = MainInterface()
        result = await interface.get_next_action("gpt-4", ["Hello"], "Test objective", "session123", "dummy.png")
        print("Test result:", result)

    asyncio.run(test())
