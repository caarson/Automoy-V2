import json
import re
import asyncio
import os
import pathlib
import socket
import sys
import psutil
import requests
import logging # Import logging
import platform # Add this import
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List # Add List here if it's used elsewhere, ensure Dict, Optional, Any are present

from core.exceptions import AutomoyError, OperationError
from core.utils.operating_system.os_interface import OSInterface
from core.utils.omniparser.omniparser_interface import OmniParserInterface
from core.lm.lm_interface import MainInterface as LLMInterface
from core.prompts.prompts import (
    VISUAL_ANALYSIS_SYSTEM_PROMPT,
    VISUAL_ANALYSIS_USER_PROMPT_TEMPLATE,
    THINKING_PROCESS_SYSTEM_PROMPT, 
    THINKING_PROCESS_USER_PROMPT_TEMPLATE, 
    STEP_GENERATION_SYSTEM_PROMPT, 
    STEP_GENERATION_USER_PROMPT_TEMPLATE, 
    ACTION_GENERATION_SYSTEM_PROMPT,
)
from config import Config
from core.utils.operating_system.desktop_utils import DesktopUtils

# Get a logger for this module
logger = logging.getLogger(__name__)

# Ensure the project root is added to the Python path
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))) # Already there, but ensure it's correct

# Add the project root to the Python path if this script is run directly
if __name__ == "__main__" and (__package__ is None or __package__ == ''):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# Define Project Root for operate.py
OPERATE_PY_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW_SCREENSHOT_FILENAME = "automoy_current.png" # Relative to project root
PROCESSED_SCREENSHOT_RELATIVE_PATH = pathlib.Path("core") / "utils" / "omniparser" / "processed_screenshot.png"

# Adjust imports to use absolute paths consistently
from core.utils.omniparser.omniparser_interface import OmniParserInterface
from core.utils.operating_system.os_interface import OSInterface
from core.utils.vmware.vmware_interface import VMWareInterface
from core.utils.web_scraping.webscrape_interface import WebScrapeInterface
from core.utils.region.mapper import map_elements_to_coords
# from core.prompts.prompts import get_system_prompt # get_system_prompt is imported below with others

# 👉 Integrated LLM interface (merged MainInterface + handle_llm_response)
from core.lm.lm_interface import MainInterface, handle_llm_response
from core.environmental.anchor.desktop_anchor_point import show_desktop
from core.utils.operating_system.desktop_utils import DesktopUtils # Added

# Config import - ensure this path is robust
# Assuming config is in the parent directory of core
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "config"))
from config import Config


# Define BASE64_RE at the module level
BASE64_RE = re.compile(r'^[A-Za-z0-9+/=\\s]{100,}$')

def clean_json_data(obj): # Renamed to avoid conflict if defined elsewhere
    """Recursively remove long base64-like strings from a JSON-like structure."""
    if isinstance(obj, dict):
        return {k: clean_json_data(v) for k, v in obj.items() if not (isinstance(v, str) and BASE64_RE.match(v))}
    elif isinstance(obj, list):
        return [clean_json_data(elem) for elem in obj]
    # Removed string cleaning part that was too aggressive, OmniParser should return clean text.
    # If specific string cleaning is needed, it should be more targeted.
    else:
        return obj

# Function to check if a port is in use
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

# Function to check if a process with a specific name is running
def is_process_running(process_name):
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == process_name:
            return True
    return False

# Helper function to update GUI state (moved to module level for broader access if needed)
async def _update_gui_state(endpoint: str, payload: dict):
    """Helper to asynchronously send state updates to the GUI."""
    try:
        # Ensure the endpoint starts with a slash
        if not endpoint.startswith("/"):
            url_endpoint = f"/state/{endpoint}" # Default to /state/ if not a full path
        else:
            url_endpoint = endpoint

        url = f"http://127.0.0.1:8000{url_endpoint}"
        
        loop = asyncio.get_event_loop()
        # Using lambda to capture current payload value for the executor thread
        current_payload = payload 
        response = await loop.run_in_executor(None, lambda: requests.post(url, json=current_payload, timeout=5))
        
        if response.status_code == 200:
            logger.debug(f"[GUI_UPDATE] Successfully sent payload to {url}. Response status: {response.status_code}, text: {response.text[:100] if response.text else 'N/A'}")
        else:
            logger.warning(f"[GUI_UPDATE] Failed to send payload to {url}. Response status: {response.status_code}, text: {response.text[:200] if response.text else 'N/A'}")
            
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to update GUI state at {url} (RequestException): {e}")
    except Exception as e:
        logger.error(f"Unexpected error in _update_gui_state sending to {url}: {e}", exc_info=True)


class AutomoyOperator:
    """Central orchestrator for Automoy autonomous operation."""

    def __init__(self, objective: str | None = None, manage_gui_window_func=None, omniparser: OmniParserInterface = None, pause_event: asyncio.Event = None): # Added pause_event
        self.os_interface = OSInterface()
        self.omniparser_instance = omniparser if omniparser else OmniParserInterface() 
        self.vmware = VMWareInterface("localhost", "user", "password")
        self.webscraper = WebScrapeInterface()
        self.llm = LLMInterface() 
        self.manage_gui_window_func = manage_gui_window_func
        self.pause_event = pause_event 
        
        self.config = Config()
        try:
            self.model = self.config.get_model()
        except Exception as e:
            logger.error(f"Could not determine model from config: {e}")
            self.model = "gpt-4"  # fallback
        self.objective = objective
        self.desktop_anchor_point = self.config.get("DESKTOP_ANCHOR_POINT", False)
        self.prompt_anchor_point = self.config.get("PROMPT_ANCHOR_POINT", False)
        self.vllm_anchor_point = self.config.get("VLLM_ANCHOR_POINT", False)
        self.anchor_prompt = self.config.get("PROMPT", "")
        self.action_delay = self.config.get("ACTION_DELAY", 2.0) # Used for delays after specific actions

        # ─── Runtime state ────────────────────────────────────────────
        self.raw_screenshot_path_for_parsing: str | None = None 
        self.active_screenshot_for_llm_gui: str | None = None 
        self.ui_json_for_llm: str | None = None 
        self.coords: dict | None = None  
        self.last_action: dict | None = None
        
        self.visual_analysis_output: str = ""
        self.thinking_process_output: str = ""
        self.generated_steps_output: list[str] = []
        self.current_step_index: int = 0
        
        self.run_capture_on_next_cycle = True
        self.last_action_execution_status: bool | None = None

    async def _capture_and_process_screenshot(self, screenshot_path: str):
        """Captures a screenshot, processes it with OmniParser, and updates self.coords."""
        logger.info(f"Preparing to capture screenshot to: {screenshot_path}")
        gui_minimized_for_screenshot = False
        try:
            # Minimize Automoy GUI first, only if configured and necessary
            if self.manage_gui_window_func and self.config.get("MINIMIZE_GUI_DURING_SCREENSHOT", True): # Use config flag
                logger.info("Minimizing Automoy GUI for screenshot.")
                await self.manage_gui_window_func("minimize")
                gui_minimized_for_screenshot = True
                await asyncio.sleep(0.5) # Give time for Automoy GUI to minimize

            # Show desktop (minimize all other windows)
            if self.desktop_anchor_point: # Only if desktop anchor point is configured
                logger.info("Showing desktop (minimizing all windows) for screenshot.")
                desktop_utils = DesktopUtils() # Assuming DesktopUtils is available
                desktop_utils.show_desktop()
                await asyncio.sleep(0.5) # Give time for windows to minimize

            logger.info(f"Capturing screenshot to: {screenshot_path}")
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            
            self.raw_screenshot_path_for_parsing = self.os_interface.take_screenshot(
                filename=screenshot_path
            )
            if not self.raw_screenshot_path_for_parsing or not os.path.exists(self.raw_screenshot_path_for_parsing):
                logger.error("Failed to capture screenshot or screenshot file not found.")
                self.run_capture_on_next_cycle = True # Retry capture
                return

            logger.info(f"Screenshot captured: {self.raw_screenshot_path_for_parsing}")
            
            # Process with OmniParser
            logger.info("Processing screenshot with OmniParser...")
            raw_parser_output = self.omniparser_instance.parse_screenshot(self.raw_screenshot_path_for_parsing)
            
            # Determine which screenshot path to use for LLM and GUI notification
            processed_screenshot_full_path = OPERATE_PY_PROJECT_ROOT / PROCESSED_SCREENSHOT_RELATIVE_PATH
            if processed_screenshot_full_path.exists():
                logger.info(f"CONFIRMED: Processed screenshot exists at {processed_screenshot_full_path} after OmniParser call.")
                self.active_screenshot_for_llm_gui = str(processed_screenshot_full_path)
            else:
                logger.warning(f"WARNING: Processed screenshot DOES NOT exist at {processed_screenshot_full_path} after OmniParser call. LLM/GUI will use raw screenshot.")
                self.active_screenshot_for_llm_gui = self.raw_screenshot_path_for_parsing # Fallback to raw

            cleaned_parser_output_for_log = clean_json_data(raw_parser_output) 
            logger.debug(f"Raw OmniParser output (cleaned for log): {json.dumps(cleaned_parser_output_for_log, indent=2)}")

            if raw_parser_output and isinstance(raw_parser_output, dict):
                if 'coords' in raw_parser_output and isinstance(raw_parser_output['coords'], list):
                    self.coords = raw_parser_output['coords']
                    logger.info(f"Assigned {len(self.coords)} elements from 'coords' to self.coords.")
                elif 'parsed_content_list' in raw_parser_output and isinstance(raw_parser_output['parsed_content_list'], list):
                    self.coords = raw_parser_output['parsed_content_list']
                    logger.info(f"Assigned {len(self.coords)} elements from 'parsed_content_list' to self.coords.")
                else:
                    logger.warning("OmniParser output does not contain 'coords' or 'parsed_content_list' as a list.")
                    self.coords = []

                if self.active_screenshot_for_llm_gui == str(processed_screenshot_full_path):
                    logger.info(f"OmniParser processing complete. Using PROCESSED screenshot for LLM/GUI: {self.active_screenshot_for_llm_gui}")
                else:
                    logger.info(f"OmniParser processing complete. Using RAW screenshot for LLM/GUI: {self.active_screenshot_for_llm_gui}")
                
                self.ui_json_for_llm = json.dumps(clean_json_data(raw_parser_output))
            else:
                logger.error(f"Failed to parse screenshot or OmniParser returned invalid data.")
                self.active_screenshot_for_llm_gui = self.raw_screenshot_path_for_parsing # Ensure fallback
                logger.info(f"LLM/GUI will use RAW screenshot due to parsing error: {self.active_screenshot_for_llm_gui}")
                self.coords = []
                self.ui_json_for_llm = None
                self.run_capture_on_next_cycle = True
                return

            logger.debug(f"self.coords after assignment: {json.dumps(self.coords[:5], indent=2)}... (first 5 elements)")
            self.run_capture_on_next_cycle = False

        except Exception as e:
            logger.error(f"Error in _capture_and_process_screenshot: {e}", exc_info=True)
            self.coords = []
            self.ui_json_for_llm = None
            self.run_capture_on_next_cycle = True
        finally:
            # Show Automoy GUI after processing, only if it was minimized for this screenshot
            if gui_minimized_for_screenshot and self.manage_gui_window_func:
                logger.info("Showing Automoy GUI after screenshot processing.")
                await self.manage_gui_window_func("show")
                await asyncio.sleep(0.2) # Give time for Automoy GUI to show

    async def _execute_action(self, action_json: dict) -> bool:
        """
        Executes the action specified in action_json.
        Updates GUI with current operation and last action result.
        Returns True if successful, False otherwise.
        """
        action_type = action_json.get("operation")
        
        # Refined action_target_description logic
        action_target_description = ""
        if action_type == "click":
            element_details = []
            if action_json.get("element_id"):
                element_details.append(f"ID '{action_json['element_id']}'")
            if action_json.get("text"): # Text specified in the action command by LLM
                element_details.append(f"text '{action_json['text']}'")
            if action_json.get("element_label"): # Label specified in the action command by LLM
                 element_details.append(f"label '{action_json['element_label']}'")
            if not element_details and action_json.get("x") is not None and action_json.get("y") is not None: # Coords specified by LLM
                element_details.append(f"coordinates ({action_json['x']}, {action_json['y']})")
            
            if element_details:
                action_target_description = f"element with {', '.join(element_details)}"
            else:
                action_target_description = "an unspecified element (check LLM output for details)"

        elif action_type == "type_text":
            action_target_description = f"text input '{action_json.get('text', '')[:50]}...'" if len(action_json.get('text', '')) > 50 else f"text input '{action_json.get('text', '')}'"
        elif action_type == "scroll":
            action_target_description = f"scroll {action_json.get('direction', 'N/A')}"
        elif action_type == "finish":
            action_target_description = "the operation"
        else:
            action_target_description = action_json.get("details", f"action '{action_type}'")

        logger.info(f"Attempting action: {action_type} on {action_target_description}")
        await _update_gui_state("/state/current_operation", {"text": f"Executing: {action_type} on {action_target_description}"})

        success = False
        error_message = None
        gui_minimized_for_action = False

        try:
            # Minimize GUI before certain actions if configured
            if action_type in ["click", "type_text"] and self.manage_gui_window_func and self.config.get("MINIMIZE_GUI_DURING_ACTION", False): # Use config flag
                logger.info(f"Minimizing Automoy GUI before '{action_type}' action.")
                await self.manage_gui_window_func("minimize")
                gui_minimized_for_action = True
                await asyncio.sleep(0.3) # Give time for GUI to minimize

            if action_type == "click":
                element_data_found = None
                target_identifier_for_log = "Unknown" 
                element_bbox_for_click = None

                action_element_id = action_json.get("element_id")
                action_text_target = action_json.get("text") 
                action_label_target = action_json.get("element_label")

                if not self.coords: 
                    error_message = "Click action failed: Coordinates data (self.coords) is not available or empty."
                    logger.error(error_message)
                elif not isinstance(self.coords, list):
                    error_message = f"Click action failed: self.coords is not a list as expected (type: {type(self.coords)})."
                    logger.error(error_message)
                else:
                    if action_element_id:
                        for elem_data in self.coords:
                            if isinstance(elem_data, dict) and (elem_data.get("id") == action_element_id or elem_data.get("element_id") == action_element_id):
                                element_data_found = elem_data
                                target_identifier_for_log = f"element_id: '{action_element_id}'"
                                break
                    
                    if not element_data_found and action_text_target:
                        for elem_data in self.coords:
                            if isinstance(elem_data, dict) and elem_data.get("text") == action_text_target:
                                element_data_found = elem_data
                                target_identifier_for_log = f"text: '{action_text_target}' (found in element '{elem_data.get('id', 'N/A')}')"
                                break
                    
                    if not element_data_found and action_label_target:
                        for elem_data in self.coords:
                            if isinstance(elem_data, dict) and elem_data.get("label") == action_label_target:
                                element_data_found = elem_data
                                target_identifier_for_log = f"label: '{action_label_target}' (found in element '{elem_data.get('id', 'N/A')}')"
                                break
                    
                    if element_data_found:
                        bbox_candidate = element_data_found.get("bbox")
                        if bbox_candidate and isinstance(bbox_candidate, (list, tuple)) and len(bbox_candidate) == 4:
                            element_bbox_for_click = bbox_candidate
                        else:
                            error_message = f"Click action failed for {target_identifier_for_log}: Bounding box missing or invalid in element data {element_data_found}."
                            logger.error(error_message)
                    else:
                        tried_identifiers_parts = []
                        if action_element_id: tried_identifiers_parts.append(f"element_id '{action_element_id}'")
                        if action_text_target: tried_identifiers_parts.append(f"text '{action_text_target}'")
                        if action_label_target: tried_identifiers_parts.append(f"label '{action_label_target}'")
                        tried_identifiers_str = ", ".join(tried_identifiers_parts) if tried_identifiers_parts else "any provided identifiers by LLM"
                        
                        error_message = f"Click action failed: Element not found using {tried_identifiers_str}."
                        
                        # Enhanced coords_debug_info
                        if isinstance(self.coords, list):
                            coords_summary = f"self.coords contains {len(self.coords)} elements. "
                            if len(self.coords) > 0:
                                coords_summary += "First up to 5 elements (text/label/id | bbox): "
                                details = []
                                for i, item in enumerate(self.coords):
                                    if i >= 5: break 
                                    if isinstance(item, dict):
                                        item_desc = item.get('text', item.get('label', item.get('id', 'N/A')))
                                        item_bbox = item.get('bbox', 'N/A')
                                        details.append(f"'{item_desc}' (bbox: {item_bbox})")
                                    else:
                                        details.append(str(item))
                                coords_summary += "; ".join(details)
                            else:
                                coords_summary += "self.coords is an empty list."
                            logger.error(f"{error_message} {coords_summary}")
                        else:
                            logger.error(f"{error_message} self.coords is not a list, type: {type(self.coords)}.")

                if element_bbox_for_click:
                    x1, y1, x2, y2 = element_bbox_for_click
                    if x2 <= x1 or y2 <= y1: 
                        error_message = f"Click action failed for {target_identifier_for_log}: Invalid bounding box {element_bbox_for_click}."
                        logger.error(error_message)
                    else:
                        click_x = (x1 + x2) // 2
                        click_y = (y1 + y2) // 2
                        
                        logger.info(f"Moving to ({click_x}, {click_y}) for element identified by {target_identifier_for_log}")
                        self.os_interface.move_mouse(click_x, click_y, duration=0.1) 
                        await asyncio.sleep(0.1) 
                        
                        logger.info(f"Clicking at ({click_x}, {click_y}) for element identified by {target_identifier_for_log} (LLM Target: {action_target_description})")
                        self.os_interface.click_mouse() 
                        await asyncio.sleep(self.action_delay) 
                        success = True
                        logger.info(f"Click on element identified by {target_identifier_for_log} successful.")
                # If element_bbox_for_click is None, success remains False, error_message should be set.
            
            elif action_type == "type_text":
                text_to_type = action_json.get("text")
                if text_to_type is None: # Empty string is a valid type action (e.g. to clear a field or trigger suggestion)
                    error_message = "Type action failed: No 'text' field provided in action JSON."
                    logger.error(error_message)
                else:
                    logger.info(f"Typing text (length {len(text_to_type)}).")
                    self.os_interface.type_text(text_to_type)
                    await asyncio.sleep(self.action_delay) 
                    success = True
                    logger.info("Type text successful.")
            
            elif action_type == "scroll":
                direction = action_json.get("direction")
                # amount = action_json.get("amount", "default") # Consider if 'amount' is needed by os_interface.scroll
                if direction:
                    logger.info(f"Scrolling {direction}.")
                    self.os_interface.scroll(direction) # Assuming os_interface.scroll takes direction
                    await asyncio.sleep(self.action_delay) 
                    success = True
                    logger.info(f"Scroll {direction} successful.")
                else:
                    error_message = "Scroll action failed: No direction provided."
                    logger.error(error_message)
            
            elif action_type == "finish":
                logger.info("Finish action received. Operation will conclude.")
                success = True # The action itself is successful in being recognized

            elif action_type == "error": # If LLM explicitly returns an error operation
                error_message = action_json.get("reasoning", "LLM indicated an error in its proposed action.")
                logger.error(f"LLM reported an error action: {error_message}")
                # success remains False

            else: # Unknown action type
                error_message = f"Unknown or unsupported action type: {action_type}"
                logger.error(error_message)
                # success remains False

            self.last_action_execution_status = success
            if success:
                logger.info(f"Action '{action_type}' on '{action_target_description}' processed successfully by operator.")
            else:
                logger.warning(f"Action '{action_type}' on '{action_target_description}' failed or was not executed. Error: {error_message if error_message else 'Reason not specified.'}")
            
            return success

        except Exception as e:
            logger.error(f"Critical error during execution of action '{action_type}' on '{action_target_description}': {e}", exc_info=True)
            self.last_action_execution_status = False
            return False
        finally:
            if gui_minimized_for_action and self.manage_gui_window_func:
                logger.info(f"Showing Automoy GUI after '{action_type}' action.")
                await self.manage_gui_window_func("show")
                await asyncio.sleep(0.2)

    # ───────────────────────────── LLM Multi-Stage Reasoning ───────────────────────────

    async def _perform_visual_analysis(self, current_screenshot_path: str, current_ui_json: str | None):
        """Performs visual analysis of the current screen and UI data."""
        logger.info("Performing visual analysis...")
        if not hasattr(self, '_llm_call_iteration'):
            self._llm_call_iteration = 0
        
        visual_analysis_user_prompt = VISUAL_ANALYSIS_USER_PROMPT_TEMPLATE.format(
            objective=self.objective,
            screenshot_elements=current_ui_json if current_ui_json else "No UI elements detected or available."
        )
        
        messages_visual = []
        if VISUAL_ANALYSIS_SYSTEM_PROMPT:
            messages_visual.append({"role": "system", "content": VISUAL_ANALYSIS_SYSTEM_PROMPT})
        messages_visual.append({"role": "user", "content": visual_analysis_user_prompt})

        try:
            response_tuple_visual = await self.llm.get_next_action(
                model=self.model,
                messages=messages_visual,
                objective="Perform visual analysis of the current screen.",
                session_id=f"automoy-op-{self._llm_call_iteration}-visual",
                screenshot_path=current_screenshot_path
            )
            raw_visual_analysis = response_tuple_visual[0]
            self.visual_analysis_output = handle_llm_response(raw_visual_analysis, "visual analysis", llm_interface=self.llm)
            logger.info(f"Visual Analysis Output: {self.visual_analysis_output[:300]}...")
            await _update_gui_state("/state/visual", {"text": self.visual_analysis_output})
        except Exception as e:
            logger.error(f"Error during visual analysis: {e}", exc_info=True)
            self.visual_analysis_output = "Error during visual analysis."
            await _update_gui_state("/state/visual", {"text": self.visual_analysis_output})
            raise

    async def _perform_thinking_process(self):
        """Generates a thinking process based on the objective and visual analysis."""
        logger.info("Generating thinking process...")
        if not self.visual_analysis_output:
            logger.warning("Visual analysis output is missing, cannot generate thinking process.")
            self.thinking_process_output = "Skipped: Visual analysis was not available."
            await _update_gui_state("/state/thinking", {"text": self.thinking_process_output})
            return

        thinking_user_prompt = THINKING_PROCESS_USER_PROMPT_TEMPLATE.format(
            objective=self.objective,
            visual_summary=self.visual_analysis_output
        )
        
        messages_thinking = []
        if THINKING_PROCESS_SYSTEM_PROMPT:
            messages_thinking.append({"role": "system", "content": THINKING_PROCESS_SYSTEM_PROMPT})
        messages_thinking.append({"role": "user", "content": thinking_user_prompt})

        try:
            response_tuple_thinking = await self.llm.get_next_action(
                model=self.model,
                messages=messages_thinking,
                objective="Generate a strategic thinking process.",
                session_id=f"automoy-op-{self._llm_call_iteration}-thinking",
                screenshot_path=None # Thinking is based on visual summary, not direct screenshot
            )
            raw_thinking = response_tuple_thinking[0]
            self.thinking_process_output = handle_llm_response(raw_thinking, "thinking process", llm_interface=self.llm)
            logger.info(f"Thinking Process Output: {self.thinking_process_output[:300]}...")
            await _update_gui_state("/state/thinking", {"text": self.thinking_process_output})
        except Exception as e:
            logger.error(f"Error during thinking process generation: {e}", exc_info=True)
            self.thinking_process_output = "Error during thinking process generation."
            await _update_gui_state("/state/thinking", {"text": self.thinking_process_output})
            raise

    async def _generate_steps(self):
        """Generates actionable steps based on objective, visual analysis, and thinking."""
        logger.info("Generating steps...")
        if not self.visual_analysis_output or not self.thinking_process_output:
            logger.warning("Visual analysis or thinking process output is missing, cannot generate steps.")
            self.generated_steps_output = ["Error: Prerequisite data (visual/thinking) missing for step generation."]
            await _update_gui_state("/state/steps", {"steps": self.generated_steps_output})
            return

        step_gen_user_prompt = STEP_GENERATION_USER_PROMPT_TEMPLATE.format(
            objective=self.objective,
            visual_summary=self.visual_analysis_output,
            thinking_summary=self.thinking_process_output
        )
        
        messages_steps = []
        if STEP_GENERATION_SYSTEM_PROMPT:
            messages_steps.append({"role": "system", "content": STEP_GENERATION_SYSTEM_PROMPT})
        messages_steps.append({"role": "user", "content": step_gen_user_prompt})

        try:
            response_tuple_steps = await self.llm.get_next_action(
                model=self.model,
                messages=messages_steps,
                objective="Generate a list of actionable steps.",
                session_id=f"automoy-op-{self._llm_call_iteration}-steps",
                screenshot_path=None 
            )
            raw_steps_output = response_tuple_steps[0]
            processed_steps_text = handle_llm_response(raw_steps_output, "step generation", llm_interface=self.llm)
            
            self.generated_steps_output = []
            if processed_steps_text:
                potential_steps = [step.strip() for step in processed_steps_text.split('\\n') if step.strip()]
                for step_line in potential_steps:
                    if re.match(r"^\\d+\\.\\s*", step_line):
                        self.generated_steps_output.append(re.sub(r"^\\d+\\.\\s*", "", step_line).strip())
                    elif potential_steps and len(potential_steps) == 1 and not re.match(r"^\\d+\\.\\s*", step_line):
                        self.generated_steps_output.append(step_line)

            if not self.generated_steps_output and processed_steps_text: 
                logger.warning(f"Could not parse steps into a numbered list. Using raw output: {processed_steps_text}")
                self.generated_steps_output = [f"Could not parse steps: {processed_steps_text}"]
            elif not self.generated_steps_output:
                self.generated_steps_output = ["No steps were generated or output was empty."]

            logger.info(f"Generated Steps: {self.generated_steps_output}")
            await _update_gui_state("/state/steps", {"steps": self.generated_steps_output})
            self.current_step_index = 0
        except Exception as e: # Added except block to fix the try statement error
            logger.error(f"Error during step generation: {e}", exc_info=True)
            self.generated_steps_output = [f"Error during step generation: {e}"]
            await _update_gui_state("/state/steps", {"text": f"Error: {e}"}) 
            raise 

    async def _ensure_plan_exists(self):
        """Ensures that a plan (visual analysis, thinking, steps) exists. Regenerates if needed."""
        if not self.visual_analysis_output or not self.thinking_process_output or not self.generated_steps_output:
            logger.info("Plan is incomplete. Regenerating full plan...")
            self.run_capture_on_next_cycle = True # Ensure fresh screenshot for new plan
            await self._capture_and_process_screenshot(self.raw_screenshot_path_for_parsing or RAW_SCREENSHOT_FILENAME)
            
            if not self.active_screenshot_for_llm_gui or not self.ui_json_for_llm:
                logger.error("Failed to capture or process screenshot for plan regeneration. Cannot proceed.")
                # Potentially update GUI with error state here
                await _update_gui_state("/state/current_operation", {"text": "Error: Failed to get screen data for planning."})
                return False # Indicate failure to ensure plan

            try:
                await self._perform_visual_analysis(self.active_screenshot_for_llm_gui, self.ui_json_for_llm)
                await self._perform_thinking_process()
                await self._generate_steps()
                if not self.generated_steps_output or "Error" in self.generated_steps_output[0]:
                    logger.error("Failed to generate a valid plan even after retry.")
                    return False # Indicate failure
            except Exception as e:
                logger.error(f"Exception during plan regeneration: {e}", exc_info=True)
                return False # Indicate failure
        return True # Plan exists or was successfully regenerated

    async def _get_action_for_current_step(self, current_step_description: str, current_step_index: int) -> Optional[Dict[str, Any]]:
        """
        Determines the next action to take based on the current step of the formulated objective.
        It queries the LLM with the current context (objective, step, screenshot) and parses the response.
        """
        logger.info(f"Getting action for step {current_step_index}: {current_step_description}")
        if not self.active_screenshot_for_llm_gui:
            logger.error("No active screenshot available for LLM input in _get_action_for_current_step.")
            # Send a specific error to GUI for operations
            error_action = {"error": "Screenshot missing for LLM."}
            await self._update_gui_state("/state/operations_generated", {"json": error_action})
            return None

        # Construct messages for LLM
        messages = self.construct_messages_for_action(current_step_description)
        
        proposed_action = None
        try:
            logger.debug(f"Querying LLM for action. Objective: {self.objective}, Step: {current_step_description}")
            # Ensure self.llm_interface is not None
            if not self.llm_interface:
                logger.error("LLM interface is not initialized in AutomoyOperator.")
                # Send a specific error to GUI for operations
                error_action = {"error": "LLM interface not initialized."}
                await self._update_gui_state("/state/operations_generated", {"json": error_action})
                return None

            response_text, _, _ = await self.llm_interface.get_next_action(
                model=self.config.get_model(), 
                messages=messages,
                objective=self.objective, # Pass the full objective
                session_id=self.session_id, # Pass the session_id
                screenshot_path=self.active_screenshot_for_llm_gui 
            )
            
            if response_text:
                # The handle_llm_response method should parse and return a single action dictionary,
                # or an empty dict if parsing fails or no valid action is found.
                proposed_action = self.llm_interface.handle_llm_response(response_text, self.objective)
                logger.info(f"LLM proposed action_data: {proposed_action}")
            else:
                logger.warning("LLM returned no response_text.")
                proposed_action = {} # Treat as no action

        except Exception as e:
            logger.error(f"Error getting action from LLM: {e}", exc_info=True)
            proposed_action = {"error": f"LLM query failed: {e}"} # Send error to GUI

        # Ensure proposed_action is a dictionary, even if empty or an error placeholder
        if not isinstance(proposed_action, dict):
            logger.warning(f"Proposed action is not a dict: {proposed_action}. Resetting to error placeholder.")
            proposed_action = {"error": "Invalid action format from LLM."}


        if proposed_action and proposed_action != {} and not proposed_action.get("error"):
            logger.info(f"Action for current step: {proposed_action}")
            await self._update_gui_state("/state/operations_generated", {"json": proposed_action})
            # Store this as the last proposed action
            self.last_proposed_action = proposed_action
            return proposed_action
        else:
            # If proposed_action is empty, None, or an error dictionary
            if proposed_action and proposed_action.get("error"):
                logger.warning(f"No valid action determined. LLM/Parsing issue: {proposed_action.get('error')}")
                await self._update_gui_state("/state/operations_generated", {"json": proposed_action})
            else:
                logger.warning(f"No valid action determined. Proposed action was empty or None: {proposed_action}")
                placeholder_action = {"info": "No action generated or action was empty."}
                await self._update_gui_state("/state/operations_generated", {"json": placeholder_action})
            self.last_proposed_action = None # Clear last proposed action
            return None

    async def operate_loop(self):
        """
        Main operational loop for Automoy.
        Orchestrates screen capture, multi-stage reasoning (visual analysis, thinking, steps),
        action generation for each step, and action execution.
        """
        logger.info(f"Starting Automoy operator loop with objective: {self.objective}")
        if not self.objective:
            logger.error("Objective is not set. Cannot start operation.")
            await _update_gui_state("/state/current_operation", {"text": "Error: Objective not set."})
            return

        if not hasattr(self, '_llm_call_iteration'): # Ensure iteration counter is initialized
            self._llm_call_iteration = 0

        self.run_capture_on_next_cycle = True # Start with a screen capture

        while True:
            if self.pause_event and not self.pause_event.is_set(): # Corrected logic: if pause_event is defined and not set (meaning paused)
                logger.info("Operation paused. Waiting for resume signal...")
                await _update_gui_state("/state/current_operation", {"text": "Operation Paused. Waiting to resume..."})
                await self.pause_event.wait() # This will block until set() is called
                logger.info("Operation resumed.")
                self.run_capture_on_next_cycle = True # Re-capture screen after resume

            try:
                # 1. Capture and Process Screenshot (if needed)
                if self.run_capture_on_next_cycle:
                    screenshot_file = os.path.join(OPERATE_PY_PROJECT_ROOT, RAW_SCREENSHOT_FILENAME)
                    logger.info(f"Initiating screen capture and processing. Target path: {screenshot_file}")
                    await self._capture_and_process_screenshot(screenshot_file)
                    
                    # After capture and process, notify GUI about the screenshot
                    if self.active_screenshot_for_llm_gui and Path(self.active_screenshot_for_llm_gui).exists():
                        abs_screenshot_path = str(Path(self.active_screenshot_for_llm_gui).resolve())
                        logger.info(f"Notifying GUI with screenshot path: {abs_screenshot_path}")
                        await _update_gui_state("/state/screenshot", {"path": abs_screenshot_path, "timestamp": datetime.now().isoformat()})
                    else:
                        logger.warning(f"Screenshot path for GUI ('{self.active_screenshot_for_llm_gui}') is not available or file does not exist. GUI will not be updated with a new screenshot.")

                    if not self.active_screenshot_for_llm_gui or self.ui_json_for_llm is None: # Check if capture failed for LLM
                        logger.error("Failed to capture or process screenshot for LLM. Retrying after delay.")
                        await _update_gui_state("/state/current_operation", {"text": "Error: Screen capture failed for LLM. Retrying..."})
                        await asyncio.sleep(2) # Wait before retrying
                        self.run_capture_on_next_cycle = True
                        continue # Retry the loop to capture again
                    self.run_capture_on_next_cycle = False # Reset flag

                # 2. Ensure Plan Exists (Visual Analysis, Thinking, Steps)
                plan_ready = await self._ensure_plan_exists()
                if not plan_ready:
                    logger.error("Failed to establish a plan. Aborting current attempt or retrying.")
                    await _update_gui_state("/state/current_operation", {"text": "Error: Failed to generate a plan. Check logs."})
                    # Decide on recovery: retry, or stop. For now, let's retry after a delay.
                    await asyncio.sleep(5)
                    self.run_capture_on_next_cycle = True # Force re-capture and re-plan
                    continue

                # 3. Get Action for Current Step
                if self.current_step_index >= len(self.generated_steps_output):
                    logger.info("All planned steps completed. Objective might be achieved.")
                    action_json = {"operation": "finish", "reasoning": "All generated steps have been executed."}
                else:
                    action_json = await self._get_action_for_current_step()

                if not action_json or "operation" not in action_json:
                    logger.error("Invalid action JSON received. Attempting to re-plan.")
                    await _update_gui_state("/state/current_operation", {"text": "Error: Invalid action from LLM. Re-planning."})
                    self.run_capture_on_next_cycle = True # Force re-capture and re-plan
                    self.visual_analysis_output = "" # Clear previous plan states
                    self.thinking_process_output = ""
                    self.generated_steps_output = []
                    continue

                # 4. Process and Execute Action
                self.last_action = action_json
                operation_type = action_json.get("operation")

                if operation_type == "finish":
                    logger.info(f"Finish action received. Reasoning: {action_json.get('reasoning', 'No reasoning provided.')}")
                    await _update_gui_state("/state/current_operation", {"text": f"Objective completed: {action_json.get('reasoning', 'All steps executed.')}"})
                    await _update_gui_state("/state/last_action_status", {"status": "finished", "action": action_json})
                    break # Exit the main operating loop

                if operation_type == "error":
                    logger.error(f"LLM indicated an error: {action_json.get('reasoning', 'No reasoning provided.')}")
                    await _update_gui_state("/state/current_operation", {"text": f"LLM Error: {action_json.get('reasoning', 'Re-evaluating...')}"})
                    self.run_capture_on_next_cycle = True # Re-capture and re-evaluate
                    # Potentially clear plan to force full replan if LLM is stuck
                    # self.visual_analysis_output = ""
                    # self.thinking_process_output = ""
                    # self.generated_steps_output = []
                    await asyncio.sleep(1) # Brief pause before re-evaluating
                    continue

                action_executed_successfully = await self._execute_action(action_json)
                self.last_action_execution_status = action_executed_successfully

                if action_executed_successfully:
                    logger.info(f"Action '{operation_type}' executed successfully. Moving to next step or re-evaluating.")
                    await _update_gui_state("/state/last_action_status", {"status": "success", "action": action_json})
                    self.current_step_index += 1
                    # After a successful action, always re-capture to see the new state,
                    # unless the action was minor and a re-capture is explicitly skipped by some logic (not implemented here)
                    self.run_capture_on_next_cycle = True
                else:
                    logger.warning(f"Action '{operation_type}' failed to execute. Re-evaluating screen and current plan.")
                    await _update_gui_state("/state/last_action_status", {"status": "failure", "action": action_json, "error": "Action execution failed."})
                    # If an action fails, we should re-capture the screen to understand the current state
                    # and then potentially re-evaluate the current step or the entire plan.
                    self.run_capture_on_next_cycle = True
                    # Consider if we should retry the same step or invalidate the plan.
                    # For now, let's assume the LLM will adapt based on the new screen state for the current step.
                    # If it repeatedly fails on the same step, the plan might need to be regenerated by _ensure_plan_exists.

                await asyncio.sleep(self.config.get("LOOP_DELAY", 1.0)) # Configurable delay between actions/cycles

            except AutomoyError as e: # Catch custom application errors
                logger.error(f"AutomoyError in operate_loop: {e}", exc_info=True)
                await _update_gui_state("/state/current_operation", {"text": f"Error: {e}. Check logs."})
                # Decide on recovery or stop
                self.run_capture_on_next_cycle = True # Try to recover by re-capturing
                await asyncio.sleep(3) # Wait a bit before retrying
            except Exception as e:
                logger.error(f"Unexpected critical error in operate_loop: {e}", exc_info=True)
                await _update_gui_state("/state/current_operation", {"text": f"Critical Error: {e}. Operation stopped."})
                # For unexpected errors, it might be safer to stop
                break
        
        logger.info("Automoy operator loop finished.")
        await _update_gui_state("/state/current_operation", {"text": "Operation finished."})
# Ensure this class definition ends correctly if there's more code below it in the actual file.
# If AutomoyOperator is the last thing in the file, this is fine.
