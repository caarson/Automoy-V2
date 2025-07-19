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
from core.lm.lm_interface import MainInterface as LLMInterface
from core.prompts.prompts import (
    THINKING_PROCESS_SYSTEM_PROMPT, 
    THINKING_PROCESS_USER_PROMPT_TEMPLATE, 
    STEP_GENERATION_SYSTEM_PROMPT, 
    STEP_GENERATION_USER_PROMPT_TEMPLATE, 
    ACTION_GENERATION_SYSTEM_PROMPT,
)
from config import Config
from core.data_models import read_state, write_state
import pyautogui

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

# Import visual analysis utilities
from core.utils.screenshot_utils import capture_screen_pil
from core.utils.operating_system.desktop_utils import DesktopUtils

# Import other required utilities
from core.utils.operating_system.os_interface import OSInterface
from core.utils.vmware.vmware_interface import VMWareInterface
from core.utils.web_scraping.webscrape_interface import WebScrapeInterface
from core.utils.region.mapper import map_elements_to_coords

# 👉 Integrated LLM interface (merged MainInterface + handle_llm_response)
from core.lm.lm_interface import MainInterface, handle_llm_response

# Config import - ensure this path is robust
# Assuming config is in the parent directory of core
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "config"))
from config import Config


# Define BASE64_RE at the module level - enhanced pattern to catch more base64-like strings
BASE64_RE = re.compile(r'^[A-Za-z0-9+/=\\s]{100,}$|^data:image/[^;]+;base64,[A-Za-z0-9+/=]+$')

def clean_json_data(obj): # Renamed to avoid conflict if defined elsewhere
    """Recursively remove long base64-like strings from a JSON-like structure."""
    if isinstance(obj, dict):
        cleaned_dict = {}
        for k, v in obj.items():
            # Skip keys that commonly contain base64 data
            if k.lower() in ['image', 'screenshot', 'img_data', 'image_data', 'base64', 'encoded_image']:
                cleaned_dict[k] = "[BASE64_IMAGE_DATA_FILTERED]"
            elif isinstance(v, str) and (BASE64_RE.match(v) or len(v) > 1000):
                # Filter very long strings or obvious base64
                cleaned_dict[k] = f"[LONG_STRING_FILTERED_{len(v)}_CHARS]"
            else:
                cleaned_dict[k] = clean_json_data(v)
        return cleaned_dict
    elif isinstance(obj, list):
        return [clean_json_data(elem) for elem in obj]
    elif isinstance(obj, str):
        # Filter extremely long strings that might be base64 or binary data
        if len(obj) > 1000 or BASE64_RE.match(obj):
            return f"[LONG_STRING_FILTERED_{len(obj)}_CHARS]"
        return obj
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
        # For the file-based GUI state system, we need to map endpoints to state keys
        state_updates = {}
        
        if endpoint == "/state/visual":
            state_updates["visual"] = payload.get("text", "")
        elif endpoint == "/state/operator_status": 
            state_updates["text"] = payload.get("text", "")
        elif endpoint == "/state/thinking":
            state_updates["thinking_process"] = payload.get("text", "")
        elif endpoint == "/state/steps_generated":
            if "steps" in payload:
                state_updates["steps"] = payload["steps"]
            if "error" in payload:
                state_updates["llm_error_message"] = payload["error"]
        elif endpoint == "/state/current_step":
            state_updates.update({
                "step_index": payload.get("step_index", 0),
                "description": payload.get("description", ""),
                "total_steps": payload.get("total_steps", 0)
            })
        elif endpoint == "/state/operations_generated":
            if "operations" in payload:
                state_updates["operations"] = payload["operations"]
            if "thinking_process" in payload:
                state_updates["thinking_process"] = payload["thinking_process"]
        elif endpoint == "/state/last_action_summary":
            state_updates.update({
                "summary": payload.get("summary", ""),
                "status": payload.get("status", "")
            })
        elif endpoint == "/state/current_operation":
            state_updates["current_operation"] = payload.get("text", "")
        elif endpoint == "/state/past_operation":
            state_updates["past_operation"] = payload.get("text", "")
        elif endpoint == "/state/screenshot":
            state_updates["path"] = payload.get("path", "")
        elif endpoint == "/state/screenshot_processed":
            # Just a notification, no state change needed
            pass
        else:
            # For unknown endpoints, try to apply the payload directly
            state_updates.update(payload)
        
        if state_updates:
            # Read current state, update it, and write back
            try:
                current_state = read_state()
                current_state.update(state_updates)
                write_state(current_state)
                logger.debug(f"[GUI_UPDATE] Updated state with: {state_updates}")
            except Exception as e:
                logger.error(f"[GUI_UPDATE] Failed to update GUI state file: {e}")
        
        logger.debug(f"[GUI_UPDATE] Processed endpoint {endpoint} with payload: {payload}")
            
    except Exception as e:
        logger.error(f"Unexpected error in _update_gui_state for endpoint {endpoint}: {e}", exc_info=True)

class ActionExecutor:
    """Executes actions on Windows using pyautogui."""
    def __init__(self):
        pyautogui.FAILSAFE = False

    def execute(self, action: dict) -> str:
        try:
            action_type = action.get("action_type") or action.get("type")
            if action_type == "key":
                key = action.get("key")
                if key:
                    pyautogui.press(key)
                    return f"Pressed key: {key}"
            elif action_type == "key_sequence":
                keys = action.get("keys")
                if isinstance(keys, list):
                    pyautogui.hotkey(*keys)
                    return f"Pressed key sequence: {keys}"
                elif isinstance(keys, str):
                    # Handle string format like "win+s"
                    key_list = [k.strip() for k in keys.replace('+', ',').split(',')]
                    pyautogui.hotkey(*key_list)
                    return f"Pressed key sequence: {key_list}"
            elif action_type == "type":
                text = action.get("text")
                if text:
                    pyautogui.typewrite(text)
                    return f"Typed text: {text}"
            elif action_type == "click":
                coord = action.get("coordinate") or action
                x = coord.get("x")
                y = coord.get("y")
                if x is not None and y is not None:
                    pyautogui.click(x, y)
                    return f"Clicked at ({x}, {y})"
            elif action_type == "screenshot":
                # Screenshot actions request a new visual analysis
                target = action.get("target", "screen")
                return f"Screenshot requested for: {target}"
            elif action_type == "special":
                # Handle special actions like show_desktop
                target = action.get("target", "")
                if target == "show_desktop":
                    # Minimize all windows to show desktop
                    import subprocess
                    subprocess.run(['powershell', '-Command', '(New-Object -comObject Shell.Application).minimizeall()'], 
                                   capture_output=True, text=True)
                    return "Desktop shown (all windows minimized)"
                else:
                    return f"Special action executed: {target}"
            elif action_type == "visual_search":
                # Visual search actions will be handled by the step executor
                target = action.get("target", "unknown")
                return f"Visual search initiated for: {target}"
            
            # If we get here, the action format wasn't recognized
            # Try to extract a reasonable summary from the action
            summary = action.get("summary", action.get("description", str(action)))
            return f"Action format not fully supported: {summary}"
        except Exception as e:
            return f"Action execution error: {e}"

class AutomoyOperator:
    """Central orchestrator for Automoy autonomous operation."""

    def __init__(self, 
                 objective: str, 
                 manage_gui_window_func: Callable[..., Coroutine[Any, Any, bool]], 
                 omniparser,  # Kept for compatibility but will be None
                 pause_event: asyncio.Event,
                 update_gui_state_func: Callable[..., Coroutine[Any, Any, None]] # Added
                 ):
        self.objective = objective
        self.manage_gui_window_func = manage_gui_window_func
        self.omniparser = omniparser  # Restored visual analysis capability
        self.pause_event = pause_event
        self._update_gui_state_func = update_gui_state_func # Store the function

        self.config = Config()
        self.llm_interface = LLMInterface()
        # Desktop utilities will be set by main.py after initialization
        self.desktop_utils = None  
        self.action_executor = ActionExecutor()

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
        logger.info("Visual analysis and desktop utilities disabled")

    def set_objective(self, new_objective: str):
        """Update the objective and trigger the operation loop."""
        logger.info(f"Setting new objective: {new_objective}")
        self.objective = new_objective
        
        # Reset state for new objective
        self.steps = []
        self.steps_for_gui = []
        self.executed_steps = []
        self.current_step_index = 0
        self.visual_analysis_output = None
        self.thinking_process_output = None
        self.operations_generated_for_gui = []
        self.last_action_summary = None
        self.consecutive_error_count = 0
        
        # Create a new task to run the operate loop asynchronously
        try:
            task = asyncio.create_task(self.operate_loop())
            logger.info("Operation loop task created successfully for new objective")
            # Add a callback to log any exceptions from the task
            def log_task_exception(task):
                if task.exception():
                    logger.error(f"Operation loop task failed with exception: {task.exception()}", exc_info=task.exception())
            task.add_done_callback(log_task_exception)
        except Exception as e:
            logger.error(f"Failed to create operation loop task: {e}", exc_info=True)

    async def _ensure_desktop_anchor(self):
        """Ensure we return to a consistent desktop state for reliable automation."""
        if self.desktop_utils:
            try:
                logger.info("Ensuring desktop anchor state")
                await self._update_gui_state_func("/state/thinking", {"text": "Returning to desktop anchor point for consistent automation state"})
                await asyncio.to_thread(self.desktop_utils.ensure_desktop_anchor)
                logger.info("Desktop anchor state ensured successfully")
                await self._update_gui_state_func("/state/thinking", {"text": "Desktop anchor point confirmed - ready for next action"})
            except Exception as e:
                logger.error(f"Desktop anchor failed: {e}", exc_info=True)
                await self._update_gui_state_func("/state/thinking", {"text": f"Desktop anchor error: {str(e)} - continuing anyway"})
        else:
            logger.warning("Desktop utilities not available - skipping anchor")
            await self._update_gui_state_func("/state/thinking", {"text": "Desktop utilities not available - skipping anchor point"})
    
    def _extract_visual_summary(self, visual_json_str: str) -> str:
        """Extract a concise 1-2 sentence summary from visual analysis JSON."""
        try:
            if not visual_json_str:
                return "No visual analysis available."
            
            visual_data = json.loads(visual_json_str)
            
            # Look for key indicators in the parsed content
            parsed_content = visual_data.get('parsed_content', [])
            if not parsed_content:
                return "Desktop visible with no major elements detected."
            
            # Count different types of elements
            buttons = [item for item in parsed_content if item.get('class', '').lower() in ['button', 'btn']]
            text_elements = [item for item in parsed_content if item.get('class', '').lower() in ['text', 'label', 'title']]
            inputs = [item for item in parsed_content if item.get('class', '').lower() in ['input', 'textbox', 'field']]
            
            # Look for specific application indicators
            window_titles = []
            app_indicators = []
            
            for item in parsed_content:
                text = item.get('text', '').strip().lower()
                if 'calculator' in text:
                    app_indicators.append('Calculator')
                elif 'notepad' in text:
                    app_indicators.append('Notepad')
                elif 'chrome' in text or 'browser' in text:
                    app_indicators.append('Browser')
                elif 'start' in text and ('menu' in text or 'button' in text):
                    app_indicators.append('Start Menu')
                elif 'taskbar' in text:
                    app_indicators.append('Taskbar')
            
            # Generate summary based on detected elements
            if app_indicators:
                apps = ', '.join(set(app_indicators))
                return f"{apps} visible on screen with {len(parsed_content)} interactive elements."
            elif len(parsed_content) > 10:
                return f"Complex interface visible with {len(parsed_content)} elements including {len(buttons)} buttons."
            elif len(parsed_content) > 5:
                return f"Interface visible with {len(parsed_content)} interactive elements."
            elif len(parsed_content) > 0:
                return f"Simple interface with {len(parsed_content)} elements detected."
            else:
                return "Clean desktop view with minimal interface elements."
                
        except Exception as e:
            logger.error(f"Error extracting visual summary: {e}", exc_info=True)
            return f"Visual analysis completed but summary extraction failed: {str(e)}"

    async def _perform_visual_analysis(self, screenshot_path: Path, task_context: str) -> Tuple[Optional[Path], Optional[str]]:
        """Perform visual analysis using OmniParser and redirect analysis to thinking display."""
        logger.info(f"Starting visual analysis for task: {task_context}")
        
        # Immediately update GUI with screenshot path
        await self._update_gui_state_func("/state/screenshot", {"path": str(screenshot_path)})
        
        # Update current operation to show visual analysis is starting  
        await self._update_gui_state_func("/state/current_operation", {"text": f"Performing visual analysis of current screen for: {task_context}"})
        
        if not self.omniparser:
            logger.warning("OmniParser not available for visual analysis")
            await self._update_gui_state_func("/state/current_operation", {"text": "Visual analysis unavailable - OmniParser not initialized. Continuing without screen analysis."})
            return None, None
        
        try:
            # Update current operation with analysis progress
            await self._update_gui_state_func("/state/current_operation", {"text": "Analyzing screenshot with OmniParser to identify UI elements..."})
            
            # Perform the visual analysis
            parsed_result = self.omniparser.parse_screenshot(str(screenshot_path))
            
            if parsed_result and "parsed_content_list" in parsed_result:
                # Process the visual analysis results
                elements_found = len(parsed_result["parsed_content_list"])
                await self._update_gui_state_func("/state/current_operation", {"text": f"Visual analysis complete: Found {elements_found} UI elements. Processing results for action planning."})
                
                # Send the visual analysis results to thinking display
                formatted_analysis = self._format_visual_analysis_for_thinking(parsed_result)
                await self._update_gui_state_func("/state/thinking", {"text": formatted_analysis})
                
                # Check if processed screenshot is available
                processed_screenshot_path = None
                if "som_image_base64" in parsed_result:
                    # The OmniParser interface should have saved the processed screenshot
                    possible_paths = [
                        Path(__file__).parent / "utils" / "omniparser" / "processed_screenshot.png",
                        Path("gui/static/processed_screenshot.png"),
                        screenshot_path.parent / "processed_screenshot.png"
                    ]
                    for path in possible_paths:
                        if path.exists():
                            processed_screenshot_path = path
                            break
                
                # If processed screenshot is found, immediately update GUI
                if processed_screenshot_path:
                    await self._update_gui_state_func("/state/screenshot_processed", {"path": str(processed_screenshot_path)})
                
                # Format the visual analysis output for LLM consumption
                visual_output = self._format_visual_analysis_result(parsed_result)
                logger.info(f"Visual analysis completed successfully with {elements_found} elements")
                
                return processed_screenshot_path, visual_output
            else:
                logger.warning("Visual analysis returned no results")
                await self._update_gui_state_func("/state/thinking", {"text": "Visual analysis completed but no UI elements were detected. Continuing with available information."})
                return None, "No visual elements detected in the current screen."
                
        except Exception as e:
            logger.error(f"Error during visual analysis: {e}", exc_info=True)
            await self._update_gui_state_func("/state/thinking", {"text": f"Visual analysis error: {str(e)}. Continuing without screen analysis."})
            return None, None

    def _format_visual_analysis_result(self, parsed_result: dict) -> str:
        """Format the visual analysis result for LLM consumption."""
        if not parsed_result or "parsed_content_list" not in parsed_result:
            return "No visual elements detected."
        
        elements = parsed_result["parsed_content_list"]
        formatted_output = ["Visual Analysis Results:"]
        
        for i, element in enumerate(elements):
            element_info = []
            if element.get("content"):
                element_info.append(f"Text: '{element['content']}'")
            if element.get("type"):
                element_info.append(f"Type: {element['type']}")
            if element.get("bbox_normalized"):
                bbox = element["bbox_normalized"]
                element_info.append(f"Position: ({bbox[0]:.2f}, {bbox[1]:.2f}, {bbox[2]:.2f}, {bbox[3]:.2f})")
            if element.get("interactivity"):
                element_info.append("Interactive: Yes")
            
            if element_info:
                formatted_output.append(f"{i+1}. {' | '.join(element_info)}")
        
        return "\n".join(formatted_output)

    def _format_visual_analysis_for_thinking(self, parsed_result: dict) -> str:
        """Format visual analysis results for display in thinking tab."""
        if not parsed_result or "parsed_content_list" not in parsed_result:
            return "Visual analysis found no UI elements."
        
        elements = parsed_result["parsed_content_list"]
        if not elements:
            return "Visual analysis completed but found no UI elements."
        
        # Create a formatted display of the visual analysis
        analysis_text = f"Visual Analysis Results ({len(elements)} elements found):\n\n"
        
        for i, element in enumerate(elements[:10], 1):  # Limit to first 10 elements
            element_info = []
            if element.get("text"):
                element_info.append(f"Text: '{element['text']}'")
            if element.get("type"):
                element_info.append(f"Type: {element['type']}")
            if element.get("coordinates"):
                coords = element["coordinates"]
                element_info.append(f"Position: ({coords.get('x', 'N/A')}, {coords.get('y', 'N/A')})")
            
            analysis_text += f"{i}. {'|'.join(element_info) if element_info else 'Unknown element'}\n"
        
        if len(elements) > 10:
            analysis_text += f"\n... and {len(elements) - 10} more elements"
        
        return analysis_text

    async def _generate_steps(self):
        logger.info("Generating steps...")
        # Update current operation to show step generation
        await self._update_gui_state_func("/state/operator_status", {"text": "running"})
        await self._update_gui_state_func("/state/current_operation", {"text": "Generating steps for objective"})
        
        # Add thinking process to the thinking tab
        await self._update_gui_state_func("/state/thinking", {"text": f"Breaking down objective into actionable steps: {self.objective}"})
        
        # Check if this is a Chrome-related goal - only use hardcoded steps if NOT requesting visual clicking
        original_goal = getattr(self, 'original_goal', '').lower()
        objective_text = self.objective.lower()
        
        # Debug logging
        logger.info(f"DEBUG: objective_text = '{objective_text}'")
        logger.info(f"DEBUG: original_goal = '{original_goal}'")
        
        if ("chrome" in objective_text or "chrome" in original_goal):
            # Check for visual keywords in either objective or original goal
            visual_keywords = ['click', 'mouse', 'visual', 'icon', 'desktop', 'screenshot', 'analyze', 'image']
            has_visual_keywords = any(keyword in original_goal for keyword in visual_keywords) or \
                                  any(keyword in objective_text for keyword in visual_keywords)
            
            logger.info(f"DEBUG: has_visual_keywords = {has_visual_keywords}")
            logger.info(f"DEBUG: visual keywords found in original_goal: {[kw for kw in visual_keywords if kw in original_goal]}")
            logger.info(f"DEBUG: visual keywords found in objective: {[kw for kw in visual_keywords if kw in objective_text]}")
            
            if not has_visual_keywords:
                logger.info("Detected Chrome goal without visual requirements - using simple hardcoded steps")
                return await self._generate_steps_simple_chrome()
            else:
                logger.info("Detected Chrome goal WITH visual clicking requirements - using proper visual analysis")
                return await self._generate_steps_chrome_visual()
        
        # Skip automatic screenshot capture - only take screenshots when explicitly requested by LLM
        visual_analysis_output = "No visual context - screenshot will be taken when needed during execution"
        
        try:
            # Update thinking with step generation process
            await self._update_gui_state_func("/state/thinking", {"text": "Generating step-by-step plan based on objective and current screen state..."})
            
            # Construct the prompt for step generation
            system_prompt_steps = STEP_GENERATION_SYSTEM_PROMPT
            user_prompt_steps = self.llm_interface.construct_step_generation_prompt(
                objective=self.objective,
                visual_analysis_output=visual_analysis_output or "No visual context available",
                thinking_process_output=self.thinking_process_output or "Initial step generation for objective",
                previous_steps_output="N/A" # Assuming this is for initial generation
            )
            messages_steps = [
                {"role": "system", "content": system_prompt_steps},
                {"role": "user", "content": user_prompt_steps}
            ]

            # Update current operation status instead of thinking
            await self._update_gui_state_func("/state/current_operation", {"text": "Communicating with LLM to generate step sequence..."})
            
            # Create a callback function to stream thinking updates for step generation
            async def step_stream_callback(token):
                """Callback to update thinking display with streamed tokens for step generation"""
                if hasattr(self, '_current_step_thinking_stream'):
                    self._current_step_thinking_stream += token
                else:
                    self._current_step_thinking_stream = token  # Start fresh with just LLM output
                await self._update_gui_state_func("/state/thinking", {"text": self._current_step_thinking_stream})
            
            # Clear thinking display for fresh LLM output
            self._current_step_thinking_stream = ""
            await self._update_gui_state_func("/state/thinking", {"text": ""})
            
            logger.debug(f"Messages for step generation LLM call (first 200 chars of user prompt): {str(messages_steps)[:200]}...")
            
            raw_llm_response, _, llm_error = await self.llm_interface.get_llm_response( # Using get_llm_response, ignoring thinking output here
                model=self.config.get_model(),
                messages=messages_steps,
                objective=self.objective,
                session_id=self.session_id,
                response_format_type="step_generation",
                thinking_callback=step_stream_callback  # Add streaming callback
            )

            if llm_error:
                logger.error(f"LLM error during step generation: {llm_error}")
                await self._update_gui_state_func("/state/current_operation", {"text": f"Error generating steps: {llm_error}"})
                await self._update_gui_state_func("/state/thinking", {"text": f"Error: {llm_error}"})
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"LLM Error: {llm_error}"})
                return
            
            if not raw_llm_response:
                logger.warning("LLM returned no response for step generation.")
                await self._update_gui_state_func("/state/thinking", {"text": "LLM provided no response for step generation"})
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "LLM provided no response for steps."})
                return

            # Update thinking with parsing process
            await self._update_gui_state_func("/state/thinking", {"text": "Processing LLM response and extracting steps..."})

            # Get parsed JSON directly from handle_llm_response
            from core.lm.lm_interface import handle_llm_response
            parsed_steps_data = handle_llm_response(raw_llm_response, "step_generation", is_json=True)
            logger.debug(f"handle_llm_response returned for step generation - Type: {type(parsed_steps_data)}")
            logger.debug(f"Parsed steps data (first 500 chars): {str(parsed_steps_data)[:500]}...")

            if not parsed_steps_data:
                logger.warning("handle_llm_response returned None or empty for step generation.")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "Failed to parse LLM step response."})
                await self._update_gui_state_func("/state/current_operation", {"text": "Failed to parse step response"})
                return
            
            # Check if the response indicates an error
            if isinstance(parsed_steps_data, dict) and "error" in parsed_steps_data:
                logger.error(f"Error from handle_llm_response: {parsed_steps_data}")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"JSON parsing error: {parsed_steps_data.get('message', 'Unknown error')}"})
                self.steps = []
                self.steps_for_gui = []
                return
            
            # Handle the parsed data - no need for additional JSON parsing
            if isinstance(parsed_steps_data, dict) and "steps" in parsed_steps_data and isinstance(parsed_steps_data["steps"], list):
                self.steps = parsed_steps_data["steps"]
                # Prepare steps for GUI (e.g., just descriptions)
                self.steps_for_gui = [{"description": step.get("description", "No description")} for step in self.steps]
            elif isinstance(parsed_steps_data, list): # If LLM directly returns a list of steps
                self.steps = parsed_steps_data
                # Handle both old and new step formats for GUI display
                if self.steps and isinstance(self.steps[0], dict):
                    # New format with step objects containing description
                    self.steps_for_gui = [{"description": step.get("description", f"Step {step.get('step_number', i+1)}")} for i, step in enumerate(self.steps)]
                else:
                    # Old format fallback
                    self.steps_for_gui = [{"description": step.get("description", "No description") if isinstance(step, dict) else str(step)} for step in self.steps]
            else:
                logger.warning(f"Parsed steps data is not in the expected format: {type(parsed_steps_data)} - {str(parsed_steps_data)[:200]}...")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "LLM step response has incorrect format."})
                await self._update_gui_state_func("/state/current_operation", {"text": "Step parsing failed - incorrect format"})
                return

            if self.steps:
                logger.info(f"Generated {len(self.steps)} steps.")
                await self._update_gui_state_func("/state/steps_generated", {"steps": self.steps_for_gui}) # Send descriptions
                await self._update_gui_state_func("/state/current_operation", {"text": f"Successfully generated {len(self.steps)} steps"})
            else:
                logger.warning("LLM did not generate any steps (parsed list was empty).")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "LLM failed to generate steps (empty list)."})
                await self._update_gui_state_func("/state/current_operation", {"text": "No steps generated"})

        except Exception as e:
            logger.error(f"Error generating steps: {e}", exc_info=True)
            await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"Error generating steps: {str(e)[:100]}..."})
            await self._update_gui_state_func("/state/current_operation", {"text": "Error during step generation"})
            self.steps = []
            self.steps_for_gui = []

    async def _get_action_for_current_step(self, current_step_description: str, current_step_index: int):
        logger.info(f"Getting action for step {current_step_index + 1}: {current_step_description}")
        action_json_str: Optional[str] = None
        action_to_execute: Optional[Dict[str, Any]] = None
        self.thinking_process_output = self.thinking_process_output if hasattr(self, 'thinking_process_output') else None # Ensure initialized

        try:
            # Check if this is a Chrome icon click step with stored coordinates
            current_step = self.steps[current_step_index] if current_step_index < len(self.steps) else {}
            if (current_step.get("action_type") == "click" and 
                current_step.get("target") == "chrome_icon_coordinates" and 
                hasattr(self, 'chrome_icon_coordinates') and 
                self.chrome_icon_coordinates):
                
                x, y = self.chrome_icon_coordinates
                logger.info(f"Using stored Chrome coordinates for click: ({x}, {y})")
                await self._update_gui_state_func("/state/thinking", {"text": f"Using previously detected Chrome coordinates: ({x}, {y})"})
                
                return {
                    "type": "click",
                    "coordinate": {"x": x, "y": y},
                    "summary": f"Click Chrome icon at detected coordinates ({x}, {y})",
                    "confidence": 90
                }
            
            # Skip automatic screenshot capture - only take screenshots when explicitly requested
            await self._update_gui_state_func("/state/current_operation", {"text": f"Generating action for step: {current_step_description}"})
            
            # Use existing visual analysis output if available, otherwise indicate no visual context
            if not self.visual_analysis_output:
                self.visual_analysis_output = "No current visual analysis - screenshot will be taken if explicitly requested"
                await self._update_gui_state_func("/state/thinking", {"text": "No visual analysis available - will capture screenshot only when requested by action"})

        except Exception as e_screenshot_va:
            logger.error(f"Error during action preparation: {e_screenshot_va}", exc_info=True)
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
            await self._update_gui_state_func("/state/operator_status", {"text": f"Formulating action for step {current_step_index + 1} (Attempt {step_retry_count + 1})"}) # MODIFIED (payload key)

            try:
                # === ENHANCED CHROME DETECTION USING OMNIPARSER ===
                # Check if this is a Chrome-related goal
                if ("chrome" in self.objective.lower() and 
                    ("click" in current_step_description.lower() or "launch" in current_step_description.lower() or 
                     "screenshot" in current_step_description.lower() or "icon" in current_step_description.lower())):
                    
                    logger.info("Chrome goal detected - attempting direct coordinate detection with OmniParser")
                    await self._update_gui_state_func("/state/thinking", {"text": "Chrome goal detected - attempting to find Chrome icon using OmniParser..."})
                    
                    try:
                        if self.omniparser:
                            # Capture screenshot for OmniParser analysis
                            from core.utils.screenshot_utils import capture_screen_pil
                            import tempfile
                            import os
                            
                            screenshot = capture_screen_pil()
                            if screenshot:
                                # Save to temporary file (OmniParser expects file path, not PIL Image)
                                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                                    temp_path = temp_file.name
                                    screenshot.save(temp_path)
                                    logger.info(f"Screenshot saved to temporary file for OmniParser: {temp_path}")
                                
                                try:
                                    # Parse screenshot with OmniParser
                                    parsed_result = self.omniparser.parse_screenshot(temp_path)
                                    
                                    if parsed_result and "parsed_content_list" in parsed_result:
                                        elements = parsed_result.get("parsed_content_list", [])
                                        logger.info(f"OmniParser found {len(elements)} UI elements")
                                        await self._update_gui_state_func("/state/thinking", 
                                            {"text": f"OmniParser analysis complete - found {len(elements)} elements, searching for Chrome..."})
                                        
                                        # Get screen dimensions for coordinate conversion
                                        import pyautogui
                                        screen_width, screen_height = pyautogui.size()
                                        
                                        # Search for Chrome icon with comprehensive criteria
                                        chrome_coords = None
                                        chrome_candidates = []
                                        
                                        for i, element in enumerate(elements):
                                            element_text = element.get("content", "").lower()
                                            element_type = element.get("type", "").lower()
                                            bbox = element.get("bbox_normalized", [])
                                            interactive = element.get("interactivity", False)
                                            
                                            # Log elements for debugging
                                            if element_text or element_type == "icon" or interactive:
                                                logger.info(f"  Element {i}: '{element_text}' type='{element_type}' interactive={interactive}")
                                            
                                            # Enhanced Chrome detection criteria
                                            is_chrome_candidate = (
                                                "chrome" in element_text or
                                                "google chrome" in element_text or
                                                "google" in element_text or
                                                ("browser" in element_text) or
                                                (element_type == "icon" and interactive) or
                                                (element_type == "button" and any(term in element_text for term in ["chrome", "browser", "google"]))
                                            )
                                            
                                            if is_chrome_candidate:
                                                chrome_candidates.append((i, element))
                                                logger.info(f"  ★ Chrome candidate found: '{element_text}' (type: {element_type})")
                                                
                                                if bbox and not all(x == 0 for x in bbox):
                                                    # Convert normalized coordinates to pixels
                                                    x1 = int(bbox[0] * screen_width)
                                                    y1 = int(bbox[1] * screen_height)
                                                    x2 = int(bbox[2] * screen_width)
                                                    y2 = int(bbox[3] * screen_height)
                                                    center_x = int((x1 + x2) / 2)
                                                    center_y = int((y1 + y2) / 2)
                                                    chrome_coords = (center_x, center_y)
                                                    
                                                    logger.info(f"  ✓ Valid Chrome coordinates found: ({center_x}, {center_y})")
                                                    await self._update_gui_state_func("/state/thinking", 
                                                        {"text": f"Chrome icon found at ({center_x}, {center_y}) - creating click action"})
                                                    break
                                        
                                        # If we found valid Chrome coordinates, create click action
                                        if chrome_coords:
                                            action_to_execute = {
                                                "type": "click",
                                                "coordinate": chrome_coords,
                                                "x": chrome_coords[0],
                                                "y": chrome_coords[1],
                                                "summary": f"Click Chrome icon at ({chrome_coords[0]}, {chrome_coords[1]}) using OmniParser coordinates",
                                                "confidence": 95,
                                                "source": "omniparser_chrome_detection"
                                            }
                                            
                                            logger.info(f"✅ Created Chrome click action: {action_to_execute}")
                                            await self._update_gui_state_func("/state/thinking", 
                                                {"text": f"✅ Chrome click action created using OmniParser coordinates!"})
                                            await self._update_gui_state_func("/state/operations_generated", {
                                                "operations": [action_to_execute],
                                                "thinking_process": f"Chrome icon detected at coordinates {chrome_coords} using OmniParser"
                                            })
                                            
                                            self.last_proposed_action = action_to_execute
                                            return action_to_execute
                                        else:
                                            logger.warning(f"Chrome candidates found ({len(chrome_candidates)}) but no valid coordinates")
                                            await self._update_gui_state_func("/state/thinking", 
                                                {"text": f"Found {len(chrome_candidates)} Chrome candidates but no valid coordinates"})
                                    else:
                                        logger.warning("OmniParser returned no results or missing parsed_content_list")
                                        
                                        # Try coordinate fallback for Chrome before keyboard approach
                                        if any(keyword in current_step_description.lower() for keyword in ['chrome', 'browser']):
                                            logger.info("Attempting Chrome coordinate fallback testing")
                                            await self._update_gui_state_func("/state/thinking", 
                                                {"text": "OmniParser found no elements - trying Chrome coordinate fallback"})
                                            
                                            # Define test coordinates for common Chrome locations
                                            test_coordinates = [
                                                (250, 100), (300, 100), (350, 100), (400, 100),
                                                (100, 200), (150, 200), (200, 200), (250, 200)
                                            ]
                                            
                                            # Use the current step index to determine which coordinate to try
                                            coord_index = getattr(self, 'chrome_coord_index', 0)
                                            if coord_index < len(test_coordinates):
                                                x, y = test_coordinates[coord_index]
                                                
                                                action_to_execute = {
                                                    "type": "click",
                                                    "coordinate": {"x": x, "y": y},
                                                    "x": x,
                                                    "y": y,
                                                    "summary": f"Testing Chrome coordinate fallback at ({x}, {y})",
                                                    "confidence": 70,
                                                    "source": "coordinate_fallback"
                                                }
                                                
                                                # Increment for next attempt
                                                self.chrome_coord_index = coord_index + 1
                                                
                                                logger.info(f"✅ Created Chrome coordinate fallback: {action_to_execute}")
                                                await self._update_gui_state_func("/state/thinking", 
                                                    {"text": f"Testing Chrome at fallback coordinates ({x}, {y})"})
                                                
                                                self.last_proposed_action = action_to_execute
                                                return action_to_execute
                                            else:
                                                # Reset coordinate index and fall back to keyboard
                                                self.chrome_coord_index = 0
                                                await self._update_gui_state_func("/state/thinking", 
                                                    {"text": "All coordinate fallbacks tried - using keyboard approach"})
                                        else:
                                            await self._update_gui_state_func("/state/thinking", 
                                                {"text": "OmniParser found no UI elements - falling back to keyboard approach"})
                                
                                finally:
                                    # Cleanup temporary file
                                    try:
                                        if os.path.exists(temp_path):
                                            os.unlink(temp_path)
                                    except Exception:
                                        pass
                            else:
                                logger.error("Failed to capture screenshot for Chrome detection")
                        else:
                            logger.warning("OmniParser not available for Chrome detection")
                            
                    except Exception as chrome_error:
                        logger.error(f"Chrome detection failed: {chrome_error}", exc_info=True)
                        await self._update_gui_state_func("/state/thinking", 
                            {"text": f"Chrome detection error: {chrome_error} - continuing with normal action generation"})
                    
                    # Chrome detection completed - continue with normal flow if no action was created
                    logger.info("Chrome detection completed - continuing with LLM-based action generation")
                
                # === END CHROME DETECTION ===
                
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

                # Update status to show LLM is thinking
                await self._update_gui_state_func("/state/operator_status", {"text": f"LLM analyzing step {current_step_index + 1}..."})

                # Update current operation status instead of thinking
                await self._update_gui_state_func("/state/current_operation", {"text": f"Communicating with LLM for action generation on step: {current_step_description}"})
                
                # Create a callback function to stream thinking updates in real-time
                async def thinking_stream_callback(token):
                    """Callback to update thinking display with streamed tokens"""
                    if hasattr(self, '_current_thinking_stream'):
                        self._current_thinking_stream += token
                    else:
                        self._current_thinking_stream = token  # Start fresh with just LLM output
                    await self._update_gui_state_func("/state/thinking", {"text": self._current_thinking_stream})
                
                # Clear thinking display for fresh LLM output
                self._current_thinking_stream = ""
                await self._update_gui_state_func("/state/thinking", {"text": ""})
                
                raw_llm_response, thinking_output, llm_error = await self.llm_interface.get_next_action(
                    model=self.config.get_model(),
                    messages=messages_action,
                    objective=self.objective,
                    session_id=self.session_id,
                    screenshot_path=None,  # Visual analysis disabled
                    thinking_callback=thinking_stream_callback  # Add streaming callback
                )
                
                # Update thinking process output and display it in the thinking tab
                self.thinking_process_output = thinking_output
                if thinking_output:
                    await self._update_gui_state_func("/state/thinking", {"text": thinking_output})
                else:
                    # Keep the final streamed output if no separate thinking output
                    pass  # The streamed output is already in thinking display

                # Update current operation status
                await self._update_gui_state_func("/state/current_operation", {"text": f"Processing LLM response for step {current_step_index + 1}"})

                if llm_error:
                    logger.error(f"LLM error during action generation: {llm_error}")
                    await self._update_gui_state_func("/state/current_operation", {"text": f"LLM Error: {llm_error}"})
                    await self._update_gui_state_func("/state/thinking", {"text": f"Error: {llm_error}"})
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "error", "summary": f"LLM Error: {llm_error}"}],
                        "thinking_process": self.thinking_process_output or f"LLM Error: {llm_error}"
                    })
                    await self._update_gui_state_func("/state/operator_status", {"text": f"LLM error on step {current_step_index + 1}"})
                    step_retry_count += 1
                    await asyncio.sleep(1)
                    continue

                if not raw_llm_response:
                    logger.warning("LLM returned no response for action generation.")
                    await self._update_gui_state_func("/state/current_operation", {"text": "LLM provided no response for action generation"})
                    await self._update_gui_state_func("/state/thinking", {"text": "No response from LLM"})
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "info", "summary": "LLM provided no action this attempt."}],
                        "thinking_process": self.thinking_process_output or "LLM gave empty response."
                    })
                    await self._update_gui_state_func("/state/operator_status", {"text": f"No LLM response for step {current_step_index + 1}"})
                    step_retry_count += 1
                    await asyncio.sleep(1) 
                    continue
                
                # Update current operation with action parsing
                await self._update_gui_state_func("/state/current_operation", {"text": "Processing LLM response and extracting action..."})
                
                from core.lm.lm_interface import handle_llm_response
                action_result = handle_llm_response(raw_llm_response, "action_generation", 
                                                   is_json=True,
                                                   llm_interface=self.llm_interface,
                                                   objective=self.objective,
                                                   current_step_description=current_step_description,
                                                   visual_analysis_output=self.visual_analysis_output)
                logger.debug(f"handle_llm_response result for action generation: {action_result}")

                if not action_result:
                    logger.warning("handle_llm_response returned None or empty.")
                    await self._update_gui_state_func("/state/thinking", {"text": "Failed to parse LLM action response - returned None or empty"})
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "warning", "summary": "Failed to parse LLM action response."}],
                        "thinking_process": self.thinking_process_output or "Could not parse LLM action."
                    })
                    step_retry_count += 1
                    await asyncio.sleep(1)
                    continue

                # Check if action_result is already a dictionary (from fallback) or a JSON string
                if isinstance(action_result, dict):
                    # It's already a parsed action (likely from fallback)
                    parsed_action = action_result
                elif isinstance(action_result, str):
                    # It's a JSON string that needs parsing
                    try:
                        parsed_action = json.loads(action_result)
                    except json.JSONDecodeError as jde:
                        logger.error(f"JSONDecodeError parsing action_result: {jde}. Content: {action_result}")
                        await self._update_gui_state_func("/state/thinking", {"text": f"JSON decode error parsing action: {jde}"})
                        await self._update_gui_state_func("/state/operations_generated", {
                            "operations": [{"type": "error", "summary": "Invalid JSON from LLM for action."}],
                            "thinking_process": self.thinking_process_output or f"JSON Error: {jde}"
                        })
                        step_retry_count += 1
                        await asyncio.sleep(1)
                        continue
                else:
                    logger.error(f"Unexpected action_result type: {type(action_result)}")
                    await self._update_gui_state_func("/state/thinking", {"text": f"Unexpected response format from action processing: {type(action_result)}"})
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "error", "summary": "Unexpected response format from action processing."}],
                        "thinking_process": self.thinking_process_output or "Unexpected response type."
                    })
                    step_retry_count += 1
                    await asyncio.sleep(1)
                    continue

                # Validate the parsed action has required fields
                if isinstance(parsed_action, dict) and "type" in parsed_action and "summary" in parsed_action:
                    action_to_execute = parsed_action 
                    self.operations_generated_for_gui = [action_to_execute]
                    logger.info(f"Action proposed by LLM: {action_to_execute}")
                    await self._update_gui_state_func("/state/thinking", {"text": f"Valid action extracted: {action_to_execute['type']} - {action_to_execute['summary']}"})
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": self.operations_generated_for_gui,
                        "thinking_process": self.thinking_process_output or "N/A"
                    })
                    break 
                else:
                    logger.warning(f"Parsed action is not in the expected format: {parsed_action}")
                    await self._update_gui_state_func("/state/thinking", {"text": f"Invalid action format received: {parsed_action}"})
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "error", "summary": "LLM action response has incorrect format."}],
                        "thinking_process": self.thinking_process_output or "Action format error."
                    })
                    step_retry_count += 1
                    await asyncio.sleep(1)
                    continue

            except Exception as e_llm_action: # This except block pairs with the outer try for the LLM call attempt
                logger.error(f"Exception during LLM call for action generation (attempt {step_retry_count + 1}): {e_llm_action}", exc_info=True)
                await self._update_gui_state_func("/state/thinking", {"text": f"Exception during action generation: {e_llm_action}"})
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
                await self._update_gui_state_func("/state/thinking", {"text": f"Max retries reached for step {current_step_index + 1} action generation"})
                await self._update_gui_state_func("/state/operations_generated", {
                    "operations": [{"type": "error", "summary": f"Max retries reached. Could not generate action for: {current_step_description}"}],
                    "thinking_process": self.thinking_process_output or "Max retries for action generation."
                })
                # Also update operator status
                await self._update_gui_state_func("/state/operator_status", {"text": f"Failed: Max errors (action gen) at step {current_step_index + 1}"}) # MODIFIED (payload key)
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
            logger.info("No pre-formulated steps. Generating steps directly without visual analysis.")
            await self._update_gui_state_func("/state/current_operation", {"text": "No pre-formulated steps available - generating initial steps based on objective"})
            try:
                await self._update_gui_state_func("/state/operator_status", {"text": "Generating initial steps..."})
                
                # Clear thinking display for LLM output
                await self._update_gui_state_func("/state/thinking", {"text": ""})
                
                # Skip visual analysis - go directly to step generation
                await self._update_gui_state_func("/state/current_operation", {"text": "Requesting LLM to generate step-by-step plan for objective"})
                self.visual_analysis_output = {"elements": [], "text_snippets": []}  # Empty visual analysis
                
                # Generate initial thinking process
                await self._update_gui_state_func("/state/thinking", {"text": "Generating initial thinking process for objective"})
                logger.info("Generating initial thinking process based on objective...")
                await self._update_gui_state_func("/state/operator_status", {"text": "Formulating strategic thinking..."})
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
                    
                    await self._update_gui_state_func("/state/thinking", {"text": "Requesting thinking process from LLM..."})
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
                    await self._update_gui_state_func("/state/operator_status", {"text": "Strategic thinking completed"})

                except Exception as e_think_gen:
                    logger.error(f"Exception during initial thinking process generation: {e_think_gen}", exc_info=True)
                    self.thinking_process_output = f"Exception generating thinking: {e_think_gen}"
                    await self._update_gui_state_func("/state/thinking", {"text": self.thinking_process_output})
                    await self._update_gui_state_func("/state/operator_status", {"text": "Error: Thinking process failed"})
                    
            except Exception as e_init:
                logger.error(f"Error during initial step generation setup: {e_init}", exc_info=True)
                await self._update_gui_state_func("/state/thinking", {"text": f"Error during initialization: {e_init}"})
                await self._update_gui_state_func("/state/operator_status", {"text": f"Error during initialization: {e_init}"})
                return
            
            logger.info("Attempting to generate steps in operate_loop after initial analysis and thinking.")
            await self._update_gui_state_func("/state/operator_status", {"text": "Formulating execution steps..."})
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
                # Update status to show action is being executed
                await self._update_gui_state_func("/state/operator_status", {"text": f"Executing action for step {self.current_step_index + 1}"})
                
                action_type = action_to_execute.get("action_type", "")
                
                # Handle screenshot actions specially - capture and analyze screen
                if action_type == "screenshot":
                    logger.info("Screenshot action requested - capturing and analyzing screen")
                    await self._update_gui_state_func("/state/thinking", {"text": "Screenshot action requested - capturing screen for analysis"})
                    
                    # Capture fresh screenshot
                    screenshot_pil = await asyncio.to_thread(capture_screen_pil)
                    if screenshot_pil:
                        screenshot_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        screenshot_filename = f"automoy_screenshot_action_{screenshot_timestamp}.png"
                        screenshot_path = Path("debug/screenshots") / screenshot_filename
                        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        await asyncio.to_thread(screenshot_pil.save, str(screenshot_path))
                        
                        # Immediately update GUI with screenshot path
                        await self._update_gui_state_func("/state/screenshot", {"path": str(screenshot_path)})
                        
                        # Perform visual analysis and redirect to thinking
                        processed_screenshot_path, analysis_result = await self._perform_visual_analysis(
                            screenshot_path, f"Screenshot action for step {self.current_step_index + 1}"
                        )
                        
                        # If processed screenshot is available, update GUI immediately
                        if processed_screenshot_path:
                            await self._update_gui_state_func("/state/screenshot_processed", {"path": str(processed_screenshot_path)})
                        
                        await self._update_gui_state_func("/state/thinking", {"text": "Screenshot captured and analyzed - information available for next actions"})
                    else:
                        await self._update_gui_state_func("/state/thinking", {"text": "Screenshot capture failed - proceeding to next step"})
                    
                    self.current_step_index += 1
                    continue
                elif action_type == "visual_search":
                    # Handle visual search actions - specifically look for Chrome
                    target = action_to_execute.get("target", "")
                    logger.info(f"Visual search action for: {target}")
                    await self._update_gui_state_func("/state/thinking", {"text": f"Visual search initiated for {target}"})
                    
                    if target == "chrome_icon":
                        # Perform Chrome icon detection
                        chrome_coords = await self._find_chrome_icon_coordinates()
                        if chrome_coords:
                            # Store coordinates for next step to use
                            self.chrome_icon_coordinates = chrome_coords
                            await self._update_gui_state_func("/state/thinking", {"text": f"Chrome icon found at coordinates: {chrome_coords}"})
                            execution_details = f"Chrome icon located at {chrome_coords}"
                        else:
                            await self._update_gui_state_func("/state/thinking", {"text": "Chrome icon not found on current screen"})
                            execution_details = "Chrome icon not detected - may need to show desktop first"
                    else:
                        execution_details = f"Visual search completed for: {target}"
                    
                    self.current_step_index += 1
                    continue
                else:
                    # --- Real action execution ---
                    await self._update_gui_state_func("/state/thinking", {"text": f"Executing action: {action_to_execute.get('type', 'unknown')} - {action_to_execute.get('summary', 'No description')}"})
                    execution_details = self.action_executor.execute(action_to_execute)
                    
                    # Return to desktop anchor after real UI actions (but not after screenshots)
                    if action_type in ["key", "key_sequence", "type", "click"]:
                        await asyncio.sleep(0.5)  # Allow action to complete
                        await self._ensure_desktop_anchor()
                
                logger.info(f"Action execution result: {execution_details}")
                
                # Update thinking with execution result
                await self._update_gui_state_func("/state/thinking", {"text": f"Action completed: {execution_details}"})
                
                # Update current operation status and past operations
                current_operation_summary = f"Step {self.current_step_index + 1}: {action_to_execute.get('description', current_step_description)}"
                await self._update_gui_state_func("/state/last_action_summary", {"summary": execution_details, "status": "success"})
                await self._update_gui_state_func("/state/current_operation", {"text": current_operation_summary})
                await self._update_gui_state_func("/state/past_operation", {"text": f"Completed: {current_operation_summary}"})
                
                self.last_action_summary = execution_details
                self.executed_steps.append({
                    "step_index": self.current_step_index,
                    "description": current_step_description,
                    "action_taken": action_to_execute,
                    "summary": self.last_action_summary,
                    "status": "success"
                })
                self.consecutive_error_count = 0
                self.current_step_index += 1
                
                # --- Process verification for Chrome launch ---
                # Check if this was the final Chrome launch step (step 3) and verify process is running
                if (self.current_step_index == 3 and 
                    hasattr(self, 'original_goal') and 
                    'chrome' in self.original_goal.lower()):
                    
                    logger.info("Chrome launch sequence completed, verifying Chrome process...")
                    await self._update_gui_state_func("/state/thinking", {"text": "Verifying Chrome browser launched successfully..."})
                    
                    # Wait a moment for Chrome to start
                    await asyncio.sleep(2)
                    
                    # Verify Chrome is running
                    chrome_running = await self._verify_process_running("chrome.exe")
                    if chrome_running:
                        await self._update_gui_state_func("/state/current_operation", {"text": "✓ Chrome launched successfully and is running"})
                        await self._update_gui_state_func("/state/thinking", {"text": "✓ Chrome process verified running - goal completed successfully"})
                        logger.info("✓ Chrome process verification successful")
                    else:
                        await self._update_gui_state_func("/state/current_operation", {"text": "⚠ Chrome launch attempt completed but process not detected"})
                        await self._update_gui_state_func("/state/thinking", {"text": "⚠ Chrome process not found - launch may have failed or Chrome may be starting up"})
                        logger.warning("⚠ Chrome process not detected after launch sequence")
                
                # --- Update GUI with completion status ---
                await self._update_gui_state_func("/state/thinking", {"text": f"Step {self.current_step_index} completed successfully, proceeding to next step"})
                await self._update_gui_state_func("/state/operator_status", {"text": f"Completed step {self.current_step_index}"})
                # Add small delay between steps for stability
                await asyncio.sleep(1)
            else:
                # ...existing code for error handling...
                logger.error(f"Failed to get a valid action for step {self.current_step_index + 1}. Stopping operation.")
                await self._update_gui_state_func("/state/thinking", {"text": f"Failed to generate valid action for step {self.current_step_index + 1} - stopping operation"})
                self.last_action_summary = f"Failed to generate action for step: {current_step_description}"
                await self._update_gui_state_func("/state/last_action_summary", {"summary": self.last_action_summary, "status": "error"})
                self.consecutive_error_count +=1
                if self.consecutive_error_count >= self.max_consecutive_errors:
                    logger.error(f"Max consecutive errors ({self.max_consecutive_errors}) reached due to action generation failure. Stopping operation.")
                    await self._update_gui_state_func("/state/thinking", {"text": f"Max consecutive errors reached ({self.max_consecutive_errors}) - operation stopped"})
                    await self._update_gui_state_func("/state/operator_status", {"text": f"Failed: Max errors (action gen) at step {self.current_step_index + 1}"}) # MODIFIED (payload key)
                else:
                     await self._update_gui_state_func("/state/thinking", {"text": f"Action generation error for step {self.current_step_index + 1} - retrying if possible"})
                     await self._update_gui_state_func("/state/operator_status", {"text": f"Error: Failed to get action for step {self.current_step_index + 1}"})
                break
        
        # Check if all steps were completed successfully
        if self.current_step_index >= len(self.steps):
            logger.info("All steps completed successfully!")
            await self._update_gui_state_func("/state/thinking", {"text": "All steps completed successfully! Operation finished."})
            await self._update_gui_state_func("/state/operator_status", {"text": "Completed: All steps executed successfully"})
            await self._update_gui_state_func("/state/current_operation", {"text": f"Operation complete - {len(self.steps)} steps executed"})
        else:
            logger.info(f"Operation stopped at step {self.current_step_index + 1} of {len(self.steps)}")
            await self._update_gui_state_func("/state/thinking", {"text": f"Operation stopped at step {self.current_step_index + 1} of {len(self.steps)} due to errors"})
            await self._update_gui_state_func("/state/current_operation", {"text": f"Operation stopped - {self.current_step_index} of {len(self.steps)} steps completed"})
    
    async def _generate_steps_simple_chrome(self):
        """Generate simple hardcoded steps for opening Chrome via Start menu - fallback only"""
        logger.info("Using simple hardcoded Chrome steps for keyboard shortcut method...")
        
        # Create simple, well-formed steps
        self.steps = [
            {
                "step_number": 1,
                "description": "Press Windows key to open Start menu",
                "action_type": "key",
                "target": "win",
                "verification": "Start menu is visible"
            },
            {
                "step_number": 2,
                "description": "Type 'chrome' to search for Chrome browser",
                "action_type": "type",
                "target": "chrome",
                "verification": "Chrome appears in search results"
            },
            {
                "step_number": 3,
                "description": "Press Enter to launch Chrome",
                "action_type": "key",
                "target": "enter",
                "verification": "Chrome browser window opens"
            }
        ]
        
        # Prepare steps for GUI display
        self.steps_for_gui = [{"description": step["description"]} for step in self.steps]
        
        # Update GUI with generated steps
        await self._update_gui_state_func("/state/steps_generated", {"steps": self.steps_for_gui})
        await self._update_gui_state_func("/state/current_operation", {"text": f"Generated {len(self.steps)} simple steps for Chrome"})
        await self._update_gui_state_func("/state/thinking", {"text": "Using hardcoded Chrome steps: Win key -> type 'chrome' -> Enter"})
        
        logger.info(f"Generated {len(self.steps)} hardcoded steps for Chrome testing")
        return True
    
    async def _generate_steps_chrome_visual(self):
        """Generate steps for Chrome using visual analysis and clicking"""
        logger.info("Generating Chrome steps with visual analysis and clicking...")
        
        # Create steps focused on visual detection and clicking
        self.steps = [
            {
                "step_number": 1,
                "description": "Take screenshot to analyze current desktop state",
                "action_type": "screenshot",
                "target": "desktop_analysis",
                "verification": "Screenshot captured and analyzed"
            },
            {
                "step_number": 2,
                "description": "Show desktop by minimizing all windows to reveal desktop icons",
                "action_type": "special",
                "target": "show_desktop",
                "verification": "Desktop is visible"
            },
            {
                "step_number": 3,
                "description": "Take desktop screenshot for Chrome icon detection",
                "action_type": "screenshot",
                "target": "chrome_detection",
                "verification": "Desktop screenshot captured"
            },
            {
                "step_number": 4,
                "description": "Locate Google Chrome icon using visual analysis",
                "action_type": "visual_search",
                "target": "chrome_icon",
                "verification": "Chrome icon located on screen"
            },
            {
                "step_number": 5,
                "description": "Click on the Chrome icon to launch browser",
                "action_type": "click",
                "target": "chrome_icon_coordinates",
                "verification": "Chrome browser launches"
            }
        ]
        
        # Prepare steps for GUI display
        self.steps_for_gui = [{"description": step["description"]} for step in self.steps]
        
        # Update GUI with generated steps
        await self._update_gui_state_func("/state/steps_generated", {"steps": self.steps_for_gui})
        await self._update_gui_state_func("/state/current_operation", {"text": f"Generated {len(self.steps)} visual steps for Chrome clicking"})
        await self._update_gui_state_func("/state/thinking", {"text": "Using visual analysis steps: Show desktop -> Screenshot -> Find Chrome icon -> Click"})
        
        logger.info(f"Generated {len(self.steps)} visual analysis steps for Chrome clicking")
        return True
    
    async def _verify_process_running(self, process_name):
        """Verify if a process is running by name"""
        try:
            import psutil
            running_processes = []
            for process in psutil.process_iter(['name', 'pid']):
                if process_name.lower() in process.info['name'].lower():
                    running_processes.append(f"{process.info['name']} (PID: {process.info['pid']})")
            
            if running_processes:
                logger.info(f"✓ Process '{process_name}' is running: {', '.join(running_processes)}")
                return True
            else:
                logger.warning(f"✗ Process '{process_name}' is not running")
                return False
        except Exception as e:
            logger.error(f"Error checking process '{process_name}': {e}")
            return False
    
    async def _find_chrome_icon_coordinates(self) -> Optional[Tuple[int, int]]:
        """Find Chrome icon on the screen using visual analysis and return click coordinates."""
        logger.info("Searching for Chrome icon using visual analysis...")
        
        try:
            # Capture current screen
            screenshot_pil = await asyncio.to_thread(capture_screen_pil)
            if not screenshot_pil:
                logger.error("Failed to capture screenshot for Chrome detection")
                return None
            
            # Save screenshot for analysis
            screenshot_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            screenshot_filename = f"chrome_detection_{screenshot_timestamp}.png"
            screenshot_path = Path("debug/screenshots") / screenshot_filename
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            
            await asyncio.to_thread(screenshot_pil.save, str(screenshot_path))
            logger.info(f"Screenshot saved for Chrome detection: {screenshot_path}")
            
            # Perform visual analysis
            if not self.omniparser:
                logger.error("OmniParser not available for Chrome detection")
                return None
            
            await self._update_gui_state_func("/state/thinking", {"text": "Analyzing screenshot to locate Chrome icon..."})
            
            # Use OmniParser to analyze the screenshot
            parsed_result = self.omniparser.parse_screenshot(str(screenshot_path))
            
            if not parsed_result or "parsed_content_list" not in parsed_result:
                logger.warning("No visual elements detected in Chrome icon search")
                return None
            
            elements = parsed_result["parsed_content_list"]
            logger.info(f"Found {len(elements)} elements in Chrome detection analysis")
            
            # Search for Chrome-related elements
            chrome_candidates = []
            for i, element in enumerate(elements):
                text = element.get("content", "").lower()
                element_type = element.get("type", "").lower()
                
                # Look for Chrome-related text or icon types
                chrome_keywords = ["chrome", "google chrome", "google", "browser"]
                if any(keyword in text for keyword in chrome_keywords):
                    chrome_candidates.append((element, i, f"text_match: '{text}'"))
                elif element_type in ["icon", "application", "app"] and "chrome" in str(element).lower():
                    chrome_candidates.append((element, i, f"type_match: {element_type}"))
            
            if not chrome_candidates:
                logger.info("No Chrome icon found in visual analysis")
                await self._update_gui_state_func("/state/thinking", {"text": "No Chrome icon detected in current view - may need to check desktop or taskbar"})
                return None
            
            # Select the best Chrome candidate
            best_candidate = chrome_candidates[0]  # Take the first match for now
            element, element_index, match_reason = best_candidate
            
            logger.info(f"Found Chrome candidate: Element {element_index} - {match_reason}")
            
            # Extract coordinates
            bbox = element.get("bbox_normalized") 
            if bbox and len(bbox) >= 4:
                # Convert normalized coordinates to pixel coordinates
                # Use actual screen dimensions, not screenshot dimensions
                import pyautogui
                screen_width, screen_height = pyautogui.size()
                
                # bbox_normalized is typically [x1, y1, x2, y2] in normalized form (0-1)
                x1, y1, x2, y2 = bbox
                center_x = int((x1 + x2) / 2 * screen_width)
                center_y = int((y1 + y2) / 2 * screen_height)
                
                logger.info(f"Chrome icon coordinates calculated: ({center_x}, {center_y}) [Screen: {screen_width}x{screen_height}]")
                await self._update_gui_state_func("/state/thinking", {"text": f"Chrome icon found at pixel coordinates: ({center_x}, {center_y})"})
                
                return (center_x, center_y)
            else:
                logger.warning("Chrome element found but no valid coordinates available")
               
                return None
                
        except Exception as e:
            logger.error(f"Error during Chrome icon detection: {e}", exc_info=True)
            await self._update_gui_state_func("/state/thinking", {"text": f"Chrome detection error: {str(e)}"})
            return None
