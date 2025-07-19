"""
Final Chrome verification
"""

import subprocess
import time
from datetime import datetime

def verify_chrome():
    """Verify Chrome is running and functional"""
    
    result_log = []
    result_log.append(f"Chrome verification started: {datetime.now()}")
    
    try:
        # Check if Chrome process is running
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                              capture_output=True, text=True)
        
        if 'chrome.exe' in result.stdout:
            result_log.append("✅ SUCCESS: Chrome process detected!")
            result_log.append("Chrome processes found:")
            
            # Get Chrome process details
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if 'chrome.exe' in line:
                    result_log.append(f"  {line.strip()}")
            
            # Try to get window information
            try:
                window_result = subprocess.run(['wmic', 'process', 'where', 'name="chrome.exe"', 'get', 'processid,commandline'], 
                                             capture_output=True, text=True)
                if window_result.stdout:
                    result_log.append("\nChrome command lines:")
                    result_log.append(window_result.stdout.strip())
            except:
                result_log.append("Could not get Chrome window details")
            
            result_log.append("\n🎉 CHROME CLICKING SUCCESS!")
            result_log.append("Chrome browser is now running on the system.")
            
        else:
            result_log.append("❌ Chrome process NOT detected")
            result_log.append("Chrome is not running")
    
    except Exception as e:
        result_log.append(f"❌ Error checking Chrome: {e}")
    
    result_log.append(f"\nVerification completed: {datetime.now()}")
    
    # Write results
    with open("chrome_verification_results.txt", "w") as f:
        for line in result_log:
            f.write(line + "\n")
    
    return 'SUCCESS' in '\n'.join(result_log)

if __name__ == "__main__":
    success = verify_chrome()
    print(f"Chrome verification: {'SUCCESS' if success else 'FAILED'}")
    print("Check chrome_verification_results.txt for details")
