import asyncio
import sys
import os
from datetime import datetime
import shutil
import json
import pathlib
from utils.operating_system.os_interface import OSInterface
from utils.omniparser.omniparser_interface import OmniParserInterface
from utils.vmware.vmware_interface import VMWareInterface
from utils.web_scraping.webscrape_interface import WebScrapeInterface
from lm_interfaces.main_interface import MainInterface
from prompts import get_system_prompt
from lm_interface import handle_llm_response
from utils.region.mapper import map_elements_to_coords  # ✅ NEW import

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "config"))
from config import Config

class AutomoyOperator:
    def __init__(self, objective=None):
        self.os_interface = OSInterface()
        self.omniparser = OmniParserInterface()
        self.vmware = VMWareInterface("localhost", "user", "password")
        self.webscraper = WebScrapeInterface()
        self.llm = MainInterface()
        self.config = Config()
        self.model = self.config.get("MODEL", "gpt-4")
        self.objective = objective

    async def startup_sequence(self):
        print("🚀 Automoy Starting Up...")
        print(f"Detected OS: {self.os_interface.os_type}")

        if not self.omniparser._check_server_ready():
            print("❌ OmniParser Server is not running! Attempting to start it…")
            self.omniparser.launch_server()
            await asyncio.sleep(1)

        if not self.vmware.is_vmware_installed():
            print("⚠️ VMWare is not installed or not detected.")

        if not self.webscraper.is_ready():
            print("⚠️ Web Scraper is not properly configured!")

        print("✅ All systems ready!")

    async def operate_loop(self):
        await self.startup_sequence()
        print("🔥 Entering Automoy Autonomous Operation Mode!")

        if not self.objective:
            try:
                self.objective = input("🎯 Enter your automation objective: ")
            except EOFError:
                self.objective = "Default objective - Automate screen flow"
                print("⚠️ No input received. Using default objective.")

        # ─── Screenshot slots ───────────────────────────────────────
        self.current_screenshot: str = None
        self.cached_screenshot: str = None
        self.saved_screenshot: str = None

        # ─── Remember last action for prompt context only ────────────
        self.last_action: dict = None

        while True:
            try:
                # ─── Take initial screenshot / parse UI if needed ─────────
                if not self.coords:
                    self.current_screenshot = self.os_interface.take_screenshot("automoy_current.png")
                    ui_data = self.omniparser.parse_screenshot(self.current_screenshot)
                    self.coords = map_elements_to_coords(ui_data, self.current_screenshot)
                    print("📸 Initial screenshot taken & UI parsed.")

                # ─── Build system + history + UI prompt ───────────────────
                system_prompt = get_system_prompt(self.model, self.objective)
                import json
                ui_json = json.dumps(self.coords, indent=2)
                history = (
                    f"Last action: {json.dumps(self.last_action)}"
                    if self.last_action else
                    "No previous action."
                )

                messages = [
                    {"role": "system", "content": self.objective},
                    {"role": "system", "content": system_prompt},
                    {"role": "system", "content": history},
                    {
                        "role": "user",
                        "content": (
                            "Here is the current UI context (parsed icons, text, coords):\n"
                            f"```\n{ui_json}\n```\n"
                            "Analyze this UI and suggest the next step (use only one JSON action)."
                        )
                    }
                ]

                # ─── Get LLM’s single JSON action ─────────────────────────
                response, _, _ = await self.llm.get_next_action(
                    model=self.model,
                    messages=messages,
                    objective=self.objective,
                    session_id="automoy-session-1",
                    screenshot_path=self.current_screenshot
                )
                print("🧬 LLM Response:", response)

                # ─── Handle special screenshot ops first ──────────────────
                if response and isinstance(response[0], dict):
                    op = response[0].get("operation")

                    if op == "take_screenshot":
                        # rotate: current → cached, drop oldest saved
                        import os
                        if self.cached_screenshot and os.path.exists(self.cached_screenshot):
                            os.remove(self.cached_screenshot)
                        self.cached_screenshot = self.current_screenshot
                        self.current_screenshot = self.os_interface.take_screenshot("automoy_current.png")
                        ui_data = self.omniparser.parse_screenshot(self.current_screenshot)
                        self.coords = map_elements_to_coords(ui_data, self.current_screenshot)
                        print("📸 New screenshot taken & UI parsed.")
                        self.last_action = response[0]
                        continue

                    if op == "save_screenshot":
                        name = response[0].get("name")
                        if name:
                            import shutil
                            shutil.copy(self.current_screenshot, name)
                            self.saved_screenshot = name
                            print(f"💾 Screenshot saved as {name}.")
                        self.last_action = response[0]
                        continue

                    if op == "open_screenshot":
                        name = response[0].get("name") or response[0].get("named")
                        target = {
                            "current_screenshot": self.current_screenshot,
                            "cached_screenshot": self.cached_screenshot,
                        }.get(name, None) or self.saved_screenshot
                        if target:
                            import subprocess
                            subprocess.Popen(["start", target], shell=True)
                            print(f"🔍 Opened screenshot {target}.")
                        else:
                            print("⚠️ No such screenshot to open.")
                        self.last_action = response[0]
                        continue

                # ─── Execute every other operation ────────────────────────
                if response and isinstance(response[0], dict):
                    handle_llm_response(
                        response,
                        self.os_interface,
                        parsed_ui=self.coords,
                        screenshot_path=self.current_screenshot
                    )
                    self.last_action = response[0]

                # ─── Optionally show VMs ─────────────────────────────────
                vm_list = self.vmware.list_vms()
                if vm_list:
                    print("🖥️ Available VMs:", vm_list)

                await asyncio.sleep(5)

            except KeyboardInterrupt:
                print("\n🛑 Automoy Operation Halted.")
                break

def operate_loop(objective=None):
    operator = AutomoyOperator(objective=objective)
    return operator.operate_loop()

if __name__ == "__main__":
    asyncio.run(operate_loop())