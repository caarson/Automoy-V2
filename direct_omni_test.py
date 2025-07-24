import sys
print("Python executable:", sys.executable)
print("Python version:", sys.version)
print("Current working directory:", __file__)

try:
    import requests
    print("Requests available")
    
    # Test if OmniParser server is running by direct HTTP call
    response = requests.get("http://127.0.0.1:8111/health", timeout=5)
    print(f"OmniParser server response: {response.status_code}")
    
    if response.status_code == 200:
        print("✓ OmniParser server is running!")
        
        # Try direct API call for analysis
        try:
            import pyautogui
            import base64
            from io import BytesIO
            
            print("Taking screenshot...")
            screenshot = pyautogui.screenshot()
            
            # Convert screenshot to base64
            buffered = BytesIO()
            screenshot.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            print("Sending to OmniParser...")
            analyze_response = requests.post(
                "http://127.0.0.1:8111/parse",
                json={"image": img_str},
                timeout=30
            )
            
            if analyze_response.status_code == 200:
                result = analyze_response.json()
                print(f"Analysis result keys: {list(result.keys())}")
                
                elements = result.get('elements', [])
                text_snippets = result.get('text_snippets', [])
                
                print(f"Found {len(elements)} elements")
                print(f"Found {len(text_snippets)} text snippets")
                
                # Look for Chrome
                chrome_found = False
                for i, element in enumerate(elements):
                    if 'chrome' in str(element).lower():
                        print(f"🎯 CHROME FOUND: {element}")
                        chrome_found = True
                
                if not chrome_found:
                    print("❌ Chrome not found in analysis")
                    print("Sample elements:")
                    for i, elem in enumerate(elements[:3]):
                        print(f"  {i}: {elem}")
                
            else:
                print(f"Analysis failed: {analyze_response.status_code}")
                
        except Exception as e:
            print(f"Screenshot analysis error: {e}")
    
except requests.exceptions.RequestException as e:
    print(f"OmniParser server not accessible: {e}")
except ImportError as e:
    print(f"Missing dependency: {e}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("Test completed")
