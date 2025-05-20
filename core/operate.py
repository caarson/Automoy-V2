import asyncio
import sys
import os
import re
import json
from datetime import datetime
import shutil
import pathlib
import string
import subprocess
import requests
import socket
import psutil
import pygetwindow as gw  # New import for window management

# Ensure the project root is added to the Python path
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Adjust imports to use absolute paths consistently
from core.utils.omniparser.omniparser_interface import OmniParserInterface
from core.utils.operating_system.os_interface import OSInterface
from core.utils.vmware.vmware_interface import VMWareInterface
from core.utils.web_scraping.webscrape_interface import WebScrapeInterface
from core.utils.region.mapper import map_elements_to_coords
from core.prompts.prompts import get_system_prompt

# 👉 Integrated LLM interface (merged MainInterface + handle_llm_response)
from core.lm.lm_interface import MainInterface, handle_llm_response
from core.environmental.anchor.desktop_anchor_point import show_desktop

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "config"))
from config import Config


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


class AutomoyOperator:
    """Central orchestrator for Automoy autonomous operation."""

    def __init__(self, objective: str | None = None):
        self.os_interface = OSInterface()
        self.omniparser = OmniParserInterface()
        self.vmware = VMWareInterface("localhost", "user", "password")
        self.webscraper = WebScrapeInterface()
        self.llm = MainInterface()

        self.config = Config()
        # Use the correct model for the selected API source
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
        

        # ─── Runtime state ────────────────────────────────────────────
        self.current_screenshot: str | None = None
        self.cached_screenshot: str | None = None
        self.saved_screenshot: str | None = None
        self.coords: dict | None = None  # Parsed UI cache
        self.last_action: dict | None = None  # For prompt context only

    # ───────────────────────────── Startup ───────────────────────────
    async def startup_sequence(self):
        print("🚀 Automoy Starting Up…")
        print(f"Detected OS: {self.os_interface.os_type}")

        # --- Launch GUI if not already running ---
        try:
            if not is_port_in_use(8000) and not is_process_running("python.exe"):
                print("[GUI] Launching Web GUI on http://127.0.0.1:8000 ...")
                subprocess.Popen([sys.executable, os.path.join("gui", "gui.py")])
                # Wait up to 30 seconds for GUI to start
                for _ in range(30):
                    if is_port_in_use(8000):
                        print("[GUI] Web GUI is now running.")
                        break
                    await asyncio.sleep(1)
                else:
                    print("[GUI] ERROR: GUI did not start in time. Exiting Automoy.")
                    sys.exit(1)
            else:
                print("[GUI] Web GUI already running.")
        except Exception as e:
            print(f"[GUI] ERROR: {e}")
            sys.exit(1)

        if not self.omniparser._check_server_ready():
            print("❌ OmniParser server is not running! Attempting to start it…")
            self.omniparser.launch_server()
            await asyncio.sleep(1)

        if not self.vmware.is_vmware_installed():
            print("⚠️ VMWare is not installed or not detected.")

        if not self.webscraper.is_ready():
            print("⚠️ Web scraper is not properly configured!")

        print("✅ All systems ready!")

    # ───────────────────────────── Loop ──────────────────────────────
    async def operate_loop(self):
        await self.startup_sequence()
        print("🔥 Entering Automoy Autonomous Operation Mode!")

        # Wait for the objective to be set by the GUI (log only once)
        waiting_logged = False
        while not self.objective:
            if not waiting_logged:
                print("[WAIT] Waiting for objective from GUI...")
                waiting_logged = True
            await asyncio.sleep(1)
        print(f"[INFO] Objective received from GUI: {self.objective}")

        first_run = True
        while True:
            try:
                # ─── Take initial screenshot & parse UI once ────────────
                if self.coords is None:
                    # If desktop anchor is enabled, show desktop before screenshot
                    if self.desktop_anchor_point and first_run:
                        print("[ANCHOR] Showing desktop (desktop anchor enabled)...")
                        show_desktop()
                        await asyncio.sleep(1)  # Give time for UI to update
                        # --- Show GUI after anchor point ---
                        try:
                            requests.get("http://127.0.0.1:8000/show_gui", timeout=1)
                            print("[GUI] GUI shown after anchor point.")
                        except Exception as e:
                            print(f"[GUI] Could not show GUI: {e}")
                        first_run = False
                    self.current_screenshot = self.os_interface.take_screenshot("automoy_current.png")

                    # Restore GUI window after screenshot completed
                    try:
                        windows = gw.getWindowsWithTitle("Automoy")
                        if windows:
                            win = windows[0]
                            win.restore()
                            win.moveTo(0, 0)
                            print("[INFO] GUI window restored at top-left after screenshot.")
                    except Exception as e:
                        print(f"[ERROR] Failed to restore GUI window: {e}")

                    ui_data = self.omniparser.parse_screenshot(self.current_screenshot)

                    # --- Write OmniParser output to debug log ---
                    try:
                        logs_dir = pathlib.Path("debug/logs/omniparser/output")
                        logs_dir.mkdir(parents=True, exist_ok=True)
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        log_path = logs_dir / f"omniparser_{ts}.txt"
                        with open(log_path, "w", encoding="utf-8") as f:
                            f.write(json.dumps(ui_data, indent=2, ensure_ascii=False))
                        print(f"[DEBUG] OmniParser output written to {log_path}")
                    except Exception as e:
                        print(f"[ERROR] Could not write OmniParser output log: {e}")

                    if ui_data is None:  # Guard against parse failures
                        print("❌ parse_screenshot failed (HTTP 500). Retrying…")
                        await asyncio.sleep(1)
                        continue

                    # --- Clean the OmniParser output for LLM ---
                    BASE64_RE = re.compile(r'^[A-Za-z0-9+/=\s]{100,}$')
                    def clean_json(obj):
                        if isinstance(obj, dict):
                            return {k: clean_json(v) for k, v in obj.items() if not (isinstance(v, str) and (len(v) > 200 and BASE64_RE.match(v)))}
                        elif isinstance(obj, list):
                            return [clean_json(x) for x in obj]
                        elif isinstance(obj, str):
                            # Remove non-printable and non-ASCII characters
                            return ''.join(c for c in obj if c in string.printable and ord(c) < 128)
                        else:
                            return obj
                    cleaned_ui_data = clean_json(ui_data)

                    self.coords = map_elements_to_coords(cleaned_ui_data, self.current_screenshot)
                    print("📸 Initial screenshot taken & UI parsed.")
                    print("🧠 Parsed UI Coord Map:", json.dumps(self.coords, indent=2))

                # ─── Get general screen description from LLM ───────────
                ui_json = json.dumps(self.coords, indent=2)
                screen_description = await self.get_screen_description(ui_json)
                print("[DEBUG] Screen description for prompt:", screen_description)

                # Only display the current screen state description if any anchor point config is enabled, and only on first run
                if self.last_action is None:
                    screen_state_lines = []
                    if self.desktop_anchor_point:
                        screen_state_lines.append("The screen is at the Windows desktop. No windows are open or focused.")
                    if self.prompt_anchor_point:
                        screen_state_lines.append("The screen is in the state described by the following prompt.")
                    if self.vllm_anchor_point:
                        screen_state_lines.append("The screen is in a virtualized environment anchor state.")
                    if self.anchor_prompt:
                        screen_state_lines.append(f"Screen state description: {self.anchor_prompt.strip()}")

                    if screen_state_lines:
                        screen_state_info = "\n".join(screen_state_lines)
                        screen_state_section = (
                            "Current screen state:\n"
                            f"```\n{screen_state_info}\n```\n"
                        )
                    else:
                        screen_state_section = ""
                else:
                    screen_state_section = ""

                user_content = (
                    "Here is a high-level description of the current UI context, as interpreted by an expert:\n"
                    f"{screen_description}\n"
                    f"{screen_state_section}"
                    "Analyze this UI and suggest the next step (use only one JSON action)."
                )
                system_prompt = get_system_prompt(self.model, self.objective)
                messages = [
                    {"role": "user", "content": user_content},
                    {"role": "system", "content": system_prompt},
                ]

                # ─── Query LLM ────────────────────────────────────────
                response_text, _, _ = await self.llm.get_next_action(
                    model=self.model,
                    messages=messages,
                    objective=self.objective,
                    session_id="automoy-session-1",
                    screenshot_path=self.current_screenshot,
                )

                # ─── Extract first action dict for special ops ────────
                first_action = None
                code_block = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
                if code_block:
                    try:
                        actions = json.loads(code_block.group(1))
                        if actions:
                            first_action = actions[0]
                    except json.JSONDecodeError:
                        pass

                # ─── Handle screenshot-related operations before exec ─
                if isinstance(first_action, dict):
                    op = first_action.get("operation")

                    # --- Take a fresh screenshot ---------------------
                    if op == "take_screenshot":
                        if self.cached_screenshot and os.path.exists(self.cached_screenshot):
                            os.remove(self.cached_screenshot)
                        self.cached_screenshot = self.current_screenshot
                        self.current_screenshot = self.os_interface.take_screenshot("automoy_current.png")
                        ui_data = self.omniparser.parse_screenshot(self.current_screenshot)
                        self.coords = map_elements_to_coords(ui_data, self.current_screenshot)
                        print("📸 New screenshot taken & UI parsed.")
                        self.last_action = first_action
                        continue

                    # --- Save current screenshot ---------------------
                    if op == "save_screenshot":
                        name = first_action.get("name")
                        if name:
                            shutil.copy(self.current_screenshot, name)
                            self.saved_screenshot = name
                            print(f"💾 Screenshot saved as {name}.")
                        self.last_action = first_action
                        continue

                    # --- Open a screenshot ---------------------------
                    if op == "open_screenshot":
                        name = first_action.get("name") or first_action.get("named")
                        target = {
                            "current_screenshot": self.current_screenshot,
                            "cached_screenshot": self.cached_screenshot,
                        }.get(name) or self.saved_screenshot
                        if target:
                            if os.name == "nt":
                                os.startfile(target)  # type: ignore[attr-defined]
                            else:
                                asyncio.create_subprocess_exec("xdg-open", target)
                            print(f"🔍 Opened screenshot {target}.")
                        else:
                            print("⚠️ No such screenshot to open.")
                        self.last_action = first_action
                        continue

                # ─── Execute general UI action via OSInterface ───────
                handle_llm_response(
                    response_text,
                    self.os_interface,
                    parsed_ui=self.coords,
                    screenshot_path=self.current_screenshot,
                )
                self.last_action = first_action

                # ─── Optionally show available VMs ───────────────────
                vm_list = self.vmware.list_vms()
                if vm_list:
                    print("🖥️ Available VMs:", vm_list)

                await asyncio.sleep(5)

            except KeyboardInterrupt:
                print("\n🛑 Automoy Operation Halted.")
                break

    async def get_screen_description(self, ui_json):
        """Send parsed UI JSON and anchor point info to the LLM for a general screen description."""
        anchor_lines = []
        if self.desktop_anchor_point:
            anchor_lines.append("The screen is at the Windows desktop. No windows are open or focused.")
        if self.prompt_anchor_point:
            anchor_lines.append("The screen is in the state described by the following prompt.")
        if self.vllm_anchor_point:
            anchor_lines.append("The screen is in a virtualized environment anchor state.")
        if self.anchor_prompt:
            anchor_lines.append(f"Screen state description: {self.anchor_prompt.strip()}")
        anchor_context = "\n".join(anchor_lines)

        prompt = (
            "You are an expert at interpreting Windows UI layouts. "
            "Given the following parsed UI JSON and anchor point context, "
            "write a concise, high-level description of the current screen. "
            "Focus on visible windows, main UI elements, and anything interactive. "
            "Do NOT repeat the raw JSON.\n\n"
            f"Anchor point context:\n{anchor_context}\n\n"
            f"Parsed UI JSON:\n{ui_json}\n"
        )
        messages = [
            {"role": "user", "content": prompt}
        ]
        description, _, _ = await self.llm.get_next_action(
            model=self.model,
            messages=messages,
            objective="Describe the current Windows screen for Automoy context.",
            session_id="automoy-screen-desc",
            screenshot_path=self.current_screenshot,
        )
        return description.strip()


# ───────────────────────────── Entrypoint ───────────────────────────

def operate_loop(objective: str | None = None):
    operator = AutomoyOperator(objective)
    return operator.operate_loop()


if __name__ == "__main__":
    asyncio.run(operate_loop())
