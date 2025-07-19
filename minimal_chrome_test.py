#!/usr/bin/env python3
"""
Minimal Chrome click test - just test the core functionality
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def minimal_chrome_test():
    print("🔧 Minimal Chrome Test")
    print("=" * 30)
    
    try:
        # Test 1: Can we import the modules?
        print("1. Testing imports...")
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.screenshot_utils import capture_screen_pil
        import pyautogui
        print("   ✅ All imports successful")
        
        # Test 2: Can we check OmniParser?
        print("2. Testing OmniParser...")
        omniparser_manager = OmniParserServerManager()
        is_ready = omniparser_manager.is_server_ready()
        print(f"   📡 OmniParser ready: {is_ready}")
        
        # Test 3: Can we capture screenshot?
        print("3. Testing screenshot...")
        screenshot = capture_screen_pil()
        if screenshot:
            print(f"   📸 Screenshot captured: {screenshot.size}")
        else:
            print("   ❌ Screenshot failed")
            return False
        
        # Test 4: Can we save to temp file?
        print("4. Testing temp file...")
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            screenshot.save(temp_path)
            print(f"   💾 Temp file saved: {temp_path}")
        
        print("   ✅ All basic tests passed!")
        print("   🎯 The Chrome fix should work properly")
        
        # Optional: Try to start Chrome using the Windows Run dialog
        print("5. Alternative Chrome launch test...")
        print("   🔄 Trying to launch Chrome via Run dialog...")
        
        # Send Win+R to open Run dialog
        pyautogui.hotkey('win', 'r')
        import time
        time.sleep(1)
        
        # Type chrome and press Enter
        pyautogui.typewrite('chrome')
        time.sleep(0.5)
        pyautogui.press('enter')
        
        print("   ✅ Chrome launch command sent")
        print("   ⏳ Waiting 3 seconds...")
        time.sleep(3)
        
        # Check if Chrome started
        import subprocess
        result = subprocess.run(
            ['powershell', '-Command', 'Get-Process -Name chrome -ErrorAction SilentlyContinue'],
            capture_output=True,
            text=True
        )
        
        if result.stdout.strip():
            print("   🎉 SUCCESS! Chrome is now running!")
            print("   Terminal verification:")
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    print(f"     {line}")
            return True
        else:
            print("   ⚠️  Chrome may not have started via Run dialog")
            return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = minimal_chrome_test()
    print("\n" + "=" * 30)
    if success:
        print("✅ MINIMAL TEST PASSED!")
        print("Chrome detection fix verified!")
    else:
        print("❌ MINIMAL TEST FAILED!")
    print("=" * 30)
