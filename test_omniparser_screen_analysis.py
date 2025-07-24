#!/usr/bin/env python3
"""
Direct OmniParser Screen Analysis Test
Writes results to debug log for analysis
"""

import os
import sys
import time
from datetime import datetime

# Add workspace to path
workspace = os.path.abspath(os.path.dirname(__file__))
if workspace not in sys.path:
    sys.path.insert(0, workspace)

# Create results file
results_file = os.path.join(workspace, "debug", "logs", "omniparser_screen_test.log")
os.makedirs(os.path.dirname(results_file), exist_ok=True)

def log_result(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
        f.flush()

def main():
    try:
        log_result("=== OMNIPARSER SCREEN ANALYSIS TEST STARTED ===")
        log_result("Testing direct OmniParser API call for screen analysis...")
        
        # Test imports
        try:
            import requests
            import base64
            import pyautogui
            from io import BytesIO
            log_result("✓ All required modules imported successfully")
        except ImportError as e:
            log_result(f"❌ Import error: {e}")
            return
        
        # Test OmniParser server connection
        log_result("1. Testing OmniParser server connection...")
        server_url = "http://127.0.0.1:8111"
        
        try:
            health_response = requests.get(f"{server_url}/health", timeout=5)
            if health_response.status_code == 200:
                log_result("✓ OmniParser server is healthy and responding")
            else:
                log_result(f"❌ Server responded with status: {health_response.status_code}")
                return
        except Exception as e:
            log_result(f"❌ Cannot connect to OmniParser server: {e}")
            return
        
        # Take screenshot
        log_result("2. Taking desktop screenshot...")
        try:
            screenshot = pyautogui.screenshot()
            log_result(f"✓ Screenshot captured: {screenshot.size[0]}x{screenshot.size[1]} pixels")
        except Exception as e:
            log_result(f"❌ Screenshot failed: {e}")
            return
        
        # Convert to base64
        log_result("3. Converting screenshot to base64...")
        try:
            buffer = BytesIO()
            screenshot.save(buffer, format="PNG")
            image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            log_result(f"✓ Base64 conversion complete: {len(image_data)} characters")
        except Exception as e:
            log_result(f"❌ Base64 conversion failed: {e}")
            return
        
        # Send to OmniParser for analysis
        log_result("4. Sending screenshot to OmniParser for analysis...")
        try:
            analysis_response = requests.post(
                f"{server_url}/parse",
                json={"image": image_data},
                timeout=30,
                headers={"Content-Type": "application/json"}
            )
            
            if analysis_response.status_code == 200:
                log_result("✓ OmniParser analysis completed successfully")
                
                # Parse results
                result = analysis_response.json()
                elements = result.get('elements', [])
                text_snippets = result.get('text_snippets', [])
                
                log_result(f"📊 ANALYSIS RESULTS:")
                log_result(f"   Elements detected: {len(elements)}")
                log_result(f"   Text snippets detected: {len(text_snippets)}")
                
                # Check if we got empty results (the main issue)
                if len(elements) == 0 and len(text_snippets) == 0:
                    log_result("⚠️  CRITICAL: OmniParser returned EMPTY analysis!")
                    log_result("   This explains why Chrome can't be found - no screen elements detected")
                    log_result("   Possible causes:")
                    log_result("   - OmniParser model loading issues")
                    log_result("   - Screenshot processing problems")
                    log_result("   - Server configuration issues")
                else:
                    log_result("✅ OmniParser detected screen elements - system should work")
                
                # Log first few elements for inspection
                if elements:
                    log_result("🔍 First few detected elements:")
                    for i, element in enumerate(elements[:5]):
                        log_result(f"   Element {i+1}: {element}")
                
                if text_snippets:
                    log_result("📝 First few text snippets:")
                    for i, text in enumerate(text_snippets[:5]):
                        log_result(f"   Text {i+1}: {text}")
                
                # Specifically look for Chrome
                log_result("🎯 CHROME DETECTION TEST:")
                chrome_found = False
                
                # Check elements for Chrome references
                for i, element in enumerate(elements):
                    element_str = str(element).lower()
                    if 'chrome' in element_str or 'google' in element_str:
                        log_result(f"   🟢 CHROME found in element {i}: {element}")
                        chrome_found = True
                
                # Check text for Chrome references  
                for i, text in enumerate(text_snippets):
                    text_str = str(text).lower()
                    if 'chrome' in text_str or 'google' in text_str:
                        log_result(f"   🟢 CHROME found in text {i}: {text}")
                        chrome_found = True
                
                if not chrome_found:
                    if len(elements) > 0 or len(text_snippets) > 0:
                        log_result("   🟡 Chrome not detected, but other elements found")
                        log_result("   Chrome may not be visible on desktop currently")
                    else:
                        log_result("   🔴 Chrome not detected AND no elements found at all")
                        log_result("   This indicates OmniParser visual analysis is not working")
                else:
                    log_result("   ✅ Chrome successfully detected by OmniParser")
                
            else:
                log_result(f"❌ Analysis failed with status: {analysis_response.status_code}")
                log_result(f"   Response: {analysis_response.text}")
                
        except Exception as e:
            log_result(f"❌ Analysis request failed: {e}")
            
    except Exception as e:
        log_result(f"❌ Critical error in test: {e}")
        import traceback
        log_result(f"   Traceback: {traceback.format_exc()}")
    
    finally:
        log_result("=== OMNIPARSER SCREEN ANALYSIS TEST COMPLETED ===")
        log_result(f"Results written to: {results_file}")
        print(f"Test completed! Check results at: {results_file}")

if __name__ == "__main__":
    main()
