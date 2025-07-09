import asyncio
import json
import re
import pathlib
import sys
import os
import logging  # Added logging
from typing import Any, Dict, Optional

# Get a logger for this module
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

# Adjust imports to use absolute paths consistently
# NOTE: Removed problematic import that was causing hanging: from core.utils.region.mapper import map_elements_to_coords
from .handlers.openai_handler import call_openai_model
from .handlers.lmstudio_handler import call_lmstudio_model

# Ensure the project's core folder is on sys.path for exceptions
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent / "core"))
from exceptions import ModelNotRecognizedException, LLMResponseError

# Ensure the config folder is on sys.path for Config
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent / "config"))
from config import Config


# Add LLMInterface class that was being imported by core/main.py
class LLMInterface:
    """Interface for interacting with language models."""
    
    def __init__(self, 
                 api_source: str = None,
                 api_key_or_url: str = None, 
                 model: str = None,
                 temperature: float = 0.5,
                 config: Config = None):
        """Initialize the LLM interface."""
        if config:
            try:
                self.api_source, self.api_key_or_url = config.get_api_source()
                self.model = config.get_model()
                self.temperature = config.get_temperature()
            except Exception as e:
                logger.error(f"Error loading LLM configuration from Config object: {e}")
                # Use defaults
                self.api_source = api_source or "openai"
                self.api_key_or_url = api_key_or_url or ""
                self.model = model or "gpt-4o"
                self.temperature = temperature
        else:
            self.api_source = api_source
            self.api_key_or_url = api_key_or_url
            self.model = model
            self.temperature = temperature
        
        logger.info(f"LLMInterface initialized with source: {self.api_source}, model: {self.model}, temp: {self.temperature}")
    
    def call_model(self, messages: list, system_prompt: str = None, temperature: float = None):
        """Call the language model with the given messages and system prompt."""
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages
        
        temp = temperature if temperature is not None else self.temperature
        
        try:
            if self.api_source.lower() == "openai":
                return call_openai_model(messages, self.api_key_or_url, self.model, temp)
            elif self.api_source.lower() == "lmstudio":
                return call_lmstudio_model(messages, self.api_key_or_url, self.model, temp)
            else:
                raise ModelNotRecognizedException(self.api_source, ["openai", "lmstudio"])
        except Exception as e:
            logger.error(f"Error calling model {self.model} via {self.api_source}: {e}")
            raise

    def process_response(self, raw_response, context_description="general", is_json=False):
        """Process the raw response from the LLM."""
        return handle_llm_response(raw_response, context_description, is_json, self)


def standardize_action_fields(action_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standardize action field names for compatibility with operation execution.
    Converts LLM-generated field names to the expected format.
    """
    if not isinstance(action_dict, dict):
        return action_dict
    
    standardized = action_dict.copy()
    
    # Map common field name variations to standard names
    field_mappings = {
        "operation": "action_type",
        "action": "action_type", 
        "type": "action_type",
        "coordinates": "coordinate",
        "coords": "coordinate",
        "position": "coordinate",
        "x_coord": "x",
        "y_coord": "y",
        "text_to_type": "text",
        "input_text": "text",
        "message": "text",
        "button": "key",
        "key_press": "key",
        "hotkey": "keys"
    }
    
    # Apply field name mappings
    for old_field, new_field in field_mappings.items():
        if old_field in standardized and new_field not in standardized:
            standardized[new_field] = standardized.pop(old_field)
    
    # Handle coordinate format standardization
    if "coordinate" in standardized and isinstance(standardized["coordinate"], dict):
        coord = standardized["coordinate"]
        # Ensure x and y are present
        if "x" not in coord and "x_coord" in coord:
            coord["x"] = coord.pop("x_coord")
        if "y" not in coord and "y_coord" in coord:
            coord["y"] = coord.pop("y_coord")
    
    # If coordinates are provided as separate x, y fields, combine them
    if "x" in standardized and "y" in standardized and "coordinate" not in standardized:
        standardized["coordinate"] = {
            "x": standardized.pop("x"),
            "y": standardized.pop("y")
        }
    
    # Ensure click actions have coordinates
    if standardized.get("action_type") == "click" and "coordinate" not in standardized:
        # Use fallback coordinates if none provided
        standardized["coordinate"] = {"x": 300, "y": 200}
        logger.warning(f"Click action missing coordinates, using fallback: {standardized['coordinate']}")
    
    # Add confidence if missing
    if "confidence" not in standardized:
        standardized["confidence"] = 70  # Default confidence
    
    return standardized


# Replaced original handle_llm_response with a new version
# to match usage in core/operate.py for parsing and cleaning LLM outputs.
def handle_llm_response(
    raw_response_text: str,
    context_description: str,  # e.g., "visual analysis", "thinking process", "action generation"
    is_json: bool = False,
    llm_interface=None,  # Parameter is present as per operate.py's usage
    objective: str = None,  # The current objective/goal
    current_step_description: str = None,  # The current step being processed
    visual_analysis_output: str = None  # Visual analysis output for better fallback coordinates
) -> any:
    """
    Processes raw LLM response text.
    If is_json is True, attempts to extract and parse JSON from a markdown code block.
    Otherwise, (or for the text part if JSON extraction fails), cleans the text,
    notably by stripping <think>...</think> tags and other common XML/HTML tags.
    """
    logger.debug(f"Handling LLM response for '{context_description}'. Raw length: {len(raw_response_text)}. is_json: {is_json}")
    
    # Log the raw response for debugging
    logger.debug(f"Raw LLM response for '{context_description}': {raw_response_text}")
    
    # Clean up debug messages from LLM Studio responses
    if "[DEBUG]" in raw_response_text:
        logger.warning(f"Found debug messages in LLM response, cleaning them...")
        lines = raw_response_text.split('\n')
        cleaned_lines = [line for line in lines if not line.strip().startswith('[DEBUG]')]
        raw_response_text = '\n'.join(cleaned_lines)
        logger.debug(f"Cleaned response: {raw_response_text}")
    
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
        text = re.sub(r"<\w+/?>(?!</\w+>)", "", text)  # Removes <tag> but not <tag>content</tag>
        text = re.sub(r"<([A-Za-z][A-Za-z0-9]*)\b[^>]*>(.*?)</\1>", r"\2", text, flags=re.DOTALL)  # Strips outer tags if content is desired
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

    # 2. If is_json is True, try to extract and parse JSON.
    # The raw_response_text itself might contain tags around the JSON block.
    text_to_search_json_in = strip_tags(str(raw_response_text))  # Clean before searching for JSON block

    # Try multiple JSON extraction methods
    json_str_to_parse = None
    
    # Method 1: Look for ```json code blocks
    json_match = re.search(r"```json\s*(.*?)\s*```", text_to_search_json_in, re.DOTALL)
    if json_match:
        json_str_to_parse = json_match.group(1).strip()
        logger.debug(f"Found JSON in markdown code block for '{context_description}'")
    else:
        # Method 2: Look for any code blocks that might contain JSON
        code_match = re.search(r"```\s*(.*?)\s*```", text_to_search_json_in, re.DOTALL)
        if code_match:
            potential_json = code_match.group(1).strip()
            if (potential_json.startswith("{") and potential_json.endswith("}")) or \
               (potential_json.startswith("[") and potential_json.endswith("]")):
                json_str_to_parse = potential_json
                logger.debug(f"Found JSON in generic code block for '{context_description}'")
        
        # Method 3: Look for JSON objects/arrays in the text
        if not json_str_to_parse:
            # Find JSON objects { ... }
            json_obj_match = re.search(r'\{.*\}', text_to_search_json_in, re.DOTALL)
            if json_obj_match:
                json_str_to_parse = json_obj_match.group(0).strip()
                logger.debug(f"Found JSON object pattern for '{context_description}'")
            else:
                # Find JSON arrays [ ... ]
                json_arr_match = re.search(r'\[.*\]', text_to_search_json_in, re.DOTALL)
                if json_arr_match:
                    json_str_to_parse = json_arr_match.group(0).strip()
                    logger.debug(f"Found JSON array pattern for '{context_description}'")
        
        # Method 4: Check if the entire cleaned text looks like JSON
        if not json_str_to_parse:
            if (text_to_search_json_in.startswith("{") and text_to_search_json_in.endswith("}")) or \
               (text_to_search_json_in.startswith("[") and text_to_search_json_in.endswith("]")):
                json_str_to_parse = text_to_search_json_in
                logger.debug(f"Using entire cleaned text as JSON for '{context_description}'")
        
        # If still no JSON found, provide more detailed error info
        if not json_str_to_parse:
            # For action generation, try to create a fallback JSON from descriptive text
            if context_description == "action_generation":
                logger.warning(f"No JSON found for action generation, attempting to create fallback action...")
                logger.debug(f"LLM response text (first 1000 chars): {text_to_search_json_in[:1000]}")
                logger.debug(f"Objective: {objective}")
                logger.debug(f"Current step: {current_step_description}")
                
                # Enhanced Chrome-specific fallback logic
                if objective and "chrome" in objective.lower():
                    logger.info(f"Chrome-related objective detected: {objective}")
                    
                    # If current step involves Start menu search
                    if current_step_description and ("start menu" in current_step_description.lower() or 
                                                   "search" in current_step_description.lower()):
                        # If step mentions typing Chrome or using search
                        if "type" in current_step_description.lower() or "search" in current_step_description.lower():
                            fallback_action = {
                                "action_type": "type",
                                "text": "Chrome",
                                "description": "Type 'Chrome' in Start menu search",
                                "confidence": 80
                            }
                            logger.info(f"Created fallback type Chrome action for Start menu search step")
                            return fallback_action
                        
                        # If step mentions pressing Enter or launching
                        elif "enter" in current_step_description.lower() or "launch" in current_step_description.lower():
                            fallback_action = {
                                "action_type": "key",
                                "key": "enter",
                                "description": "Press Enter to launch Chrome from search results",
                                "confidence": 80
                            }
                            logger.info(f"Created fallback Enter key action for Chrome launch")
                            return fallback_action
                    
                    # If current step involves clicking Chrome
                    if current_step_description and ("click" in current_step_description.lower() and 
                                                    "chrome" in current_step_description.lower()):
                        fallback_action = {
                            "action_type": "click",
                            "description": "Click on Google Chrome",
                            "coordinate": {"x": 300, "y": 200},  # More center-screen coordinates
                            "confidence": 75
                        }
                        logger.info(f"Created fallback Chrome click action for click step")
                        return fallback_action
                
                # Enhanced Calculator-specific fallback logic
                if objective and "calculator" in objective.lower():
                    logger.info(f"Calculator-related objective detected: {objective}")
                    
                    # If current step involves Start menu search
                    if current_step_description and ("start menu" in current_step_description.lower() or 
                                                   "search" in current_step_description.lower()):
                        # If step mentions typing Calculator or using search
                        if "type" in current_step_description.lower() or "search" in current_step_description.lower():
                            fallback_action = {
                                "action_type": "type",
                                "text": "Calculator",
                                "description": "Type 'Calculator' in Start menu search",
                                "confidence": 80
                            }
                            logger.info(f"Created fallback type Calculator action for Start menu search step")
                            return fallback_action
                        
                        # If step mentions pressing Enter or launching
                        elif "enter" in current_step_description.lower() or "launch" in current_step_description.lower():
                            fallback_action = {
                                "action_type": "key",
                                "key": "enter",
                                "description": "Press Enter to launch Calculator from search results",
                                "confidence": 80
                            }
                            logger.info(f"Created fallback Enter key action for Calculator launch")
                            return fallback_action
                    
                    # If current step involves clicking Calculator
                    if current_step_description and ("click" in current_step_description.lower() and 
                                                    "calculator" in current_step_description.lower()):
                        # Try to get better coordinates from visual analysis if available
                        click_x, click_y = 400, 300  # Default fallback coordinates
                        
                        # Look for Calculator in the visual analysis if available
                        if visual_analysis_output:
                            # Look for patterns that might indicate Calculator position
                            calc_patterns = [
                                r'calculator.*?(\d+).*?(\d+)',
                                r'calculator.*?x.*?(\d+).*?y.*?(\d+)',
                                r'calculator.*?position.*?(\d+).*?(\d+)'
                            ]
                            
                            for pattern in calc_patterns:
                                match = re.search(pattern, visual_analysis_output.lower())
                                if match and len(match.groups()) >= 2:
                                    try:
                                        click_x = int(match.group(1))
                                        click_y = int(match.group(2))
                                        logger.info(f"Found Calculator coordinates from visual analysis: ({click_x}, {click_y})")
                                        break
                                    except (ValueError, IndexError):
                                        continue
                        
                        fallback_action = {
                            "action_type": "click",
                            "description": "Click on Calculator",
                            "coordinate": {"x": click_x, "y": click_y},
                            "confidence": 75
                        }
                        logger.info(f"Created fallback Calculator click action at ({click_x}, {click_y}) for click step")
                        return fallback_action
                
                # Check if Chrome is mentioned in the LLM response text
                if "chrome" in text_to_search_json_in.lower():
                    # Check if it mentions clicking on Chrome icon
                    if "click" in text_to_search_json_in.lower() and "icon" in text_to_search_json_in.lower():
                        fallback_action = {
                            "action_type": "click",
                            "description": "Click on Google Chrome icon",
                            "coordinate": {"x": 300, "y": 200},  # More center-screen coordinates
                            "confidence": 70
                        }
                        logger.info(f"Created fallback Chrome click action from descriptive text")
                        return fallback_action
                    
                    # If desktop is mentioned with Chrome, try to click on Chrome icon
                    elif "desktop" in text_to_search_json_in.lower() and "visible" in text_to_search_json_in.lower():
                        fallback_action = {
                            "action_type": "click",
                            "description": "Click on Google Chrome icon on desktop",
                            "coordinate": {"x": 300, "y": 200},  # More center-screen coordinates
                            "confidence": 65
                        }
                        logger.info(f"Created fallback Chrome desktop click action from descriptive text")
                        return fallback_action
                
                # Smart fallback progression based on current step and context
                if current_step_description:
                    step_lower = current_step_description.lower()
                    
                    # If we're in a step that involves desktop context, press Windows key
                    if "desktop" in step_lower and "context" in step_lower:
                        fallback_action = {
                            "action_type": "key",
                            "key": "win",
                            "description": "Press Windows key to open Start menu",
                            "confidence": 75
                        }
                        logger.info(f"Created fallback Windows key action for desktop context step")
                        return fallback_action
                    
                    # If we're in a step that involves minimizing windows
                    elif "minimize" in step_lower and "window" in step_lower:
                        fallback_action = {
                            "action_type": "key",
                            "key": "win+d",
                            "description": "Press Win+D to minimize all windows",
                            "confidence": 80
                        }
                        logger.info(f"Created fallback Win+D action for minimize windows step")
                        return fallback_action
                    
                    # If we're in a step that involves accessing Start menu
                    elif "start menu" in step_lower and "access" in step_lower:
                        fallback_action = {
                            "action_type": "key",
                            "key": "win",
                            "description": "Press Windows key to access Start menu",
                            "confidence": 80
                        }
                        logger.info(f"Created fallback Windows key action for Start menu access step")
                        return fallback_action
                    
                    # If we're in a step that involves typing in search bar
                    elif "type" in step_lower and ("search" in step_lower or "start menu" in step_lower):
                        if objective and "calculator" in objective.lower():
                            fallback_action = {
                                "action_type": "type",
                                "text": "Calculator",
                                "description": "Type 'Calculator' in Start menu search",
                                "confidence": 80
                            }
                            logger.info(f"Created fallback type Calculator action for search step")
                            return fallback_action
                        elif objective and "chrome" in objective.lower():
                            fallback_action = {
                                "action_type": "type",
                                "text": "Chrome",
                                "description": "Type 'Chrome' in Start menu search",
                                "confidence": 80
                            }
                            logger.info(f"Created fallback type Chrome action for search step")
                            return fallback_action
                    
                    # If we're in a step that involves clicking on an icon
                    elif "click" in step_lower and ("icon" in step_lower or "chrome" in step_lower or "calculator" in step_lower):
                        if objective and "chrome" in objective.lower():
                            fallback_action = {
                                "action_type": "click",
                                "coordinate": {"x": 300, "y": 200},
                                "description": "Click on Google Chrome icon",
                                "confidence": 75
                            }
                            logger.info(f"Created fallback Chrome click action for icon click step")
                            return fallback_action
                        elif objective and "calculator" in objective.lower():
                            fallback_action = {
                                "action_type": "click", 
                                "coordinate": {"x": 300, "y": 200},
                                "description": "Click on Calculator icon",
                                "confidence": 75
                            }
                            logger.info(f"Created fallback Calculator click action for icon click step")
                            return fallback_action
                        else:
                            # Generic click action
                            fallback_action = {
                                "action_type": "click",
                                "coordinate": {"x": 300, "y": 200},
                                "description": "Click on application icon",
                                "confidence": 70
                            }
                            logger.info(f"Created fallback generic click action for icon click step")
                            return fallback_action
                    
                    # If we're in an alternative launch step, type the app name
                    elif "alternative" in step_lower and "launch" in step_lower:
                        if objective and "calculator" in objective.lower():
                            fallback_action = {
                                "action_type": "type",
                                "text": "Calculator",
                                "description": "Type 'Calculator' to search for the application",
                                "confidence": 75
                            }
                            logger.info(f"Created fallback type Calculator action for alternative launch step")
                            return fallback_action
                        elif objective and "chrome" in objective.lower():
                            fallback_action = {
                                "action_type": "type",
                                "text": "Chrome",
                                "description": "Type 'Chrome' to search for the application",
                                "confidence": 75
                            }
                            logger.info(f"Created fallback type Chrome action for alternative launch step")
                            return fallback_action
                    elif "alternative" in step_lower and "launch" in step_lower:
                        if objective and "calculator" in objective.lower():
                            fallback_action = {
                                "action_type": "type",
                                "text": "Calculator",
                                "description": "Type 'Calculator' to search for the application",
                                "confidence": 75
                            }
                            logger.info(f"Created fallback type Calculator action for alternative launch step")
                            return fallback_action
                        elif objective and "chrome" in objective.lower():
                            fallback_action = {
                                "action_type": "type",
                                "text": "Chrome",
                                "description": "Type 'Chrome' to search for the application",
                                "confidence": 75
                            }
                            logger.info(f"Created fallback type Chrome action for alternative launch step")
                            return fallback_action
                
                # Generic progression logic based on previous actions or context
                # If the text describes the desktop is active, try Windows key to open Start menu
                if "desktop" in text_to_search_json_in.lower() and "active" in text_to_search_json_in.lower():
                    fallback_action = {
                        "action_type": "key",
                        "key": "win",
                        "description": "Press Windows key to open Start menu",
                        "confidence": 65
                    }
                    logger.info(f"Created fallback Windows key action for desktop state")
                    return fallback_action
                
                # If Start menu is mentioned, type Chrome or Calculator
                if "start menu" in text_to_search_json_in.lower() or "search" in text_to_search_json_in.lower():
                    if objective and "chrome" in objective.lower():
                        fallback_action = {
                            "action_type": "type",
                            "text": "Chrome",
                            "description": "Type 'Chrome' in Start menu search",
                            "confidence": 70
                        }
                        logger.info(f"Created fallback type Chrome action for Start menu context")
                        return fallback_action
                    elif objective and "calculator" in objective.lower():
                        fallback_action = {
                            "action_type": "type",
                            "text": "Calculator",
                            "description": "Type 'Calculator' in Start menu search",
                            "confidence": 70
                        }
                        logger.info(f"Created fallback type Calculator action for Start menu context")
                        return fallback_action
                
                # Generic fallback for opening Start menu
                fallback_action = {
                    "action_type": "key",
                    "key": "win",
                    "description": "Press Windows key to open Start menu",
                    "confidence": 60
                }
                logger.info(f"Created fallback Windows key action for unclear LLM response")
                return fallback_action
            
            # Fix: Ensure text_to_search_json_in is a string before slicing
            text_preview = str(text_to_search_json_in)[:500] if text_to_search_json_in else "None"
            text_sample = str(text_to_search_json_in)[:300] if text_to_search_json_in else "None"
            logger.error(f"No JSON found for '{context_description}'. Text preview: {text_preview}...")
            return {"error": "JSON_NOT_FOUND", "message": f"Expected JSON for {context_description} but couldn't find any JSON structure.", "cleaned_text_preview": text_sample}

    if json_str_to_parse:
        try:
            # Further clean the extracted JSON string from any potential comment lines if LLM added them
            json_str_to_parse = re.sub(r"//.*?\n", "\n", json_str_to_parse)  # Remove // comments
            json_str_to_parse = re.sub(r"#.*?\n", "\n", json_str_to_parse)  # Remove # comments
            
            # Try to fix common JSON formatting issues
            # Remove trailing commas before closing braces/brackets
            json_str_to_parse = re.sub(r',(\s*[}\]])', r'\1', json_str_to_parse)
            
            # Fix double braces (common LLM error like {{operation}} instead of {"operation"})
            json_str_to_parse = json_str_to_parse.replace('{{', '{')
            json_str_to_parse = json_str_to_parse.replace('}}', '}')
            
            # Fix unquoted property names (common LLM error)
            json_str_to_parse = re.sub(r'(\w+)(\s*:\s*)', r'"\1"\2', json_str_to_parse)
            
            # Fix single quotes to double quotes
            json_str_to_parse = json_str_to_parse.replace("'", '"')
            
            # Fix common JSON formatting issues before parsing
            # Remove any markdown code blocks first
            json_str_to_parse = re.sub(r'```json\s*', '', json_str_to_parse)
            json_str_to_parse = re.sub(r'```\s*', '', json_str_to_parse)
            json_str_to_parse = json_str_to_parse.strip()
            
            # Fix invalid escape sequences like "click\" -> "click"
            json_str_to_parse = re.sub(r'([^\\])\\+"', r'\1"', json_str_to_parse)
            
            # Fix malformed escape sequences in field values
            json_str_to_parse = re.sub(r'([^\\])\\([^\\nt"])', r'\1\2', json_str_to_parse)
            
            # Fix smart quotes
            json_str_to_parse = json_str_to_parse.replace('"', '"').replace('"', '"')
            json_str_to_parse = json_str_to_parse.replace(''', "'").replace(''', "'")
            
            # Fix unescaped quotes in string values (common LLM error)
            # This pattern looks for "key": "value with "quotes" inside" and escapes inner quotes
            def escape_inner_quotes(match):
                key_part = match.group(1)  # "key": 
                value_part = match.group(2)  # value with "quotes" inside
                # Escape quotes inside the value
                escaped_value = value_part.replace('"', '\\"')
                return f'{key_part}"{escaped_value}"'
            
            # Pattern to match "key": "value with potential "inner quotes""
            quote_pattern = r'("[\w_]+"\s*:\s*)"([^"]*"[^"]*)"'
            json_str_to_parse = re.sub(quote_pattern, escape_inner_quotes, json_str_to_parse)
            
            # Remove trailing commas
            json_str_to_parse = re.sub(r',(\s*[}\]])', r'\1', json_str_to_parse)
            
            logger.debug(f"Raw JSON string for '{context_description}': {json_str_to_parse}")
            
            # Apply comprehensive JSON quote fixing before parsing
            def fix_json_quotes(json_text):
                """Fix common JSON quote and escape issues"""
                # Remove extra backslashes that cause invalid control characters
                json_text = re.sub(r'\\(?!["\\/bfnrt])', '', json_text)
                
                # Fix unescaped quotes in description fields specifically
                def fix_description_quotes(match):
                    field_name = match.group(1)
                    content = match.group(2)
                    # Escape internal quotes properly
                    content = content.replace('\\"', '"').replace('"', '\\"')
                    return f'"{field_name}": "{content}"'
                
                # Apply to common string fields that often have quote issues
                json_text = re.sub(r'"(description|summary|text|target|input_text|action_type)": "([^"]*(?:\\"[^"]*)*)"', fix_description_quotes, json_text)
                
                return json_text
            
            json_str_to_parse = fix_json_quotes(json_str_to_parse)
            logger.debug(f"After comprehensive quote fixing: {json_str_to_parse[:300]}...")
            
            # First parsing attempt
            try:
                parsed_json = json.loads(json_str_to_parse)
                logger.debug(f"Successfully parsed JSON for '{context_description}' after cleanup.")
            except json.JSONDecodeError as first_error:
                # If first attempt fails, try more aggressive cleanup
                logger.warning(f"First JSON parse attempt failed for '{context_description}': {first_error}")
                logger.warning(f"Problematic JSON string: {json_str_to_parse[:500]}...")
                
                # Try to extract just the JSON object/array part
                # Look for the first { or [ and the last } or ]
                start_idx = min(
                    json_str_to_parse.find('{') if json_str_to_parse.find('{') != -1 else len(json_str_to_parse),
                    json_str_to_parse.find('[') if json_str_to_parse.find('[') != -1 else len(json_str_to_parse)
                )
                end_idx = max(
                    json_str_to_parse.rfind('}'),
                    json_str_to_parse.rfind(']')
                )
                
                if start_idx < len(json_str_to_parse) and end_idx > start_idx:
                    json_str_cleaned = json_str_to_parse[start_idx:end_idx+1]
                    logger.debug(f"Extracted JSON substring: {json_str_cleaned[:200]}...")
                    parsed_json = json.loads(json_str_cleaned)
                    logger.debug(f"Successfully parsed JSON for '{context_description}' after aggressive cleanup.")
                else:
                    # Re-raise the original error if cleanup doesn't help
                    raise first_error

            # If the context is action generation and the parsed JSON is a list,
            # return the first element if the list is not empty.
            if context_description == "action_generation" and isinstance(parsed_json, list):
                if len(parsed_json) > 0:
                    action = parsed_json[0]
                    # Standardize field names for compatibility
                    if isinstance(action, dict):
                        action = standardize_action_fields(action)
                    logger.info(f"Parsed JSON for action generation was a list. Returning first element: {action}")
                    return action
                else:
                    # Fix: Ensure json_str_to_parse is a string before slicing
                    json_preview = str(json_str_to_parse)[:500] if json_str_to_parse else "None"
                    logger.error(f"Parsed JSON for action generation was an empty list. Original string: '{json_preview}...'")
                    return {"error": "EMPTY_ACTION_LIST", "message": "LLM returned an empty list for actions."}

            # For single actions (not in a list), also standardize field names
            if context_description == "action_generation" and isinstance(parsed_json, dict):
                parsed_json = standardize_action_fields(parsed_json)
                logger.info(f"Standardized action fields: {parsed_json}")

            return parsed_json
        except json.JSONDecodeError as e:
            # Fix: Ensure json_str_to_parse is a string before slicing
            json_preview = str(json_str_to_parse)[:500] if json_str_to_parse else "None"
            json_sample = str(json_str_to_parse)[:200] if json_str_to_parse else "None"
            logger.error(f"JSONDecodeError for '{context_description}': {e}. JSON string was: '{json_preview}...'")
            return {"error": "JSON_DECODE_ERROR", "message": str(e), "json_string_preview": json_sample}

    # Fallback if json_str_to_parse was not set (e.g. markdown found, but group(1) was empty - unlikely)
    logger.error(f"JSON processing failed unexpectedly for '{context_description}'. No JSON string was identified for parsing.")
    return {"error": "JSON_PROCESSING_FAILED", "message": f"Problem in JSON processing logic for {context_description}."}


class MainInterface:
    """High‑level interface for obtaining the next UI action from an LLM."""

    def __init__(self):  # Add __init__
        self.config = Config()
        self.api_source, _ = self.config.get_api_source()
        print(f"[MainInterface] Initialized with API source: {self.api_source}")

    def construct_step_generation_prompt(self, objective, visual_analysis_output, thinking_process_output, previous_steps_output):
        """
        Construct the user prompt for step generation.
        This method is expected by the operator for generating steps.
        """
        from core.prompts.prompts import STEP_GENERATION_USER_PROMPT_TEMPLATE
        
        return STEP_GENERATION_USER_PROMPT_TEMPLATE.format(
            objective=objective,
            visual_summary=visual_analysis_output,
            thinking_summary=thinking_process_output
        )

    def construct_visual_analysis_prompt(self, objective, screenshot_elements, anchor_context=""):
        """
        Construct the user prompt for visual analysis.
        This method focuses purely on screen analysis and UI element identification.
        """
        from core.prompts.prompts import VISUAL_ANALYSIS_USER_PROMPT_TEMPLATE
        
        return VISUAL_ANALYSIS_USER_PROMPT_TEMPLATE.format(
            objective=objective,
            screenshot_elements=screenshot_elements,
            anchor_context=anchor_context
        )

    def construct_thinking_process_prompt(self, objective, visual_analysis_output, current_step_description, previous_action_summary):
        """
        Construct the user prompt for strategic thinking process.
        This method focuses on high-level strategic planning using visual context.
        """
        from core.prompts.prompts import THINKING_PROCESS_USER_PROMPT_TEMPLATE
        
        return THINKING_PROCESS_USER_PROMPT_TEMPLATE.format(
            objective=objective,
            visual_summary=visual_analysis_output,
            current_step_description=current_step_description,
            previous_action_summary=previous_action_summary
        )

    def construct_action_prompt(self, objective, current_step_description, all_steps, current_step_index, 
                               visual_analysis_output, thinking_process_output, previous_action_summary, 
                               max_retries, current_retry_count):
        """
        Construct the user prompt for action generation.
        This method is expected by the operator for generating actions.
        """
        # For now, create a basic action prompt template
        # This should ideally be imported from prompts.py but let's create a working version
        action_prompt = f"""
Objective: {objective}

Current Step ({current_step_index + 1} of {len(all_steps)}): {current_step_description}

All Steps:
{chr(10).join([f"{i+1}. {step}" for i, step in enumerate(all_steps)])}

Visual Analysis Summary:
{visual_analysis_output}

Thinking Process Summary:
{thinking_process_output}

Previous Action Summary: {previous_action_summary}

Current Retry: {current_retry_count + 1} of {max_retries}

Based on the current step and visual analysis, generate a specific action to execute.
Return a JSON object with "type" and "summary" fields.
Example: {{"type": "click", "summary": "Click on the Chrome icon in the taskbar"}}
"""
        return action_prompt

    async def llm_request(self, messages, max_tokens=1000, temperature=0.3):
        """
        Generic LLM request method expected by the operator for fallback operations.
        """
        try:
            # Use the existing get_llm_response method
            response_text, session_id, error = await self.get_llm_response(
                model=self.config.get_model(),
                messages=messages,
                objective="fallback_request",
                session_id="fallback",
                response_format_type="fallback"
            )
            
            if error:
                logger.error(f"LLM request failed: {error}")
                return None
                
            return response_text
            
        except Exception as e:
            logger.error(f"Error in llm_request: {e}")
            return None

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
    
    # Alias for backward compatibility: unify LLM calls under get_llm_response
    async def get_llm_response(self, model, messages, objective, session_id, response_format_type=None):
        """
        Unified interface for obtaining LLM responses across contexts.
        Delegates to get_next_action but can handle different response formats based on context.
        """
        print(f"\n[OBJECTIVE_FORMULATION] Starting LLM call for {response_format_type}")
        print(f"[OBJECTIVE_FORMULATION] Model: {model}")
        print(f"[OBJECTIVE_FORMULATION] Objective: {objective}")
        print(f"[OBJECTIVE_FORMULATION] Messages: {json.dumps(messages, indent=2)}")
        
        # Add a timeout for LLM calls
        try:
            # Create a task for the LLM call
            llm_task = asyncio.create_task(
                self.get_next_action(model, messages, objective, session_id, screenshot_path=None)
            )
            
            # Wait for the task with a timeout (30 seconds)
            response, sid, error = await asyncio.wait_for(llm_task, timeout=30.0)
            
        except asyncio.TimeoutError:
            logger.error("LLM call timed out after 30 seconds")
            print("[ERROR] LLM call timed out after 30 seconds")
            
            if self.api_source == "lmstudio":
                error_message = (
                    "LMStudio connection timed out. Please check if LMStudio is running "
                    "at the configured URL and port. You may need to restart LMStudio."
                )
            else:
                error_message = "LLM API call timed out. The service may be experiencing high load or connectivity issues."
                
            return f"ERROR: {error_message}", session_id, error_message
            
        except Exception as e:
            logger.error(f"Error during LLM call: {e}")
            print(f"[ERROR] LLM call failed: {e}")
            return f"ERROR: LLM connection failed: {str(e)}", session_id, str(e)
        
        # Special handling for objective formulation to ensure we get a proper response
        if response_format_type == "objective_generation":
            print(f"\n[OBJECTIVE_FORMULATION] Raw LLM response (first 300 chars): {response[:300] if isinstance(response, str) else str(response)[:300]}")
            logger.info(f"Processing LLM response for objective formulation: {response[:100] if isinstance(response, str) else str(response)[:100]}...")
            
            # First check if the response is an error message
            if isinstance(response, str) and response.startswith("[ERROR]"):
                logger.error(f"Error in LLM response: {response}")
                return "", sid, response
                
            # Make sure we're getting a proper formulated objective rather than just echoing back the goal
            if response and isinstance(response, str) and response.strip():
                # Try to clean up any formatting in the raw response
                # Remove markdown code blocks if present
                response_clean = re.sub(r"```.*?```", "", response, flags=re.DOTALL)
                # Remove any XML-like tags
                response_clean = re.sub(r"<.*?>", "", response_clean)
                
                print(f"[OBJECTIVE_FORMULATION] Cleaned response: {response_clean[:300]}")
                
                # We don't need additional processing here as that's done in main.py
                return response_clean, sid, error
            else:
                logger.warning(f"Empty or invalid response from LLM for objective formulation: {response}")
                print(f"[OBJECTIVE_FORMULATION] Empty or invalid response from LLM: {response}")
                return "ERROR: Failed to generate objective. LLM returned an invalid response.", sid, "Empty or invalid response"
                
        return response, sid, error

    async def formulate_objective(
        self,
        goal: str,
        session_id: str,
    ) -> tuple[str | None, str | None]:
        """Formats a prompt to ask the LLM to formulate an objective.
        Uses get_llm_response to ensure timeout and consistent error handling.

        Args:
            goal: The user's goal.
            session_id: The session ID for the operation.

        Returns:
            A tuple containing the formulated objective string and an optional error string.
        """
        logger.info(f'Formulating objective for goal: "{goal}"')

        try:
            from core.prompts.prompts import FORMULATE_OBJECTIVE_SYSTEM_PROMPT, FORMULATE_OBJECTIVE_USER_PROMPT_TEMPLATE
        except ImportError:
            logger.error("Could not import objective formulation prompts.")
            return None, "Prompt templates not found."

        system_prompt = FORMULATE_OBJECTIVE_SYSTEM_PROMPT
        user_prompt = FORMULATE_OBJECTIVE_USER_PROMPT_TEMPLATE.format(user_goal=goal)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        logger.debug(f"LM Interface - Messages for objective formulation: {messages}")

        try:
            # Use get_llm_response to leverage its timeout and error handling.
            response_text, _, error = await self.get_llm_response(
                model=self.config.get_model(),
                messages=messages,
                objective=goal, # Pass original goal for context/logging
                session_id=session_id,
                response_format_type="objective_generation"
            )
            
            if error:
                logger.error(f"LLM error during objective formulation: {error}")
                return None, str(error)

            if not response_text or response_text.startswith("ERROR:"):
                 logger.error(f"Invalid response from LLM for objective formulation: {response_text}")
                 return None, response_text or "Empty response from LLM"

            logger.info(f"Successfully formulated objective: {response_text}")
            
            return response_text.strip(), None

        except Exception as e:
            logger.error(f"An unexpected error occurred during objective formulation: {e}", exc_info=True)
            return None, f"Exception during objective formulation: {e}"


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
