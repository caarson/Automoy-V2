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
from datetime import datetime

from core.exceptions import AutomoyError, OperationError
from core.utils.operating_system.os_interface import OSInterface
from core.utils.omniparser.omniparser_interface import OmniParserInterface
from core.lm.lm_interface import MainInterface as LLMInterface
from core.prompts.prompts import (
    VISUAL_ANALYSIS_SYSTEM_PROMPT, # <-- Updated
    VISUAL_ANALYSIS_USER_PROMPT_TEMPLATE, # <-- Added
    THINKING_PROCESS_PROMPT,
    STEPS_GENERATION_PROMPT,
    ACTION_GENERATION_SYSTEM_PROMPT, # <-- Added
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
        
        # Using httpx for async requests if available, otherwise fallback or make it a requirement
        # For now, using requests in a thread to avoid blocking, though httpx is preferred for async
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: requests.post(url, json=payload, timeout=5))
        # print(f"[GUI_UPDATE] Sent {payload} to {url}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to update GUI state at {url}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in _update_gui_state: {e}")


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
            # Ensure the directory for the screenshot exists
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            
            # Capture screenshot using OSInterface
            self.raw_screenshot_path_for_parsing = self.os_interface.take_screenshot(
                filename=screenshot_path
            )
            if not self.raw_screenshot_path_for_parsing or not os.path.exists(self.raw_screenshot_path_for_parsing):
                logger.error("Failed to capture screenshot or screenshot file not found.")
                self.run_capture_on_next_cycle = True # Retry capture
                return

            logger.info(f"Screenshot captured: {self.raw_screenshot_path_for_parsing}")
            self.active_screenshot_for_llm_gui = self.raw_screenshot_path_for_parsing

            # Process with OmniParser
            logger.info("Processing screenshot with OmniParser...")
            raw_parser_output = self.omniparser_instance.parse_screenshot(self.raw_screenshot_path_for_parsing)
            
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

                processed_screenshot_path = OPERATE_PY_PROJECT_ROOT / PROCESSED_SCREENSHOT_RELATIVE_PATH
                if processed_screenshot_path.exists():
                    self.active_screenshot_for_llm_gui = str(processed_screenshot_path)
                    logger.info(f"Using processed screenshot for GUI: {self.active_screenshot_for_llm_gui}")
                else:
                    logger.warning(f"Processed screenshot not found at {processed_screenshot_path}, GUI might show raw.")

                self.ui_json_for_llm = json.dumps(clean_json_data(raw_parser_output))
            else:
                logger.error("Failed to parse screenshot or parser returned invalid data.")
                self.coords = []
                self.ui_json_for_llm = None
                self.run_capture_on_next_cycle = True
                return

            logger.debug(f"self.coords after assignment: {json.dumps(self.coords[:5], indent=2)}... (first 5 elements)")
            self.run_capture_on_next_cycle = False # Successfully captured and processed

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
                        
                        coords_debug_info = ""
                        if isinstance(self.coords, list):
                            example_elements = [str(item.get('id', item.get('text', 'Unknown Element')) if isinstance(item, dict) else item) for i, item in enumerate(self.coords) if i < 3]
                            coords_debug_info = f"First ~3 elements in self.coords: {example_elements}"
                        else:
                            coords_debug_info = f"self.coords type: {type(self.coords)}"
                        error_message = f"Click action failed: Element not found using {tried_identifiers_str}."
                        logger.error(f"{error_message} {coords_debug_info}")

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

    # ───────────────────────────── Startup ───────────────────────────
    async def startup_sequence(self):
        # This method is now primarily called from main.py before operate_loop
        # It can remain for direct testing of operate.py if needed.
        logger.info("🚀 Automoy Starting Up (within operator)...")
        logger.info(f"Detected OS: {self.os_interface.os_type}")

        # GUI launch is handled by main.py
        # OmniParser server check/launch
        if not self.omniparser._check_server_ready():
            logger.error("❌ OmniParser server is not running! Attempting to start it…")
            if self.omniparser.launch_server(): # launch_server should return success/failure
                 await asyncio.sleep(5) # Give server time to start
                 if not self.omniparser._check_server_ready():
                    logger.error("❌ OmniParser server failed to start properly. Exiting.")
                    sys.exit(1)
            else:
                logger.error("❌ Failed to initiate OmniParser server launch. Exiting.")
                sys.exit(1)
        else:
            logger.info("✅ OmniParser server already running or started successfully.")


        if not self.vmware.is_vmware_installed():
            logger.warning("⚠️ VMWare is not installed or not detected.")

        if not self.webscraper.is_ready():
            logger.warning("⚠️ Web scraper is not properly configured!")

        logger.info("✅ All systems ready (within operator startup_sequence)!")    


    # ───────────────────────────── Loop ──────────────────────────────
    async def operate_loop(self, max_iterations: int = 10): 
        logger.info(f"Starting operation loop for objective: {self.objective}")
        screenshot_dir = self.config.get("SCREENSHOT_DIR", os.path.join(OPERATE_PY_PROJECT_ROOT, "debug", "screenshots"))
        os.makedirs(screenshot_dir, exist_ok=True)
        current_screenshot_path = os.path.join(screenshot_dir, "automoy_current_capture.png")

        max_consecutive_llm_errors = 3
        llm_error_count = 0
        iteration_count = 0 

        while True: 
            await self.pause_event.wait()
            logger.debug(f"Operator cycle {iteration_count + 1}. Pause event is set, operator proceeding.")

            if self.run_capture_on_next_cycle:
                await self._capture_and_process_screenshot(screenshot_path=current_screenshot_path)
                if not self.ui_json_for_llm: 
                    logger.error("Screenshot capture/processing failed. Retrying next cycle.")
                    await asyncio.sleep(1) 
                    continue

            action_json = await self._get_next_action_from_llm(
                current_screenshot_path=self.active_screenshot_for_llm_gui, 
                current_ui_json=self.ui_json_for_llm
            )

            if action_json and action_json.get("request_new_screenshot"):
                logger.info("LLM requested a new screenshot for the next cycle.")
                self.run_capture_on_next_cycle = True
            
            if not action_json or action_json.get("operation") == "error" or action_json.get("action_type") == "error": 
                llm_error_count += 1
                error_msg = action_json.get("message", action_json.get("reasoning", "Unknown error from LLM or empty action.")) if action_json else "No action JSON returned by LLM."
                logger.error(f"LLM returned error or no action. Count: {llm_error_count}. Message: {error_msg}")
                
                if llm_error_count >= max_consecutive_llm_errors:
                    logger.critical(f"Max consecutive LLM errors ({max_consecutive_llm_errors}) reached. Stopping operator.")
                    break 
                
                await asyncio.sleep(1) 
                continue 
            
            llm_error_count = 0 

            action_to_execute = action_json
            if "action_type" in action_to_execute and "operation" not in action_to_execute: # Ensure "operation" field
                action_to_execute["operation"] = action_to_execute["action_type"]

            action_success = await self._execute_action(action_to_execute)
            executed_operation = action_to_execute.get("operation")

            if executed_operation == "finish":
                logger.info("Operator received 'finish' action. Objective assumed complete or stopping as instructed.")
                await _update_gui_state("/state/current_operation", {"text": "Operation finished."})
                break

            if not action_success:
                logger.warning(f"Action '{executed_operation}' targeting '{action_to_execute.get('action_target_description', 'N/A')}' failed during execution. Will attempt new screenshot and LLM cycle.")
                self.run_capture_on_next_cycle = True 
            else:
                # If action was successful, LLM might have already requested a new screenshot.
                # If not, we assume the state changed and a new screenshot is generally needed unless LLM says otherwise.
                # However, if LLM explicitly sets request_new_screenshot to False, we honor that.
                if not action_json.get("request_new_screenshot", False): # Default to True if not specified by LLM after a successful action
                    # This logic can be debated: always take screenshot vs. only if LLM requests or action fails.
                    # For now, if action is success AND LLM did not request new_screenshot=True, we assume LLM might want to act on same screen.
                    # Let's change to: if action was successful, only take new screenshot if LLM requested it OR if it's a major action.
                    # The current logic is: if request_new_screenshot is True, it's set. If action fails, it's set.
                    # If action succeeds and request_new_screenshot is False, it remains False. This seems fine.
                    pass


            # General delay between operator cycles, distinct from specific action delays
            await asyncio.sleep(self.config.get("OPERATOR_CYCLE_DELAY", 0.5)) # Using a distinct config key
            iteration_count += 1
            # Max iteration check is typically handled by the caller (e.g., main.py)
            # if max_iterations and iteration_count >= max_iterations:
            #     logger.info(f"Reached max_iterations ({max_iterations}). Stopping operator.")
            #     break


    async def _get_next_action_from_llm(self, current_screenshot_path: str, current_ui_json: str | None): # Added current_ui_json
        """
        Gets the next action from the LLM based on the current UI state.
        This involves:
        1. Performing visual analysis of the current screen.
        2. Generating a thinking process based on the analysis and objective.
        3. Deciding the next action (e.g., click, type, finish).
        Updates GUI with visual analysis and thinking process.
        The LLM can request a new screenshot by including 'request_new_screenshot': True in its response.
        """
        logger.info(f"Getting next action from LLM. Screenshot: {current_screenshot_path}")
        if not current_ui_json:
            logger.warning("No UI JSON available for LLM. Requesting new screenshot.")
            return {
                "operation": "error", # Or a specific operation to re-capture
                "reasoning": "UI JSON data is missing, cannot proceed with analysis.",
                "request_new_screenshot": True
            }

        # 0. Generate Steps if not already generated (or if objective changes, etc. - simplified for now)
        if not self.generated_steps_output: # Only generate once, or based on some condition
            try:
                logger.info("Generating initial steps...")
                steps_generation_user_prompt = STEPS_GENERATION_PROMPT.format(
                    objective=self.objective,
                    # Provide dummy/placeholder values for keys expected by STEPS_GENERATION_PROMPT
                    # when it's called before visual_analysis_output and thinking_process_output are available.
                    thinking_output="Initial step generation: Thinking process not yet available for prompt.",
                    screen_description="Initial step generation: Screen description not yet available for prompt."
                )
                raw_steps_output = await self.llm.generate_text_async(
                    system_prompt=None, # Or a specific system prompt for step generation
                    user_prompt=steps_generation_user_prompt,
                    model=self.model,
                    # temperature=0.6,
                    # max_tokens=400
                )
                # Assuming steps are returned as a list in a JSON structure, or a newline-separated string
                # For simplicity, let's assume newline-separated string that handle_llm_response can process or we parse here
                parsed_steps_response = handle_llm_response(raw_steps_output, "steps generation", llm_interface=self.llm)
                
                if isinstance(parsed_steps_response, str):
                    self.generated_steps_output = [step.strip() for step in parsed_steps_response.split('\\n') if step.strip()]
                elif isinstance(parsed_steps_response, list): # If LLM returns a list directly
                    self.generated_steps_output = parsed_steps_response
                else:
                    logger.warning(f"Steps generation returned unexpected type: {type(parsed_steps_response)}. Steps not updated.")
                    self.generated_steps_output = ["Could not parse generated steps."]

                logger.info(f"Generated Steps: {self.generated_steps_output}")
                await _update_gui_state("/state/steps_generated", {"list": self.generated_steps_output})
            except Exception as e:
                logger.error(f"Error during steps generation: {e}", exc_info=True)
                self.generated_steps_output = ["Error generating steps."]
                await _update_gui_state("/state/steps_generated", {"list": self.generated_steps_output})
        
        # 1. Perform Visual Analysis
        try:
            logger.info("Performing visual analysis...")
            visual_analysis_user_prompt = VISUAL_ANALYSIS_USER_PROMPT_TEMPLATE.format(
                objective=self.objective,
                ui_json=current_ui_json,
                previous_actions=json.dumps(self.last_action) if self.last_action else "N/A"
            )
            # Assuming self.llm.generate_text_async exists and works as expected
            # Parameters like model, temperature, max_tokens would ideally come from config or be defaults in LLMInterface
            raw_visual_analysis = await self.llm.generate_text_async(
                system_prompt=VISUAL_ANALYSIS_SYSTEM_PROMPT,
                user_prompt=visual_analysis_user_prompt,
                model=self.model, # Using model from self.config
                # temperature=0.5, # Example, adjust as needed
                # max_tokens=300   # Example, adjust as needed
            )
            self.visual_analysis_output = handle_llm_response(raw_visual_analysis, "visual analysis", llm_interface=self.llm) # Pass llm_interface
            logger.info(f"Visual Analysis Output: {self.visual_analysis_output[:200]}...") # Log snippet
            await _update_gui_state("/state/visual", {"text": self.visual_analysis_output}) # CORRECTED ENDPOINT
        except Exception as e:
            logger.error(f"Error during visual analysis: {e}", exc_info=True)
            self.visual_analysis_output = "Error during visual analysis."
            await _update_gui_state("/state/visual", {"text": self.visual_analysis_output}) # CORRECTED ENDPOINT
            # Potentially return an error action or request new screenshot
            return {
                "operation": "error",
                "reasoning": f"Failed to perform visual analysis: {e}",
                "request_new_screenshot": True # Good idea to get a fresh view if analysis fails
            }

        # 2. Generate Thinking Process
        try:
            logger.info("Generating thinking process...")
            # Determine current step description (placeholder for now)
            current_step_desc = "Determining next optimal action towards the objective."
            if self.generated_steps_output and 0 <= self.current_step_index < len(self.generated_steps_output):
                current_step_desc = self.generated_steps_output[self.current_step_index]

            thinking_process_user_prompt = THINKING_PROCESS_PROMPT.format(
                objective=self.objective,
                visual_summary=self.visual_analysis_output,
                ui_elements=current_ui_json, # Provide the full UI JSON here
                previous_actions=json.dumps(self.last_action) if self.last_action else "N/A",
                current_step_description=current_step_desc
            )
            raw_thinking_process = await self.llm.generate_text_async(
                system_prompt=None, # THINKING_PROCESS_PROMPT is often used as a single combined prompt
                user_prompt=thinking_process_user_prompt,
                model=self.model,
                # temperature=0.7,
                # max_tokens=500
            )
            self.thinking_process_output = handle_llm_response(raw_thinking_process, "thinking process", llm_interface=self.llm) # Pass llm_interface
            logger.info(f"Thinking Process Output (raw from LLM): {raw_thinking_process[:300]}...") # Log raw
            logger.info(f"Thinking Process Output (handled): {self.thinking_process_output[:300]}...") # Log handled
            await _update_gui_state("/state/thinking", {"text": self.thinking_process_output}) # CORRECTED ENDPOINT
        except Exception as e:
            logger.error(f"Error during thinking process generation: {e}", exc_info=True)
            self.thinking_process_output = "Error during thinking process generation."
            await _update_gui_state("/state/thinking", {"text": self.thinking_process_output}) # CORRECTED ENDPOINT
            return {
                "operation": "error",
                "reasoning": f"Failed to generate thinking process: {e}",
                "request_new_screenshot": True
            }

        # 3. Decide Next Action
        try:
            logger.info("Deciding next action...")
            # The user prompt for action generation needs all relevant context
            action_generation_user_prompt = (
                f"Objective: {self.objective}\\n\\n"
                f"Current Screen Visual Analysis:\\n{self.visual_analysis_output}\\n\\n"
                f"My Thinking Process:\\n{self.thinking_process_output}\\n\\n"
                f"Current UI Elements (JSON):\\n{current_ui_json}\\n\\n"
                # f"Screenshot Path (for context, not for direct opening by LLM): {current_screenshot_path}\\n\\n" # LLM doesn't use path
                f"Previous Action: {json.dumps(self.last_action) if self.last_action else 'N/A'}\\n\\n"
                "Based on all the above, provide the next action as a JSON object."
            )
            
            raw_action_json_str = await self.llm.generate_text_async(
                system_prompt=ACTION_GENERATION_SYSTEM_PROMPT, # This defines the expected JSON output format
                user_prompt=action_generation_user_prompt,
                model=self.model,
                # temperature=0.3, # Lower temperature for more deterministic actions
                # max_tokens=200
            )
            
            # Attempt to parse the LLM response as JSON
            action_json = handle_llm_response(raw_action_json_str, "action generation", is_json=True, llm_interface=self.llm) # Pass llm_interface

            if not action_json or not isinstance(action_json, dict):
                logger.error(f"Failed to parse action JSON from LLM or invalid format. Raw: {raw_action_json_str}")
                # Fallback or error action
                return {
                    "operation": "error",
                    "reasoning": "LLM returned invalid action JSON.",
                    "raw_response": raw_action_json_str,
                    "request_new_screenshot": True # Good to refresh if LLM is confused
                }

            logger.info(f"LLM proposed action: {action_json}")
            
            # Ensure 'request_new_screenshot' defaults to False if not provided by LLM
            if "request_new_screenshot" not in action_json:
                action_json["request_new_screenshot"] = False
            
            self.last_action = action_json # Store the proposed action (before execution)
            return action_json

        except Exception as e:
            logger.error(f"Error during action generation: {e}", exc_info=True)
            return {
                "operation": "error",
                "reasoning": f"Failed to generate action: {e}",
                "request_new_screenshot": True
            }
