import json
import re
import pathlib
import sys
import os
import logging  # Added logging

# Get a logger for this module
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

# Adjust imports to use absolute paths consistently
from core.utils.region.mapper import map_elements_to_coords  # This might be unused by the new handle_llm_response
from .handlers.openai_handler import call_openai_model
from .handlers.lmstudio_handler import call_lmstudio_model

# Ensure the project's core folder is on sys.path for exceptions
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent / "core"))
from exceptions import ModelNotRecognizedException

# Ensure the config folder is on sys.path for Config
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent / "config"))
from config import Config


# Replaced original handle_llm_response with a new version
# to match usage in core/operate.py for parsing and cleaning LLM outputs.
def handle_llm_response(
    raw_response_text: str,
    context_description: str,  # e.g., "visual analysis", "thinking process", "action generation"
    is_json: bool = False,
    llm_interface=None  # Parameter is present as per operate.py's usage
) -> any:
    """
    Processes raw LLM response text.
    If is_json is True, attempts to extract and parse JSON from a markdown code block.
    Otherwise, (or for the text part if JSON extraction fails), cleans the text,
    notably by stripping <think>...</think> tags and other common XML/HTML tags.
    """
    logger.debug(f"Handling LLM response for '{context_description}'. Raw length: {len(raw_response_text)}. is_json: {is_json}")

    processed_text = raw_response_text

    # 1. Strip <think>...</think> tags and other unwanted XML/HTML-like tags from the text.
    # This should happen regardless of whether we expect JSON, as thinking might be around the JSON.
    def strip_tags(text):
        if not isinstance(text, str):  # Ensure text is a string
            logger.warning(f"Attempted to strip tags from non-string input: {type(text)}")
            return ""  # Or return the input as is, or raise error
        # Remove <think>...</think> tags
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        # Remove any simple, standalone XML/HTML tag like <tag_name> or <tag_name/>
        # This is a basic attempt and might need refinement if complex HTML/XML is possible and undesired.
        text = re.sub(r"<\\w+/?>(?!</\\w+>)", "", text)  # Removes <tag> but not <tag>content</tag>
        text = re.sub(r"<([A-Za-z][A-Za-z0-9]*)\\b[^>]*>(.*?)</\\1>", "\\2", text, flags=re.DOTALL)  # Strips outer tags if content is desired
        # A more aggressive stripping of any tag:
        # text = re.sub(r"<[^>]+>", "", text)
        return text.strip()

    if not is_json:
        processed_text = strip_tags(str(raw_response_text))  # Ensure input is string
        logger.debug(f"Cleaned text for '{context_description}': {processed_text[:300]}...")
        return processed_text

    # 2. If is_json is True, try to extract and parse JSON.
    # The raw_response_text itself might contain tags around the JSON block.
    text_to_search_json_in = strip_tags(str(raw_response_text))  # Clean before searching for JSON block

    json_match = re.search(r"```json\\s*(.*?)\\s*```", text_to_search_json_in, re.DOTALL)
    json_str_to_parse = None

    if json_match:
        json_str_to_parse = json_match.group(1).strip()
    else:
        # If no markdown block, the cleaned text itself might be JSON.
        # This is risky, as it might be a string that just happens to start with { or [
        # For now, we will attempt to parse it if it looks like JSON, but log a warning.
        if text_to_search_json_in.startswith("{") and text_to_search_json_in.endswith("}") or \
           text_to_search_json_in.startswith("[") and text_to_search_json_in.endswith("]"):
            logger.warning(f"No JSON markdown code block found for '{context_description}' when is_json=True. Attempting to parse entire cleaned text.")
            json_str_to_parse = text_to_search_json_in
        else:
            logger.error(f"No JSON markdown code block found for '{context_description}' and cleaned text does not appear to be a JSON object/array. Cleaned text: {text_to_search_json_in[:300]}...")
            return {"error": "JSON_NOT_FOUND", "message": f"Expected JSON for {context_description} but couldn't find ```json block or parseable JSON structure.", "cleaned_text_preview": text_to_search_json_in[:200]}

    if json_str_to_parse:
        try:
            # Further clean the extracted JSON string from any potential comment lines if LLM added them
            json_str_to_parse = re.sub(r"//.*?\\n", "\\n", json_str_to_parse)  # Remove // comments
            json_str_to_parse = re.sub(r"#.*?\\n", "\\n", json_str_to_parse)  # Remove # comments
            parsed_json = json.loads(json_str_to_parse)
            logger.debug(f"Successfully parsed JSON for '{context_description}'.")
            return parsed_json
        except json.JSONDecodeError as e:
            logger.error(f"JSONDecodeError for '{context_description}': {e}. JSON string was: '{json_str_to_parse[:500]}...'")
            return {"error": "JSON_DECODE_ERROR", "message": str(e), "json_string_preview": json_str_to_parse[:200]}

    # Fallback if json_str_to_parse was not set (e.g. markdown found, but group(1) was empty - unlikely)
    logger.error(f"JSON processing failed unexpectedly for '{context_description}'. No JSON string was identified for parsing.")
    return {"error": "JSON_PROCESSING_FAILED", "message": f"Problem in JSON processing logic for {context_description}."}


class MainInterface:
    """High‑level interface for obtaining the next UI action from an LLM."""

    def __init__(self):  # Add __init__
        self.config = Config()
        self.api_source, _ = self.config.get_api_source()
        print(f"[MainInterface] Initialized with API source: {self.api_source}")

    async def get_next_action(self, model, messages, objective, session_id, screenshot_path):
        """
        Send the `messages` conversation context to the chosen model and
        return its raw text response.

        Returns:
            tuple[str, str, None]: (response_text, session_id, None)
        """
        print(f"[MainInterface] Using model: {model} via API source: {self.api_source}")  # Updated log

        if self.api_source == "openai":
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
        elif self.api_source == "lmstudio":
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
