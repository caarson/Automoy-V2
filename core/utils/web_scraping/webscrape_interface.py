import requests
from bs4 import BeautifulSoup
import time

class WebScrapeInterface:
    def __init__(self):
        self.headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/91.0.4472.124 Safari/537.36")
        }
    
    def google_search(self, query, num_results=10):
        search_url = f"https://www.google.com/search?q={query}&num={num_results}"
        response = requests.get(search_url, headers=self.headers)
    
        if response.status_code != 200:
            print("Error fetching search results")
            return []
    
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for g in soup.find_all('div', class_='tF2Cxc'):
            link = g.find('a')['href']
            title = g.find('h3').text if g.find('h3') else "No title available"
            results.append((title, link))
    
        return results
    
    def fetch_page_content(self, url):
        response = requests.get(url, headers=self.headers)
    
        if response.status_code != 200:
            print("Error fetching page content")
            return ""
    
        soup = BeautifulSoup(response.text, "html.parser")
        return soup.get_text()
    
    def is_ready(self):
        # Stub logic for now
        return True

# For testing the class:
if __name__ == "__main__":
    interface = WebScrapeInterface()
    search_query = "los angeles weather"
    results = interface.google_search(search_query)
    
    print("Search Results:")
    for idx, (title, link) in enumerate(results):
        print(f"{idx + 1}. {title} - {link}")
    
    # Automatically select a result containing "weather"
    selected_link = None
    for title, link in results:
        if "weather" in title.lower():
            selected_link = link
            break
    
    if selected_link:
        print("\nFetching content from:", selected_link)
        page_content = interface.fetch_page_content(selected_link)
        print("\nPage Content (first 1000 characters):\n", page_content[:1000])
    else:
        print("\nNo relevant weather link found.")
