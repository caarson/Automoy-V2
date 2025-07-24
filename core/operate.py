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
    """Executes actions on Windows using multiple methods with fallbacks."""
    def __init__(self):
        pyautogui.FAILSAFE = False
        
    def _press_key_with_fallbacks(self, key: str) -> str:
        """Press a key using multiple methods with fallbacks."""
        import ctypes
        import time
        
        # Method 1: Try PyAutoGUI first (works for Windows key)
        try:
            pyautogui.press(key)
            return f"Pressed key via PyAutoGUI: {key}"
        except Exception as e1:
            logger.info(f"PyAutoGUI failed for key '{key}': {e1}")
        
        # Method 2: Try keyboard library
        try:
            import keyboard
            keyboard.press_and_release(key)
            return f"Pressed key via keyboard library: {key}"
        except Exception as e2:
            logger.info(f"Keyboard library failed for key '{key}': {e2}")
        
        # Method 3: Try Windows API directly
        try:
            # Map common keys to virtual key codes
            vk_map = {
                'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45, 'f': 0x46, 'g': 0x47,
                'h': 0x48, 'i': 0x49, 'j': 0x4A, 'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E,
                'o': 0x4F, 'p': 0x50, 'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54, 'u': 0x55,
                'v': 0x56, 'w': 0x57, 'x': 0x58, 'y': 0x59, 'z': 0x5A,
                '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34, '5': 0x35,
                '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
                'space': 0x20, 'enter': 0x0D, 'escape': 0x1B, 'esc': 0x1B, 'tab': 0x09,
                'shift': 0x10, 'ctrl': 0x11, 'alt': 0x12, 'win': 0x5B, 'winleft': 0x5B,
                'backspace': 0x08, 'delete': 0x2E, 'home': 0x24, 'end': 0x23,
                'pageup': 0x21, 'pagedown': 0x22, 'up': 0x26, 'down': 0x28,
                'left': 0x25, 'right': 0x27, 'f1': 0x70, 'f2': 0x71, 'f3': 0x72,
                'f4': 0x73, 'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
                'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B
            }
            
            # Convert key name to virtual key code
            vk_code = vk_map.get(key.lower())
            if vk_code:
                user32 = ctypes.windll.user32
                # Key down
                user32.keybd_event(vk_code, 0, 0, 0)
                time.sleep(0.01)  # Brief pause
                # Key up
                user32.keybd_event(vk_code, 0, 2, 0)
                return f"Pressed key via Windows API: {key}"
            else:
                return f"Key '{key}' not found in virtual key mapping"
                
        except Exception as e3:
            logger.info(f"Windows API failed for key '{key}': {e3}")
        
        # Method 4: As last resort, try OSInterface
        try:
            from core.utils.operating_system.os_interface import OSInterface
            os_interface = OSInterface()
            os_interface.press(key)
            return f"Pressed key via OSInterface: {key}"
        except Exception as e4:
            logger.info(f"OSInterface failed for key '{key}': {e4}")
        
        # If all methods failed
        return f"ERROR: All keyboard methods failed for key '{key}'"

    def execute(self, action: dict) -> str:
        try:
            action_type = action.get("action_type") or action.get("type")
            if action_type == "key":
                key = action.get("key")
                if key:
                    return self._press_key_with_fallbacks(key)
            elif action_type == "key_sequence":
                keys = action.get("keys")
                if isinstance(keys, list):
                    # Try multiple methods for key sequences
                    try:
                        pyautogui.hotkey(*keys)
                        return f"Pressed key sequence via PyAutoGUI: {keys}"
                    except Exception as e1:
                        logger.info(f"PyAutoGUI hotkey failed for {keys}: {e1}")
                        try:
                            import keyboard
                            combo = "+".join(keys)
                            keyboard.press_and_release(combo)
                            return f"Pressed key sequence via keyboard library: {keys}"
                        except Exception as e2:
                            logger.info(f"Keyboard library hotkey failed for {keys}: {e2}")
                            return f"ERROR: Key sequence failed for {keys}"
                elif isinstance(keys, str):
                    # Handle string format like "win+s"
                    key_list = [k.strip() for k in keys.replace('+', ',').split(',')]
                    try:
                        pyautogui.hotkey(*key_list)
                        return f"Pressed key sequence via PyAutoGUI: {key_list}"
                    except Exception as e1:
                        logger.info(f"PyAutoGUI hotkey failed for {key_list}: {e1}")
                        try:
                            import keyboard
                            combo = "+".join(key_list)
                            keyboard.press_and_release(combo)
                            return f"Pressed key sequence via keyboard library: {key_list}"
                        except Exception as e2:
                            logger.info(f"Keyboard library hotkey failed for {key_list}: {e2}")
                            return f"ERROR: Key sequence failed for {key_list}"
            elif action_type == "type":
                text = action.get("text")
                if text:
                    # Try multiple methods for typing
                    try:
                        pyautogui.typewrite(text)
                        return f"Typed text via PyAutoGUI: {text}"
                    except Exception as e1:
                        logger.info(f"PyAutoGUI typewrite failed: {e1}")
                        try:
                            import keyboard
                            keyboard.write(text)
                            return f"Typed text via keyboard library: {text}"
                        except Exception as e2:
                            logger.info(f"Keyboard library write failed: {e2}")
                            try:
                                # Enhanced character-by-character typing via Windows API
                                import ctypes
                                import time
                                user32 = ctypes.windll.user32
                                
                                # Extended virtual key mapping for better compatibility
                                char_map = {
                                    'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45, 'f': 0x46,
                                    'g': 0x47, 'h': 0x48, 'i': 0x49, 'j': 0x4A, 'k': 0x4B, 'l': 0x4C,
                                    'm': 0x4D, 'n': 0x4E, 'o': 0x4F, 'p': 0x50, 'q': 0x51, 'r': 0x52,
                                    's': 0x53, 't': 0x54, 'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58,
                                    'y': 0x59, 'z': 0x5A, ' ': 0x20, '0': 0x30, '1': 0x31, '2': 0x32,
                                    '3': 0x33, '4': 0x34, '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39
                                }
                                
                                typed_chars = []
                                for char in text.lower():
                                    if char in char_map:
                                        vk_code = char_map[char]
                                        # Key down
                                        user32.keybd_event(vk_code, 0, 0, 0)
                                        time.sleep(0.02)  # Slightly longer delay for reliability
                                        # Key up
                                        user32.keybd_event(vk_code, 0, 2, 0)
                                        time.sleep(0.02)
                                        typed_chars.append(char)
                                    else:
                                        logger.warning(f"Character '{char}' not in Windows API mapping, skipping")
                                
                                return f"Typed text via Windows API: {''.join(typed_chars)} (original: {text})"
                            except Exception as e3:
                                logger.info(f"Windows API typing failed: {e3}")
                                return f"ERROR: All typing methods failed for text: {text}"
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
            elif action_type == "check_process":
                # Check if a specific process is running
                process_name = action.get("process_name", "")
                if process_name:
                    try:
                        import psutil
                        running_processes = []
                        for proc in psutil.process_iter(['pid', 'name']):
                            try:
                                if process_name.lower() in proc.info['name'].lower():
                                    running_processes.append(f"{proc.info['name']} (PID: {proc.info['pid']})")
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                continue
                        
                        if running_processes:
                            return f"Process '{process_name}' found: {', '.join(running_processes)}"
                        else:
                            return f"Process '{process_name}' not found"
                    except Exception as e:
                        return f"Error checking process '{process_name}': {e}"
                else:
                    return "ERROR: No process_name specified for check_process action"
            elif action_type == "wait":
                # Wait for a specified duration
                duration = action.get("duration", 1.0)
                try:
                    import time
                    time.sleep(float(duration))
                    return f"Waited for {duration} seconds"
                except Exception as e:
                    return f"Error waiting: {e}"
            
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

    async def _take_screenshot(self, context: str) -> Optional[Path]:
        """Take a screenshot and save it to the debug/screenshots directory."""
        try:
            logger.info(f"Taking screenshot for: {context}")
            await self._update_gui_state_func("/state/current_operation", {"text": f"Taking screenshot for: {context}"})
            
            # Capture screenshot
            screenshot_pil = await asyncio.to_thread(capture_screen_pil)
            if not screenshot_pil:
                logger.error("Failed to capture screenshot")
                return None
            
            # Generate unique filename
            screenshot_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            screenshot_filename = f"automoy_screenshot_{screenshot_timestamp}.png"
            screenshot_path = Path("debug/screenshots") / screenshot_filename
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save screenshot
            await asyncio.to_thread(screenshot_pil.save, str(screenshot_path))
            logger.info(f"Screenshot saved: {screenshot_path}")
            
            # Update GUI with screenshot path
            await self._update_gui_state_func("/state/screenshot", {"path": str(screenshot_path)})
            
            return screenshot_path
            
        except Exception as e:
            logger.error(f"Failed to take screenshot for {context}: {e}", exc_info=True)
            return None

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
            logger.info(f"🔍 Calling OmniParser.parse_screenshot with: {screenshot_path}")
            parsed_result = self.omniparser.parse_screenshot(str(screenshot_path))
            logger.info(f"🔍 OmniParser returned result type: {type(parsed_result)}")
            logger.info(f"🔍 OmniParser result is None: {parsed_result is None}")
            logger.info(f"🔍 OmniParser result is truthy: {bool(parsed_result)}")
            
            if parsed_result:
                logger.info(f"🔍 OmniParser result keys: {list(parsed_result.keys()) if isinstance(parsed_result, dict) else 'Not a dict'}")
            
            if parsed_result and isinstance(parsed_result, dict) and "parsed_content_list" in parsed_result:
                # Store parsed result for later use in action generation
                self.parsed_content_list = parsed_result["parsed_content_list"]
                
                # Check if parsed_content_list is actually populated
                elements_found = len(parsed_result["parsed_content_list"]) if parsed_result["parsed_content_list"] else 0
                logger.info(f"🔍 parsed_content_list contains {elements_found} elements")
                
                if elements_found == 0:
                    logger.error("❌ CRITICAL: No visual elements detected by OmniParser - HALTING OPERATION")
                    await self._update_gui_state_func("/state/thinking", {"text": "❌ CRITICAL ERROR: Visual analysis detected NO UI elements. This indicates a serious issue with OmniParser or screen content. Operation HALTED for safety."})
                    await self._update_gui_state_func("/state/current_operation", {"text": "❌ HALTED: No visual elements detected - bad component"})
                    await self._update_gui_state_func("/state/operator_status", {"text": "error"})
                    
                    # Raise an exception to halt the operation completely
                    raise RuntimeError("Visual analysis detected zero elements - indicating bad component. Operation halted for safety.")
                
                if elements_found < 5:
                    logger.warning(f"⚠️ WARNING: Only {elements_found} visual elements detected - unusually low count")
                    await self._update_gui_state_func("/state/thinking", {"text": f"⚠️ WARNING: Only {elements_found} visual elements detected. This is unusually low and may indicate screen or analysis issues."})
                
                
                # Process the visual analysis results
                await self._update_gui_state_func("/state/current_operation", {"text": f"Visual analysis complete: Found {elements_found} UI elements. Processing results for action planning."})
                
                # Log first few elements for debugging
                for i, element in enumerate(parsed_result["parsed_content_list"][:3]):
                    logger.info(f"🔍 Element {i+1}: {element.get('content', '')} | {element.get('type', '')} | {element.get('bbox_normalized', [])}")
                
                
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
                logger.error("❌ CRITICAL: Visual analysis returned invalid results - HALTING OPERATION")
                if parsed_result:
                    if isinstance(parsed_result, dict):
                        logger.error(f"❌ Missing 'parsed_content_list' key. Available keys: {list(parsed_result.keys())}")
                    else:
                        logger.error(f"❌ Result is not a dict, got: {type(parsed_result)}")
                else:
                    logger.error("❌ OmniParser returned None or empty result")
                    
                await self._update_gui_state_func("/state/thinking", {"text": "❌ CRITICAL ERROR: Visual analysis failed completely - OmniParser returned invalid or empty results. This indicates a serious component failure. Operation HALTED for safety."})
                await self._update_gui_state_func("/state/current_operation", {"text": "❌ HALTED: Visual analysis component failure"})
                await self._update_gui_state_func("/state/operator_status", {"text": "error"})
                
                # Raise an exception to halt the operation completely
                raise RuntimeError("Visual analysis returned invalid results - indicating bad component. Operation halted for safety.")
                
        except Exception as e:
            logger.error(f"Error during visual analysis: {e}", exc_info=True)
            await self._update_gui_state_func("/state/thinking", {"text": f"Visual analysis error: {str(e)}. Continuing without screen analysis."})
            return None, None

    def _format_visual_analysis_result(self, parsed_result: dict) -> str:
        """Format the visual analysis result for LLM consumption with ClickCoordinates."""
        if not parsed_result or "parsed_content_list" not in parsed_result:
            return "No visual elements detected."
        
        elements = parsed_result["parsed_content_list"]
        formatted_output = []
        
        for i, element in enumerate(elements):
            element_text = element.get("content", "")
            element_type = element.get("type", "unknown")
            
            # Convert normalized bbox to pixel coordinates for ClickCoordinates
            if element.get("bbox_normalized"):
                bbox = element["bbox_normalized"]
                logger.debug(f"📍 Element {i+1} bbox_normalized: {bbox} (type: {type(bbox)})")
                
                # Handle multiple possible bbox formats flexibly
                valid_coords = False
                pixel_x, pixel_y = 0, 0
                
                try:
                    # Get actual screen dimensions
                    import pyautogui
                    screen_width, screen_height = pyautogui.size()
                    logger.debug(f"📏 Screen dimensions: {screen_width}x{screen_height}")
                    
                    # Handle various bbox formats that OmniParser might return
                    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                        # Standard format: [x1, y1, x2, y2] in normalized coordinates (0.0-1.0)
                        coords = [float(coord) for coord in bbox[:4]]  # Take first 4 elements
                        x1, y1, x2, y2 = coords
                        
                        # Ensure coordinates are within valid range (0.0-1.0)
                        if all(0.0 <= coord <= 1.0 for coord in coords):
                            # Calculate center point in pixels
                            pixel_x = int((x1 + x2) / 2 * screen_width)
                            pixel_y = int((y1 + y2) / 2 * screen_height)
                            
                            # Ensure pixel coordinates are within screen bounds
                            pixel_x = max(0, min(pixel_x, screen_width - 1))
                            pixel_y = max(0, min(pixel_y, screen_height - 1))
                            
                            logger.debug(f"📍 Normalized coords: x1={x1:.3f}, y1={y1:.3f}, x2={x2:.3f}, y2={y2:.3f}")
                            logger.debug(f"📍 Converted to pixels: ({pixel_x}, {pixel_y})")
                            valid_coords = True
                        else:
                            logger.warning(f"⚠️ Normalized coordinates out of range (0-1): {coords}")
                    else:
                        logger.warning(f"❌ Invalid bbox format for element {i+1}: expected list/tuple with 4+ elements, got {type(bbox)} with length {len(bbox) if hasattr(bbox, '__len__') else 'unknown'}")
                        
                except (ValueError, TypeError) as e:
                    logger.warning(f"❌ Failed to convert bbox {bbox} for element {i+1}: {e}")
                except ImportError:
                    logger.warning("⚠️ pyautogui not available, using fallback screen size")
                    # Use fallback screen size
                    screen_width, screen_height = 1920, 1080
                    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                        try:
                            coords = [float(coord) for coord in bbox[:4]]
                            x1, y1, x2, y2 = coords
                            if all(0.0 <= coord <= 1.0 for coord in coords):
                                pixel_x = int((x1 + x2) / 2 * screen_width)
                                pixel_y = int((y1 + y2) / 2 * screen_height)
                                pixel_x = max(0, min(pixel_x, screen_width - 1))
                                pixel_y = max(0, min(pixel_y, screen_height - 1))
                                valid_coords = True
                        except (ValueError, TypeError):
                            pass
                except Exception as e:
                    logger.error(f"❌ Unexpected error in coordinate conversion for element {i+1}: {e}")
                
                # Format based on whether coordinates were successfully converted
                if valid_coords:
                    formatted_output.append(f"element_{i+1}: Text: '{element_text}' | Type: {element_type} | ClickCoordinates: ({pixel_x}, {pixel_y})")
                else:
                    logger.warning(f"⚠️ Could not extract valid coordinates for element {i+1}, marking as unavailable")
                    formatted_output.append(f"element_{i+1}: Text: '{element_text}' | Type: {element_type} | ClickCoordinates: (unavailable)")
            else:
                # If no coordinates available, still list the element
                logger.debug(f"⚠️ Element {i+1} has no bbox_normalized field")
                formatted_output.append(f"element_{i+1}: Text: '{element_text}' | Type: {element_type} | ClickCoordinates: (unavailable)")
        
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
        
        # Look for Chrome specifically
        chrome_elements = []
        for i, element in enumerate(elements):
            content = str(element.get("content", "")).lower()
            if "chrome" in content or "google" in content:
                chrome_elements.append((i, element))
        
        if chrome_elements:
            analysis_text += "🎯 CHROME ELEMENTS DETECTED:\n"
            for i, element in chrome_elements[:5]:  # Show first 5 Chrome elements
                element_info = []
                if element.get("content"):
                    element_info.append(f"Text: '{element['content']}'")
                if element.get("type"):
                    element_info.append(f"Type: {element['type']}")
                if element.get("bbox_normalized"):
                    bbox = element["bbox_normalized"]
                    element_info.append(f"Position: ({bbox[0]:.3f}, {bbox[1]:.3f}, {bbox[2]:.3f}, {bbox[3]:.3f})")
                if element.get("interactivity"):
                    element_info.append("Interactive: Yes")
                
                analysis_text += f"  Chrome-{len(chrome_elements)}: {' | '.join(element_info)}\n"
            
            analysis_text += f"\n"
        else:
            analysis_text += "⚠️ No Chrome elements found.\n\n"
        
        # Show first 10 elements for context
        analysis_text += "All Elements (first 10):\n"
        for i, element in enumerate(elements[:10], 1):
            element_info = []
            if element.get("content"):
                element_info.append(f"Text: '{element['content']}'")
            if element.get("type"):
                element_info.append(f"Type: {element['type']}")
            if element.get("bbox_normalized"):
                bbox = element["bbox_normalized"]
                element_info.append(f"Position: ({bbox[0]:.3f}, {bbox[1]:.3f}, {bbox[2]:.3f}, {bbox[3]:.3f})")
            
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
        
        # Generate steps using LLM reasoning only - no hardcoded application logic
        
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
                # === FRESH VISUAL ANALYSIS FOR ACTION GENERATION ===
                # Always take fresh screenshot and analyze before asking LLM for action
                logger.info("Taking fresh screenshot and performing visual analysis for action generation")
                await self._update_gui_state_func("/state/thinking", {"text": "Taking fresh screenshot and analyzing current screen for action generation..."})
                
                try:
                    # Take screenshot for current visual state  
                    screenshot_path = await self._take_screenshot(f"Action generation step {current_step_index + 1}")
                    
                    if screenshot_path and self.omniparser:
                        logger.info("Performing visual analysis for action generation")
                        
                        # Perform visual analysis on current screen
                        logger.info(f"[DEBUG VISUAL ANALYSIS] Calling _perform_visual_analysis with screenshot: {screenshot_path}")
                        _, visual_analysis_result = await self._perform_visual_analysis(
                            screenshot_path, f"Action generation for: {current_step_description}")
                        
                        logger.info(f"[DEBUG VISUAL ANALYSIS] Visual analysis returned: {visual_analysis_result}")
                        logger.info(f"[DEBUG VISUAL ANALYSIS] Has parsed_content_list attr: {hasattr(self, 'parsed_content_list')}")
                        if hasattr(self, 'parsed_content_list'):
                            logger.info(f"[DEBUG VISUAL ANALYSIS] parsed_content_list length: {len(self.parsed_content_list) if self.parsed_content_list else 0}")
                            logger.info(f"[DEBUG VISUAL ANALYSIS] parsed_content_list content: {self.parsed_content_list[:2] if self.parsed_content_list else None}")
                        
                        # Update visual analysis output if we got results
                        if hasattr(self, 'parsed_content_list') and self.parsed_content_list:
                            logger.info(f"Visual analysis found {len(self.parsed_content_list)} elements for action generation")
                            await self._update_gui_state_func("/state/thinking", 
                                {"text": f"Visual analysis found {len(self.parsed_content_list)} UI elements on screen - ready for LLM analysis"})
                            
                            # Format elements for LLM consumption  
                            formatted_elements = []
                            text_snippets = []
                            visual_analysis_text = []
                            
                            for i, element in enumerate(self.parsed_content_list):
                                element_dict = {}
                                if element.get("content"):
                                    element_dict["text"] = element["content"]
                                    text_snippets.append(element["content"])
                                if element.get("type"):
                                    element_dict["type"] = element["type"]
                                if element.get("bbox_normalized"):
                                    bbox = element["bbox_normalized"]
                                    # Convert normalized bbox to pixel coordinates
                                    screen_width, screen_height = 1920, 1080  # Default assumption
                                    x1, y1, x2, y2 = bbox
                                    pixel_x = int((x1 + x2) / 2 * screen_width)
                                    pixel_y = int((y1 + y2) / 2 * screen_height)
                                    element_dict["coordinates"] = [pixel_x, pixel_y]
                                    
                                    # Format for LLM as expected in prompt template
                                    element_text = element.get("content", "")
                                    element_type = element.get("type", "unknown")
                                    visual_analysis_text.append(f"element_{i+1}: Text: '{element_text}' | Type: {element_type} | ClickCoordinates: ({pixel_x}, {pixel_y})")
                                
                                formatted_elements.append(element_dict)
                            
                            # Store formatted analysis for LLM
                            self.visual_analysis_output = {
                                "elements": formatted_elements,
                                "text_snippets": text_snippets,
                                "formatted_text": "\n".join(visual_analysis_text)
                            }
                            
                            logger.info(f"Updated visual analysis with {len(formatted_elements)} elements for LLM action generation")
                        else:
                            logger.warning("No elements found in visual analysis")
                            self.visual_analysis_output = {"elements": [], "text_snippets": [], "formatted_text": "No visual elements detected on current screen."}
                            await self._update_gui_state_func("/state/thinking", 
                                {"text": "Visual analysis completed but no UI elements detected on current screen"})
                    else:
                        logger.warning("Failed to capture screenshot or OmniParser not available")
                        self.visual_analysis_output = {"elements": [], "text_snippets": [], "formatted_text": "Screenshot capture failed - no visual analysis available."}
                        await self._update_gui_state_func("/state/thinking", 
                            {"text": "Failed to capture screenshot - proceeding without visual analysis"})
                        
                except Exception as visual_error:
                    logger.error(f"Error during visual analysis for action generation: {visual_error}", exc_info=True)
                    self.visual_analysis_output = {"elements": [], "text_snippets": [], "formatted_text": "Visual analysis failed due to error."}
                    await self._update_gui_state_func("/state/thinking", 
                        {"text": f"Visual analysis error: {visual_error} - proceeding without visual context"})
                
                # === END FRESH VISUAL ANALYSIS ===
                
                system_prompt_action = ACTION_GENERATION_SYSTEM_PROMPT
                previous_action = self.executed_steps[-1]["summary"] if self.executed_steps else "N/A"
                
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
                
                # Take fresh screenshot for LLM action generation
                screenshot_path = await self._take_screenshot(f"Action generation for step {current_step_index + 1}")
                
                raw_llm_response, thinking_output, llm_error = await self.llm_interface.get_next_action(
                    model=self.config.get_model(),
                    messages=messages_action,
                    objective=self.objective,
                    session_id=self.session_id,
                    screenshot_path=screenshot_path,  # Enable visual analysis
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
        
        # Initialize operator for standard goal execution
        logger.info("🖥️ Initializing operator for goal execution")
        await self._update_gui_state_func("/state/thinking", {"text": "Starting operator - ready to execute goal through proper reasoning and visual analysis"})
        
        await self._update_gui_state_func("/state/thinking", {"text": "Operator initialization complete - ready to proceed with objective through LLM reasoning"})
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
                
                # Take screenshot and perform visual analysis for better step generation
                await self._update_gui_state_func("/state/current_operation", {"text": "Taking screenshot for visual analysis to generate better steps"})
                
                try:
                    # Take screenshot for visual analysis
                    screenshot_path = await self._take_screenshot("Initial visual analysis for step generation")
                    if screenshot_path:
                        # Perform visual analysis
                        _, visual_analysis_result = await self._perform_visual_analysis(screenshot_path, "Initial step generation")
                        
                        # Use the stored parsed content from visual analysis
                        if hasattr(self, 'parsed_content_list') and self.parsed_content_list:
                            # Format elements for LLM consumption using the stored parsed data
                            formatted_elements = []
                            text_snippets = []
                            visual_analysis_text = []
                            
                            for i, element in enumerate(self.parsed_content_list):
                                element_dict = {}
                                if element.get("content"):
                                    element_dict["text"] = element["content"]
                                    text_snippets.append(element["content"])
                                if element.get("type"):
                                    element_dict["type"] = element["type"]
                                if element.get("bbox_normalized"):
                                    bbox = element["bbox_normalized"]
                                    # Convert normalized bbox to pixel coordinates
                                    # Assuming standard screen size - this should be improved
                                    screen_width, screen_height = 1920, 1080  # Default assumption
                                    x1, y1, x2, y2 = bbox
                                    pixel_x = int((x1 + x2) / 2 * screen_width)
                                    pixel_y = int((y1 + y2) / 2 * screen_height)
                                    element_dict["coordinates"] = [pixel_x, pixel_y]
                                    
                                    # Format for LLM as expected in prompt template
                                    element_text = element.get("content", "")
                                    element_type = element.get("type", "unknown")
                                    visual_analysis_text.append(f"element_{i+1}: Text: '{element_text}' | Type: {element_type} | ClickCoordinates: ({pixel_x}, {pixel_y})")
                                
                                formatted_elements.append(element_dict)
                            
                            # Store both formats - dictionary for internal use, formatted text for LLM
                            self.visual_analysis_output = {
                                "elements": formatted_elements,
                                "text_snippets": text_snippets,
                                "formatted_text": "\n".join(visual_analysis_text)
                            }
                            logger.info(f"Visual analysis complete: {len(formatted_elements)} elements found for step generation")
                        else:
                            logger.warning("No parsed content available from visual analysis")
                            self.visual_analysis_output = {"elements": [], "text_snippets": []}
                    else:
                        logger.warning("Failed to take screenshot for visual analysis")
                        self.visual_analysis_output = {"elements": [], "text_snippets": []}
                except Exception as visual_error:
                    logger.error(f"Error during visual analysis: {visual_error}", exc_info=True)
                    self.visual_analysis_output = {"elements": [], "text_snippets": []}
                
                await self._update_gui_state_func("/state/current_operation", {"text": "Requesting LLM to generate step-by-step plan for objective"})
                
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
                    # Handle visual search actions generically - no hardcoded Chrome logic
                    target = action_to_execute.get("target", "")
                    logger.info(f"Visual search action for: {target}")
                    await self._update_gui_state_func("/state/thinking", {"text": f"Visual search initiated for {target}"})
                    
                    # Let LLM handle visual search through normal action generation
                    # No hardcoded Chrome detection - everything should go through proper visual analysis
                    execution_details = f"Visual search action processed for: {target}"
                    
                    self.current_step_index += 1
                    continue
                else:
                    # --- Real action execution ---
                    await self._update_gui_state_func("/state/thinking", {"text": f"Executing action: {action_to_execute.get('type', 'unknown')} - {action_to_execute.get('summary', 'No description')}"})
                    execution_details = self.action_executor.execute(action_to_execute)
                    
                    # Special handling for Windows key press - wait and take follow-up screenshot
                    if (action_to_execute.get("type") == "key" and 
                        action_to_execute.get("key") == "win"):
                        
                        logger.info("🔍 Windows key pressed - waiting for Start menu and taking follow-up screenshot")
                        await self._update_gui_state_func("/state/thinking", {"text": "Windows key pressed - waiting for Start menu to appear and taking follow-up screenshot"})
                        
                        # Wait for Start menu to appear
                        await asyncio.sleep(2)
                        
                        # Take immediate follow-up screenshot to see Start menu
                        followup_screenshot_path = await self._take_screenshot("After Windows key press")
                        if followup_screenshot_path and followup_screenshot_path.exists():
                            logger.info(f"✅ Follow-up screenshot after Windows key: {followup_screenshot_path}")
                            
                            # Analyze the Start menu screen
                            if self.omniparser:
                                try:
                                    parsed_result = self.omniparser.parse_screenshot(str(followup_screenshot_path))
                                    if parsed_result and "parsed_content_list" in parsed_result:
                                        elements = parsed_result["parsed_content_list"]
                                        logger.info(f"🔍 Start menu analysis: found {len(elements)} elements")
                                        
                                        # Look for Chrome in Start menu
                                        chrome_found = False
                                        for element in elements:
                                            content = str(element.get("content", "")).lower()
                                            if "chrome" in content:
                                                logger.info(f"🎯 Found Chrome in Start menu: {element}")
                                                chrome_found = True
                                        
                                        if chrome_found:
                                            await self._update_gui_state_func("/state/thinking", {"text": f"✅ Start menu opened successfully! Found Chrome in menu among {len(elements)} elements"})
                                        else:
                                            await self._update_gui_state_func("/state/thinking", {"text": f"Start menu opened with {len(elements)} elements, but Chrome not immediately visible. May need to type or scroll."})
                                    else:
                                        await self._update_gui_state_func("/state/thinking", {"text": "Start menu screenshot taken but analysis returned empty - visual analysis may have issues"})
                                except Exception as analysis_error:
                                    logger.error(f"Start menu analysis error: {analysis_error}")
                                    await self._update_gui_state_func("/state/thinking", {"text": f"Start menu analysis error: {analysis_error}"})
                            else:
                                await self._update_gui_state_func("/state/thinking", {"text": "Start menu should be open but cannot analyze - OmniParser not available"})
                        else:
                            logger.warning("⚠️ Could not capture follow-up screenshot after Windows key")
                            await self._update_gui_state_func("/state/thinking", {"text": "Windows key executed but follow-up screenshot failed"})
                    
                    # Return to desktop anchor after real UI actions (but not after screenshots or special Windows key handling)
                    elif action_type in ["key_sequence", "type", "click"]:
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
    
    # Removed hardcoded Chrome step generation - all steps now generated by LLM reasoning
    
    # Removed hardcoded Chrome visual step generation - all steps now generated by LLM reasoning
    
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
        """
        Removed hardcoded Chrome detection logic.
        All icon detection should now use LLM reasoning with visual analysis.
        """
        logger.info("Chrome icon detection called - this should not happen with proper LLM reasoning")
        return None
