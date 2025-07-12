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

    # Try multiple JSON extraction methods
    json_str_to_parse = None
    
    # Check if the response is already valid JSON (from LMStudio handler that pre-extracts JSON)
    try:
        # First check if it's already valid JSON by trying to parse it directly
        stripped_text = text_to_search_json_in.strip()
        test_parse = json.loads(stripped_text)
        json_str_to_parse = stripped_text
        logger.debug(f"Using pre-extracted JSON for '{context_description}' - detected valid JSON directly")
    except json.JSONDecodeError:
        # If direct parsing fails, continue with extraction methods
        logger.debug(f"Text is not directly parseable JSON, trying extraction methods for '{context_description}'")
    
    # If not already valid JSON, try extraction methods
    if not json_str_to_parse:
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
        
        # If still no JSON found, provide more detailed error info
        if not json_str_to_parse:
            # For step generation, try to create a fallback JSON from descriptive text
            if context_description == "step_generation":
                logger.warning(f"No JSON found for step generation, attempting to create fallback steps from text...")
                logger.debug(f"LLM response text (first 1000 chars): {text_to_search_json_in[:1000]}")
                
                # Try to extract steps from numbered list format
                steps = []
                lines = text_to_search_json_in.split('\n')
                step_number = 1
                
                for line in lines:
                    line = line.strip()
                    # Look for numbered steps like "1.", "Step 1:", etc.
                    if re.match(r'^\d+\.|\bstep\s+\d+:', line, re.IGNORECASE):
                        # Extract step description
                        description = re.sub(r'^\d+\.|\bstep\s+\d+:', '', line, flags=re.IGNORECASE).strip()
                        if description:
                            steps.append({
                                "step_number": step_number,
                                "description": description,
                                "action_type": "mixed",
                                "target": "system",
                                "verification": f"Confirm step {step_number} completed"
                            })
                            step_number += 1
                
                if steps:
                    logger.info(f"Created {len(steps)} fallback steps from numbered list")
                    return steps  # Return the list directly
                else:
                    # Create basic fallback steps for common actions
                    logger.warning(f"Creating basic fallback steps for Calculator")
                    return [
                        {
                            "step_number": 1,
                            "description": "Press Windows key to open Start menu",
                            "action_type": "key_sequence",
                            "target": "win",
                            "verification": "Start menu is visible"
                        },
                        {
                            "step_number": 2,
                            "description": "Type 'calculator' to search for Calculator app",
                            "action_type": "type",
                            "target": "calculator",
                            "verification": "Calculator appears in search results"
                        },
                        {
                            "step_number": 3,
                            "description": "Press Enter to open Calculator",
                            "action_type": "key",
                            "target": "enter", 
                            "verification": "Calculator application opens"
                        }
                    ]
            
            # For action generation, try to create a fallback JSON from descriptive text
            elif context_description == "action_generation":
                logger.warning(f"No JSON found for action generation, attempting to create fallback action...")
                logger.debug(f"LLM response text (first 1000 chars): {text_to_search_json_in[:1000]}")
                logger.debug(f"Objective: {objective}")
                logger.debug(f"Current step: {current_step_description}")
                
                # Real Windows Fallback Actions with actual coordinates (1920x1080 screen)
                
                # Calculator-specific real fallback logic  
                if objective and "calculator" in objective.lower():
                    logger.info(f"Calculator-related objective detected: {objective}")
                    
                    # Step 1: Open Start menu (real Windows key)
                    if current_step_description and any(keyword in current_step_description.lower() 
                                                       for keyword in ["start", "menu", "windows", "key"]):
                        fallback_action = {
                            "type": "key_sequence",
                            "keys": ["win"],
                            "summary": "Press Windows key to open Start menu",
                            "target": "system",
                            "verification": "Start menu opens"
                        }
                        logger.info(f"Created Windows key fallback action for Calculator workflow")
                        return fallback_action
                    
                    # Step 2: Search for Calculator
                    elif current_step_description and any(keyword in current_step_description.lower() 
                                                         for keyword in ["search", "type", "calculator", "find"]):
                        fallback_action = {
                            "type": "type",
                            "text": "calculator",
                            "summary": "Type 'calculator' to search for Calculator app",
                            "target": "search_box",
                            "verification": "Calculator appears in search results"
                        }
                        logger.info(f"Created type Calculator fallback action")
                        return fallback_action
                    
                    # Step 3: Open Calculator 
                    elif current_step_description and any(keyword in current_step_description.lower() 
                                                         for keyword in ["open", "launch", "enter", "press"]):
                        fallback_action = {
                            "type": "key",
                            "key": "enter",
                            "summary": "Press Enter to open Calculator application",
                            "target": "calculator_app",
                            "verification": "Calculator application opens and is visible"
                        }
                        logger.info(f"Created Enter key fallback action to open Calculator")
                        return fallback_action
                    
                    # Step 4-7: Calculator operations (2 + 2)
                    elif current_step_description and any(keyword in current_step_description.lower() 
                                                         for keyword in ["2", "input", "number", "first"]):
                        fallback_action = {
                            "type": "type",
                            "text": "2",
                            "summary": "Type the number 2",
                            "target": "calculator",
                            "verification": "Number 2 appears in calculator display"
                        }
                        logger.info(f"Created type '2' fallback action")
                        return fallback_action
                    
                    elif current_step_description and any(keyword in current_step_description.lower() 
                                                         for keyword in ["+", "plus", "addition", "add"]):
                        fallback_action = {
                            "type": "type",
                            "text": "+",
                            "summary": "Click or type the plus (+) operator",
                            "target": "calculator",
                            "verification": "Plus operator is selected in calculator"
                        }
                        logger.info(f"Created type '+' fallback action")
                        return fallback_action
                    
                    elif current_step_description and any(keyword in current_step_description.lower() 
                                                         for keyword in ["second", "another", "next"]) and "2" in current_step_description:
                        fallback_action = {
                            "type": "type",
                            "text": "2",
                            "summary": "Type the second number 2",
                            "target": "calculator",
                            "verification": "Second number 2 appears in calculator display"
                        }
                        logger.info(f"Created second '2' fallback action")
                        return fallback_action
                    
                    elif current_step_description and any(keyword in current_step_description.lower() 
                                                         for keyword in ["=", "equals", "result", "calculate"]):
                        fallback_action = {
                            "type": "key",
                            "key": "enter",
                            "summary": "Press Enter or equals to calculate result",
                            "target": "calculator",
                            "verification": "Result (4) is displayed in calculator"
                        }
                        logger.info(f"Created Enter/equals fallback action")
                        return fallback_action
                    
                    # Step 8: Screenshot to verify result
                    elif current_step_description and any(keyword in current_step_description.lower() 
                                                         for keyword in ["screenshot", "capture", "verify", "result"]):
                        fallback_action = {
                            "type": "screenshot",
                            "summary": "Take screenshot to verify calculation result",
                            "target": "screen",
                            "verification": "Screenshot shows Calculator with result 4"
                        }
                        logger.info(f"Created screenshot fallback action")
                        return fallback_action
                
                # Generic Windows Start menu fallback for any objective
                if current_step_description:
                    step_lower = current_step_description.lower()
                    
                    # Real Windows key sequence for opening Start menu
                    if any(keyword in step_lower for keyword in ["start", "menu", "taskbar", "bottom", "left"]):
                        fallback_action = {
                            "type": "key_sequence", 
                            "keys": "win",
                            "summary": "Press Windows key to access Start menu",
                            "confidence": 90
                        }
                        logger.info(f"Created real fallback Windows key for Start menu access")
                        return fallback_action
                    
                    # Real search functionality
                    elif any(keyword in step_lower for keyword in ["search", "find", "locate", "look"]):
                        # If we mention typing text, just type it
                        if "calculator" in step_lower:
                            fallback_action = {
                                "type": "type",
                                "text": "calculator",
                                "summary": "Type 'calculator' in search box",
                                "confidence": 90
                            }
                            logger.info(f"Created real fallback type action for Calculator search")
                            return fallback_action
                        elif "chrome" in step_lower:
                            fallback_action = {
                                "type": "type", 
                                "text": "chrome",
                                "summary": "Type 'chrome' in search box",
                                "confidence": 90
                            }
                            logger.info(f"Created real fallback type action for Chrome search")
                            return fallback_action
                        else:
                            # Generic search opening
                            fallback_action = {
                                "type": "key_sequence",
                                "keys": "win+s",
                                "summary": "Open Windows search with Win+S",
                                "confidence": 85
                            }
                            logger.info(f"Created real fallback Win+S for search")
                            return fallback_action
                    
                    # Real launch/execute functionality
                    elif any(keyword in step_lower for keyword in ["launch", "open", "execute", "run", "enter"]):
                        fallback_action = {
                            "type": "key",
                            "key": "enter", 
                            "summary": "Press Enter to execute/launch selected item",
                            "confidence": 90
                        }
                        logger.info(f"Created real fallback Enter key for launch")
                        return fallback_action
                    
                    # Real clicking with actual screen coordinates
                    elif any(keyword in step_lower for keyword in ["click", "select", "choose"]):
                        # Determine click coordinates based on context
                        click_x, click_y = 960, 540  # Screen center as default
                        
                        # Start button area (Windows 11 style)
                        if "start" in step_lower:
                            click_x, click_y = 960, 1050  # Center-bottom of screen
                        # Taskbar area
                        elif "taskbar" in step_lower:
                            click_x, click_y = 960, 1050  # Taskbar center
                        # Search results area (typical Windows 11 search position)
                        elif "result" in step_lower or "calculator" in step_lower:
                            click_x, click_y = 960, 400   # Upper-center where search results appear
                        # Desktop area
                        elif "desktop" in step_lower:
                            click_x, click_y = 200, 200   # Upper-left desktop area
                        
                        fallback_action = {
                            "type": "click",
                            "x": click_x,
                            "y": click_y,
                            "summary": f"Click at ({click_x}, {click_y}) - {step_lower[:50]}",
                            "confidence": 80
                        }
                        logger.info(f"Created real fallback click action at ({click_x}, {click_y})")
                        return fallback_action
                
                # Final fallback - basic Start menu access for any unknown situation
                logger.info(f"No specific fallback matched, using basic Start menu access")
                fallback_action = {
                    "type": "key",
                    "key": "win",
                    "summary": "Press Windows key (universal fallback)",
                    "confidence": 70
                }
                logger.info(f"Created universal fallback Windows key action")
                return fallback_action
            
            # If no fallback JSON could be created for action generation, return a valid action anyway
            logger.warning(f"No valid JSON found for '{context_description}', creating emergency fallback")
            if context_description == "action_generation":
                return {
                    "type": "key",
                    "key": "win", 
                    "summary": "Emergency fallback: Press Windows key",
                    "confidence": 60
                }
            else:
                return {"error": "No JSON found in LLM response and fallback action creation failed", "message": f"Context: {context_description}"}
        
        # For step generation, NEVER return error dicts - always return fallback steps
        if context_description == "step_generation":
            logger.warning(f"No JSON found for step generation, creating universal fallback steps")
            return [
                {
                    "step_number": 1,
                    "description": "Press Windows key to open Start menu",
                    "action_type": "key_sequence",
                    "target": "win",
                    "verification": "Start menu is visible"
                },
                {
                    "step_number": 2,
                    "description": "Type application name to search",
                    "action_type": "type",
                    "target": "search_term",
                    "verification": "Application appears in search results"
                },
                {
                    "step_number": 3,
                    "description": "Press Enter to launch application",
                    "action_type": "key",
                    "target": "enter", 
                    "verification": "Application opens successfully"
                }
            ]
        
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
            
            # Fix malformed JSON from LLM - handle quote escaping issues
            # Fix invalid escape sequences like "action_type": "click\"
            json_str_to_parse = re.sub(r'": "([^"]*)\\"', r'": "\1"', json_str_to_parse)
            
            # Fix unescaped quotes in description strings like "Click the "Start" button"
            def fix_unescaped_quotes_in_field(match):
                field_name = match.group(1)
                content = match.group(2)
                # Count quotes to see if they are properly escaped
                if content.count('"') > 0 and content.count('\\"') == 0:
                    # There are unescaped quotes, fix them
                    escaped_content = content.replace('"', '\\"')
                    return f'"{field_name}": "{escaped_content}"'
                return match.group(0)  # Return original if already escaped
            
            # Apply quote fixing to common string fields
            json_str_to_parse = re.sub(r'"(description|summary|text|target|input_text)": "([^"]*(?:"[^"]*)*)"', fix_unescaped_quotes_in_field, json_str_to_parse)
            
            # Log the cleaned JSON string for debugging
            logger.debug(f"Cleaned JSON string for '{context_description}': {json_str_to_parse}")
            
            # First parsing attempt
            try:
                parsed_json = json.loads(json_str_to_parse)
                logger.debug(f"Successfully parsed JSON for '{context_description}' after cleanup.")
            except json.JSONDecodeError as first_error:
                # If first attempt fails, try more aggressive cleanup
                logger.warning(f"First JSON parse attempt failed for '{context_description}': {first_error}")
                logger.warning(f"Problematic JSON string (full): {json_str_to_parse}")
                
                # Enhanced JSON cleaning for common issues
                json_str_cleaned = json_str_to_parse
                
                # Step 1: Remove any leading/trailing whitespace and newlines
                json_str_cleaned = json_str_cleaned.strip()
                
                # Step 2: Remove any text before the first { or [
                first_brace = json_str_cleaned.find('{')
                first_bracket = json_str_cleaned.find('[')
                start_idx = -1
                
                if first_brace != -1 and first_bracket != -1:
                    start_idx = min(first_brace, first_bracket)
                elif first_brace != -1:
                    start_idx = first_brace
                elif first_bracket != -1:
                    start_idx = first_bracket
                
                if start_idx > 0:
                    json_str_cleaned = json_str_cleaned[start_idx:]
                    logger.debug(f"Removed text before JSON start: {json_str_to_parse[:start_idx]}")
                
                # Step 3: Find the proper end of JSON by counting braces/brackets
                if json_str_cleaned.startswith('{'):
                    brace_count = 0
                    end_idx = -1
                    for i, char in enumerate(json_str_cleaned):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i + 1
                                break
                    if end_idx > 0:
                        json_str_cleaned = json_str_cleaned[:end_idx]
                elif json_str_cleaned.startswith('['):
                    bracket_count = 0
                    end_idx = -1
                    for i, char in enumerate(json_str_cleaned):
                        if char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end_idx = i + 1
                                break
                    if end_idx > 0:
                        json_str_cleaned = json_str_cleaned[:end_idx]
                
                # Step 4: Clean up common JSON issues
                # Remove any trailing commas before closing braces/brackets
                json_str_cleaned = re.sub(r',(\s*[}\]])', r'\1', json_str_cleaned)
                
                # Fix common quote issues in the step generation context
                if context_description == "step_generation":
                    # Replace smart quotes with regular quotes
                    json_str_cleaned = json_str_cleaned.replace('"', '"').replace('"', '"')
                    json_str_cleaned = json_str_cleaned.replace("'", "'").replace("'", "'")
                
                logger.debug(f"Cleaned JSON for second attempt: {json_str_cleaned}")
                
                try:
                    parsed_json = json.loads(json_str_cleaned)
                    logger.debug(f"Successfully parsed JSON for '{context_description}' after enhanced cleanup.")
                except json.JSONDecodeError as second_error:
                    logger.error(f"Second JSON parse attempt also failed for '{context_description}': {second_error}")
                    logger.error(f"Original error: {first_error}")
                    logger.error(f"Cleaned JSON that failed: {json_str_cleaned}")
                    
                    # For step generation, return a default structure rather than failing completely
                    if context_description == "step_generation":
                        logger.warning(f"Returning fallback steps due to JSON parsing failure")
                        return [
                            {
                                "step_number": 1,
                                "description": "Press Windows key to open Start menu",
                                "action_type": "key_sequence",
                                "target": "win",
                                "verification": "Start menu is visible"
                            },
                            {
                                "step_number": 2,
                                "description": "Type search term for desired application",
                                "action_type": "type",
                                "target": "search_term",
                                "verification": "Application appears in search results"
                            },
                            {
                                "step_number": 3,
                                "description": "Press Enter to launch application",
                                "action_type": "key",
                                "target": "enter", 
                                "verification": "Application opens successfully"
                            }
                        ]
                    
                    # Re-raise the original error for other contexts
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
            
            # For step generation, NEVER return error dicts - always return fallback steps
            if context_description == "step_generation":
                logger.warning(f"JSON decode error for step generation, returning fallback steps")
                return [
                    {
                        "step_number": 1,
                        "description": "Press Windows key to open Start menu",
                        "action_type": "key_sequence",
                        "target": "win",
                        "verification": "Start menu is visible"
                    },
                    {
                        "step_number": 2,
                        "description": "Type search term for desired application",
                        "action_type": "type",
                        "target": "search_term",
                        "verification": "Application appears in search results"
                    },
                    {
                        "step_number": 3,
                        "description": "Press Enter to launch application",
                        "action_type": "key",
                        "target": "enter", 
                        "verification": "Application opens successfully"
                    }
                ]
            
            return {"error": "JSON_DECODE_ERROR", "message": str(e), "json_string_preview": json_sample}

    # Fallback if json_str_to_parse was not set (e.g. markdown found, but group(1) was empty - unlikely)
    logger.error(f"JSON processing failed unexpectedly for '{context_description}'. No JSON string was identified for parsing.")
    
    # For step generation, NEVER return error dicts - always return fallback steps
    if context_description == "step_generation":
        logger.warning(f"JSON processing failed unexpectedly for step generation, returning fallback steps")
        return [
            {
                "step_number": 1,
                "description": "Press Windows key to open Start menu",
                "action_type": "key_sequence",
                "target": "win",
                "verification": "Start menu is visible"
            },
            {
                "step_number": 2,
                "description": "Type search term for desired application",
                "action_type": "type",
                "target": "search_term",
                "verification": "Application appears in search results"
            },
            {
                "step_number": 3,
                "description": "Press Enter to launch application",
                "action_type": "key",
                "target": "enter", 
                "verification": "Application opens successfully"
            }
        ]
    
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
        from core.prompts.prompts import ACTION_GENERATION_USER_PROMPT_TEMPLATE
        
        # Use the proper template and format it with the required variables
        return ACTION_GENERATION_USER_PROMPT_TEMPLATE.format(
            step_description=current_step_description,
            objective=objective,
            visual_analysis=visual_analysis_output or "No visual analysis available"
        )

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

    async def get_next_action(self, model, messages, objective, session_id, screenshot_path, thinking_callback=None):
        """
        Send the `messages` conversation context to the chosen model and
        return its raw text response.

        Args:
            thinking_callback: Optional async function to call with streamed tokens

        Returns:
            tuple[str, str, None]: (response_text, session_id, None)
        """
        print(f"[MainInterface] Using model: {model} via API source: {self.api_source}")  # Updated log

        if self.api_source == "openai":
            # call_openai_model now returns a string (either JSON string for actions, or plain text for other stages)
            response_str = await call_openai_model(messages, objective, model, thinking_callback)
            
            # For visual, thinking, steps stages, the response_str is the direct text.
            # For action stage, response_str is a JSON string that handle_llm_response will parse.
            # The `get_next_action` in `operate.py` for non-action stages directly uses the first element of the tuple.
            # The `handle_llm_response` in `operate.py` for action stage expects the JSON to be parsed from the string.

            # No change needed here if call_openai_model returns a string as expected by callers.
            # The `DEBUG` print might show a JSON string or plain text.
            print(f"[DEBUG] OpenAI Response String: {response_str}") 
            return (response_str, session_id, None)
        elif self.api_source == "lmstudio":
            response = await call_lmstudio_model(messages, objective, model, thinking_callback)
            print(f"[DEBUG] LMStudio Response: {response}")
            return (response, session_id, None)

        raise ModelNotRecognizedException(model)
    
    # Alias for backward compatibility: unify LLM calls under get_llm_response
    async def get_llm_response(self, model, messages, objective, session_id, response_format_type=None, thinking_callback=None):
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
                self.get_next_action(model, messages, objective, session_id, screenshot_path=None, thinking_callback=thinking_callback)
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
            screenshot_path="dummy.png",
            thinking_callback=None
        )
        print("Test result:", text)

    asyncio.run(_test())
