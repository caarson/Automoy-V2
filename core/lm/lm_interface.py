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

# Import prompt templates and system prompts
sys.path.append(str(pathlib.Path(__file__).parent.parent / "prompts"))
from prompts import (
    THINKING_PROCESS_USER_PROMPT_TEMPLATE,
    STEP_GENERATION_USER_PROMPT_TEMPLATE,
    ACTION_GENERATION_SYSTEM_PROMPT,
    DEFAULT_PROMPT
)


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
        return processed_text    # 2. If is_json is True, try to extract and parse JSON.
    # The raw_response_text itself might contain tags around the JSON block.
    text_to_search_json_in = strip_tags(str(raw_response_text))  # Clean before searching for JSON block

    json_match = re.search(r"```json\s*(.*?)\s*```", text_to_search_json_in, re.DOTALL)
    json_str_to_parse = None

    if json_match:
        json_str_to_parse = json_match.group(1).strip()
    else:
        # If no markdown block, check if the cleaned text itself might be JSON.
        # Try to find JSON array or object patterns in the cleaned text
        cleaned_text = text_to_search_json_in.strip()
        
        # Look for JSON array pattern
        array_match = re.search(r'(\[.*?\])', cleaned_text, re.DOTALL)
        if array_match:
            json_str_to_parse = array_match.group(1).strip()
            logger.info(f"Found JSON array in cleaned text for '{context_description}'")
        # Look for JSON object pattern
        elif cleaned_text.startswith("{") and cleaned_text.endswith("}"):
            json_str_to_parse = cleaned_text
            logger.info(f"Found JSON object in cleaned text for '{context_description}'")
        # Try the entire cleaned text if it looks like JSON
        elif (cleaned_text.startswith("{") and cleaned_text.endswith("}")) or \
             (cleaned_text.startswith("[") and cleaned_text.endswith("]")):
            logger.warning(f"No JSON markdown code block found for '{context_description}' when is_json=True. Attempting to parse entire cleaned text.")
            json_str_to_parse = cleaned_text
        else:
            logger.error(f"No JSON markdown code block found for '{context_description}' and cleaned text does not appear to be a JSON object/array. Cleaned text: {cleaned_text[:300]}...")
            return {"error": "JSON_NOT_FOUND", "message": f"Expected JSON for {context_description} but couldn't find ```json block or parseable JSON structure.", "cleaned_text_preview": cleaned_text[:200]}

    if json_str_to_parse:
        try:            # Further clean the extracted JSON string from any potential comment lines if LLM added them
            json_str_to_parse = re.sub(r"//.*?\n", "\n", json_str_to_parse)  # Remove // comments
            json_str_to_parse = re.sub(r"#.*?\n", "\n", json_str_to_parse)  # Remove # comments
            parsed_json = json.loads(json_str_to_parse)
            logger.debug(f"Successfully parsed JSON for '{context_description}'.")

            # If the context is action generation and the parsed JSON is a list,
            # return the first element if the list is not empty.
            if context_description == "action generation" and isinstance(parsed_json, list):
                if len(parsed_json) > 0:
                    logger.info(f"Parsed JSON for action generation was a list. Returning first element: {parsed_json[0]}")
                    return parsed_json[0]
                else:
                    logger.error(f"Parsed JSON for action generation was an empty list. Original string: '{json_str_to_parse[:500]}...'")
                    return {"error": "EMPTY_ACTION_LIST", "message": "LLM returned an empty list for actions."}

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

    def construct_thinking_process_prompt(self, objective, visual_analysis_output, current_step_description, previous_action_summary, anchor_point_context=None):
        """
        Construct a prompt for thinking process generation based on objective and visual analysis.
        
        Args:
            objective: The main objective/goal
            visual_analysis_output: Output from visual analysis stage
            current_step_description: Description of current step being planned
            previous_action_summary: Summary of previous actions taken
            anchor_point_context: Context from anchor point configuration
              Returns:
            str: Formatted prompt for thinking process generation
        """
        base_prompt = THINKING_PROCESS_USER_PROMPT_TEMPLATE.format(
            objective=objective,
            visual_summary=visual_analysis_output or "No visual analysis available."
        )
        if anchor_point_context:
            base_prompt = f"{anchor_point_context}\n\n{base_prompt}"
        
        return base_prompt

    def construct_step_generation_prompt(self, objective, visual_analysis_output, thinking_process_output, previous_steps_output, anchor_point_context=None):
        """
        Construct a prompt for step generation based on objective, visual analysis, and thinking process.
        
        Args:
            objective: The main objective/goal
            visual_analysis_output: Output from visual analysis stage
            thinking_process_output: Output from thinking process stage
            previous_steps_output: Output from previous step generation (if any)
            anchor_point_context: Context from anchor point configuration
            
        Returns:
            str: Formatted prompt for step generation        """
        base_prompt = STEP_GENERATION_USER_PROMPT_TEMPLATE.format(
            objective=objective,
            visual_summary=visual_analysis_output or "No visual analysis available.",
            thinking_summary=thinking_process_output or "No thinking process output available."
        )
        
        if anchor_point_context:
            base_prompt = f"{anchor_point_context}\n\n{base_prompt}"
        
        return base_prompt

    def construct_action_prompt(self, objective, current_step_description, all_steps, current_step_index, 
                               visual_analysis_output, thinking_process_output, previous_action_summary, 
                               max_retries, current_retry_count, anchor_point_context=None):
        """
        Construct a prompt for action generation based on current context.
        
        Args:
            objective: The main objective/goal
            current_step_description: Description of the current step to execute
            all_steps: List of all step descriptions
            current_step_index: Index of current step being executed
            visual_analysis_output: Output from visual analysis
            thinking_process_output: Output from thinking process
            previous_action_summary: Summary of previous action taken
            max_retries: Maximum retry attempts allowed
            current_retry_count: Current retry attempt number
            
        Returns:
            str: Formatted prompt for action generation
        """
        # Build context about progress
        steps_context = f"Step {current_step_index + 1} of {len(all_steps)}: {current_step_description}"
        if current_step_index > 0:
            previous_steps = "\n".join([f"{i+1}. {step}" for i, step in enumerate(all_steps[:current_step_index])])
            steps_context += f"\n\nPrevious steps completed:\n{previous_steps}"
          # Build retry context
        retry_context = ""
        if current_retry_count > 0:
            retry_context = f"\n\nNote: This is retry attempt {current_retry_count + 1} of {max_retries}. Previous attempt may have failed."
        
        # Build anchor point context
        anchor_context = ""
        if anchor_point_context:
            anchor_context = f"\n\n{anchor_point_context}"
        
        # Construct the full prompt using the DEFAULT_PROMPT format
        action_prompt = f"""
Current Objective: {objective}
{anchor_context}

Current Step to Execute: {steps_context}

Visual Analysis of Current Screen:
{visual_analysis_output or "No visual analysis available."}

Strategic Context:
{thinking_process_output or "No strategic context available."}

Previous Action Summary:
{previous_action_summary or "No previous action."}
{retry_context}

Please analyze the current screen and generate the next action to complete the current step. Follow the action format requirements exactly.
        """.strip()
        
        return action_prompt

    async def get_llm_response(self, model, messages, objective, session_id, response_format_type="default"):
        """
        Get a response from the LLM and handle different response formats.
        
        Args:
            model: The model to use
            messages: List of message dictionaries with role and content
            objective: The objective/goal context
            session_id: Session identifier
            response_format_type: Type of response expected ("thinking_process", "step_generation", "action_generation", "default")
            
        Returns:
            tuple: (raw_response, thinking_output, error)
                - raw_response: Raw text response from LLM
                - thinking_output: Processed output (usually same as raw_response for non-action types)
                - error: Error message if any, None otherwise
        """
        try:
            # Get raw response using existing get_next_action method
            raw_response, _, _ = await self.get_next_action(model, messages, objective, session_id, None)
            
            if not raw_response:
                return None, None, "LLM returned no response"
            
            # For most response types, thinking_output is the same as raw_response
            # The handle_llm_response function in operate.py will do additional processing
            thinking_output = raw_response
            
            logger.debug(f"LLM response for {response_format_type}: {raw_response[:200]}...")
            
            return raw_response, thinking_output, None
            
        except Exception as e:
            error_msg = f"Error in get_llm_response: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, None, error_msg


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
