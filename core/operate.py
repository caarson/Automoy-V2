import json
import re
import asyncio
import os
import pathlib
import socket
import sys
import psutil
import requests
from datetime import datetime

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

from core.prompts.prompts import (
    VISUAL_ANALYSIS_SYSTEM_PROMPT, # <-- Updated
    VISUAL_ANALYSIS_USER_PROMPT_TEMPLATE, # <-- Added
    THINKING_PROCESS_PROMPT,
    STEPS_GENERATION_PROMPT,
    ACTION_GENERATION_SYSTEM_PROMPT, # <-- Added
)

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
        print(f"[WARNING] Failed to update GUI state at {url}: {e}")
    except Exception as e:
        print(f"[ERROR] Unexpected error in _update_gui_state: {e}")


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
            print(f"[ERROR] Could not determine model from config: {e}")
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


    async def _execute_action(self, action_json: dict) -> bool:
        """
        Placeholder for executing an action.
        In a real implementation, this would interact with OSInterface, etc.
        Returns True if successful, False otherwise.
        """
        operation = action_json.get("operation", "").lower()
        element_id = action_json.get("element_id")
        text_to_type = action_json.get("text")
        keys_to_press = action_json.get("keys") # For press/hotkey operations
        coordinates = action_json.get("coordinates") # e.g., {"x": 100, "y": 200}
        scroll_direction = action_json.get("scroll_direction") # "up", "down", "left", "right"
        scroll_amount = action_json.get("scroll_amount", 1) # Number of scroll units/clicks

        action_description_for_gui = f"Executing: {operation}"
        if element_id: action_description_for_gui += f" on element '{element_id}'"
        if text_to_type: action_description_for_gui += f" with text '{text_to_type[:30]}...'"
        if keys_to_press: action_description_for_gui += f" pressing keys '{keys_to_press}'"
        if scroll_direction: action_description_for_gui += f" scrolling {scroll_direction}"

        print(f"[EXECUTE_ACTION] Attempting: {action_description_for_gui} | Full JSON: {action_json}")
        await _update_gui_state("/state/current_operation", {"text": action_description_for_gui})
        
        try:
            # Hide GUI before action if necessary (e.g., for clicks that might be obscured)
            if operation in ["click", "double_click", "right_click"] and self.manage_gui_window_func:
                await self.manage_gui_window_func("hide")
                await asyncio.sleep(0.2) # Brief pause for window to hide

            target_x, target_y = None, None

            if element_id and self.coords and element_id in self.coords:
                element_info = self.coords[element_id]
                bbox = element_info.get("bbox")
                if bbox and len(bbox) == 4:
                    x, y, w, h = bbox
                    target_x, target_y = x + w // 2, y + h // 2
                    print(f"[EXECUTE_ACTION] Target element '{element_id}' found at center ({target_x}, {target_y}) from bbox {bbox}")
                else:
                    print(f"[WARNING] Bbox for element '{element_id}' is invalid or missing: {bbox}. Cannot click element by ID.")
                    # Fallback to screen-level operation or fail
            elif coordinates and isinstance(coordinates, dict) and "x" in coordinates and "y" in coordinates:
                target_x, target_y = int(coordinates["x"]), int(coordinates["y"])
                print(f"[EXECUTE_ACTION] Using provided coordinates: ({target_x}, {target_y})")

            if operation == "click":
                if target_x is not None and target_y is not None:
                    self.os_interface.move_mouse(target_x, target_y, duration=0.2)
                    await asyncio.sleep(0.1) # Short pause after move before click
                    self.os_interface.click_mouse(button="left")
                    print(f"[EXECUTE_ACTION] Clicked at ({target_x}, {target_y})")
                else:
                    print(f"[EXECUTE_ACTION] Click operation failed: No valid coordinates for element '{element_id}' or direct coords.")
                    return False
            elif operation == "double_click":
                if target_x is not None and target_y is not None:
                    self.os_interface.move_mouse(target_x, target_y, duration=0.2)
                    await asyncio.sleep(0.1)
                    pyautogui.doubleClick(x=target_x, y=target_y) # OSInterface doesn't have double_click, use pyautogui directly
                    print(f"[EXECUTE_ACTION] Double-clicked at ({target_x}, {target_y})")
                else:
                    print(f"[EXECUTE_ACTION] Double_click operation failed: No valid coordinates.")
                    return False
            elif operation == "right_click":
                if target_x is not None and target_y is not None:
                    self.os_interface.move_mouse(target_x, target_y, duration=0.2)
                    await asyncio.sleep(0.1)
                    self.os_interface.click_mouse(button="right")
                    print(f"[EXECUTE_ACTION] Right-clicked at ({target_x}, {target_y})")
                else:
                    print(f"[EXECUTE_ACTION] Right_click operation failed: No valid coordinates.")
                    return False
            elif operation == "type":
                if text_to_type is not None: # Check if text_to_type is None, not just falsy
                    if target_x is not None and target_y is not None: # Click to focus if coords provided
                        self.os_interface.move_mouse(target_x, target_y, duration=0.2)
                        await asyncio.sleep(0.1)
                        self.os_interface.click_mouse(button="left")
                        await asyncio.sleep(0.2) # Wait for focus
                    self.os_interface.type_text(str(text_to_type)) # Ensure text is string
                    print(f"[EXECUTE_ACTION] Typed: '{text_to_type}'")
                else:
                    print(f"[EXECUTE_ACTION] Type operation failed: No text provided.")
                    return False
            elif operation == "press_keys":
                if keys_to_press:
                    if isinstance(keys_to_press, list):
                        self.os_interface.hotkey(*keys_to_press) # Pass as separate arguments for hotkey
                        print(f"[EXECUTE_ACTION] Pressed hotkey combination: {keys_to_press}")
                    elif isinstance(keys_to_press, str):
                        self.os_interface.press(keys_to_press) # Single key press
                        print(f"[EXECUTE_ACTION] Pressed key: {keys_to_press}")
                    else:
                        print(f"[EXECUTE_ACTION] Press_keys operation failed: Invalid 'keys' format '{keys_to_press}'.")
                        return False
                else:
                    print(f"[EXECUTE_ACTION] Press_keys operation failed: No keys provided.")
                    return False
            elif operation == "scroll":
                if scroll_direction and scroll_amount:
                    scroll_val = 0
                    if scroll_direction == "up": scroll_val = int(scroll_amount) * 100 # PyAutoGUI scroll units can be large
                    elif scroll_direction == "down": scroll_val = -int(scroll_amount) * 100
                    # Horizontal scroll might need different handling or OSInterface extension
                    # For now, focusing on vertical. PyAutoGUI's scroll is vertical.
                    # pyautogui.hscroll() for horizontal if needed.
                    if scroll_val != 0:
                        if target_x is not None and target_y is not None: # Scroll at specific element location
                            self.os_interface.move_mouse(target_x, target_y, duration=0.2)
                            await asyncio.sleep(0.1)
                        pyautogui.scroll(scroll_val) # Use pyautogui directly for scroll
                        print(f"[EXECUTE_ACTION] Scrolled {scroll_direction} by {scroll_amount} units (value: {scroll_val}).")
                    else:
                        print(f"[EXECUTE_ACTION] Scroll operation failed: Invalid scroll direction '{scroll_direction}'.")
                        return False
                else:
                    print(f"[EXECUTE_ACTION] Scroll operation failed: scroll_direction or scroll_amount not provided.")
                    return False
            elif operation == "take_screenshot": # LLM might request this explicitly
                # This is usually handled by run_capture_on_next_cycle = True
                # But if LLM asks, we can acknowledge it.
                print("[EXECUTE_ACTION] 'take_screenshot' action noted. Next cycle will capture.")
                self.run_capture_on_next_cycle = True # Ensure it happens
                # No direct OS action here, loop handles it.
            elif operation == "finish_objective":
                print("[EXECUTE_ACTION] 'finish_objective' action received. Objective considered complete by LLM.")
                # This will cause the loop to break or re-evaluate based on current logic
                self.generated_steps_output = [] # Clear steps
                self.current_step_index = 0
                # Potentially set a flag to stop the main loop if desired, or let it re-evaluate
                await _update_gui_state("/state/current_operation", {"text": "Objective marked as finished by AI."})
                # To actually stop, main.py would need to observe a state or this would raise a specific exception
                return True # Action itself is "successful"
            elif operation == "fail_objective":
                print("[EXECUTE_ACTION] 'fail_objective' action received. Objective considered failed by LLM.")
                self.generated_steps_output = []
                self.current_step_index = 0
                await _update_gui_state("/state/current_operation", {"text": "Objective marked as failed by AI."})
                return True # Action itself is "successful" in terms of execution
            else:
                print(f"[EXECUTE_ACTION] Unknown or unsupported operation: '{operation}'")
                return False

            await asyncio.sleep(0.5) # General delay after most actions for UI to react
            print(f"[EXECUTE_ACTION] Successfully executed: {operation}")
            return True
        except Exception as e:
            print(f"[EXECUTE_ACTION_ERROR] Error during '{operation}': {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            if operation in ["click", "double_click", "right_click"] and self.manage_gui_window_func:
                await asyncio.sleep(0.1) # Ensure action completes before showing GUI
                await self.manage_gui_window_func("show")

    # ───────────────────────────── Startup ───────────────────────────
    async def startup_sequence(self):
        # This method is now primarily called from main.py before operate_loop
        # It can remain for direct testing of operate.py if needed.
        print("🚀 Automoy Starting Up (within operator)...")
        print(f"Detected OS: {self.os_interface.os_type}")

        # GUI launch is handled by main.py
        # OmniParser server check/launch
        if not self.omniparser._check_server_ready():
            print("❌ OmniParser server is not running! Attempting to start it…")
            if self.omniparser.launch_server(): # launch_server should return success/failure
                 await asyncio.sleep(5) # Give server time to start
                 if not self.omniparser._check_server_ready():
                    print("❌ OmniParser server failed to start properly. Exiting.")
                    sys.exit(1)
            else:
                print("❌ Failed to initiate OmniParser server launch. Exiting.")
                sys.exit(1)
        else:
            print("✅ OmniParser server already running or started successfully.")


        if not self.vmware.is_vmware_installed():
            print("⚠️ VMWare is not installed or not detected.")

        if not self.webscraper.is_ready():
            print("⚠️ Web scraper is not properly configured!")

        print("✅ All systems ready (within operator startup_sequence)!")    


    # ───────────────────────────── Loop ──────────────────────────────
    async def operate_loop(self):
        # startup_sequence is now expected to be called by the main script before this.
        print("🔥 Entering Automoy Autonomous Operation Mode!")

        if not self.objective:
            print("[ERROR] Objective not set for AutomoyOperator. Exiting operate_loop.")
            await _update_gui_state("/state/current_operation", {"text": "Error: Objective not set."})
            return
        
        if self.pause_event: # Ensure pause_event is set before using
            self.pause_event.set() # Ensure it's not paused by default when starting

        print(f"[INFO] Objective received: {self.objective}")

        await _update_gui_state("/state/clear_all_operational_data", {})
        # Formulated objective is set by main.py, then user confirms, then operate_loop starts.

        first_cycle_for_anchors = True # Controls initial anchor application and full re-planning logic

        while True: # Main operational cycle
            try:
                if self.pause_event:
                    if not self.pause_event.is_set():
                        print("[OPERATE_LOOP] Pause event is not set. Waiting for resume...", flush=True)
                    await self.pause_event.wait() # Check pause state at the beginning of each cycle
                    if not self.pause_event.is_set(): # Should not happen if wait() returned unless cleared immediately after
                        print("[OPERATE_LOOP] Woke from wait but event is still clear. Re-waiting.", flush=True)
                        await self.pause_event.wait()


                print(f"[OPERATE_LOOP] Top of loop. run_capture_on_next_cycle: {self.run_capture_on_next_cycle}, first_cycle_for_anchors: {first_cycle_for_anchors}, steps: {len(self.generated_steps_output)}, current_idx: {self.current_step_index}", flush=True)

                if self.last_action:
                    # GUI update for last_action is handled after its execution.
                    pass

                # --- 1. CAPTURE AND PARSE SCREEN (Selective) ---
                if self.run_capture_on_next_cycle:
                    if self.pause_event:
                        if not self.pause_event.is_set(): print("[OPERATE_LOOP] Paused before capture.", flush=True)
                        await self.pause_event.wait() # Check before capture
                    print("[OPERATE_LOOP] Running screen capture and parse cycle.", flush=True)
                    if self.manage_gui_window_func: await self.manage_gui_window_func("hide")
                    
                    if first_cycle_for_anchors and self.desktop_anchor_point:
                        print("[ANCHOR] Applying desktop anchor point (showing desktop).")
                        # Assuming show_desktop is synchronous
                        await asyncio.get_event_loop().run_in_executor(None, show_desktop)
                        await asyncio.sleep(0.5) 

                    raw_screenshot_filename_for_cycle = f"automoy_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    # Ensure screenshot path is absolute, take_screenshot should handle this.
                    # Let's assume it saves to a known directory or OPERATE_PY_PROJECT_ROOT / "screenshots"
                    # For now, assume it saves relative to where OSInterface runs or an absolute path.
                    # To be safe, let's ensure it's in project root if not absolute.
                    capture_path = OPERATE_PY_PROJECT_ROOT / raw_screenshot_filename_for_cycle
                    self.raw_screenshot_path_for_parsing = self.os_interface.take_screenshot(str(capture_path))
                    print(f"[CAPTURE] Raw screenshot saved to: {self.raw_screenshot_path_for_parsing}")

                    if self.manage_gui_window_func: await self.manage_gui_window_func("show")

                    await _update_gui_state("/state/current_operation", {"text": "Parsing screen elements..."})
                    print("[OMNIPARSER] Calling OmniParser for UI elements...")
                    
                    processed_screenshot_abs_path = OPERATE_PY_PROJECT_ROOT / PROCESSED_SCREENSHOT_RELATIVE_PATH
                    processed_screenshot_abs_path.parent.mkdir(parents=True, exist_ok=True)

                    # Run synchronous parse_screenshot in an executor
                    loop = asyncio.get_event_loop()
                    parsed_data = await loop.run_in_executor(
                        None,  # Uses the default ThreadPoolExecutor
                        self.omniparser_instance.parse_screenshot,
                        self.raw_screenshot_path_for_parsing  # Argument to parse_screenshot
                        # output_image_path is handled by parse_screenshot internally now
                    )
                    
                    if parsed_data and "coords" in parsed_data and "som_image_base64" in parsed_data:
                        self.ui_json_for_llm = json.dumps(parsed_data.get("coords")) # Or however ui_json_for_llm should be structured
                        self.coords = parsed_data.get("coords")
                        print(f"[OMNIPARSER] Successfully parsed. UI JSON length: {len(self.ui_json_for_llm)}. Coords for {len(self.coords)} elements.")
                        # The processed_screenshot.png is saved by parse_screenshot in its own directory,
                        # and also copied to gui/static/processed_screenshot.png
                        self.active_screenshot_for_llm_gui = str(OPERATE_PY_PROJECT_ROOT / "gui" / "static" / "processed_screenshot.png")
                    else:
                        print("[ERROR] OmniParser failed or returned unexpected data. Using raw screenshot for LLM.")
                        self.ui_json_for_llm = "{}" # Empty JSON if parsing failed
                        self.coords = {}
                        self.active_screenshot_for_llm_gui = self.raw_screenshot_path_for_parsing
                    
                    await _update_gui_state("/state/screenshot", {"path": self.active_screenshot_for_llm_gui, "timestamp": datetime.now().isoformat()})

                    # --- 2. VISUAL ANALYSIS STAGE (after capture) ---
                    if self.pause_event:
                        if not self.pause_event.is_set(): print("[OPERATE_LOOP] Paused before VA.", flush=True)
                        await self.pause_event.wait() # Check before VA
                    await _update_gui_state("/state/current_operation", {"text": "Performing visual analysis..."})
                    print("[LLM] Performing Visual Analysis...")
                    
                    anchor_context_for_va = ""
                    if first_cycle_for_anchors: # Only add anchor context if it's a "fresh start" cycle
                        if self.prompt_anchor_point and self.anchor_prompt:
                            anchor_context_for_va += f"\\nImportant Context Provided by User: {self.anchor_prompt}\\n"
                        if self.vllm_anchor_point:
                            anchor_context_for_va += "\\nNote: Advanced Visual Language Model insights are being incorporated.\\n"
                        if anchor_context_for_va:
                             print(f"[ANCHOR] Including anchor context for Visual Analysis: {anchor_context_for_va.strip()}")
                    
                    visual_analysis_user_prompt = VISUAL_ANALYSIS_USER_PROMPT_TEMPLATE.format(
                        initial_objective_context=anchor_context_for_va, # Corrected key
                        ui_json=self.ui_json_for_llm if self.ui_json_for_llm else "No structured UI elements available.", # Corrected key
                        screenshot_context="" # Added missing key, assuming empty if not specifically prepared
                    )
                    messages_va = [
                        {"role": "system", "content": VISUAL_ANALYSIS_SYSTEM_PROMPT},
                        {"role": "user", "content": visual_analysis_user_prompt}
                    ]
                    self.visual_analysis_output, _, _ = await self.llm.get_next_action(
                        model=self.model, messages=messages_va, objective="Analyze the visual content of the screen.",
                        session_id="automoy-va", screenshot_path=self.active_screenshot_for_llm_gui
                    )
                    print(f"[OPERATE_LOOP DEBUG] Visual Analysis Output before sending to GUI: '{self.visual_analysis_output[:200]}...' (Length: {len(self.visual_analysis_output)})") # DEBUG ADD
                    if not self.visual_analysis_output:
                        print("[ERROR] Visual analysis returned empty. This might affect planning.")
                        self.visual_analysis_output = "Visual analysis failed or returned empty."
                    
                    await _update_gui_state("visual", {"text": self.visual_analysis_output})
                    self.run_capture_on_next_cycle = False # Reset flag after successful capture and VA
                
                elif not self.visual_analysis_output or not self.active_screenshot_for_llm_gui:
                    print("[ERROR] No existing visual analysis or screenshot, but capture was skipped. Forcing capture.")
                    self.run_capture_on_next_cycle = True
                    first_cycle_for_anchors = True # Treat as a need for fresh start
                    await asyncio.sleep(0.1)
                    continue

                # --- PLAN GENERATION / UPDATE ---
                if not self.generated_steps_output or first_cycle_for_anchors: # Need new plan or re-plan
                    if self.pause_event:
                        if not self.pause_event.is_set(): print("[OPERATE_LOOP] Paused before planning.", flush=True)
                        await self.pause_event.wait() # Check before planning
                    print("[OPERATE_LOOP] Entering planning phase (Thinking & Steps generation).", flush=True)
                    
                    # 3. THINKING PROCESS STAGE
                    await _update_gui_state("/state/current_operation", {"text": "Formulating plan (Thinking)..."})
                    print("[LLM] Performing Thinking Process...")
                    thinking_prompt = THINKING_PROCESS_PROMPT.format(
                        objective=self.objective, screen_description=self.visual_analysis_output
                    )
                    messages_thinking = [{"role": "user", "content": thinking_prompt}]
                    self.thinking_process_output, _, _ = await self.llm.get_next_action(
                        model=self.model, messages=messages_thinking, objective="Reason about the user's objective and current screen.",
                        session_id="automoy-thinking", screenshot_path=self.active_screenshot_for_llm_gui
                    )
                    if not self.thinking_process_output:
                         print("[ERROR] Thinking process returned empty.")
                         self.thinking_process_output = "Thinking process failed or returned empty."
                    await _update_gui_state("thinking", {"text": self.thinking_process_output})

                    # 4. STEPS GENERATION STAGE
                    if self.pause_event:
                        if not self.pause_event.is_set(): print("[OPERATE_LOOP] Paused before step generation.", flush=True)
                        await self.pause_event.wait() # Check before step generation
                    await _update_gui_state("/state/current_operation", {"text": "Generating steps..."})
                    print("[LLM] Generating execution steps...")
                    steps_generation_prompt_formatted = STEPS_GENERATION_PROMPT.format(
                        objective=self.objective,
                        thinking_output=self.thinking_process_output, # Corrected key
                        screen_description=self.visual_analysis_output, # Added missing key based on prompt definition
                        previous_actions=json.dumps(self.last_action) if self.last_action else "None"
                    )
                    messages_steps = [{"role": "user", "content": steps_generation_prompt_formatted}]
                    
                    generated_steps_text, _, _ = await self.llm.get_next_action(
                        model=self.model, messages=messages_steps, objective="Generate a sequence of steps.",
                        session_id="automoy-steps", screenshot_path=self.active_screenshot_for_llm_gui
                    )
                    
                    if generated_steps_text:
                        # Split by newline, then strip whitespace from each potential step
                        raw_steps = [step.strip() for step in generated_steps_text.split('\n') if step.strip()]
                        
                        # Further filter: keep only lines that start with a number and a period (e.g., "1. ")
                        # OR if no such lines exist, keep all non-empty raw_steps (LLM might not number them)
                        numbered_steps = [s for s in raw_steps if re.match(r"^\d+\.\s+", s)]
                        
                        if numbered_steps:
                            self.generated_steps_output = numbered_steps
                        elif raw_steps: # Fallback if no numbered steps found but raw_steps has content
                            print("[STEPS] LLM did not provide numbered steps. Using raw lines as steps.")
                            self.generated_steps_output = raw_steps
                        else:
                            self.generated_steps_output = []
                    else:
                        self.generated_steps_output = []

                    print(f"[STEPS] LLM Generated Steps: {self.generated_steps_output}")
                    await _update_gui_state("steps_generated", {"list": self.generated_steps_output})
                    
                    if not self.generated_steps_output:
                        print("[ERROR] LLM did not generate any steps. Will retry planning in next cycle.")
                        await _update_gui_state("/state/current_operation", {"text": "Error: No steps generated. Retrying."})
                        self.run_capture_on_next_cycle = True 
                        first_cycle_for_anchors = True # Force full re-plan
                        await asyncio.sleep(self.action_delay)
                        continue 
                    
                    self.current_step_index = 0 
                    first_cycle_for_anchors = False # Planning complete for now

                # --- STEP EXECUTION ---
                if self.current_step_index >= len(self.generated_steps_output):
                    print("[INFO] All generated steps processed. Objective might be complete or requires re-evaluation.")
                    await _update_gui_state("/state/current_operation", {"text": "Plan completed. Re-evaluating..."})
                    self.run_capture_on_next_cycle = True 
                    first_cycle_for_anchors = True 
                    self.generated_steps_output = [] 
                    await asyncio.sleep(self.action_delay)
                    continue

                current_step_for_action = self.generated_steps_output[self.current_step_index]
                step_display_text = f"Step {self.current_step_index + 1}/{len(self.generated_steps_output)}: {current_step_for_action}"
                print(f"[ACTION_GEN] Processing: {step_display_text}")
                await _update_gui_state("/state/current_operation", {"text": f"Preparing for: {step_display_text}"})

                # 5. ACTION GENERATION STAGE
                if self.pause_event:
                    if not self.pause_event.is_set(): print("[OPERATE_LOOP] Paused before action generation.", flush=True)
                    await self.pause_event.wait() # Check before action generation
                await _update_gui_state("/state/current_operation", {"text": f"Generating action for: {current_step_for_action}"})

                # Construct the user content for the action generation prompt
                action_generation_user_content = f"""Current Objective: {self.objective}

Current Screen Description (Visual Analysis):
{self.visual_analysis_output}

UI Elements (JSON):
{self.ui_json_for_llm if self.ui_json_for_llm else "{}"}

Step to Execute: {current_step_for_action}

Result of Previous Action (if any):
{json.dumps(self.last_action, indent=2) if self.last_action else "No previous action or first action."}

Based *only* on the 'Step to Execute' and the 'UI Elements (JSON)' and 'Current Screen Description', provide a single JSON object for the next operation.
Follow the action formats specified in the system prompt.
"""
                # ACTION_GENERATION_SYSTEM_PROMPT is imported from core.prompts.prompts
                messages_action = [
                    {"role": "system", "content": ACTION_GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": action_generation_user_content}
                ]
                
                raw_action_response_text, _, _ = await self.llm.get_next_action(
                    model=self.model, messages=messages_action, objective="Generate a single JSON action for the current step.",
                    session_id="automoy-action", screenshot_path=self.active_screenshot_for_llm_gui
                )
                print(f"[DEBUG] Raw LLM response for action: '{raw_action_response_text}'")

                action_json = None
                if raw_action_response_text:
                    # Attempt to strip markdown and then parse
                    cleaned_response = raw_action_response_text.strip()
                    if cleaned_response.startswith("```json"):
                        cleaned_response = cleaned_response[7:]
                        if cleaned_response.endswith("```"):
                            cleaned_response = cleaned_response[:-3]
                        cleaned_response = cleaned_response.strip()
                    
                    try:
                        action_json = json.loads(cleaned_response)
                        print(f"[DEBUG] Successfully parsed JSON from cleaned response: {action_json}")
                    except json.JSONDecodeError as e_json:
                        print(f"⚠️ Error decoding JSON directly: {e_json}. Trying regex search as fallback.")
                        # Fallback to regex search if direct parsing fails
                        try:
                            match = re.search(r"\{.*\}", raw_action_response_text, re.DOTALL)
                            if match:
                                json_str = match.group(0)
                                action_json = json.loads(json_str)
                                print(f"[DEBUG] Successfully parsed JSON via regex: {action_json}")
                            else:
                                print(f"[ERROR] No JSON object found in LLM response via regex: '{raw_action_response_text}'")
                        except json.JSONDecodeError as e_regex:
                            print(f"⚠️ Error decoding JSON via regex: {e_regex}. Raw: '{raw_action_response_text}'")
                        except Exception as e_parse: # Catch any other error during parsing
                            print(f"⚠️ Unexpected error parsing action: {e_parse}. Raw: '{raw_action_response_text}'")
                    except Exception as e_general_parse:
                         print(f"⚠️ Unexpected error during action parsing: {e_general_parse}. Raw: '{raw_action_response_text}'")
                
                action_executed_successfully = False
                if action_json and isinstance(action_json, dict) and "operation" in action_json:
                    print(f"[ACTION] Valid action extracted: {action_json}")
                    await _update_gui_state("operations_generated", {"current_operations_generated": action_json })

                    if self.pause_event:
                        if not self.pause_event.is_set(): print("[OPERATE_LOOP] Paused before executing action.", flush=True)
                        await self.pause_event.wait() # Check before executing action
                    action_executed_successfully = await self._execute_action(action_json)
                    
                    self.last_action = {
                        "step_index": self.current_step_index,
                        "step_description": current_step_for_action, 
                        "action_generated": action_json, 
                        "status": "success" if action_executed_successfully else "failure", 
                        "timestamp": datetime.now().isoformat()
                    }
                else: # Parsing failed or JSON invalid
                    print(f"⚠️ Could not extract a valid JSON action. Raw: '{raw_action_response_text}'. Re-planning.")
                    await _update_gui_state("/state/current_operation", {"text": "Error: Could not understand action. Re-planning."})
                    self.last_action = {
                        "step_index": self.current_step_index,
                        "step_description": current_step_for_action,
                        "action_generated": raw_action_response_text, 
                        "status": "parsing_failure",
                        "timestamp": datetime.now().isoformat()
                    }
                
                await _update_gui_state("last_action_result", {"text": json.dumps(self.last_action, indent=2)})

                if action_executed_successfully:
                    print(f"[ACTION] Successfully executed step {self.current_step_index + 1}: {action_json.get('operation')}")
                    self.current_step_index += 1
                    self.run_capture_on_next_cycle = True 
                else: # Execution failed OR parsing failed
                    print(f"[ACTION_ERROR] Failed to process step {self.current_step_index + 1}. Re-planning.")
                    self.run_capture_on_next_cycle = True 
                    first_cycle_for_anchors = True 
                    self.generated_steps_output = [] # Clear steps to force re-plan

                await asyncio.sleep(self.action_delay)

            except KeyboardInterrupt:
                print("🛑 Automoy operation interrupted by user (KeyboardInterrupt).")
                await _update_gui_state("/state/current_operation", {"text": "Operation stopped by user."})
                break 
            except Exception as e:
                print(f"💥 An unexpected error occurred in operate_loop: {e}")
                import traceback
                traceback.print_exc()
                await _update_gui_state("/state/current_operation", {"text": f"Runtime Error: {e}. Check logs."})
                self.run_capture_on_next_cycle = True
                first_cycle_for_anchors = True
                self.generated_steps_output = []
                await asyncio.sleep(5) 
            finally:                
                pass
        
        print("🏁 Automoy Autonomous Operation Mode exited.")
        await _update_gui_state("/state/current_operation", {"text": "Operation loop ended."})

# ───────────────────────────── Entrypoint ───────────────────────────

def operate_loop(objective: str | None = None, omniparser_instance: OmniParserInterface = None, manage_gui_window_func=None, pause_event: asyncio.Event = None): # Added pause_event
    operator = AutomoyOperator(objective=objective, manage_gui_window_func=manage_gui_window_func, omniparser=omniparser_instance, pause_event=pause_event)
    return operator.operate_loop()


if __name__ == "__main__":
    async def main_test():
        # This is for direct testing of operate.py
        # For this to work, GUI and OmniParser should be running independently or launched by this script.
        
        # Create a dummy manage_gui_window_func for testing if not running through main.py
        async def dummy_manage_gui(action):
            print(f"[DUMMY_GUI_MANAGE] {action}")
            await asyncio.sleep(0.1)

        test_pause_event = asyncio.Event()
        # operator = AutomoyOperator(objective="Open Notepad and type \'Hello from Automoy V2\' and then save the file to desktop as automoy_test.txt and then close notepad.", manage_gui_window_func=dummy_manage_gui)
        
        # For a more complete test, you might want to launch servers here if they aren't up
        # For example, by calling parts of the main.py startup logic or a simplified version.
        
        # Test with a simple objective
        operator = AutomoyOperator(
            objective="What is on the screen?", 
            manage_gui_window_func=dummy_manage_gui,
            pause_event=test_pause_event # Pass the event
        )
        # Manually call startup if you want to test that part too from here
        # await operator.startup_sequence() 
        
        # To test pause, you could clear the event from another task
        # async def toggle_pause():
        #     await asyncio.sleep(10)
        #     print("[TEST_PAUSE] Clearing pause event (pausing).")
        #     test_pause_event.clear()
        #     await asyncio.sleep(10)
        #     print("[TEST_PAUSE] Setting pause event (resuming).")
        #     test_pause_event.set()
        # asyncio.create_task(toggle_pause())

        await operator.operate_loop()

    asyncio.run(main_test())
