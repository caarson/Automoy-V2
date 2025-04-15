import asyncio
import time
from utils.operating_system.os_interface import OSInterface
from utils.omniparser.omniparser_interface import OmniParserInterface
from utils.vmware.vmware_interface import VMWareInterface
from utils.web_scraping.webscrape_interface import WebScrapeInterface
from lm_interfaces.main_interface import MainInterface

class AutomoyOperator:
    def __init__(self):
        """Initialize Automoy's core interfaces."""
        self.os_interface = OSInterface()
        self.omniparser = OmniParserInterface()
        self.vmware = VMWareInterface("localhost", "user", "password")  # replace with real creds if needed
        self.webscraper = WebScrapeInterface()
        self.llm = MainInterface()

    async def startup_sequence(self):
        """Run startup checks and ensure all modules are ready."""
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
        """Main operational loop of Automoy."""
        await self.startup_sequence()
        print("🔥 Entering Automoy Autonomous Operation Mode!")

        while True:
            try:
                # 1. Screenshot -> OmniParser -> Click Buttons
                screenshot_path = self.os_interface.take_screenshot("automoy_screenshot.png")
                ui_data = self.omniparser.parse_screenshot(screenshot_path)

                if ui_data:
                    print("🖼️ Parsed UI Data:")
                    for entry in ui_data.get("parsed_content_list", []):
                        content = entry.get("content", "")
                        position = entry.get("position", {})
                        x, y = position.get("x"), position.get("y")

                        print(f" - [{entry['type'].upper()}] '{content}' at ({x}, {y})")

                        if entry["type"] == "button":
                            self.os_interface.move_mouse(x, y, duration=0.3)
                            self.os_interface.click_mouse()
                            time.sleep(0.5)

                # 2. Web scraping (real logic)
                raw_html_text = self.webscraper.fetch_page_content("https://example.com")
                if raw_html_text:
                    print("🌐 Scraped Content Preview:", raw_html_text[:300])

                # 3. Ask LLM (placeholder)
                messages = ["Analyze the UI and suggest next steps."]
                objective = "Autonomously control and interpret UI"
                session_id = "session-001"
                screenshot_path = "automoy_screenshot.png"

                response, _, _ = await self.llm.get_next_action(
                    model="gpt-4",
                    messages=messages,
                    objective=objective,
                    session_id=session_id,
                    screenshot_path=screenshot_path
                )
                print("🤖 LLM Response:", response)

                # 4. Basic OS automation
                self.os_interface.press("enter")
                print("⌨️ Simulated Enter Key Press")

                # 5. VMWare Integration (optional)
                vm_list = self.vmware.list_vms()
                if vm_list:
                    print("🖥️ Available VMs:", vm_list)

                await asyncio.sleep(5)

            except KeyboardInterrupt:
                print("\n🛑 Automoy Operation Halted.")
                break

# Module-level callable for external run
def operate_loop():
    operator = AutomoyOperator()
    return operator.operate_loop()

if __name__ == "__main__":
    asyncio.run(operate_loop())
