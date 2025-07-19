import requests
import json

print("Testing OmniParser connection...")

try:
    # Test if OmniParser is running
    response = requests.get("http://localhost:8111", timeout=5)
    print("OmniParser is running!")
    
    # Try to process an existing screenshot
    try:
        with open('current_screenshot.png', 'rb') as f:
            files = {'image': ('screenshot.png', f, 'image/png')}
            response = requests.post('http://localhost:8111/process_image', files=files, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                elements = result.get('elements', [])
                print(f"Found {len(elements)} elements in the screenshot")
                
                # Look for Chrome
                chrome_found = []
                for i, elem in enumerate(elements):
                    text = elem.get('text', '').lower()
                    if any(word in text for word in ['chrome', 'google', 'browser']):
                        chrome_found.append(f"Element {i}: '{elem.get('text', '')}' at {elem.get('bbox', [])}")
                
                if chrome_found:
                    print(f"Chrome elements found:")
                    for item in chrome_found:
                        print(f"  - {item}")
                else:
                    print("No Chrome elements found!")
                    print("First 5 elements:")
                    for i, elem in enumerate(elements[:5]):
                        print(f"  {i}: '{elem.get('text', '')}' - {elem.get('bbox', [])}")
                        
            else:
                print(f"Error processing image: {response.status_code}")
                
    except FileNotFoundError:
        print("No current_screenshot.png found")
    except Exception as e:
        print(f"Error processing screenshot: {e}")
        
except Exception as e:
    print(f"Cannot connect to OmniParser: {e}")
