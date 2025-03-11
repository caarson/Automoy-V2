import json

from handlers.openai_handler import call_openai_model
from handlers.lmstudio_handler import call_lmstudio_model

sys.path.append(str(pathlib.Path(__file__).parent.parent / "core"))
from exceptions import ModelNotRecognizedException

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent / "config"))
from config import Config  # Import Config class


async def get_next_action(model, messages, objective, session_id, screenshot_path):
    """
    get_next_action is responsible for sending the conversation `messages` to the chosen model
    (either OpenAI or LMStudio) and returning the raw text response.

    We REMOVED the unconditional calls to `preprocess_with_ocr_and_yolo`. Now this function
    only delegates to the model. If you need screenshot / OCR / YOLO, do it based on the AI's
    chosen actions in your main flow.
    """
    print(f"[handlers_api] Using model: {model}")

    # Load config and determine which API source to use (lmstudio or openai).
    config = Config()
    api_source, _ = config.get_api_source()

    # Call the model based on the determined API source.
    if api_source == "openai":
        response = await call_openai_model(messages, objective, model)
        print(f"[DEBUG] OpenAI Response: {response}")
        # Return the raw text plus session_id, no full_data (None by default).
        return (response, session_id, None)

    elif api_source == "lmstudio":
        response = await call_lmstudio_model(messages, objective, model)
        print(f"[DEBUG] LMStudio Response: {response}")
        # Return the raw text plus session_id, no full_data (None by default).
        return (response, session_id, None)

    # If we have neither openai nor lmstudio, raise an exception.
    raise ModelNotRecognizedException(model)
