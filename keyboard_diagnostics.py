"""
Keyboard Input Diagnostics Tool
This script tests different keyboard libraries to identify why only Windows key works.
"""

import os
import time
import traceback

def test_keyboard_libraries():
    print("=== KEYBOARD INPUT DIAGNOSTICS ===")
    print(f"Running on: {os.name}")
    print()
    
    # Test 1: PyAutoGUI
    print("1. Testing PyAutoGUI...")
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        
        print("   - Library imported successfully")
        
        # Test different keys
        test_keys = ['a', 'space', 'enter', 'escape', 'tab', 'win']
        
        for key in test_keys:
            try:
                print(f"   - Testing key: {key}")
                time.sleep(0.5)  # Brief pause to see the test
                pyautogui.press(key)
                print(f"   ✓ {key} - SUCCESS")
            except Exception as e:
                print(f"   ✗ {key} - FAILED: {e}")
                
        # Test hotkeys
        print("   - Testing hotkey combinations...")
        try:
            print("   - Testing Win+D...")
            time.sleep(0.5)
            pyautogui.hotkey('win', 'd')
            print("   ✓ Win+D - SUCCESS")
        except Exception as e:
            print(f"   ✗ Win+D - FAILED: {e}")
            
        try:
            print("   - Testing Ctrl+A...")
            time.sleep(0.5)
            pyautogui.hotkey('ctrl', 'a')
            print("   ✓ Ctrl+A - SUCCESS")
        except Exception as e:
            print(f"   ✗ Ctrl+A - FAILED: {e}")
            
    except Exception as e:
        print(f"   ✗ PyAutoGUI - IMPORT FAILED: {e}")
        traceback.print_exc()
    
    print()
    
    # Test 2: Keyboard library
    print("2. Testing keyboard library...")
    try:
        import keyboard
        print("   - Library imported successfully")
        
        # Test if we can send keys
        test_keys = ['a', 'space', 'enter', 'esc', 'tab', 'win']
        
        for key in test_keys:
            try:
                print(f"   - Testing key: {key}")
                time.sleep(0.5)
                keyboard.press_and_release(key)
                print(f"   ✓ {key} - SUCCESS")
            except Exception as e:
                print(f"   ✗ {key} - FAILED: {e}")
                
        # Test combinations
        print("   - Testing key combinations...")
        try:
            print("   - Testing Win+D...")
            time.sleep(0.5)
            keyboard.press_and_release('win+d')
            print("   ✓ Win+D - SUCCESS")
        except Exception as e:
            print(f"   ✗ Win+D - FAILED: {e}")
            
        try:
            print("   - Testing Ctrl+A...")
            time.sleep(0.5)
            keyboard.press_and_release('ctrl+a')
            print("   ✓ Ctrl+A - SUCCESS")
        except Exception as e:
            print(f"   ✗ Ctrl+A - FAILED: {e}")
            
    except Exception as e:
        print(f"   ✗ keyboard - IMPORT FAILED: {e}")
        traceback.print_exc()
    
    print()
    
    # Test 3: Windows-specific methods
    print("3. Testing Windows-specific methods...")
    try:
        import ctypes
        from ctypes import wintypes
        
        print("   - ctypes imported successfully")
        
        # Test SendInput method
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        # Virtual key codes for testing
        VK_A = 0x41
        VK_SPACE = 0x20
        VK_ENTER = 0x0D
        VK_ESCAPE = 0x1B
        VK_LWIN = 0x5B
        
        # Test A key
        print("   - Testing A key with SendInput...")
        time.sleep(0.5)
        result = user32.keybd_event(VK_A, 0, 0, 0)  # Key down
        user32.keybd_event(VK_A, 0, 2, 0)  # Key up
        print(f"   ✓ A key - Result: {result}")
        
        # Test Windows key
        print("   - Testing Windows key with SendInput...")
        time.sleep(0.5)
        result = user32.keybd_event(VK_LWIN, 0, 0, 0)  # Key down
        user32.keybd_event(VK_LWIN, 0, 2, 0)  # Key up
        print(f"   ✓ Windows key - Result: {result}")
        
    except Exception as e:
        print(f"   ✗ Windows-specific - FAILED: {e}")
        traceback.print_exc()
    
    print()
    
    # Check permissions
    print("4. Checking permissions...")
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        print(f"   - Running as administrator: {bool(is_admin)}")
        
        if not is_admin:
            print("   ! Consider running as administrator for full keyboard access")
        
    except Exception as e:
        print(f"   ✗ Permission check failed: {e}")
    
    print()
    print("=== DIAGNOSTICS COMPLETE ===")
    print("Please check the results above to identify which keyboard methods work.")
    print("If only Windows key works, there might be:")
    print("1. Permission issues (try running as administrator)")
    print("2. Antivirus blocking keyboard input")
    print("3. System security policies preventing automation")
    print("4. Library version conflicts")

if __name__ == "__main__":
    print("Starting keyboard diagnostics in 3 seconds...")
    print("Make sure to have a text editor or notepad open to see the key presses!")
    time.sleep(3)
    test_keyboard_libraries()
