#!/usr/bin/env python3
"""
Quick Safety Halt Test - Verify visual elements detection safety measures
"""

import os
import sys
import json
import requests
import time

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from core.operate import AutomoyOperator
from core.utils.operating_system.desktop_utils import DesktopUtils

def test_omniparser_response():
    """Test OmniParser response to see what kind of visual elements it detects"""
    print("=== Testing OmniParser Visual Elements Detection ===")
    
    # Check if OmniParser is running
    try:
        response = requests.get("http://localhost:8111/health", timeout=5)
        print(f"✅ OmniParser server is running (status: {response.status_code})")
    except Exception as e:
        print(f"❌ OmniParser server not available: {e}")
        return False
    
    # Capture screenshot
    print("\n1. Capturing current screenshot...")
    screenshot_path = DesktopUtils.capture_current_screen()
    if not screenshot_path or not os.path.exists(screenshot_path):
        print("❌ Failed to capture screenshot")
        return False
    print(f"✅ Screenshot captured: {screenshot_path}")
    
    # Test OmniParser directly
    print("\n2. Testing OmniParser analysis...")
    try:
        with open(screenshot_path, 'rb') as f:
            files = {'image': f}
            response = requests.post("http://localhost:8111/upload", files=files, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ OmniParser responded successfully")
            
            # Check what elements were detected
            elements = result.get('parsed_elements', [])
            print(f"📊 Detected {len(elements)} visual elements")
            
            if len(elements) == 0:
                print("🚨 ZERO ELEMENTS DETECTED - This should trigger safety halt!")
                return "ZERO_ELEMENTS"
            else:
                print("✅ Visual elements detected - normal operation")
                # Show first few elements
                for i, elem in enumerate(elements[:3]):
                    elem_type = elem.get('type', 'unknown')
                    elem_text = elem.get('text', 'no text')[:50]
                    print(f"   Element {i+1}: {elem_type} - '{elem_text}'")
                return "ELEMENTS_FOUND"
        else:
            print(f"❌ OmniParser error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ OmniParser analysis failed: {e}")
        return False

def test_operator_safety():
    """Test the AutomoyOperator safety measures"""
    print("\n=== Testing AutomoyOperator Safety Measures ===")
    
    try:
        # Create operator instance
        operator = AutomoyOperator()
        print("✅ AutomoyOperator created successfully")
        
        # Test visual analysis with current screen
        print("\n3. Testing visual analysis safety...")
        context = "Testing visual elements detection"
        
        try:
            result = operator._perform_visual_analysis(context)
            print(f"✅ Visual analysis completed")
            print(f"📊 Analysis result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            
            # Check if elements were found
            if isinstance(result, dict):
                elements = result.get('parsed_elements', [])
                if len(elements) == 0:
                    print("🚨 ZERO ELEMENTS - Should have triggered RuntimeError!")
                    return False
                else:
                    print(f"✅ Found {len(elements)} elements - safety check passed")
                    return True
            else:
                print(f"⚠️ Unexpected result type: {type(result)}")
                return False
                
        except RuntimeError as e:
            if "Visual analysis detected zero elements" in str(e):
                print(f"✅ SAFETY HALT TRIGGERED: {e}")
                print("🎯 Safety measures working correctly!")
                return True
            else:
                print(f"❌ Unexpected RuntimeError: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Operator test failed: {e}")
        return False

def main():
    """Run all safety tests"""
    print("🔍 Starting Visual Elements Safety Tests")
    print("=" * 50)
    
    # Test 1: Direct OmniParser
    omni_result = test_omniparser_response()
    
    # Test 2: Operator safety
    operator_result = test_operator_safety()
    
    print("\n" + "=" * 50)
    print("📋 TEST SUMMARY:")
    print(f"   OmniParser Response: {omni_result}")
    print(f"   Operator Safety: {operator_result}")
    
    if operator_result:
        print("✅ ALL SAFETY TESTS PASSED!")
        print("🎯 Visual elements detection safety measures are working correctly")
    else:
        print("❌ SAFETY TESTS FAILED!")
        print("⚠️ Visual elements detection may not halt properly on bad components")

if __name__ == "__main__":
    main()
