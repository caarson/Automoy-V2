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
        self.llm = MainInterface()
        self.manage_gui_window_func = manage_gui_window_func
        self.pause_event = pause_event # Store the pause event
        
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
        self.action_delay = self.config.get("ACTION_DELAY", 2.0)

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
        try:
            # Minimize Automoy GUI first
            if self.manage_gui_window_func:
                logger.info("Minimizing Automoy GUI for screenshot.")
                await self.manage_gui_window_func("minimize")
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
            # Show Automoy GUI after processing, regardless of desktop anchor point usage
            if self.manage_gui_window_func:
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
        # Prioritize element_id, then text, then element_label for identifying click targets
        # For other actions, the primary identifier might be 'text' (e.g., for type_text) or other specific fields.
        if action_type == "click":
            action_details = action_json.get("element_id") or action_json.get("text") or action_json.get("element_label", "")
        else:
            action_details = action_json.get("text", "") # Default to text for other operations like type_text

        logger.info(f"Attempting action: {action_type}, Details: {str(action_details)[:50]}...") # Log action attempt

        # Update GUI: Current operation
        await _update_gui_state("/state/current_operation", {"text": f"Executing: {action_type} on '{str(action_details)}'"})

        success = False
        error_message = None

        try:
            if action_type == "click":
                element_data_found = None
                target_identifier_for_log = "Unknown" # For logging
                element_bbox_for_click = None

                action_element_id = action_json.get("element_id")
                action_text = action_json.get("text")
                action_label = action_json.get("element_label")

                if not self.coords: # self.coords could be None or an empty list
                    error_message = "Click action failed: Coordinates data (self.coords) is not available or empty."
                    logger.error(f"{error_message}")
                elif not isinstance(self.coords, list):
                    error_message = f"Click action failed: self.coords is not a list as expected (type: {type(self.coords)})."
                    logger.error(f"{error_message}")
                else:
                    # 1. Try with element_id (if provided by LLM)
                    if action_element_id:
                        for elem_data in self.coords:
                            if isinstance(elem_data, dict) and elem_data.get("id") == action_element_id: # Assuming parser uses "id"
                                element_data_found = elem_data
                                target_identifier_for_log = f"element_id: '{action_element_id}'"
                                break
                            elif isinstance(elem_data, dict) and elem_data.get("element_id") == action_element_id: # Fallback to "element_id"
                                element_data_found = elem_data
                                target_identifier_for_log = f"element_id: '{action_element_id}' (matched on 'element_id' field)"
                                break
                    
                    # 2. If not found by element_id, try with text (if provided)
                    if not element_data_found and action_text:
                        for elem_data in self.coords:
                            if isinstance(elem_data, dict) and elem_data.get("text") == action_text:
                                element_data_found = elem_data
                                target_identifier_for_log = f"text: '{action_text}' (found in element '{elem_data.get('id', 'N/A')}')"
                                break
                    
                    # 3. If not found by text, try with label (if provided)
                    if not element_data_found and action_label:
                        for elem_data in self.coords:
                            if isinstance(elem_data, dict) and elem_data.get("label") == action_label:
                                element_data_found = elem_data
                                target_identifier_for_log = f"label: '{action_label}' (found in element '{elem_data.get('id', 'N/A')}')"
                                break
                    
                    if element_data_found: # element_data_found is now a dict
                        bbox_candidate = element_data_found.get("bbox")
                        if bbox_candidate and isinstance(bbox_candidate, (list, tuple)) and len(bbox_candidate) == 4:
                            element_bbox_for_click = bbox_candidate
                        else:
                            error_message = f"Click action failed for {target_identifier_for_log}: Bounding box missing or invalid in element data {element_data_found}."
                            logger.error(f"{error_message}")
                    else:
                        tried_identifiers_parts = []
                        if action_element_id: tried_identifiers_parts.append(f"element_id '{action_element_id}'")
                        if action_text: tried_identifiers_parts.append(f"text '{action_text}'")
                        if action_label: tried_identifiers_parts.append(f"label '{action_label}'")
                        tried_identifiers_str = ", ".join(tried_identifiers_parts) if tried_identifiers_parts else "any provided identifiers"
                        
                        # Log a snippet of self.coords if it's small, or just its type and length
                        coords_debug_info = ""
                        if isinstance(self.coords, list):
                            if len(self.coords) < 5: # Log small lists directly
                                coords_debug_info = f"Coords list: {self.coords}"
                            else: # For larger lists, just log a few IDs or texts
                                example_elements = []
                                for i, item in enumerate(self.coords):
                                    if i < 3: # Log first 3 elements' id or text
                                        if isinstance(item, dict):
                                            example_elements.append(item.get('id', item.get('text', 'Unknown Element')))
                                        else:
                                            example_elements.append(str(item))
                                    else:
                                        break
                                coords_debug_info = f"First ~3 elements in self.coords: {example_elements}"
                        else:
                            coords_debug_info = f"self.coords type: {type(self.coords)}"

                        error_message = f"Click action failed: Element not found using {tried_identifiers_str}."
                        logger.error(f"{error_message} {coords_debug_info}")


                if element_bbox_for_click:
                    x1, y1, x2, y2 = element_bbox_for_click
                    if x2 <= x1 or y2 <= y1: # Degenerate bbox check
                        error_message = f"Click action failed for {target_identifier_for_log}: Invalid bounding box {element_bbox_for_click}."
                        logger.error(f"{error_message}")
                    else:
                        click_x = (x1 + x2) // 2
                        click_y = (y1 + y2) // 2
                        
                        logger.info(f"Moving to ({click_x}, {click_y}) for element identified by {target_identifier_for_log}")
                        self.os_interface.move_mouse(click_x, click_y, duration=0.1) 
                        await asyncio.sleep(0.1) 
                        
                        logger.info(f"Clicking at ({click_x}, {click_y}) for element identified by {target_identifier_for_log}")
                        self.os_interface.click_mouse() 
                        await asyncio.sleep(self.action_delay) 
                        success = True
                        logger.info(f"Click on element identified by {target_identifier_for_log} successful.")
                # If element_bbox_for_click is None, success remains False, error_message might have been set.
            
            elif action_type == "type_text":
                # ...existing code for type_text handling...
                pass
            # ...existing code for other actions...
            
            await asyncio.sleep(0.5) # General delay after most actions for UI to react
            logger.info(f"Successfully executed: {action_type}")
            return True
        except Exception as e:
            logger.error(f"Error during '{action_type}': {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            if action_type in ["click", "double_click", "right_click"] and self.manage_gui_window_func:
                await asyncio.sleep(0.1) # Ensure action completes before showing GUI
                await self.manage_gui_window_func("show")

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
    async def operate_loop(self, max_iterations: int = 10): # Added max_iterations from main.py for consistency
        logger.info(f"Starting operation loop for objective: {self.objective}")
        # Ensure screenshot directory exists, use a consistent name for the capture
        # PROJECT_ROOT is defined in main.py, ensure config access is robust or pass it
        # For now, assuming config path is okay.
        screenshot_dir = self.config.get("SCREENSHOT_DIR", os.path.join(OPERATE_PY_PROJECT_ROOT, "debug", "screenshots"))
        os.makedirs(screenshot_dir, exist_ok=True)
        # Use a timestamped or iteration-based name if you want to keep all screenshots
        # For now, overwriting "automoy_current_capture.png"
        current_screenshot_path = os.path.join(screenshot_dir, "automoy_current_capture.png")


        max_consecutive_llm_errors = 3
        llm_error_count = 0
        iteration_count = 0 # Add iteration count

        while True: # Removed max_iterations from here, main.py's loop has it. Or keep it if operate_loop is self-contained.
                    # For now, assuming this loop can run "indefinitely" until 'finish' or error.
            await self.pause_event.wait()
            logger.debug(f"Operator cycle {iteration_count + 1}. Pause event is set, operator proceeding.")

            if self.run_capture_on_next_cycle:
                await self._capture_and_process_screenshot(screenshot_path=current_screenshot_path)
                # self.run_capture_on_next_cycle is set to False inside _capture_and_process_screenshot on success
                # If it failed, it remains True, and the loop will retry capture next.
                if not self.ui_json_for_llm: # If capture or processing failed critically
                    logger.error("Screenshot capture/processing failed. Retrying next cycle.")
                    await asyncio.sleep(1) # Wait before retrying
                    continue


            # Pass the path to the screenshot that was just taken (or the existing one if no new capture)
            # Also pass self.ui_json_for_llm so LLM knows current parsed state
            action_json = await self._get_next_action_from_llm(
                current_screenshot_path=self.active_screenshot_for_llm_gui, # Path to image LLM "sees"
                current_ui_json=self.ui_json_for_llm
            )

            if action_json and action_json.get("request_new_screenshot"):
                logger.info("LLM requested a new screenshot for the next cycle.")
                self.run_capture_on_next_cycle = True
            
            if not action_json or action_json.get("operation") == "error" or action_json.get("action_type") == "error": # Handle "action_type" too
                llm_error_count += 1
                error_msg = action_json.get("message", action_json.get("reasoning", "Unknown error from LLM or empty action."))
                logger.error(f"LLM returned error or no action. Count: {llm_error_count}. Message: {error_msg}")
                # self.current_action_description = f"LLM Error: {error_msg}" # Update state for GUI if needed
                
                # Log this as a failed operation in history (if self.past_operations exists)
                # if hasattr(self, 'past_operations') and isinstance(self.past_operations, list):
                #     self.past_operations.append({
                #         "action": "llm_communication", "details": error_msg,
                #         "status": "failure", "error_message": error_msg
                #     })

                if llm_error_count >= max_consecutive_llm_errors:
                    logger.critical(f"Max consecutive LLM errors ({max_consecutive_llm_errors}) reached. Stopping operator.")
                    # Update GUI about this critical failure (main.py should handle this based on operator state)
                    break 
                
                # If LLM errored, it's often good to get a fresh view.
                # self.run_capture_on_next_cycle = True # This is now handled by LLM's "request_new_screenshot"
                await asyncio.sleep(1) 
                continue 
            
            llm_error_count = 0 

            # Execute the action
            # _execute_action needs to be adapted if it returns two values now.
            # Assuming it returns a single boolean for success for now.
            action_to_execute = action_json # The whole JSON is the action
            
            # The placeholder _get_next_action_from_llm returns "action_type", "element_id", "reasoning"
            # The _execute_action expects "operation", "element_id", "text", "element_label"
            # We need to map these or change the LLM output format.
            # For now, let's assume LLM output needs mapping or _execute_action is more flexible.
            # Let's make a simple mapping for the placeholder:
            if "action_type" in action_to_execute and "operation" not in action_to_execute:
                action_to_execute["operation"] = action_to_execute["action_type"]

            action_success = await self._execute_action(action_to_execute)
            executed_operation = action_to_execute.get("operation") # Get operation after potential mapping

            # Update GUI with the outcome of the action (main.py should handle this)

            if executed_operation == "finish":
                logger.info("'finish' action received. Stopping operator.")
                # Update GUI state to "Finished" (main.py handles this)
                break

            if not action_success:
                logger.warning(f"Action '{executed_operation}' failed. Loop will continue.")
                # Decide if a new screenshot is needed after a failed action.
                # Often, a failed action means the UI state is unexpected, so a new screenshot is good.
                self.run_capture_on_next_cycle = True 
            
            # Small delay before next cycle
            await asyncio.sleep(self.config.get("ACTION_DELAY_SECONDS", 0.5)) # Reduced default slightly
            iteration_count += 1
            # if max_iterations and iteration_count >= max_iterations:
            #     logger.info(f"Reached max_iterations ({max_iterations}). Stopping operator.")
            #     break


    async def _get_next_action_from_llm(self, current_screenshot_path: str, current_ui_json: str | None): # Added current_ui_json
        """
        Gets the next action from the LLM based on the current UI state.
        The LLM can request a new screenshot by including 'request_new_screenshot': True in its response.
        """
        # This is a placeholder implementation.
        logger.info(f"Getting next action from LLM. Current screenshot: {current_screenshot_path}")
        if current_ui_json:
            logger.debug(f"Current UI JSON for LLM (first 200 chars): {current_ui_json[:200]}...")
        else:
            logger.warning("No UI JSON available for LLM. LLM might request a new screenshot.")

        # Simulate LLM processing
        await asyncio.sleep(1) 

        # Example: Simulate LLM deciding if it needs a new screenshot
        # For testing, let's say it requests a new screenshot every 3 calls or if no UI JSON
        if not hasattr(self, '_llm_call_count'):
            self._llm_call_count = 0
        self._llm_call_count += 1

        request_new_shot = False
        if not current_ui_json or self._llm_call_count % 3 == 0:
            # request_new_shot = True # Disabled for now to test single shot logic first
            pass


        # Simulate LLM returning a "click" action or "finish"
        if self._llm_call_count > 5: # Simulate finishing after a few actions
             return {
                "operation": "finish", # "action_type" was used before, ensure consistency or map it
                "reasoning": "Objective likely completed after 5 actions.",
                "request_new_screenshot": request_new_shot 
            }
        else:
            return {
                "operation": "click", # Changed from "action_type" to "operation"
                "element_id": f"button_{self._llm_call_count}", # Simulate different clicks
                "reasoning": f"User asked to click button_{self._llm_call_count}.",
                "request_new_screenshot": request_new_shot 
            }
