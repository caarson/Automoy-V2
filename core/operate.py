import asyncio
import sys
import os
import re
import json
from datetime import datetime
import shutil
import pathlib

from utils.operating_system.os_interface import OSInterface
from utils.omniparser.omniparser_interface import OmniParserInterface
from utils.vmware.vmware_interface import VMWareInterface
from utils.web_scraping.webscrape_interface import WebScrapeInterface
from utils.region.mapper import map_elements_to_coords
from core.prompts.prompts import get_system_prompt

# 👉 Integrated LLM interface (merged MainInterface + handle_llm_response)
from core.lm.lm_interface import MainInterface, handle_llm_response

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "config"))
from config import Config


class AutomoyOperator:
    """Central orchestrator for Automoy autonomous operation."""

    def __init__(self, objective: str | None = None):
        self.os_interface = OSInterface()
        self.omniparser = OmniParserInterface()
        self.vmware = VMWareInterface("localhost", "user", "password")
        self.webscraper = WebScrapeInterface()
        self.llm = MainInterface()

        self.config = Config()
        self.model = self.config.get("MODEL", "gpt-4")
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

        if not self.objective:
            try:
                self.objective = input("🎯 Enter your automation objective: ")
            except EOFError:
                self.objective = "Default objective – Automate screen flow"
                print("⚠️ No input received. Using default objective.")

        while True:
            try:
                # ─── Take initial screenshot & parse UI once ────────────
                if self.coords is None:
                    self.current_screenshot = self.os_interface.take_screenshot("automoy_current.png")
                    ui_data = self.omniparser.parse_screenshot(self.current_screenshot)

                    if ui_data is None:  # Guard against parse failures
                        print("❌ parse_screenshot failed (HTTP 500). Retrying…")
                        await asyncio.sleep(1)
                        continue

                    self.coords = map_elements_to_coords(ui_data, self.current_screenshot)
                    print("📸 Initial screenshot taken & UI parsed.")
                    print("🧠 Parsed UI Coord Map:", json.dumps(self.coords, indent=2))

                # ─── Build conversation for the LLM ───────────────────
                ui_json = json.dumps(self.coords, indent=2)

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
                    "Here is the current UI context (parsed icons, text, coords):\n"
                    f"```\n{ui_json}\n```\n"
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


# ───────────────────────────── Entrypoint ───────────────────────────

def operate_loop(objective: str | None = None):
    operator = AutomoyOperator(objective)
    return operator.operate_loop()


if __name__ == "__main__":
    asyncio.run(operate_loop())
