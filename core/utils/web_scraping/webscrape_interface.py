import requests
from bs4 import BeautifulSoup
import time

def google_search(query, num_results=10):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    search_url = f"https://www.google.com/search?q={query}&num={num_results}"
    response = requests.get(search_url, headers=headers)
    
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

def fetch_page_content(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print("Error fetching page content")
        return ""
    
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.get_text()

if __name__ == "__main__":
    search_query = "los angeles weather"
    results = google_search(search_query)
    
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
        page_content = fetch_page_content(selected_link)
        print("\nPage Content:\n", page_content[:1000])  # Display first 1000 characters
    else:
        print("\nNo relevant weather link found.")
