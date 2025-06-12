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
import time # ADDED
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Coroutine, Tuple # MODIFIED

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
        # Ensure payload is not None, default to empty dict if it is, to satisfy requests.post
        response = await loop.run_in_executor(None, lambda: requests.post(url, json=current_payload if current_payload is not None else {}, timeout=5))
        
        if response.status_code == 200:
            logger.debug(f"[GUI_UPDATE] Successfully sent payload to {url}. Response status: {response.status_code}, text: {response.text[:100] if response.text else 'N/A'}")
        else:
            # For 422 errors, log more of the response to see validation details
            if response.status_code == 422:
                logger.warning(f"[GUI_UPDATE] Failed to send payload to {url}. Response status: {response.status_code}, text: {response.text}")
            else:
                logger.warning(f"[GUI_UPDATE] Failed to send payload to {url}. Response status: {response.status_code}, text: {response.text[:200] if response.text else 'N/A'}")
            
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to update GUI state at {url} (RequestException): {e}")
    except Exception as e:
        logger.error(f"Unexpected error in _update_gui_state sending to {url}: {e}", exc_info=True)

class AutomoyOperator:
    """Central orchestrator for Automoy autonomous operation."""

    def __init__(self, 
                 objective: str, 
                 manage_gui_window_func: Callable[..., Coroutine[Any, Any, bool]], 
                 omniparser,  # This should be an instance of OmniParserInterface
                 pause_event: asyncio.Event,
                 update_gui_state_func: Callable[..., Coroutine[Any, Any, None]] # Added
                 ):
        self.objective = objective
        self.manage_gui_window_func = manage_gui_window_func
        self.omniparser = omniparser 
        self.pause_event = pause_event
        self._update_gui_state_func = update_gui_state_func # Store the function

        self.config = Config()
        self.llm_interface = MainInterface()
        self.desktop_utils = DesktopUtils() # Instantiate DesktopUtils

        self.steps: List[Dict[str, Any]] = []
        self.steps_for_gui: List[Dict[str, Any]] = []
        self.executed_steps: List[Dict[str, Any]] = []
        
        self.current_step_index: int = 0
        self.current_screenshot_path: Optional[Path] = None
        self.current_processed_screenshot_path: Optional[Path] = None
        self.visual_analysis_output: Optional[str] = None
        self.thinking_process_output: Optional[str] = None
        self.operations_generated_for_gui: List[Dict[str, str]] = [] # For GUI display
        self.last_action_summary: Optional[str] = None

        self.max_retries_per_step = self.config.get_max_retries_per_step()
        self.max_consecutive_errors = self.config.get_max_consecutive_errors()
        self.consecutive_error_count = 0
        
        self.session_id = f"automoy-op-{int(time.time())}"
        logger.info(f"AutomoyOperator initialized with session ID: {self.session_id}")
        logger.info(f"Objective: {self.objective}")
        # Log omniparser type
        logger.debug(f"OmniParser interface type: {type(self.omniparser)}")
        if not hasattr(self.omniparser, 'get_analysis'):
            logger.error("OmniParser interface does not have 'get_analysis' method!")
            # Potentially raise an error or handle this state
            # For now, logging it. This could be a source of issues if not addressed.

    async def _perform_visual_analysis(self, screenshot_path: Path, task_context: str) -> Tuple[Optional[Path], Optional[str]]:
        logger.info(f"Performing visual analysis for task: {task_context} on screenshot: {screenshot_path}")
        processed_screenshot_path: Optional[Path] = None
        analysis_results_json_str: Optional[str] = None # Initialize
        try:
            # Ensure omniparser is available and has the parse_screenshot method
            if not self.omniparser or not hasattr(self.omniparser, 'parse_screenshot'): # MODIFIED
                logger.error("OmniParser is not available or misconfigured (missing 'parse_screenshot').") # MODIFIED
                await self._update_gui_state_func("/state/visual", {"text": "Error: OmniParser not available or misconfigured."}) # MODIFIED (endpoint and payload key)
                return None, None

            logger.info(f"Calling omniparser.parse_screenshot for {screenshot_path}")
            parsed_data = self.omniparser.parse_screenshot(str(screenshot_path)) # MODIFIED

            if not parsed_data:
                logger.error("OmniParser failed to parse screenshot or returned no data.")
                await self._update_gui_state_func("/state/visual", {"text": "Error: OmniParser failed to process screenshot."}) # MODIFIED (endpoint and payload key)
                return None, None

            analysis_results_json_str = json.dumps(parsed_data) # MODIFIED
            
            internal_processed_path = OPERATE_PY_PROJECT_ROOT / PROCESSED_SCREENSHOT_RELATIVE_PATH
            if internal_processed_path.exists():
                processed_screenshot_path = internal_processed_path
                logger.info(f"Processed screenshot available at: {processed_screenshot_path}")
                # Notify GUI that the processed screenshot (expected at gui/static/processed_screenshot.png) is ready
                logger.debug(f"Updating GUI about processed screenshot being ready (expected at /static/processed_screenshot.png)")
                await self._update_gui_state_func("/state/screenshot_processed", {}) # MODIFIED (endpoint and empty payload)
            else:
                logger.warning(f"Processed screenshot not found at expected internal path: {internal_processed_path}. GUI might not show it.")
                # Attempt to check the static path directly as a fallback for logging
                gui_static_processed_path = OPERATE_PY_PROJECT_ROOT.parent / "gui" / "static" / "processed_screenshot.png"
                if gui_static_processed_path.exists():
                    logger.info(f"Processed screenshot IS present in GUI static folder: {gui_static_processed_path}")
                    await self._update_gui_state_func("/state/screenshot_processed", {}) # MODIFIED (endpoint and empty payload)
                else:
                    logger.warning(f"Processed screenshot also not found in GUI static folder: {gui_static_processed_path}. Using original screenshot path as fallback for processed path.")
                processed_screenshot_path = screenshot_path # Fallback

            logger.debug(f"Visual analysis from OmniParser (first 500 chars): {analysis_results_json_str[:500] if analysis_results_json_str else 'None'}...") # MODIFIED
            await self._update_gui_state_func("/state/visual", {"text": analysis_results_json_str or "No visual analysis generated."}) # MODIFIED (endpoint and payload key)
            self.visual_analysis_output = analysis_results_json_str # Store it
            return processed_screenshot_path, analysis_results_json_str

        except Exception as e:
            logger.error(f"Error during visual analysis: {e}", exc_info=True)
            await self._update_gui_state_func("/state/visual", {"text": f"Error in visual analysis: {e}"}) # MODIFIED (endpoint and payload key)
            self.visual_analysis_output = None # Clear on error
            return None, None

    async def _generate_steps(self):
        logger.info("Generating steps...")
        if not self.visual_analysis_output and not self.thinking_process_output:
            logger.warning("Visual analysis or thinking process output is missing, cannot generate steps.")
            await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "Missing visual analysis or thinking process."})
            return
        # ... existing code ...
        try:
            # Construct the prompt for step generation
            system_prompt_steps = STEP_GENERATION_SYSTEM_PROMPT
            user_prompt_steps = self.llm_interface.construct_step_generation_prompt(
                objective=self.objective,
                visual_analysis_output=self.visual_analysis_output or "No visual analysis available.",
                thinking_process_output=self.thinking_process_output or "No prior thinking process output available for step generation.",
                previous_steps_output="N/A" # Assuming this is for initial generation
            )
            messages_steps = [
                {"role": "system", "content": system_prompt_steps},
                {"role": "user", "content": user_prompt_steps}
            ]

            logger.debug(f"Messages for step generation LLM call (first 200 chars of user prompt): {str(messages_steps)[:200]}...")
            
            raw_llm_response, _, llm_error = await self.llm_interface.get_llm_response( # Using get_llm_response, ignoring thinking output here
                model=self.config.get_model(),
                messages=messages_steps,
                objective=self.objective,
                session_id=self.session_id,
                response_format_type="step_generation" 
            )

            if llm_error:
                logger.error(f"LLM error during step generation: {llm_error}")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"LLM Error: {llm_error}"})
                return
            
            if not raw_llm_response:
                logger.warning("LLM returned no response for step generation.")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "LLM provided no response for steps."})
                return

            steps_json_str = handle_llm_response(raw_llm_response, "step_generation")
            logger.debug(f"LLM response (steps_json_str) for step generation: {steps_json_str[:500] if steps_json_str else 'None'}...")

            if not steps_json_str:
                logger.warning("handle_llm_response returned None or empty for steps_json_str.")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "Failed to parse LLM step response."})
                return
            
            try:
                parsed_steps_data = json.loads(steps_json_str)
                if isinstance(parsed_steps_data, dict) and "steps" in parsed_steps_data and isinstance(parsed_steps_data["steps"], list):
                    self.steps = parsed_steps_data["steps"]
                    # Prepare steps for GUI (e.g., just descriptions)
                    self.steps_for_gui = [{"description": step.get("description", "No description")} for step in self.steps]
                elif isinstance(parsed_steps_data, list): # If LLM directly returns a list of steps
                    self.steps = parsed_steps_data
                    self.steps_for_gui = [{"description": step.get("description", "No description")} for step in self.steps]
                else:
                    logger.warning(f"Parsed steps JSON is not in the expected format: {steps_json_str}")
                    await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "LLM step response has incorrect format."})
                    return

                if self.steps:
                    logger.info(f"Generated {len(self.steps)} steps.")
                    await self._update_gui_state_func("/state/steps_generated", {"steps": self.steps_for_gui}) # Send descriptions
                else:
                    logger.warning("LLM did not generate any steps (parsed list was empty).")
                    await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "LLM failed to generate steps (empty list)."})
            
            except json.JSONDecodeError as jde:
                logger.error(f"JSONDecodeError parsing steps_json_str: {jde}. Content: {steps_json_str}")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"Invalid JSON from LLM for steps: {jde}"})
                self.steps = []
                self.steps_for_gui = []

        except Exception as e:
            logger.error(f"Error generating steps: {e}", exc_info=True)
            await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"Error generating steps: {e}"})
            self.steps = []
            self.steps_for_gui = []

    async def _get_action_for_current_step(self, current_step_description: str, current_step_index: int):
        logger.info(f"Getting action for step {current_step_index + 1}: {current_step_description}")
        action_json_str: Optional[str] = None
        action_to_execute: Optional[Dict[str, Any]] = None
        self.thinking_process_output = self.thinking_process_output if hasattr(self, 'thinking_process_output') else None # Ensure initialized

        try:
            await self.manage_gui_window_func("hide")
            await asyncio.sleep(0.5)
            screenshot_filename = f"automoy_step_{current_step_index + 1}_action_context.png"
            self.current_screenshot_path = self.desktop_utils.capture_current_screen(filename_prefix=screenshot_filename.split('.')[0])
            await self.manage_gui_window_func("show")
            await asyncio.sleep(0.5)

            if not self.current_screenshot_path:
                logger.error("Failed to capture screenshot for action generation.")
                await self._update_gui_state_func("/state/operations_generated", {
                    "operations": [{"type": "error", "summary": "Failed to capture screenshot."}],
                    "thinking_process": "Error: Screenshot capture failed."
                })
                return None
            
            # Send path of the raw screenshot to GUI for it to copy and display
            logger.debug(f"Updating GUI with raw screenshot path for action generation: {str(self.current_screenshot_path)}")
            await self._update_gui_state_func("/state/screenshot", {"path": str(self.current_screenshot_path)}) # MODIFIED (payload key)

            self.current_processed_screenshot_path, self.visual_analysis_output = await self._perform_visual_analysis(
                screenshot_path=self.current_screenshot_path,
                task_context=f"Current step: {current_step_description}"
            )
            if not self.visual_analysis_output:
                logger.warning("Visual analysis failed or produced no output for the current step.")
                await self._update_gui_state_func("/state/operations_generated", {
                    "operations": [{"type": "error", "summary": "Visual analysis failed for current step."}],
                    "thinking_process": self.thinking_process_output
                })
                return None

        except Exception as e_screenshot_va:
            logger.error(f"Error during screenshot capture or visual analysis for action: {e_screenshot_va}", exc_info=True)
            await self._update_gui_state_func("/state/operations_generated", {
                "operations": [{"type": "error", "summary": f"Error preparing for action: {e_screenshot_va}"}],
                "thinking_process": f"Error: {e_screenshot_va}"
            })
            return None

        step_retry_count = 0
        while step_retry_count < self.max_retries_per_step:
            await self.pause_event.wait()
            if not self.pause_event.is_set(): # Check if pause_event is not set (meaning pause is active)
                 logger.info("Operation paused by user. Waiting for resume...")
                 await self._update_gui_state_func("/state/operator_status", {"text": "Paused"}) # MODIFIED (payload key)
                 await self.pause_event.wait() # Wait until event is set (resume)
                 logger.info("Operation resumed by user.")
                 await self._update_gui_state_func("/state/operator_status", {"text": f"Resumed. Processing step {current_step_index + 1}"}) # MODIFIED (payload key)

            logger.info(f"Attempt {step_retry_count + 1}/{self.max_retries_per_step} to generate action for step: {current_step_description}")
            await self._update_gui_state_func("/state/operator_status", {"text": f"Generating action for step {current_step_index + 1} (Attempt {step_retry_count + 1})"}) # MODIFIED (payload key)

            try:
                system_prompt_action = ACTION_GENERATION_SYSTEM_PROMPT
                previous_action = self.executed_steps[-1]["summary"] if self.executed_steps else "N/A" # CORRECTED
                
                user_prompt_action = self.llm_interface.construct_action_prompt(
                    objective=self.objective,
                    current_step_description=current_step_description,
                    all_steps=[s['description'] for s in self.steps],
                    current_step_index=current_step_index,
                    visual_analysis_output=self.visual_analysis_output or "No visual analysis available.",
                    thinking_process_output=self.thinking_process_output or "No prior thinking process output for this action.",
                    previous_action_summary=self.last_action_summary or "This is the first action or previous action summary is not available.",
                    max_retries=self.max_retries_per_step,
                    current_retry_count=step_retry_count
                )

                messages_action = [
                    {"role": "system", "content": system_prompt_action},
                    {"role": "user", "content": user_prompt_action}
                ]
                
                logger.debug(f"Messages for action generation LLM call (first 200 chars of user prompt): {str(messages_action)[:200]}")

                raw_llm_response, thinking_output, llm_error = await self.llm_interface.get_next_action(
                    model=self.config.get_model(),
                    messages=messages_action,
                    objective=self.objective,
                    session_id=self.session_id,
                    screenshot_path=str(self.current_processed_screenshot_path) if self.current_processed_screenshot_path else str(self.current_screenshot_path)
                )
                
                self.thinking_process_output = thinking_output

                if llm_error:
                    logger.error(f"LLM error during action generation: {llm_error}")
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "error", "summary": f"LLM Error: {llm_error}"}],
                        "thinking_process": self.thinking_process_output or f"LLM Error: {llm_error}"
                    })
                    step_retry_count += 1
                    await asyncio.sleep(1)
                    continue

                if not raw_llm_response:
                    logger.warning("LLM returned no response for action generation.")
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "info", "summary": "LLM provided no action this attempt."}],
                        "thinking_process": self.thinking_process_output or "LLM gave empty response."
                    })
                    step_retry_count += 1
                    await asyncio.sleep(1) 
                    continue
                
                action_json_str = handle_llm_response(raw_llm_response, "action_generation")
                logger.debug(f"LLM response (action_json_str) for action generation: {action_json_str[:500] if action_json_str else 'None'}")

                if not action_json_str:
                    logger.warning("handle_llm_response returned None or empty for action_json_str.")
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "warning", "summary": "Failed to parse LLM action response."}],
                        "thinking_process": self.thinking_process_output or "Could not parse LLM action."
                    })
                    step_retry_count += 1
                    await asyncio.sleep(1)
                    continue

                try:
                    parsed_action = json.loads(action_json_str)
                    if isinstance(parsed_action, dict) and "type" in parsed_action and "summary" in parsed_action:
                        action_to_execute = parsed_action 
                        self.operations_generated_for_gui = [action_to_execute]
                        logger.info(f"Action proposed by LLM: {action_to_execute}")
                        await self._update_gui_state_func("/state/operations_generated", {
                            "operations": self.operations_generated_for_gui,
                            "thinking_process": self.thinking_process_output or "N/A"
                        })
                        break 
                    else:
                        logger.warning(f"Parsed action JSON is not in the expected format: {action_json_str}")
                        await self._update_gui_state_func("/state/operations_generated", {
                            "operations": [{"type": "error", "summary": "LLM action response has incorrect format."}],
                            "thinking_process": self.thinking_process_output or "Action format error."
                        })
                except json.JSONDecodeError as jde:
                    logger.error(f"JSONDecodeError parsing action_json_str: {jde}. Content: {action_json_str}")
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "error", "summary": "Invalid JSON from LLM for action."}],
                        "thinking_process": self.thinking_process_output or f"JSON Error: {jde}"
                    })

            except Exception as e_llm_action: # This except block pairs with the outer try for the LLM call attempt
                logger.error(f"Exception during LLM call for action generation (attempt {step_retry_count + 1}): {e_llm_action}", exc_info=True)
                await self._update_gui_state_func("/state/operations_generated", {
                    "operations": [{"type": "error", "summary": f"Error generating action: {e_llm_action}"}],
                    "thinking_process": self.thinking_process_output or f"Exception: {e_llm_action}"
                })
            
            step_retry_count += 1
            if step_retry_count < self.max_retries_per_step:
                logger.info(f"Pausing before next action generation retry attempt for step {current_step_index + 1}.")
                await asyncio.sleep(min(5, step_retry_count * 2))
            else:
                logger.error(f"Max retries ({self.max_retries_per_step}) reached for generating action for step {current_step_index + 1}.")
                await self._update_gui_state_func("/state/operations_generated", {
                    "operations": [{"type": "error", "summary": f"Max retries reached. Could not generate action for: {current_step_description}"}],
                    "thinking_process": self.thinking_process_output or "Max retries for action generation."
                })
                # Also update operator status
                await self._update_gui_state_func("/state/operator_status", {"text": f"Failed: Max retries for action on step {current_step_index + 1}"}) # MODIFIED (payload key)
                return None 

        if not action_to_execute:
            logger.error(f"Failed to generate a valid action for step {current_step_index + 1} after all retries.")
            return None

        self.last_proposed_action = action_to_execute
        logger.info(f"Successfully generated action for step {current_step_index + 1}: {action_to_execute}")
        return action_to_execute

    async def operate_loop(self):
        logger.info("AutomoyOperator.operate_loop started.")
        await self._update_gui_state_func("/state/operator_status", {"text": "Starting Operator..."}) # MODIFIED (payload key)
        # Ensure step_retry_count is defined if used directly in this loop for step execution retries,
        # but it seems action generation retries are self-contained in _get_action_for_current_step.
        # action_to_execute will be defined before use in the loop.

        if not self.steps: # If steps were not pre-formulated
            logger.info("No pre-formulated steps. Performing initial visual analysis to generate steps.")
            try:
                await self.manage_gui_window_func("hide")
                await asyncio.sleep(0.5) 
                screenshot_path_obj = self.desktop_utils.capture_current_screen(filename_prefix="automoy_initial_state_")
                
                if screenshot_path_obj:
                    logger.debug(f"Updating GUI with initial raw screenshot path: {str(screenshot_path_obj)}")
                    await self._update_gui_state_func("/state/screenshot", {"path": str(screenshot_path_obj)}) # MODIFIED (payload key)
                else:
                    logger.error("Failed to capture initial screenshot for analysis.")
                    await self._update_gui_state_func("/state/operator_status", {"text": "Error: Failed to capture screen for initial analysis"}) # MODIFIED
                    return


                logger.info(f"Initial screenshot captured: {screenshot_path_obj}")
                await self.manage_gui_window_func("show")
                await asyncio.sleep(0.5)

                if screenshot_path_obj:
                    self.current_processed_screenshot_path, visual_analysis_json = await self._perform_visual_analysis(
                        screenshot_path=screenshot_path_obj,
                        task_context=self.objective 
                    )
                    logger.info("Initial visual analysis performed and output stored.")
                else:
                    # This case is already handled above, but as a safeguard:
                    logger.error("Failed to capture initial screenshot. Cannot generate steps.")
                    await self._update_gui_state_func("/state/operator_status", {"text": "Error: Failed to capture screen"}) # MODIFIED (payload key)
                    await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "Failed to capture screen for initial analysis."})
                    return 

            except Exception as e_init_va:
                logger.error(f"Error during initial visual analysis: {e_init_va}", exc_info=True)
                await self._update_gui_state_func("/state/operator_status", {"text": f"Error during initial analysis: {e_init_va}"}) # MODIFIED (payload key)
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"Initial analysis failed: {e_init_va}"})
                return

            # Generate initial thinking process if not already available
            if self.visual_analysis_output and not self.thinking_process_output:
                logger.info("Generating initial thinking process based on objective and visual analysis...")
                await self._update_gui_state_func("/state/operator_status", {"text": "Generating initial thinking process..."}) # MODIFIED (payload key)
                try:
                    system_prompt_think = THINKING_PROCESS_SYSTEM_PROMPT
                    user_prompt_think = self.llm_interface.construct_thinking_process_prompt(
                        objective=self.objective,
                        visual_analysis_output=self.visual_analysis_output,
                        current_step_description="N/A (Overall objective planning)", 
                        previous_action_summary="N/A (Initial planning)"
                    )
                    messages_think = [
                        {"role": "system", "content": system_prompt_think},
                        {"role": "user", "content": user_prompt_think}
                    ]
                    
                    raw_llm_response_think, thinking_output_think, llm_error_think = await self.llm_interface.get_llm_response(
                        model=self.config.get_model(),
                        messages=messages_think,
                        objective=self.objective, 
                        session_id=self.session_id,
                        response_format_type="thinking_process"
                    )

                    if llm_error_think:
                        logger.error(f"LLM error during initial thinking process generation: {llm_error_think}")
                        self.thinking_process_output = f"Error generating thinking: {llm_error_think}"
                    elif thinking_output_think:
                        self.thinking_process_output = thinking_output_think
                        logger.info(f"Initial thinking process generated: {self.thinking_process_output[:200]}...")
                    elif raw_llm_response_think: 
                        self.thinking_process_output = raw_llm_response_think 
                        logger.info(f"Initial thinking process (from raw response): {self.thinking_process_output[:200]}...")
                    else:
                        logger.warning("LLM returned no response or thinking output for initial thinking process.")
                        self.thinking_process_output = "LLM provided no thinking output."
                    
                    await self._update_gui_state_func("/state/thinking", {"text": self.thinking_process_output})

                except Exception as e_think_gen:
                    logger.error(f"Exception during initial thinking process generation: {e_think_gen}", exc_info=True)
                    self.thinking_process_output = f"Exception generating thinking: {e_think_gen}"
                    await self._update_gui_state_func("/state/thinking", {"text": self.thinking_process_output})
            
            logger.info("Attempting to generate steps in operate_loop after initial analysis and thinking.")
            await self._generate_steps() 

            if not self.steps:
                logger.warning("No steps were formulated even after initial analysis and thinking. Operator loop cannot proceed.")
                await self._update_gui_state_func("/state/operator_status", {"text": "Failed: No steps formulated"}) # MODIFIED (payload key)
                return
            else:
                logger.info(f"Successfully generated {len(self.steps)} steps.")
                await self._update_gui_state_func("/state/operator_status", {"text": "Steps Generated"}) # MODIFIED (payload key)
        
        # Main loop for executing steps
        self.current_step_index = 0 # Ensure it starts at 0
        self.consecutive_error_count = 0 # Reset consecutive error counter

        while self.current_step_index < len(self.steps):
            await self.pause_event.wait() 
            if not self.pause_event.is_set():
                 logger.info("Operation paused by user (before step execution). Waiting for resume...")
                 await self._update_gui_state_func("/state/operator_status", {"text": "Paused"}) # MODIFIED (payload key)
                 await self.pause_event.wait()
                 logger.info("Operation resumed by user.")
            
            current_step = self.steps[self.current_step_index]
            current_step_description = current_step.get("description", "No description")
            logger.info(f"Processing step {self.current_step_index + 1}/{len(self.steps)}: {current_step_description}")
            await self._update_gui_state_func("/state/current_step", {"step_index": self.current_step_index, "description": current_step_description, "total_steps": len(self.steps)})
            await self._update_gui_state_func("/state/operator_status", {"text": f"Executing step {self.current_step_index + 1}"}) # MODIFIED (payload key)
            
            # Initialize action_to_execute for the current step
            action_to_execute: Optional[Dict[str, Any]] = None 
            
            # Get action for the current step (this now includes its own retry loop)
            # _get_action_for_current_step will also handle screenshots and visual analysis for the action
            action_to_execute = await self._get_action_for_current_step(
                current_step_description=current_step_description,
                current_step_index=self.current_step_index
            )

            if action_to_execute:
                logger.info(f"Action to execute for step {self.current_step_index + 1}: {action_to_execute}")
                # Placeholder for executing the action
                # action_result = await self.execute_action(action_to_execute) 
                # For now, simulate successful execution for flow testing
                action_type = action_to_execute.get("type", "unknown_action")
                action_summary = action_to_execute.get("summary", "No summary provided.")
                
                # Simulate action execution
                logger.info(f"Simulating execution of action: {action_type} - {action_summary}")
                await asyncio.sleep(1) # Simulate work
                action_successful = True # Assume success for now
                execution_details = f"Successfully executed: {action_summary}"

                if action_successful:
                    self.last_action_summary = execution_details # Update with actual outcome
                    self.executed_steps.append({
                        "step_index": self.current_step_index,
                        "description": current_step_description,
                        "action_taken": action_to_execute,
                        "summary": self.last_action_summary,
                        "status": "success"
                    })
                    logger.info(f"Step {self.current_step_index + 1} executed successfully. Summary: {self.last_action_summary}")
                    await self._update_gui_state_func("/state/last_action_summary", {"summary": self.last_action_summary, "status": "success"})
                    self.consecutive_error_count = 0 # Reset error count on success
                    self.current_step_index += 1 # Move to next step
                else:
                    # Handle action execution failure
                    self.last_action_summary = f"Failed to execute action: {action_summary}. Details: {execution_details}"
                    logger.error(self.last_action_summary)
                    self.executed_steps.append({
                        "step_index": self.current_step_index,
                        "description": current_step_description,
                        "action_taken": action_to_execute,
                        "summary": self.last_action_summary,
                        "status": "failed"
                    })
                    await self._update_gui_state_func("/state/last_action_summary", {"summary": self.last_action_summary, "status": "error"})
                    self.consecutive_error_count += 1
                    # Decide on retry logic for step execution here, or break/stop
                    if self.consecutive_error_count >= self.max_consecutive_errors:
                        logger.error(f"Max consecutive errors ({self.max_consecutive_errors}) reached. Stopping operation.")
                        await self._update_gui_state_func("/state/operator_status", {"text": f"Failed: Max errors reached at step {self.current_step_index + 1}"}) # MODIFIED (payload key)
                        break
                    # If not max errors, could implement step retry or just log and try next step (or stop)
                    # For now, let's assume we stop on first action execution failure to simplify.
                    # To try next step, you would increment current_step_index. To retry step, you wouldn't.
                    logger.warning(f"Action execution failed for step {self.current_step_index + 1}. Stopping as per current logic.")
                    await self._update_gui_state_func("/state/operator_status", {"text": f"Failed: Action execution error at step {self.current_step_index + 1}"}) # MODIFIED (payload key)
                    break 

            else: 
                logger.error(f"Failed to get a valid action for step {self.current_step_index + 1}. Stopping operation.")
                self.last_action_summary = f"Failed to generate action for step: {current_step_description}"
                await self._update_gui_state_func("/state/last_action_summary", {"summary": self.last_action_summary, "status": "error"})
                self.consecutive_error_count +=1
                if self.consecutive_error_count >= self.max_consecutive_errors:
                    logger.error(f"Max consecutive errors ({self.max_consecutive_errors}) reached due to action generation failure. Stopping operation.")
                    await self._update_gui_state_func("/state/operator_status", {"text": f"Failed: Max errors (action gen) at step {self.current_step_index + 1}"}) # MODIFIED (payload key)
                else:
                     await self._update_gui_state_func("/state/operator_status", {"text": f"Error: Failed to get action for step {self.current_step_index + 1}"}) # MODIFIED (payload key)
                break 
        
        if self.current_step_index >= len(self.steps) and self.consecutive_error_count == 0:
            logger.info("All steps executed successfully.")
            await self._update_gui_state_func("/state/operator_status", {"text": "Completed"}) # MODIFIED (payload key)
            await self._update_gui_state_func("/state/last_action_summary", {"summary": "All steps completed successfully.", "status": "success"})
        elif self.consecutive_error_count > 0: # Loop broke due to errors
             logger.warning(f"Operator loop finished due to {self.consecutive_error_count} consecutive error(s).")
             # Status already updated by the error handling within the loop
        elif self.current_step_index < len(self.steps): # Loop broke for other reasons (e.g. manual stop not yet implemented)
            logger.warning(f"Operator loop finished prematurely at step {self.current_step_index + 1} out of {len(self.steps)}.")
            await self._update_gui_state_func("/state/operator_status", {"text": f"Stopped prematurely at step {self.current_step_index + 1}"}) # MODIFIED (payload key)

        logger.info("AutomoyOperator.operate_loop finished.")
