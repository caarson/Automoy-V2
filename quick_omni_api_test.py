#!/usr/bin/env python3
"""
Quick OmniParser Server Test - Direct HTTP API Call
"""

print("=== TESTING OMNIPARSER DIRECT API ===")

try:
    import requests
    import base64
    import pyautogui
    from io import BytesIO
    
    print("✓ Dependencies imported")
    
    # Test server health
    print("\n1. Testing OmniParser server health...")
    health_url = "http://127.0.0.1:8111/health"
    try:
        response = requests.get(health_url, timeout=5)
        print(f"Health check status: {response.status_code}")
        if response.status_code == 200:
            print("✓ OmniParser server is healthy")
        else:
            print(f"❌ Server health check failed: {response.status_code}")
            exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to OmniParser server: {e}")
        exit(1)
    
    # Take screenshot
    print("\n2. Taking screenshot...")
    screenshot = pyautogui.screenshot()
    print(f"✓ Screenshot taken: {screenshot.size}")
    
    # Convert to base64
    print("3. Converting to base64...")
    buffered = BytesIO()
    screenshot.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    print(f"✓ Base64 conversion complete: {len(img_str)} characters")
    
    # Send to OmniParser
    print("4. Sending to OmniParser for analysis...")
    parse_url = "http://127.0.0.1:8111/parse"
    
    try:
        analyze_response = requests.post(
            parse_url,
            json={"image": img_str},
            timeout=30
        )
        
        print(f"Analysis response status: {analyze_response.status_code}")
        
        if analyze_response.status_code == 200:
            result = analyze_response.json()
            print("✓ Analysis successful!")
            print(f"Response keys: {list(result.keys())}")
            
            elements = result.get('elements', [])
            text_snippets = result.get('text_snippets', [])
            
            print(f"\n=== ANALYSIS RESULTS ===")
            print(f"Elements found: {len(elements)}")
            print(f"Text snippets found: {len(text_snippets)}")
            
            if elements:
                print("\nFirst 3 elements:")
                for i, elem in enumerate(elements[:3]):
                    print(f"  Element {i}: {elem}")
            else:
                print("⚠ NO ELEMENTS DETECTED!")
            
            if text_snippets:
                print("\nFirst 3 text snippets:")
                for i, text in enumerate(text_snippets[:3]):
                    print(f"  Text {i}: {text}")
            else:
                print("⚠ NO TEXT SNIPPETS DETECTED!")
            
            # Look for Chrome specifically
            print(f"\n=== CHROME DETECTION ===")
            chrome_found = False
            
            for i, element in enumerate(elements):
                if 'chrome' in str(element).lower():
                    print(f"🎯 CHROME FOUND in element {i}: {element}")
                    chrome_found = True
            
            for i, text in enumerate(text_snippets):
                if 'chrome' in str(text).lower():
                    print(f"🎯 CHROME FOUND in text {i}: {text}")
                    chrome_found = True
            
            if not chrome_found:
                print("❌ Chrome NOT detected in analysis")
                print("\nThis explains why the system can't click Chrome!")
                print("Either Chrome icon is not visible or OmniParser isn't detecting it properly.")
            else:
                print("✅ Chrome detected! The click system should work.")
                
        else:
            print(f"❌ Analysis failed: {analyze_response.status_code}")
            print(f"Response: {analyze_response.text}")
            
    except Exception as e:
        print(f"❌ Analysis request failed: {e}")
        
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n=== TEST COMPLETE ===")
