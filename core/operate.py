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
        self.vmware = VMWareInterface()
        self.webscraper = WebScrapeInterface()
        self.llm = MainInterface()

    async def startup_sequence(self):
        """Run startup checks and ensure all modules are ready."""
        print("🚀 Automoy Starting Up...")
        # Step 1: OS Environment Check
        print(f"Detected OS: {self.os_interface.os_type}")

        # Step 2: OmniParser Server Check
        if not self.omniparser.check_server_status():
            print("❌ OmniParser Server is not running! Attempting to start it...")
            self.omniparser.start_server()
            await asyncio.sleep(5)

        # Step 3: Confirm VMWare Connectivity
        if not self.vmware.is_vmware_installed():
            print("⚠️ VMWare is not installed or not detected.")

        # Step 4: Confirm Web Scraping Setup
        if not self.webscraper.is_ready():
            print("⚠️ Web Scraper is not properly configured!")

        print("✅ All systems ready!")

    async def operate_loop(self):
        """Main operational loop of Automoy."""
        await self.startup_sequence()
        print("🔥 Entering Automoy Autonomous Operation Mode!")
        while True:
            try:
                # Example: UI Parsing using OmniParser
                ui_data = self.omniparser.capture_and_parse()
                if ui_data:
                    print("🖼️ Extracted UI Data:", ui_data)

                # Example: Web Scraping Execution
                scraped_data = self.webscraper.scrape_page("https://example.com")
                if scraped_data:
                    print("🌐 Scraped Data:", scraped_data)

                # Example: Interacting with LLM for Decisions
                response = self.llm.process_input("Analyze the UI and suggest next steps.")
                print("🤖 LLM Response:", response)

                # Example: Operating System Control
                self.os_interface.press("enter")
                print("⌨️ Simulated Enter Key Press")

                # Example: Handling Virtual Machines
                vm_list = self.vmware.list_vms()
                if vm_list:
                    print("🖥️ Available VMs:", vm_list)

                await asyncio.sleep(5)  # Adjust timing as needed
            except KeyboardInterrupt:
                print("\n🛑 Automoy Operation Halted.")
                break

# Module-level function to provide a uniform interface.
def operate_loop():
    """
    This function instantiates AutomoyOperator and returns its operate_loop coroutine.
    This allows other modules to do:
         from operate import operate_loop
         asyncio.run(operate_loop())
    """
    operator = AutomoyOperator()
    return operator.operate_loop()

# For direct testing:
if __name__ == "__main__":
    asyncio.run(operate_loop())
