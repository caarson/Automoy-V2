import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import random


# Modify initialization to delay browser launch until explicitly requested
class WebScrapeInterface:
    def __init__(self):
        self.driver = None  # Delay initialization of the browser

    def initialize_browser(self):
        if self.driver is None:
            chrome_options = uc.ChromeOptions()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36')

            self.driver = uc.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def simulate_human_behavior(self):
        if self.driver is None:
            raise RuntimeError("Browser not initialized. Call initialize_browser() first.")
        try:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1.5, 3.0))
        except Exception:
            pass

    def google_search(self, query, num_results=10):
        self.initialize_browser()
        self.driver.get(f'https://www.google.com/search?q={query}&num={num_results}')
        time.sleep(random.uniform(2.5, 4.0))
        self.simulate_human_behavior()

        page_source = self.driver.page_source
        if 'Our systems have detected unusual traffic' in page_source or 'id="captcha-form"' in page_source:
            print("[INFO] CAPTCHA or block detected. Switching to Bing search.")
            return self.bing_search(query, num_results)

        results = []
        try:
            search_results = self.driver.find_elements(By.CSS_SELECTOR, 'div.tF2Cxc')
            for result in search_results:
                try:
                    title_elem = result.find_element(By.TAG_NAME, 'h3')
                    link_elem = result.find_element(By.TAG_NAME, 'a')
                    title = title_elem.text if title_elem else 'No title'
                    link = link_elem.get_attribute('href') if link_elem else None
                    if title and link:
                        results.append((title, link))
                except Exception:
                    continue
        except Exception as e:
            print("Error parsing Google results:", e)

        return results

    def bing_search(self, query, num_results=10):
        self.initialize_browser()
        self.driver.get(f'https://www.bing.com/search?q={query}&count={num_results}')
        time.sleep(random.uniform(2.5, 4.0))
        self.simulate_human_behavior()

        results = []
        try:
            search_results = self.driver.find_elements(By.CSS_SELECTOR, 'li.b_algo')
            for result in search_results:
                try:
                    title_elem = result.find_element(By.TAG_NAME, 'h2')
                    link_elem = title_elem.find_element(By.TAG_NAME, 'a')
                    title = title_elem.text if title_elem else 'No title'
                    link = link_elem.get_attribute('href') if link_elem else None
                    if title and link:
                        results.append((title, link))
                except Exception:
                    continue
        except Exception as e:
            print("Error parsing Bing results:", e)

        return results

    def fetch_page_content(self, url, max_chars=2000):
        try:
            self.initialize_browser()
            self.driver.get(url)
            time.sleep(random.uniform(2.5, 4.5))
            self.simulate_human_behavior()
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator=' ', strip=True)
            return text[:max_chars]
        except Exception as e:
            print("Error fetching page content:", e)
            return ""

    def close(self):
        if self.driver is not None:
            self.driver.quit()
            self.driver = None

    def is_ready(self):
        """Check if the browser driver is initialized and ready."""
        return self.driver is not None


# Interactive CLI
if __name__ == "__main__":
    interface = WebScrapeInterface()
    last_results = []
    try:
        while True:
            user_input = input("Enter your search query (or M# to read from previous result, or Q to quit): ").strip()
            if user_input.upper() == "Q":
                break
            elif user_input.upper().startswith('M') and user_input[1:].isdigit():
                idx = int(user_input[1:]) - 1
                if 0 <= idx < len(last_results):
                    title, link = last_results[idx]
                    print(f"\nFetching content from: {link}")
                    page_content = interface.fetch_page_content(link)
                    print(f"\n--- {title} ---\n")
                    print(page_content)
                else:
                    print("[ERROR] Invalid selection.")
                continue
            else:
                results = interface.google_search(user_input)
                last_results = results
                print("\nSearch Results:")
                for i, (title, link) in enumerate(results):
                    print(f"{i+1}. {title}\n   {link}\n")

                if results:
                    title, link = results[0]
                    print(f"\nAuto-previewing first result: {title}")
                    page_content = interface.fetch_page_content(link)
                    print(f"\n--- Preview ---\n{page_content}\n")
    except KeyboardInterrupt:
        print("\n[INFO] User terminated.")
    finally:
        interface.close()
