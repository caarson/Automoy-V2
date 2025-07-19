import subprocess

# Simple Chrome check
try:
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                          capture_output=True, text=True)
    
    if 'chrome.exe' in result.stdout:
        print("SUCCESS: Chrome is running!")
        print("Chrome processes:")
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if 'chrome.exe' in line:
                print(f"  {line.strip()}")
        
        with open("final_chrome_status.txt", "w") as f:
            f.write("CHROME RUNNING: SUCCESS\n")
            f.write(result.stdout)
    else:
        print("FAILED: Chrome not running")
        with open("final_chrome_status.txt", "w") as f:
            f.write("CHROME RUNNING: FAILED\n")
            
except Exception as e:
    print(f"Error: {e}")
    with open("final_chrome_status.txt", "w") as f:
        f.write(f"ERROR: {e}\n")
