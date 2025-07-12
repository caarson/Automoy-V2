#!/usr/bin/env python3
"""
Test script to check running processes and verify if Chrome is running
"""
import subprocess
import psutil
import time

def check_process_running(process_name):
    """Check if a process is running by name"""
    for process in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            if process_name.lower() in process.info['name'].lower():
                return True, process.info
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False, None

def list_chrome_processes():
    """List all Chrome-related processes"""
    chrome_processes = []
    for process in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
        try:
            if 'chrome' in process.info['name'].lower():
                chrome_processes.append({
                    'pid': process.info['pid'],
                    'name': process.info['name'],
                    'exe': process.info.get('exe', 'N/A')
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return chrome_processes

def open_chrome_with_click():
    """Simulate opening Chrome by pressing Win key and clicking"""
    import pyautogui
    import time
    
    print("🎯 Attempting to open Chrome...")
    
    # Press Windows key to open start menu
    print("1. Pressing Windows key...")
    pyautogui.press('win')
    time.sleep(2)
    
    # Type 'chrome' to search
    print("2. Typing 'chrome'...")
    pyautogui.typewrite('chrome')
    time.sleep(2)
    
    # Press Enter to launch
    print("3. Pressing Enter to launch...")
    pyautogui.press('enter')
    time.sleep(3)
    
    return True

def main():
    print("🔍 CHROME PROCESS DETECTION TEST")
    print("=" * 50)
    
    # Check if Chrome is already running
    print("\n1. Checking if Chrome is already running...")
    is_running, proc_info = check_process_running('chrome')
    
    if is_running:
        print(f"✓ Chrome is already running: {proc_info}")
        chrome_procs = list_chrome_processes()
        print(f"Found {len(chrome_procs)} Chrome processes:")
        for proc in chrome_procs[:3]:  # Show first 3
            print(f"  - PID {proc['pid']}: {proc['name']}")
    else:
        print("❌ Chrome is not currently running")
        
        # Try to open Chrome
        print("\n2. Attempting to open Chrome...")
        try:
            open_chrome_with_click()
            
            # Wait and check again
            print("\n3. Waiting 5 seconds and checking again...")
            time.sleep(5)
            
            is_running_after, proc_info_after = check_process_running('chrome')
            if is_running_after:
                print(f"✓ SUCCESS: Chrome is now running: {proc_info_after}")
                chrome_procs_after = list_chrome_processes()
                print(f"Found {len(chrome_procs_after)} Chrome processes:")
                for proc in chrome_procs_after[:3]:
                    print(f"  - PID {proc['pid']}: {proc['name']}")
            else:
                print("❌ FAILED: Chrome is still not running")
                
        except Exception as e:
            print(f"❌ Error trying to open Chrome: {e}")
    
    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    main()
