#!/usr/bin/env python3
"""
Test desktop anchor point functionality.
"""
import sys
import os
import time

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
sys.path.insert(0, project_root)

from config.config import Config
from core.environmental.anchor.desktop_anchor_point import show_desktop

def test_desktop_anchor_config():
    """Test if desktop anchor point configuration is loaded correctly."""
    print("Testing desktop anchor point configuration...")
    
    config = Config()
    desktop_anchor_enabled = config.get("DESKTOP_ANCHOR_POINT", False)
    
    print(f"DESKTOP_ANCHOR_POINT setting: {desktop_anchor_enabled}")
    print(f"Type: {type(desktop_anchor_enabled)}")
    
    if desktop_anchor_enabled:
        print("✅ Desktop anchor point is ENABLED")
    else:
        print("❌ Desktop anchor point is DISABLED")
    
    return desktop_anchor_enabled

def test_show_desktop_function():
    """Test the show_desktop function."""
    print("\nTesting show_desktop function...")
    
    try:
        print("Calling show_desktop()...")
        show_desktop()
        print("✅ show_desktop() executed successfully")
        time.sleep(2)  # Give time to see the effect
        return True
    except Exception as e:
        print(f"❌ show_desktop() failed: {e}")
        return False

def main():
    print("🔍 Testing Desktop Anchor Point Functionality")
    print("=" * 50)
    
    # Test configuration loading
    config_works = test_desktop_anchor_config()
    
    # Test show_desktop function
    function_works = test_show_desktop_function()
    
    print("\n" + "=" * 50)
    if config_works and function_works:
        print("🎉 All tests passed! Desktop anchor point should work correctly.")
    else:
        print("❌ Some tests failed. Check the configuration or implementation.")
    
    print("\nNote: If DESKTOP_ANCHOR_POINT is True in environment.txt,")
    print("the application should now show the desktop before taking screenshots.")

if __name__ == "__main__":
    main()
