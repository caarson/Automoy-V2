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
from core.lm.lm_interface import MainInterface as LLMInterface, handle_llm_response
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

class OperationParser:
    """Parser for DEFAULT_PROMPT format operations with real execution capabilities."""
    
    def __init__(self, os_interface: OSInterface, desktop_utils: DesktopUtils, manage_gui_window_func=None):
        self.os_interface = os_interface
        self.desktop_utils = desktop_utils
        self.last_visual_analysis = None  # Store last visual analysis for text-based operations
        self.manage_gui_window_func = manage_gui_window_func  # Function to hide/show GUI during screenshots
        
    def set_visual_analysis(self, visual_analysis_data: Optional[Dict[str, Any]]):
        """Set the current visual analysis data for text-based operations."""
        self.last_visual_analysis = visual_analysis_data        
    async def parse_and_execute_operation(self, action_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Parse an operation from DEFAULT_PROMPT format and execute it.
        
        Args:
            action_dict: Dictionary containing operation details from LLM
            
        Returns:
            Tuple of (success: bool, details: str)
        """
        try:
            # Extract operation from action_dict
            if not isinstance(action_dict, dict):
                return False, f"Invalid action format: expected dict, got {type(action_dict)}"
              # Look for operation in various possible formats
            operation = None
            if "operation" in action_dict:
                operation = action_dict["operation"]
            elif "type" in action_dict and action_dict["type"] in ["click", "write", "press", "take_screenshot", "save_screenshot", "open_screenshot", "done"]:
                operation = action_dict["type"]
            else:
                # Try to parse from summary if it contains operation info
                summary = action_dict.get("summary", "")
                if "click" in summary.lower():
                    operation = "click"
                elif "type" in summary.lower() or "write" in summary.lower():
                    operation = "write"
                elif "press" in summary.lower():
                    operation = "press"
                elif "screenshot" in summary.lower():
                    operation = "take_screenshot"
                else:
                    return False, f"Could not identify operation from action: {action_dict}"
            
            logger.info(f"Executing operation: {operation}")
            
            # Execute the operation
            if operation == "click":
                return await self._execute_click(action_dict)
            elif operation == "write":
                return await self._execute_write(action_dict)
            elif operation == "press":
                return await self._execute_press(action_dict)
            elif operation == "take_screenshot":
                return await self._execute_screenshot(action_dict)
            elif operation == "save_screenshot":
                return await self._execute_save_screenshot(action_dict)
            elif operation == "open_screenshot":
                return await self._execute_open_screenshot(action_dict)
            elif operation == "done":
                return await self._execute_done(action_dict)
            else:
                return False, f"Unknown operation: {operation}"
                
        except Exception as e:
            logger.error(f"Error executing operation: {e}", exc_info=True)
            return False, f"Exception during operation execution: {e}"

    async def _execute_click(self, action_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """Execute click operation."""
        try:
            # Look for text-based click first
            if "text" in action_dict:
                text = action_dict["text"].strip()
                logger.info(f"Attempting to click on text: '{text}'")
                
                # Debug: Check if visual analysis data is available
                if self.last_visual_analysis:
                    logger.info(f"Visual analysis data is available, type: {type(self.last_visual_analysis)}")
                    if isinstance(self.last_visual_analysis, dict):
                        logger.debug(f"Visual analysis data keys: {list(self.last_visual_analysis.keys())}")
                    else:
                        logger.warning(f"Visual analysis data is not a dict: {self.last_visual_analysis}")
                else:
                    logger.warning("No visual analysis data available for text-based clicking")
                
                # Try to find coordinates for the text using visual analysis
                if self.last_visual_analysis and isinstance(self.last_visual_analysis, dict):
                    coords = self._find_text_coordinates(text, self.last_visual_analysis)
                    if coords:
                        x, y = coords
                        logger.info(f"Moving mouse to coordinates ({x}, {y}) before clicking")
                        self.os_interface.move_mouse(x, y, duration=0.5)
                        await asyncio.sleep(0.2)  # Brief pause before click
                        logger.info(f"Clicking at coordinates ({x}, {y})")
                        self.os_interface.click_mouse("left")
                        await asyncio.sleep(0.5)  # Wait after click for UI response
                        return True, f"Successfully clicked on text '{text}' at coordinates ({x}, {y})"
                    else:
                        logger.error(f"Could not find coordinates for text: '{text}' in visual analysis data")
                        return False, f"Could not find coordinates for text: '{text}'"
                else:
                    logger.error(f"No valid visual analysis data available for text-based clicking: '{text}'")
                    return False, f"No visual analysis data available for text-based clicking: '{text}'"
            
            # Look for location-based click
            elif "location" in action_dict:
                location = action_dict["location"]
                if isinstance(location, str):
                    # Parse "X Y" format
                    coords = location.strip().split()
                    if len(coords) == 2:
                        try:
                            x, y = int(coords[0]), int(coords[1])
                            self.os_interface.move_mouse(x, y, duration=0.5)
                            await asyncio.sleep(0.2)  # Brief pause before click
                            self.os_interface.click_mouse("left")
                            await asyncio.sleep(0.5)  # Wait after click for UI response
                            return True, f"Successfully clicked at coordinates ({x}, {y})"
                        except ValueError:
                            return False, f"Invalid coordinates format: {location}"
                    else:
                        return False, f"Invalid location format, expected 'X Y': {location}"
                elif isinstance(location, (list, tuple)) and len(location) == 2:
                    x, y = int(location[0]), int(location[1])
                    self.os_interface.move_mouse(x, y, duration=0.5)
                    await asyncio.sleep(0.2)
                    self.os_interface.click_mouse("left")
                    await asyncio.sleep(0.5)
                    return True, f"Successfully clicked at coordinates ({x}, {y})"
                else:
                    return False, f"Invalid location format: {location}"
            
            # Look for coordinates in other fields
            elif "coordinates" in action_dict:
                coords = action_dict["coordinates"]
                if isinstance(coords, (list, tuple)) and len(coords) == 2:
                    x, y = int(coords[0]), int(coords[1])
                    self.os_interface.move_mouse(x, y, duration=0.5)
                    await asyncio.sleep(0.2)
                    self.os_interface.click_mouse("left")
                    await asyncio.sleep(0.5)
                    return True, f"Successfully clicked at coordinates ({x}, {y})"
                else:
                    return False, f"Invalid coordinates format: {coords}"
            
            else:
                return False, "Click operation missing required 'text' or 'location' parameter"
                
        except Exception as e:
            return False, f"Error during click execution: {e}"
    
    def _find_text_coordinates(self, target_text: str, visual_analysis_data: Dict[str, Any]) -> Optional[Tuple[int, int]]:
        """
        Find coordinates for text using visual analysis data.
        
        Args:
            target_text: Text to find coordinates for
            visual_analysis_data: Parsed visual analysis data from OmniParser
            
        Returns:
            Tuple of (x, y) coordinates if found, None otherwise
        """
        try:
            target_lower = target_text.lower().strip()
            logger.info(f"Searching for coordinates of text: '{target_text}' (normalized: '{target_lower}')")
            
            # Debug: Log the structure of visual analysis data
            logger.debug(f"Visual analysis data keys: {list(visual_analysis_data.keys()) if isinstance(visual_analysis_data, dict) else 'Not a dict'}")
            
            # Look for coords data in the visual analysis
            coords_data = visual_analysis_data.get("coords", [])
            if not coords_data:
                logger.warning("No coords data found in visual analysis")
                # Try alternative keys that OmniParser might use
                for alt_key in ["elements", "items", "objects", "text_elements"]:
                    if alt_key in visual_analysis_data:
                        coords_data = visual_analysis_data[alt_key]
                        logger.info(f"Found coordinate data under alternative key: '{alt_key}'")
                        break
                
                if not coords_data:
                    logger.warning(f"No coordinate data found in visual analysis. Available keys: {list(visual_analysis_data.keys())}")
                    return None
            
            logger.info(f"Found {len(coords_data)} elements in coordinate data")
            
            # Search through all detected elements
            best_match = None
            best_match_score = 0
            
            for i, item in enumerate(coords_data):
                if not isinstance(item, dict):
                    logger.debug(f"Skipping non-dict item {i}: {type(item)}")
                    continue
                    
                content = item.get("content", "").lower().strip()
                bbox = item.get("bbox", [])
                  # Log each element for debugging
                logger.debug(f"Element {i}: content='{content}', bbox={bbox}")
                
                # Check if the target text matches or is contained in the content
                if target_lower in content:
                    match_score = len(target_lower) / len(content) if content else 0
                    logger.info(f"Found potential match: '{content}' (score: {match_score:.2f}, bbox: {item.get('bbox', [])})")
                    
                    if match_score > best_match_score:
                        best_match = item
                        best_match_score = match_score
                elif content in target_lower:
                    match_score = len(content) / len(target_lower) if target_lower else 0
                    logger.info(f"Found potential reverse match: '{content}' (score: {match_score:.2f}, bbox: {item.get('bbox', [])})")
                    
                    if match_score > best_match_score:
                        best_match = item
                        best_match_score = match_score
            
            if best_match:
                content = best_match.get("content", "")
                bbox = best_match.get("bbox", [])
                
                if len(bbox) >= 4:
                    # bbox format: [x1, y1, x2, y2] (normalized coordinates 0-1 relative to screenshot)
                    # Calculate center point
                    center_x = (bbox[0] + bbox[2]) / 2
                    center_y = (bbox[1] + bbox[3]) / 2
                    
                    logger.info(f"Raw bbox coordinates: {bbox}")
                    logger.info(f"Calculated center (normalized): ({center_x:.3f}, {center_y:.3f})")
                    
                    # CRITICAL FIX: Get screenshot dimensions instead of screen dimensions
                    # The bbox coordinates are normalized to the screenshot image, not the full screen
                    try:
                        # Try to get screenshot dimensions from the last screenshot file
                        from PIL import Image
                        import pyautogui
                        
                        # Look for the current screenshot file
                        screenshot_files = [
                            Path("automoy_current.png"),
                            Path("gui/static/automoy_current.png"),
                            Path("screenshot.png")
                        ]
                        
                        screenshot_width, screenshot_height = None, None
                        
                        for screenshot_file in screenshot_files:
                            if screenshot_file.exists():
                                try:
                                    with Image.open(screenshot_file) as img:
                                        screenshot_width, screenshot_height = img.size
                                        logger.info(f"Found screenshot dimensions from {screenshot_file}: {screenshot_width}x{screenshot_height}")
                                        break
                                except Exception as e:
                                    logger.debug(f"Could not read {screenshot_file}: {e}")
                        
                        # Fallback to screen dimensions if screenshot not found
                        if screenshot_width is None or screenshot_height is None:
                            logger.warning("Could not find screenshot file, falling back to screen dimensions")
                            screenshot_width, screenshot_height = pyautogui.size()
                        
                        logger.info(f"Using dimensions for coordinate conversion: {screenshot_width}x{screenshot_height}")
                        
                        # Convert normalized coordinates to pixel coordinates
                        pixel_x = int(center_x * screenshot_width)
                        pixel_y = int(center_y * screenshot_height)
                        
                        # Ensure coordinates are within bounds
                        pixel_x = max(0, min(pixel_x, screenshot_width - 1))
                        pixel_y = max(0, min(pixel_y, screenshot_height - 1))
                        
                    except ImportError:
                        logger.error("PIL (Pillow) not available for image dimension reading")
                        # Fallback to screen dimensions
                        import pyautogui
                        screen_width, screen_height = pyautogui.size()
                        pixel_x = int(center_x * screen_width)
                        pixel_y = int(center_y * screen_height)
                        pixel_x = max(0, min(pixel_x, screen_width - 1))
                        pixel_y = max(0, min(pixel_y, screen_height - 1))
                    
                    logger.info(f"Found text '{target_text}' in content '{content}' at normalized ({center_x:.3f}, {center_y:.3f}) -> pixel ({pixel_x}, {pixel_y})")
                    
                    # Additional validation: ensure coordinates are reasonable
                    if pixel_x == 0 and pixel_y == 0:
                        logger.warning(f"Suspicious coordinates (0,0) detected! This might indicate a conversion issue.")
                        logger.warning(f"Original bbox: {bbox}, center: ({center_x:.3f}, {center_y:.3f})")
                        logger.warning(f"Used dimensions: {screenshot_width}x{screenshot_height}")
                        
                        # If we get (0,0), it might be because the normalized coordinates are actually 0
                        # Let's check if the bbox values are truly zero or very small
                        if all(coord < 0.01 for coord in bbox):
                            logger.error(f"Bbox coordinates are too small/zero: {bbox}. This indicates an issue with visual analysis.")
                            return None
                    
                    return (pixel_x, pixel_y)
                else:
                    logger.warning(f"Best match found but bbox has insufficient coordinates: {bbox}")
            
            logger.warning(f"Text '{target_text}' not found in visual analysis data. Searched through {len(coords_data)} elements.")
            return None
            
        except Exception as e:
            logger.error(f"Error finding text coordinates: {e}", exc_info=True)
            return None
    
    async def _execute_write(self, action_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """Execute write/type operation."""
        try:
            text = action_dict.get("text", "")
            if not text:
                return False, "Write operation missing required 'text' parameter"
            
            logger.info(f"Typing text: '{text}'")
            # Small delay before typing
            await asyncio.sleep(0.3)
            self.os_interface.type_text(text)
            
            # Dynamic wait time based on text length
            wait_time = max(0.5, len(text) * 0.02)  # Minimum 0.5s, scale with text length
            await asyncio.sleep(wait_time)
            
            return True, f"Successfully typed text: '{text}'"
            
        except Exception as e:
            return False, f"Error during write execution: {e}"
    
    async def _execute_press(self, action_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """Execute key press operation."""
        try:
            keys = action_dict.get("keys", [])
            if not keys:
                return False, "Press operation missing required 'keys' parameter"
            
            logger.info(f"Pressing keys: {keys}")
            
            # Small delay before key press
            await asyncio.sleep(0.2)
            
            if isinstance(keys, list):
                # Multiple keys (hotkey combination)
                self.os_interface.hotkey(*keys)
                key_description = " + ".join(keys)
            else:
                # Single key
                self.os_interface.press(keys)
                key_description = str(keys)
              # Wait for system to process the key press
            await asyncio.sleep(0.8)
            return True, f"Successfully pressed: {key_description}"
            
        except Exception as e:
            return False, f"Error during key press execution: {e}"
    
    async def _execute_screenshot(self, action_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """Execute screenshot operation."""
        try:
            logger.info("Taking screenshot")
            
            # Hide GUI window before taking screenshot to avoid interference
            if self.manage_gui_window_func:
                logger.debug("Hiding GUI window before screenshot")
                await self.manage_gui_window_func("hide")
                await asyncio.sleep(0.5)  # Wait for GUI to hide
            
            # Take screenshot using desktop_utils
            screenshot_path = self.desktop_utils.capture_current_screen(
                filename_prefix="automoy_operation_screenshot"
            )
            
            # Show GUI window again after screenshot
            if self.manage_gui_window_func:
                logger.debug("Showing GUI window after screenshot")
                await self.manage_gui_window_func("show")
                await asyncio.sleep(0.3)  # Brief wait for GUI to show
            
            if screenshot_path and screenshot_path.exists():
                return True, f"Successfully captured screenshot: {screenshot_path}"
            else:
                return False, "Failed to capture screenshot"
                
        except Exception as e:
            # Ensure GUI is shown again even if there's an error
            if self.manage_gui_window_func:
                try:
                    await self.manage_gui_window_func("show")
                except Exception as gui_error:
                    logger.error(f"Failed to show GUI after screenshot error: {gui_error}")
            return False, f"Error during screenshot execution: {e}"
    
    async def _execute_save_screenshot(self, action_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """Execute save screenshot operation."""
        try:
            name = action_dict.get("name", "saved_screenshot")
            logger.info(f"Saving screenshot with name: {name}")
            
            # Take screenshot with specified name
            screenshot_path = self.desktop_utils.capture_current_screen(
                filename_prefix=f"automoy_saved_{name}"
            )
            
            if screenshot_path and screenshot_path.exists():
                return True, f"Successfully saved screenshot as: {screenshot_path}"
            else:
                return False, f"Failed to save screenshot with name: {name}"
                
        except Exception as e:
            return False, f"Error during save screenshot execution: {e}"
    
    async def _execute_open_screenshot(self, action_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """Execute open screenshot operation."""
        try:
            name = action_dict.get("name") or action_dict.get("named")
            if not name:
                return False, "Open screenshot operation missing required 'name' or 'named' parameter"
            
            logger.info(f"Opening screenshot: {name}")
            # This would involve finding and opening a previously saved screenshot
            # For now, just acknowledge the request
            return True, f"Screenshot open requested for: {name} (feature pending implementation)"
            
        except Exception as e:
            return False, f"Error during open screenshot execution: {e}"
    
    async def _execute_done(self, action_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """Execute done operation."""
        try:
            summary = action_dict.get("summary", "Task completed")
            logger.info(f"Task completion: {summary}")
            return True, f"Task marked as complete: {summary}"
            
        except Exception as e:
            return False, f"Error during done execution: {e}"
    
    def get_operation_wait_time(self, operation: str) -> float:
        """
        Get dynamic wait time based on operation type.
        
        Args:
            operation: The type of operation performed
            
        Returns:
            Wait time in seconds
        """
        wait_times = {
            "click": 1.0,           # UI elements need time to respond
            "write": 0.5,           # Text input is usually fast
            "press": 1.2,           # Key combinations might trigger complex actions
            "take_screenshot": 0.5, # Screenshots are immediate
            "save_screenshot": 0.5, # Save operations are quick
            "open_screenshot": 0.8, # File operations might take time
            "done": 0.1,            # Task completion is immediate
        }
        return wait_times.get(operation, 1.0)  # Default 1 second

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
        self.os_interface = OSInterface()  # Initialize OS interface for real operations
        self.operation_parser = OperationParser(self.os_interface, self.desktop_utils, manage_gui_window_func)  # Initialize operation parser with GUI management

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
        
        self.anchor_point_context: Optional[str] = None  # For anchor point context in prompts
        
        self.session_id = f"automoy-op-{int(time.time())}"
        logger.info(f"AutomoyOperator initialized with session ID: {self.session_id}")
        logger.info(f"Objective: {self.objective}")
        # Log omniparser type
        logger.debug(f"OmniParser interface type: {type(self.omniparser)}")
        if not hasattr(self.omniparser, 'get_analysis'):
            logger.error("OmniParser interface does not have 'get_analysis' method!")            # Potentially raise an error or handle this state
            # For now, logging it. This could be a source of issues if not addressed.
    
    async def _perform_visual_analysis(self, screenshot_path: Path, task_context: str) -> Tuple[Optional[Path], Optional[str], Optional[Dict[str, Any]]]:
        """
        Perform visual analysis on the screenshot using OmniParser and process through LLM.
        Returns the processed screenshot path, the visual analysis text output, and raw parsed data.
        """
        logger.info(f"Performing visual analysis for task: {task_context} on screenshot: {screenshot_path}")
        await self._update_gui_state_func("/state/current_operation", {"text": f"Performing visual analysis for: {task_context[:50]}..."})
        
        processed_screenshot_path: Optional[Path] = None
        analysis_results_text: Optional[str] = None
        parsed_data: Optional[Dict[str, Any]] = None
        try:
            # Ensure omniparser is available and has the parse_screenshot method
            if not self.omniparser or not hasattr(self.omniparser, 'parse_screenshot'):
                logger.error("OmniParser is not available or misconfigured (missing 'parse_screenshot').")
                await self._update_gui_state_func("/state/visual", {"text": "Error: OmniParser not available or misconfigured."})
                return None, None, None

            logger.info(f"Calling omniparser.parse_screenshot for {screenshot_path}")
            parsed_data = self.omniparser.parse_screenshot(str(screenshot_path))

            if not parsed_data:
                logger.error("OmniParser failed to parse screenshot or returned no data.")
                await self._update_gui_state_func("/state/visual", {"text": "Error: OmniParser failed to process screenshot."})
                return None, None, None# Convert parsed data to formatted string for LLM input
            if isinstance(parsed_data, dict):
                screenshot_elements = json.dumps(parsed_data, indent=2)
            else:
                screenshot_elements = str(parsed_data)
            
            logger.debug(f"Raw OmniParser output (first 500 chars): {screenshot_elements[:500]}...")
            
            # Process through LLM for visual analysis
            try:
                from core.prompts.prompts import VISUAL_ANALYSIS_SYSTEM_PROMPT, VISUAL_ANALYSIS_USER_PROMPT_TEMPLATE
                
                visual_prompt = VISUAL_ANALYSIS_USER_PROMPT_TEMPLATE.format(
                    objective=task_context,
                    screenshot_elements=screenshot_elements
                )
                
                logger.info("Sending visual analysis request to LLM...")
                
                # Create messages for LLM request
                messages = [
                    {"role": "system", "content": VISUAL_ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": visual_prompt}
                ]
                
                # Use the correct method from MainInterface
                raw_response, thinking_output, error = await self.llm_interface.get_llm_response(
                    model=self.llm_interface.config.get_model(),
                    messages=messages,
                    objective=task_context,
                    session_id="visual_analysis",
                    response_format_type="default"
                )
                
                if error:
                    visual_analysis_response = None
                    logger.error(f"Visual analysis LLM request failed: {error}")
                else:
                    # Process the raw response to remove <think> tags and clean it
                    visual_analysis_response = handle_llm_response(
                        raw_response, 
                        "visual_analysis", 
                        is_json=False
                    )
                
                if visual_analysis_response and visual_analysis_response.strip():
                    analysis_results_text = visual_analysis_response.strip()
                    logger.info(f"Visual analysis completed successfully: {analysis_results_text[:200]}...")
                else:
                    analysis_results_text = "Visual analysis completed but no response from LLM."
                    logger.warning("LLM returned empty response for visual analysis.")
                    
            except Exception as e_llm:
                logger.error(f"Error during LLM visual analysis: {e_llm}", exc_info=True)
                analysis_results_text = f"Error during LLM visual analysis: {str(e_llm)}"
            
            # Handle processed screenshot path
            internal_processed_path = OPERATE_PY_PROJECT_ROOT / PROCESSED_SCREENSHOT_RELATIVE_PATH
            if internal_processed_path.exists():
                processed_screenshot_path = internal_processed_path
                logger.info(f"Processed screenshot available at: {processed_screenshot_path}")
                # Notify GUI that the processed screenshot (expected at gui/static/processed_screenshot.png) is ready
                logger.debug(f"Updating GUI about processed screenshot being ready (expected at /static/processed_screenshot.png)")
                await self._update_gui_state_func("/state/screenshot_processed", {})
            else:
                logger.warning(f"Processed screenshot not found at expected internal path: {internal_processed_path}. GUI might not show it.")
                # Attempt to check the static path directly as a fallback for logging
                gui_static_processed_path = OPERATE_PY_PROJECT_ROOT.parent / "gui" / "static" / "processed_screenshot.png"
                if gui_static_processed_path.exists():
                    logger.info(f"Processed screenshot IS present in GUI static folder: {gui_static_processed_path}")
                    await self._update_gui_state_func("/state/screenshot_processed", {})
                else:
                    logger.warning(f"Processed screenshot also not found in GUI static folder: {gui_static_processed_path}. Using original screenshot path as fallback for processed path.")
                processed_screenshot_path = screenshot_path # Fallback
            
            logger.debug(f"Processed visual analysis text: {analysis_results_text}")
            await self._update_gui_state_func("/state/visual", {"text": analysis_results_text or "No visual analysis generated."})
            self.visual_analysis_output = analysis_results_text # Store it
            return processed_screenshot_path, analysis_results_text, parsed_data

        except Exception as e:
            logger.error(f"Error during visual analysis: {e}", exc_info=True)
            await self._update_gui_state_func("/state/visual", {"text": f"Error in visual analysis: {e}"})
            self.visual_analysis_output = None # Clear on error
            return None, None, None

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
                thinking_process_output=self.thinking_process_output or "No prior thinking process output available for step generation.",                previous_steps_output="N/A", # Assuming this is for initial generation
                anchor_point_context=getattr(self, 'anchor_point_context', None)
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
            
            steps_json_str = handle_llm_response(raw_llm_response, "step_generation", is_json=True)
            logger.info(f"DEBUG - _generate_steps - Raw LLM response (first 500 chars): {raw_llm_response[:500] if raw_llm_response else 'None'}")
            logger.info(f"DEBUG - _generate_steps - Processed steps_json_str type: {type(steps_json_str)}")
            logger.info(f"DEBUG - _generate_steps - Processed steps_json_str content: {str(steps_json_str)[:500] if steps_json_str else 'None'}")
            
            if not steps_json_str:
                logger.warning("handle_llm_response returned None or empty for steps_json_str.")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "Failed to parse LLM step response."})
                return
                
            # Check if handle_llm_response returned an error dict
            if isinstance(steps_json_str, dict) and "error" in steps_json_str:
                logger.error(f"handle_llm_response returned error: {steps_json_str}")
                await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": f"JSON parsing error: {steps_json_str.get('message', 'Unknown error')}"})
                return
                  
            try:
                # Handle case where handle_llm_response already parsed the JSON (when is_json=True)
                if isinstance(steps_json_str, (list, dict)):
                    parsed_steps_data = steps_json_str
                    logger.info(f"DEBUG - _generate_steps - handle_llm_response already returned parsed data")
                else:
                    # Fallback: if it's still a string, parse it manually
                    parsed_steps_data = json.loads(steps_json_str)
                    logger.info(f"DEBUG - _generate_steps - Manually parsed JSON from string")
                    
                logger.info(f"DEBUG - _generate_steps - Parsed steps data: {parsed_steps_data}")
                logger.info(f"DEBUG - _generate_steps - Parsed steps data type: {type(parsed_steps_data)}")
                logger.info(f"DEBUG - _generate_steps - Is dict? {isinstance(parsed_steps_data, dict)}")
                logger.info(f"DEBUG - _generate_steps - Is list? {isinstance(parsed_steps_data, list)}")
                  
                if isinstance(parsed_steps_data, dict) and "steps" in parsed_steps_data and isinstance(parsed_steps_data["steps"], list):
                    self.steps = parsed_steps_data["steps"]
                    # Prepare steps for GUI (e.g., just descriptions)
                    self.steps_for_gui = [{"description": step.get("description", "No description")} for step in self.steps]
                    logger.info(f"DEBUG - _generate_steps - Steps extracted from dict format: {len(self.steps)} steps")
                    logger.info(f"DEBUG - _generate_steps - self.steps after dict parsing: {self.steps}")
                elif isinstance(parsed_steps_data, list): # If LLM directly returns a list of steps
                    self.steps = parsed_steps_data
                    self.steps_for_gui = [{"description": step.get("description", "No description")} for step in self.steps]
                    logger.info(f"DEBUG - _generate_steps - Steps extracted from list format: {len(self.steps)} steps")
                    logger.info(f"DEBUG - _generate_steps - self.steps after list parsing: {self.steps}")
                else:
                    logger.warning(f"DEBUG - _generate_steps - Parsed steps JSON is not in expected format: {steps_json_str}")
                    logger.warning(f"DEBUG - _generate_steps - Parsed data type: {type(parsed_steps_data)}")
                    logger.warning(f"DEBUG - _generate_steps - Parsed data content: {parsed_steps_data}")
                    await self._update_gui_state_func("/state/steps_generated", {"steps": [], "error": "LLM step response has incorrect format."})
                    return

                if self.steps:
                    logger.info(f"DEBUG - _generate_steps - Final steps count: {len(self.steps)}")
                    logger.info(f"DEBUG - _generate_steps - Final self.steps: {self.steps}")
                    logger.info(f"DEBUG - _generate_steps - Final self.steps_for_gui: {self.steps_for_gui}")
                    logger.info(f"Generated {len(self.steps)} steps.")
                    await self._update_gui_state_func("/state/steps_generated", {"steps": self.steps_for_gui}) # Send descriptions
                else:
                    logger.warning("DEBUG - _generate_steps - LLM did not generate any steps (parsed list was empty).")
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

            self.current_processed_screenshot_path, self.visual_analysis_output, parsed_visual_data = await self._perform_visual_analysis(
                screenshot_path=self.current_screenshot_path,
                task_context=f"Current step: {current_step_description}"
            )
            
            # Pass visual analysis data to OperationParser for text-based operations
            if parsed_visual_data:
                self.operation_parser.set_visual_analysis(parsed_visual_data)
                logger.debug("Visual analysis data passed to OperationParser")
            else:
                logger.warning("No visual analysis data to pass to OperationParser")
            
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
                    current_retry_count=step_retry_count,
                    anchor_point_context=getattr(self, 'anchor_point_context', None)
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
                        "thinking_process": self.thinking_process_output or f"LLM Error: {llm_error}"                    })
                    step_retry_count += 1
                    await asyncio.sleep(1)
                    continue

                if not raw_llm_response:
                    logger.warning("LLM returned no response for action generation.")
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "info", "summary": "LLM provided no action this attempt."}],
                        "thinking_process": self.thinking_process_output or "LLM gave empty response."                    })
                    step_retry_count += 1
                    await asyncio.sleep(1) 
                    continue
                
                action_json_str = handle_llm_response(raw_llm_response, "action_generation", is_json=True)
                logger.debug(f"Raw LLM response for action generation (first 500 chars): {raw_llm_response[:500] if raw_llm_response else 'None'}")
                logger.debug(f"Processed action_json_str type: {type(action_json_str)}")
                logger.debug(f"Processed action_json_str content: {str(action_json_str)[:500] if action_json_str else 'None'}")

                if not action_json_str:
                    logger.warning("handle_llm_response returned None or empty for action_json_str.")
                    await self._update_gui_state_func("/state/operations_generated", {
                        "operations": [{"type": "warning", "summary": "Failed to parse LLM action response."}],
                        "thinking_process": self.thinking_process_output or "Could not parse LLM action."
                    })
                    step_retry_count += 1
                    await asyncio.sleep(1)
                    continue

                # Check if handle_llm_response returned an error dict
                if isinstance(action_json_str, dict) and "error" in action_json_str:
                    logger.error(f"handle_llm_response returned error: {action_json_str}")
                    await self._update_gui_state_func("/state/operations_generated", {                        "operations": [{"type": "error", "summary": f"JSON parsing error: {action_json_str.get('message', 'Unknown error')}"}],
                        "thinking_process": self.thinking_process_output or f"JSON Error: {action_json_str.get('message', 'Unknown error')}"
                    })
                    step_retry_count += 1
                    await asyncio.sleep(1)
                    continue
                
                try:
                    # Handle case where handle_llm_response already parsed the JSON (when is_json=True)
                    if isinstance(action_json_str, (list, dict)):
                        parsed_action = action_json_str
                        logger.info(f"DEBUG - _get_action_for_current_step - handle_llm_response already returned parsed data")
                    else:
                        parsed_action = json.loads(action_json_str)
                    
                    # Handle case where LLM returns an array of actions - take the first one
                    if isinstance(parsed_action, list) and len(parsed_action) > 0:
                        logger.info(f"LLM returned array of actions, taking first: {parsed_action}")
                        parsed_action = parsed_action[0]
                    elif isinstance(parsed_action, list) and len(parsed_action) == 0:
                        logger.warning("LLM returned empty array of actions")
                        await self._update_gui_state_func("/state/operations_generated", {
                            "operations": [{"type": "error", "summary": "LLM returned empty action array."}],
                            "thinking_process": self.thinking_process_output or "Empty action array from LLM."
                        })
                        step_retry_count += 1
                        await asyncio.sleep(1)
                        continue
                        
                    # Check for the new format with "operation" field (used by OperationParser)
                    if isinstance(parsed_action, dict) and "operation" in parsed_action:
                        action_to_execute = parsed_action 
                        self.operations_generated_for_gui = [action_to_execute]
                        logger.info(f"Action proposed by LLM: {action_to_execute}")
                        await self._update_gui_state_func("/state/operations_generated", {
                            "operations": self.operations_generated_for_gui,
                            "thinking_process": self.thinking_process_output or "N/A"
                        })
                        break 
                    # Also check for legacy format with "type" and "summary" fields for backward compatibility
                    elif isinstance(parsed_action, dict) and "type" in parsed_action and "summary" in parsed_action:
                        action_to_execute = parsed_action 
                        self.operations_generated_for_gui = [action_to_execute]
                        logger.info(f"Action proposed by LLM (legacy format): {action_to_execute}")
                        await self._update_gui_state_func("/state/operations_generated", {
                            "operations": self.operations_generated_for_gui,
                            "thinking_process": self.thinking_process_output or "N/A"
                        })
                        break 
                    else:
                        logger.warning(f"Parsed action JSON is not in the expected format: {action_json_str}")
                        logger.warning(f"Expected dict with 'operation' field, got: {type(parsed_action)}, keys: {list(parsed_action.keys()) if isinstance(parsed_action, dict) else 'N/A'}")
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

    async def _apply_anchor_point_configuration(self):
        """Apply anchor point configuration based on environment settings."""
        logger.info("Checking anchor point configuration...")
        
        try:
            # Check if DESKTOP_ANCHOR_POINT is enabled in environment.txt
            desktop_anchor_enabled = self.config.get_env("DESKTOP_ANCHOR_POINT", False)
            prompt_anchor_enabled = self.config.get_env("PROMPT_ANCHOR_POINT", False) 
            
            if desktop_anchor_enabled:
                logger.info("Desktop anchor point is enabled. Applying desktop anchor point...")
                await self._update_gui_state_func("/state/operator_status", {"text": "Applying desktop anchor point..."})
                
                # Import and use the desktop anchor point functionality
                from core.environmental.anchor.desktop_anchor_point import show_desktop
                
                try:
                    show_desktop()
                    logger.info("Desktop anchor point applied successfully - all windows minimized")
                    await self._update_gui_state_func("/state/operator_status", {"text": "Desktop anchor point applied"})
                    
                    # Add anchor point context to prompts
                    self._add_anchor_point_context("desktop")
                    
                    # Wait a moment for the desktop to settle
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Failed to apply desktop anchor point: {e}")
                    await self._update_gui_state_func("/state/operator_status", {"text": f"Desktop anchor point failed: {e}"})
            
            elif prompt_anchor_enabled:
                logger.info("Prompt anchor point is enabled. Adding prompt context...")
                await self._update_gui_state_func("/state/operator_status", {"text": "Applying prompt anchor point..."})
                
                # Get the prompt context from configuration
                prompt_context = self.config.get_env("PROMPT", "")
                if prompt_context:
                    self._add_anchor_point_context("prompt", prompt_context)
                    logger.info(f"Prompt anchor point context added: {prompt_context[:100]}...")
                    await self._update_gui_state_func("/state/operator_status", {"text": "Prompt anchor point context added"})
                else:
                    logger.warning("Prompt anchor point enabled but no PROMPT context found in configuration")
                    await self._update_gui_state_func("/state/operator_status", {"text": "Prompt anchor point enabled but no context found"})
            
            else:
                logger.info("No anchor point configuration enabled. Proceeding without anchor point.")
                await self._update_gui_state_func("/state/operator_status", {"text": "No anchor point applied"})
                
        except Exception as e:
            logger.error(f"Error in anchor point configuration: {e}", exc_info=True)
            await self._update_gui_state_func("/state/operator_status", {"text": f"Anchor point error: {e}"})

    def _add_anchor_point_context(self, anchor_type: str, custom_context: str = None):
        """Add anchor point context that will be included in LLM prompts."""
        if anchor_type == "desktop":
            self.anchor_point_context = (
                "ANCHOR POINT CONTEXT: You are starting from the Windows desktop. "
                "All windows have been minimized and the desktop is clean. "
                "The taskbar is visible at the bottom with minimized applications. "
                "This is your starting point for all operations."
            )
            logger.info("Desktop anchor point context added to prompts")
        elif anchor_type == "prompt" and custom_context:
            self.anchor_point_context = f"ANCHOR POINT CONTEXT: {custom_context.strip()}"
            logger.info("Custom prompt anchor point context added to prompts")
        else:
            self.anchor_point_context = None
            logger.info("No anchor point context set")

    async def operate_loop(self):
        logger.info("AutomoyOperator.operate_loop started.")
        await self._update_gui_state_func("/state/operator_status", {"text": "Starting Operator..."}) # MODIFIED (payload key)
        
        # Check and apply anchor point configuration before taking any screenshots
        await self._apply_anchor_point_configuration()
        
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
                    self.current_processed_screenshot_path, visual_analysis_json, parsed_visual_data = await self._perform_visual_analysis(
                        screenshot_path=screenshot_path_obj,
                        task_context=self.objective 
                    )
                    
                    # Pass initial visual analysis data to OperationParser
                    if parsed_visual_data:
                        self.operation_parser.set_visual_analysis(parsed_visual_data)
                        logger.debug("Initial visual analysis data passed to OperationParser")
                    
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
                        previous_action_summary="N/A (Initial planning)",
                        anchor_point_context=getattr(self, 'anchor_point_context', None)
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
                        # Process the thinking output to remove <think> tags
                        self.thinking_process_output = handle_llm_response(
                            thinking_output_think, 
                            "thinking_process", 
                            is_json=False
                        )
                        logger.info(f"Initial thinking process generated: {self.thinking_process_output[:200]}...")
                    elif raw_llm_response_think: 
                        # Process the raw response to remove <think> tags
                        self.thinking_process_output = handle_llm_response(
                            raw_llm_response_think, 
                            "thinking_process", 
                            is_json=False
                        )
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

            logger.info(f"DEBUG - operate_loop - Steps generation completed")
            logger.info(f"DEBUG - operate_loop - self.steps type: {type(self.steps)}")
            logger.info(f"DEBUG - operate_loop - self.steps length: {len(self.steps) if self.steps else 0}")
            logger.info(f"DEBUG - operate_loop - self.steps content: {self.steps}")
            logger.info(f"DEBUG - operate_loop - self.steps_for_gui type: {type(self.steps_for_gui)}")
            logger.info(f"DEBUG - operate_loop - self.steps_for_gui length: {len(self.steps_for_gui) if self.steps_for_gui else 0}")
            logger.info(f"DEBUG - operate_loop - self.steps_for_gui content: {self.steps_for_gui}")

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

        logger.info(f"DEBUG - operate_loop - Before execution loop:")
        logger.info(f"DEBUG - operate_loop - self.current_step_index: {self.current_step_index}")
        logger.info(f"DEBUG - operate_loop - len(self.steps): {len(self.steps) if self.steps else 'self.steps is None'}")
        logger.info(f"DEBUG - operate_loop - Loop condition (self.current_step_index < len(self.steps)): {self.current_step_index < len(self.steps) if self.steps else 'Cannot evaluate - self.steps is None'}")
        logger.info(f"DEBUG - operate_loop - About to enter while loop")
        
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
            
            # Update current operation display with comprehensive info
            current_op_info = f"Step {self.current_step_index + 1}/{len(self.steps)}: {current_step_description}"
            if hasattr(self, 'thinking_process_output') and self.thinking_process_output:
                current_op_info += f" | Thinking: {self.thinking_process_output[:50]}..."
            await self._update_gui_state_func("/state/current_operation", {"text": current_op_info})
            
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
                
                # Real execution using the initialized OperationParser
                success, execution_details = await self.operation_parser.parse_and_execute_operation(action_to_execute)
                  # Get dynamic wait time based on operation type
                operation_type = action_to_execute.get("operation") or action_to_execute.get("type", "unknown")
                wait_time = self.operation_parser.get_operation_wait_time(operation_type)
                
                if success:
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
                    
                    # Update past operation display with comprehensive info
                    past_op_info = f"Completed Step {self.current_step_index + 1}: {current_step_description} | Result: {self.last_action_summary}"
                    await self._update_gui_state_func("/state/last_action_result", {"text": past_op_info})
                    
                    self.consecutive_error_count = 0 # Reset error count on success
                    
                    # Apply dynamic wait time based on operation type
                    logger.info(f"Applying {wait_time}s wait time for {operation_type} operation")
                    await asyncio.sleep(wait_time)
                    
                    self.current_step_index += 1 # Move to next step                else:
                    # Handle action execution failure
                    self.last_action_summary = f"Failed to execute operation: {execution_details}"
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
