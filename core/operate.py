import asyncio
import time
import sys
import pathlib
from utils.operating_system.os_interface import OSInterface
from utils.omniparser.omniparser_interface import OmniParserInterface
from utils.vmware.vmware_interface import VMWareInterface
from utils.web_scraping.webscrape_interface import WebScrapeInterface
from lm_interfaces.main_interface import MainInterface
from prompts import get_system_prompt
from parsing import handle_llm_response

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
            print("❌ OmniParser Server is not running! Attempting to start it...")
            self.omniparser.start_server()
            await asyncio.sleep(5)

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

        while True:
            try:
                screenshot_path = self.os_interface.take_screenshot("automoy_screenshot.png")
                ui_data = self.omniparser.parse_screenshot(screenshot_path)

                if ui_data:
                    print("🖼️ Parsed UI Data:")
                    for entry in ui_data.get("parsed_content_list", []):
                        content = entry.get("content", "")
                        position = entry.get("position", {})
                        x, y = position.get("x"), position.get("y")
                        print(f" - [{entry['type'].upper()}] '{content}' at ({x}, {y})")

                raw_html_text = self.webscraper.fetch_page_content("https://example.com")
                if raw_html_text:
                    print("🌐 Scraped Content Preview:", raw_html_text[:300])

                system_prompt = get_system_prompt(self.model, self.objective)
                messages = [
                    {"role": "system", "content": self.objective},
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Analyze the UI and suggest next steps."}
                ]

                response, _, _ = await self.llm.get_next_action(
                    model=self.model,
                    messages=messages,
                    objective=self.objective,
                    session_id="automoy-session-1",
                    screenshot_path=screenshot_path
                )
                print("🧠 LLM Response:", response)

                handle_llm_response(response, self.os_interface)

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
