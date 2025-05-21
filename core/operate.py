import asyncio
import json
import os
import pathlib
import re
import socket
import subprocess
import sys
from datetime import datetime

import psutil
import requests # Added for _update_gui_state

# Ensure the project root is added to the Python path
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))) # Already there, but ensure it's correct

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

# Corrected import path for prompts assuming 'prompts' is a module in 'core'
from core.prompts.prompts import (
    VISUAL_ANALYSIS_PROMPT,
    THINKING_PROCESS_PROMPT,
    STEPS_GENERATION_PROMPT,
    get_system_prompt # DEFAULT_PROMPT is used by get_system_prompt
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

    def __init__(self, objective: str | None = None, manage_gui_window_func=None, omniparser: OmniParserInterface = None): # Added manage_gui_window_func
        self.os_interface = OSInterface()
        self.omniparser = OmniParserInterface()
        self.vmware = VMWareInterface("localhost", "user", "password")
        self.webscraper = WebScrapeInterface()
        self.llm = MainInterface()
        self.manage_gui_window_func = manage_gui_window_func # Store the function
        self.omniparser_instance = omniparser # Store the OmniParserInterface instance

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
        self.action_delay = self.config.get("ACTION_DELAY", 2.0) # Load action delay

        # ─── Runtime state ────────────────────────────────────────────
        self.current_screenshot: str | None = None
        # self.cached_screenshot: str | None = None # Not used in new flow
        # self.saved_screenshot: str | None = None # Not used in new flow
        self.coords: dict | None = None  # Parsed UI cache
        self.last_action: dict | None = None
        self.current_step_index = 0 # To track progress through generated steps
        
        # Variables to store LLM reasoning stages for GUI update
        self.visual_analysis_output: str = ""
        self.thinking_process_output: str = ""
        self.generated_steps_output: list[str] = []

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
        # However, for standalone testing of operate.py, we might call it here.
        # For now, assuming main.py handles startup.
        # await self.startup_sequence() 

        print("🔥 Entering Automoy Autonomous Operation Mode!")

        if not self.objective:
            print("[ERROR] Objective not set for AutomoyOperator. Exiting operate_loop.")
            # Update GUI about the error before returning
            await _update_gui_state("/state/current_operation", {"text": "Error: Objective not set."})
            await _update_gui_state("/state/status", {"status": "Error"}) # Assuming a /state/status endpoint
            return
        
        print(f"[INFO] Objective received: {self.objective}")

        await _update_gui_state("/state/clear_all_operational_data", {})
        await _update_gui_state("/state/objective", {"text": self.objective})


        first_cycle_for_anchors = True

        while True: # Main operational cycle
            try:
                # 0. Update GUI: Past Operation (from previous loop iteration's last_action)
                if self.last_action:
                    past_op_text = json.dumps(self.last_action)
                    await _update_gui_state("/state/past_operation", {"text": past_op_text})


                # 1. CAPTURE AND PARSE CURRENT SCREEN STATE
                await _update_gui_state("/state/current_operation", {"text": "Preparing for screen capture..."})
                print("[STATE] Preparing for screen capture...")
                
                if self.desktop_anchor_point and first_cycle_for_anchors:
                    print("[ANCHOR] Applying desktop anchor point...")
                    show_desktop()
                    await asyncio.sleep(0.5) # Reduced from 1.5, as main delay is consolidated
                
                if self.manage_gui_window_func:
                    print("[OPERATE_LOOP] Hiding windows...")
                    await self.manage_gui_window_func("hide")
                    await asyncio.sleep(0.5) # Pause for windows to hide

                print("[OPERATE_LOOP] Setting black background for screenshot.")
                DesktopUtils.set_desktop_background_solid_color(0,0,0)
                await asyncio.sleep(0.1) # Brief pause for background to apply
                
                await _update_gui_state("/state/current_operation", {"text": "Capturing and parsing screen..."})
                print("[STATE] Capturing and parsing current screen state...")
                self.current_screenshot = self.os_interface.take_screenshot("automoy_current.png")
                await _update_gui_state("/state/screenshot_processed", {"processed": False})

                # Use the stored OmniParser instance
                ui_data = self.omniparser_instance.parse_screenshot(self.current_screenshot)
                
                print("[OPERATE_LOOP] Restoring original background post-screenshot.")
                DesktopUtils.restore_desktop_background_settings()
                await asyncio.sleep(0.1) # Brief pause for background to restore

                if self.manage_gui_window_func:
                    print("[OPERATE_LOOP] Restoring windows post-screenshot.")
                    await self.manage_gui_window_func("show")
                    await asyncio.sleep(0.2) # Brief pause for windows to show

                if ui_data is None:
                    print("❌ OmniParser failed to parse screenshot. Retrying after delay...")
                    await _update_gui_state("/state/current_operation", {"text": "OmniParser failed. Retrying..."})
                    await asyncio.sleep(3)
                    continue
                
                await _update_gui_state("/state/screenshot_processed", {"processed": True}) # GUI notified: processing done
                
                try:
                    logs_dir = pathlib.Path("debug/logs/omniparser/output")
                    logs_dir.mkdir(parents=True, exist_ok=True)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    log_path = logs_dir / f"omniparser_{ts}.json"
                    with open(log_path, "w", encoding="utf-8") as f:
                        json.dump(ui_data, f, indent=2)
                    print(f"[DEBUG] OmniParser output written to {log_path}")
                except Exception as e:
                    print(f"[ERROR] Could not write OmniParser output log: {e}")

                cleaned_ui_data = clean_json_data(ui_data)
                self.coords = map_elements_to_coords(cleaned_ui_data, self.current_screenshot)
                ui_json_for_llm = json.dumps(self.coords, indent=2)
                print("[STATE] Screen state captured and parsed.")

                # 2. VISUAL ANALYSIS STAGE
                await _update_gui_state("/state/current_operation", {"text": "Analyzing screen (Visual)..."})
                print("[LLM] Performing Visual Analysis...")
                screenshot_context_for_llm = "A screenshot is also available for context." if self.current_screenshot else ""
                visual_prompt = VISUAL_ANALYSIS_PROMPT.format(
                    ui_json=ui_json_for_llm,
                    screenshot_context=screenshot_context_for_llm
                )
                messages_visual = [{"role": "user", "content": visual_prompt}]
                self.visual_analysis_output, _, _ = await self.llm.get_next_action(
                    model=self.model, messages=messages_visual, objective="Describe the current screen.",
                    session_id="automoy-visual", screenshot_path=self.current_screenshot
                )
                self.visual_analysis_output = self.visual_analysis_output.strip()
                await _update_gui_state("/state/visual", {"text": self.visual_analysis_output})
                print(f"[VISUAL] LLM Screen Description: {self.visual_analysis_output}")

                # 3. THINKING PROCESS STAGE
                await _update_gui_state("/state/current_operation", {"text": "Formulating plan (Thinking)..."})
                print("[LLM] Performing Thinking Process...")
                thinking_prompt_context = self.visual_analysis_output # Use visual analysis output
                if first_cycle_for_anchors:
                    anchor_context_lines = []
                    if self.desktop_anchor_point:
                        anchor_context_lines.append("The screen was initially at the Windows desktop (desktop anchor was applied).")
                    if self.prompt_anchor_point:
                        anchor_context_lines.append(f"An initial prompt anchor was set: \'{self.anchor_prompt.strip()}\'")
                    if self.vllm_anchor_point: 
                        anchor_context_lines.append("The system started in a VLLM-specific anchor state.")
                    if anchor_context_lines:
                        thinking_prompt_context += "\\n\\nInitial Anchor Context (first cycle only):\\n" + "\\n".join(anchor_context_lines)
                
                thinking_prompt = THINKING_PROCESS_PROMPT.format(
                    objective=self.objective, screen_description=thinking_prompt_context
                )
                messages_thinking = [{"role": "user", "content": thinking_prompt}]
                self.thinking_process_output, _, _ = await self.llm.get_next_action(
                    model=self.model, messages=messages_thinking, objective="Reason about the user\'s objective and current screen.",
                    session_id="automoy-thinking"
                )
                self.thinking_process_output = self.thinking_process_output.strip()
                await _update_gui_state("/state/thinking", {"text": self.thinking_process_output})
                print(f"[THINKING] LLM Output: {self.thinking_process_output}")

                # 4. STEPS GENERATION STAGE
                await _update_gui_state("/state/current_operation", {"text": "Generating steps for plan..."})
                print("[LLM] Performing Steps Generation...")
                steps_prompt = STEPS_GENERATION_PROMPT.format(
                    objective=self.objective, thinking_output=self.thinking_process_output, screen_description=self.visual_analysis_output
                )
                messages_steps = [{"role": "user", "content": steps_prompt}]
                steps_raw_output, _, _ = await self.llm.get_next_action(
                    model=self.model, messages=messages_steps, objective="Generate actionable steps.",
                    session_id="automoy-steps"
                )
                self.generated_steps_output = [step.strip() for step in re.findall(r"^\\d+\\.\\s*(.*)", steps_raw_output, re.MULTILINE)]
                if not self.generated_steps_output and steps_raw_output.strip(): 
                    self.generated_steps_output = [line.strip().lstrip("0123456789.- ").rstrip() for line in steps_raw_output.strip().split('\\n') if line.strip().lstrip("0123456789.- ").rstrip()]

                if not self.generated_steps_output:
                    print("[ERROR] No steps generated by LLM. Will retry cycle.")
                    await _update_gui_state("/state/current_operation", {"text": "Failed to generate steps. Retrying..."})
                    await asyncio.sleep(self.action_delay)
                    first_cycle_for_anchors = False 
                    continue
                await _update_gui_state("/state/steps", {"steps": self.generated_steps_output}) # Send as list
                print(f"[STEPS] LLM Generated Steps: {self.generated_steps_output}")

                # 5. ACTION EXECUTION LOOP
                for i, current_step_objective in enumerate(self.generated_steps_output):
                    self.current_step_index = i
                    current_operation_text = f"Executing Step {i+1}/{len(self.generated_steps_output)}: {current_step_objective}"
                    print(f"[ACTION] {current_operation_text}")
                    await _update_gui_state("/state/current_operation", {"text": current_operation_text})
                    
                    action_system_prompt = get_system_prompt(self.model, current_step_objective)
                    
                    action_user_content = (
                        "Current UI Description (from Visual Analysis):\\n"
                        f"{self.visual_analysis_output}\\n\\n" # Use the stored visual analysis
                        "Objective for this specific step:\\n"
                        f"{current_step_objective}\\n\\n"
                        "Provide a single JSON action to achieve this step based on the UI description."
                    )
                    messages_action = [
                        {"role": "user", "content": action_user_content},
                        {"role": "system", "content": action_system_prompt},
                    ]

                    action_response_text, _, _ = await self.llm.get_next_action(
                        model=self.model, messages=messages_action, objective=current_step_objective,
                        session_id="automoy-action", screenshot_path=self.current_screenshot
                    )

                    current_action_details = None
                    code_block = re.search(r"```json\s*(.*?)\s*```", action_response_text, re.DOTALL)
                    if code_block:
                        try:
                            action_json_str = code_block.group(1)
                            parsed_actions = json.loads(action_json_str)
                            if isinstance(parsed_actions, list) and len(parsed_actions) > 0:
                                current_action_details = parsed_actions[0]
                        except json.JSONDecodeError as e:
                            print(f"[ERROR] Failed to decode JSON action: {e}. Raw: {action_json_str}")
                            break 
                    
                    if not current_action_details:
                        print(f"[WARNING] No valid action JSON found for step: {current_step_objective}. LLM Response: {action_response_text[:500]}...")
                        if "done" not in current_step_objective.lower():
                             print("[WARNING] Step was not \'done\' and no action produced. Breaking from steps to re-plan.")
                             break 
                        else: 
                            print("[INFO] Step implies completion, moving to next step or finishing.")
                            if i == len(self.generated_steps_output) -1: 
                                print("[INFO] Last step implied completion. Objective might be complete.")
                                await _update_gui_state("/state/current_operation", {"text": "Objective likely complete."})
                                return 
                            continue 

                    op = current_action_details.get("operation")
                    if op == "take_screenshot":
                        print("[ACTION] Performing \'take_screenshot\' operation...")
                        await _update_gui_state("/state/current_operation", {"text": "Preparing for LLM-invoked screenshot..."})
                        
                        if self.manage_gui_window_func:
                            print("[LLM_ACTION_SCREENSHOT] Hiding windows...")
                            await self.manage_gui_window_func("hide")
                            await asyncio.sleep(0.5) # Pause for windows to hide

                        print("[LLM_ACTION_SCREENSHOT] Setting black background...")
                        DesktopUtils.set_desktop_background_solid_color(0,0,0)
                        await asyncio.sleep(0.1) # Brief pause for background
                        
                        await _update_gui_state("/state/current_operation", {"text": "Taking new screenshot (LLM action)..."})
                        self.current_screenshot = self.os_interface.take_screenshot("automoy_current.png")
                        await _update_gui_state("/state/screenshot_processed", {"processed": False}) 

                        # Use the stored OmniParser instance
                        ui_data_new = self.omniparser_instance.parse_screenshot(self.current_screenshot)

                        print("[LLM_ACTION_SCREENSHOT] Restoring original background...")
                        DesktopUtils.restore_desktop_background_settings()
                        await asyncio.sleep(0.1) # Brief pause
                        
                        if self.manage_gui_window_func:
                            print("[LLM_ACTION_SCREENSHOT] Restoring windows...")
                            await self.manage_gui_window_func("show")
                            await asyncio.sleep(0.2) # Brief pause
                        
                        await _update_gui_state("/state/screenshot_processed", {"processed": True})


                        if ui_data_new:
                            cleaned_ui_data_new = clean_json_data(ui_data_new)
                            self.coords = map_elements_to_coords(cleaned_ui_data_new, self.current_screenshot)
                            ui_json_for_llm_refresh = json.dumps(self.coords, indent=2)
                            
                            await _update_gui_state("/state/current_operation", {"text": "Re-analyzing screen after new screenshot..."})
                            visual_prompt_refresh = VISUAL_ANALYSIS_PROMPT.format(ui_json=ui_json_for_llm_refresh, screenshot_context="A screenshot is also available for context.")
                            messages_visual_refresh = [{"role": "user", "content": visual_prompt_refresh}]
                            
                            self.visual_analysis_output, _, _ = await self.llm.get_next_action( model=self.model, messages=messages_visual_refresh, objective="Describe the current screen (refresh).", session_id="automoy-visual-refresh", screenshot_path=self.current_screenshot)
                            self.visual_analysis_output = self.visual_analysis_output.strip() 
                            await _update_gui_state("/state/visual", {"text": self.visual_analysis_output}) # Update GUI with new visual analysis
                            print(f"[VISUAL REFRESH] Screen Description Updated: {self.visual_analysis_output}")
                        else:
                            print("[ERROR] Failed to parse new screenshot after \'take_screenshot\' action.")
                            await _update_gui_state("/state/current_operation", {"text": "Failed to process new screenshot."})
                        
                        await asyncio.sleep(self.action_delay)
                        continue 

                    elif op == "done":
                        summary = current_action_details.get("summary", "Task complete.")
                        print(f"[ACTION] \'done\' operation received: {summary}. Objective complete.")
                        await _update_gui_state("/state/current_operation", {"text": f"Objective Complete: {summary}"})
                        handle_llm_response(action_response_text, self.os_interface, self.coords, self.current_screenshot)
                        self.last_action = current_action_details # Store "done" as last action
                        return 

                    print(f"[ACTION] Executing operation: {op} with details: {current_action_details}")
                    handle_llm_response(
                        action_response_text, self.os_interface,
                        parsed_ui=self.coords, screenshot_path=self.current_screenshot
                    )
                    self.last_action = current_action_details
                    
                    await asyncio.sleep(self.action_delay)

                print("[INFO] Finished executing current list of steps.")
                first_cycle_for_anchors = False 

            except KeyboardInterrupt:
                print("\\n🛑 Automoy Operation Halted by user.")
                await _update_gui_state("/state/current_operation", {"text": "Operation halted by user."})
                break
            except Exception as e:
                print(f"[ERROR] Unhandled exception in operate_loop: {e}")
                import traceback
                traceback.print_exc()
                await _update_gui_state("/state/current_operation", {"text": f"Error: {e}. Retrying..."})
                print("Retrying main loop after 5 seconds...")
                await asyncio.sleep(5)
                first_cycle_for_anchors = False


# ───────────────────────────── Entrypoint ───────────────────────────

def operate_loop(objective: str | None = None, omniparser_instance: OmniParserInterface = None, manage_gui_window_func=None): # Added manage_gui_window_func
    operator = AutomoyOperator(objective=objective, manage_gui_window_func=manage_gui_window_func, omniparser=omniparser_instance)
    return operator.operate_loop()


if __name__ == "__main__":
    async def main_test():
        # This is for direct testing of operate.py
        # For this to work, GUI and OmniParser should be running independently or launched by this script.
        
        # Create a dummy manage_gui_window_func for testing if not running through main.py
        async def dummy_manage_gui(action):
            print(f"[DUMMY_GUI_MANAGE] {action}")
            await asyncio.sleep(0.1)

        # operator = AutomoyOperator(objective="Open Notepad and type \'Hello from Automoy V2\' and then save the file to desktop as automoy_test.txt and then close notepad.", manage_gui_window_func=dummy_manage_gui)
        
        # For a more complete test, you might want to launch servers here if they aren't up
        # For example, by calling parts of the main.py startup logic or a simplified version.
        
        # Test with a simple objective
        operator = AutomoyOperator(
            objective="What is on the screen?", 
            manage_gui_window_func=dummy_manage_gui
        )
        # Manually call startup if you want to test that part too from here
        # await operator.startup_sequence() 
        await operator.operate_loop()

    asyncio.run(main_test())
