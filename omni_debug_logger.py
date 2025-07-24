#!/usr/bin/env python3
"""
OmniParser Debug Logger - Writes results to file
"""

import os
import sys
import traceback
from datetime import datetime

# Add the workspace to the Python path
workspace_path = r"c:\Users\imitr\OneDrive\Documentos\GitHub\Automoy-V2"
if workspace_path not in sys.path:
    sys.path.insert(0, workspace_path)

# Create logs directory
log_dir = os.path.join(workspace_path, "debug", "logs")
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, "omniparser_test.log")

def log_message(message):
    """Write message to log file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
        f.flush()

try:
    log_message("=== OMNIPARSER API TEST STARTED ===")
    
    # Test imports
    log_message("Testing imports...")
    import requests
    import base64
    import pyautogui
    from io import BytesIO
    log_message("✓ All imports successful")
    
    # Test server health
    log_message("Testing OmniParser server health...")
    health_url = "http://127.0.0.1:8111/health"
    
    try:
        response = requests.get(health_url, timeout=5)
        log_message(f"Health check response: {response.status_code}")
        
        if response.status_code == 200:
            log_message("✓ OmniParser server is healthy")
            
            # Take screenshot
            log_message("Taking screenshot...")
            screenshot = pyautogui.screenshot()
            log_message(f"✓ Screenshot taken: {screenshot.size}")
            
            # Convert to base64
            log_message("Converting to base64...")
            buffered = BytesIO()
            screenshot.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            log_message(f"✓ Base64 conversion complete: {len(img_str)} characters")
            
            # Send to OmniParser
            log_message("Sending to OmniParser for analysis...")
            parse_url = "http://127.0.0.1:8111/parse"
            
            analyze_response = requests.post(
                parse_url,
                json={"image": img_str},
                timeout=30
            )
            
            log_message(f"Analysis response status: {analyze_response.status_code}")
            
            if analyze_response.status_code == 200:
                result = analyze_response.json()
                log_message("✓ Analysis successful!")
                log_message(f"Response keys: {list(result.keys())}")
                
                elements = result.get('elements', [])
                text_snippets = result.get('text_snippets', [])
                
                log_message(f"Elements found: {len(elements)}")
                log_message(f"Text snippets found: {len(text_snippets)}")
                
                # Log first few elements
                if elements:
                    log_message("First 3 elements:")
                    for i, elem in enumerate(elements[:3]):
                        log_message(f"  Element {i}: {elem}")
                else:
                    log_message("⚠ NO ELEMENTS DETECTED!")
                
                # Log first few text snippets
                if text_snippets:
                    log_message("First 3 text snippets:")
                    for i, text in enumerate(text_snippets[:3]):
                        log_message(f"  Text {i}: {text}")
                else:
                    log_message("⚠ NO TEXT SNIPPETS DETECTED!")
                
                # Look for Chrome specifically
                log_message("=== CHROME DETECTION ANALYSIS ===")
                chrome_found = False
                
                for i, element in enumerate(elements):
                    elem_str = str(element).lower()
                    if 'chrome' in elem_str:
                        log_message(f"🎯 CHROME FOUND in element {i}: {element}")
                        chrome_found = True
                    if 'google' in elem_str:
                        log_message(f"🔍 GOOGLE reference in element {i}: {element}")
                
                for i, text in enumerate(text_snippets):
                    text_str = str(text).lower()
                    if 'chrome' in text_str:
                        log_message(f"🎯 CHROME FOUND in text {i}: {text}")
                        chrome_found = True
                    if 'google' in text_str:
                        log_message(f"🔍 GOOGLE reference in text {i}: {text}")
                
                if not chrome_found:
                    log_message("❌ Chrome NOT detected in visual analysis")
                    log_message("This explains why the system can't click Chrome!")
                    log_message("Need to investigate why OmniParser isn't seeing Chrome icon")
                else:
                    log_message("✅ Chrome detected! Visual system should work.")
                    
            else:
                log_message(f"❌ Analysis failed: {analyze_response.status_code}")
                log_message(f"Response text: {analyze_response.text}")
                
        else:
            log_message(f"❌ Server health check failed: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        log_message("❌ Cannot connect to OmniParser server - server may not be running")
    except Exception as e:
        log_message(f"❌ Server test failed: {str(e)}")
        log_message(f"Exception details: {traceback.format_exc()}")
        
except Exception as e:
    log_message(f"❌ Critical error: {str(e)}")
    log_message(f"Full traceback: {traceback.format_exc()}")

log_message("=== TEST COMPLETE ===")
log_message(f"Log written to: {log_file}")
print(f"Test complete! Check log at: {log_file}")
