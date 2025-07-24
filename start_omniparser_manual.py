#!/usr/bin/env python3
"""
Manual OmniParser Server Start and Test
This will manually start the OmniParser server and test it
"""

import os
import sys
import time
import subprocess
from datetime import datetime

# Add workspace to path
workspace = os.path.abspath(os.path.dirname(__file__))
if workspace not in sys.path:
    sys.path.insert(0, workspace)

# Results file
results_file = os.path.join(workspace, "debug", "logs", "omniparser_manual_test.log")
os.makedirs(os.path.dirname(results_file), exist_ok=True)

def log_result(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
        f.flush()
    print(f"[{timestamp}] {message}")

def main():
    try:
        log_result("=== MANUAL OMNIPARSER SERVER TEST ===")
        
        # Clear previous log
        with open(results_file, "w") as f:
            f.write("")
        
        log_result("Starting manual OmniParser server launch and test...")
        
        # Check if server is already running
        log_result("1. Checking if OmniParser server is already running...")
        try:
            import requests
            response = requests.get("http://localhost:8111/probe/", timeout=3)
            if response.status_code == 200:
                log_result("✅ OmniParser server is already running!")
                log_result("Proceeding to test the running server...")
                test_server()
                return
        except:
            pass
        
        log_result("❌ Server not running - need to start it manually")
        
        # Paths
        conda_exe = r"C:\Users\imitr\anaconda3\Scripts\conda.exe"
        server_path = os.path.join(workspace, "dependencies", "OmniParser-master", "omnitool", "omniparserserver")
        model_path = os.path.join(workspace, "dependencies", "OmniParser-master", "weights", "icon_detect", "model.pt")
        caption_path = os.path.join(workspace, "dependencies", "OmniParser-master", "weights", "icon_caption_florence")
        
        # Verify paths exist
        log_result("2. Verifying required paths...")
        if not os.path.exists(conda_exe):
            log_result(f"❌ Conda not found at: {conda_exe}")
            return
        log_result(f"✅ Conda found: {conda_exe}")
        
        if not os.path.exists(server_path):
            log_result(f"❌ Server path not found: {server_path}")
            return
        log_result(f"✅ Server path found: {server_path}")
        
        if not os.path.exists(model_path):
            log_result(f"❌ Model not found: {model_path}")
            return
        log_result(f"✅ Model found: {model_path}")
        
        if not os.path.exists(caption_path):
            log_result(f"❌ Caption model not found: {caption_path}")
            return  
        log_result(f"✅ Caption model found: {caption_path}")
        
        # Build command
        log_result("3. Building OmniParser server command...")
        cmd = [
            conda_exe, "run", "-n", "automoy_env",
            sys.executable, "omniparserserver.py",
            "--som_model_path", model_path,
            "--caption_model_name", "florence2", 
            "--caption_model_path", caption_path,
            "--device", "cpu",  # Force CPU to avoid CUDA issues
            "--BOX_TRESHOLD", "0.15",
            "--port", "8111"
        ]
        
        log_result(f"Command: {' '.join(cmd)}")
        log_result(f"Working directory: {server_path}")
        
        # Start server
        log_result("4. Starting OmniParser server...")
        try:
            server_process = subprocess.Popen(
                cmd,
                cwd=server_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            log_result(f"✅ Server process started with PID: {server_process.pid}")
        except Exception as e:
            log_result(f"❌ Failed to start server: {e}")
            return
        
        # Monitor server startup
        log_result("5. Monitoring server startup...")
        start_time = time.time()
        server_ready = False
        
        while time.time() - start_time < 120:  # 2 minute timeout
            # Check if process is still alive
            if server_process.poll() is not None:
                log_result(f"❌ Server process exited with code: {server_process.returncode}")
                # Try to get some output
                try:
                    stdout, stderr = server_process.communicate(timeout=5)
                    log_result(f"Server output: {stdout}")
                    if stderr:
                        log_result(f"Server errors: {stderr}")
                except:
                    pass
                return
            
            # Check if server is responding
            try:
                import requests
                response = requests.get("http://localhost:8111/probe/", timeout=3)
                if response.status_code == 200:
                    log_result("✅ OmniParser server is ready!")
                    server_ready = True
                    break
            except requests.RequestException:
                pass
            
            log_result("   Server starting... (checking again in 3 seconds)")
            time.sleep(3)
        
        if not server_ready:
            log_result("❌ Server failed to start within timeout")
            server_process.terminate()
            return
        
        # Test the server
        log_result("6. Testing server functionality...")
        test_server()
        
        # Keep server running for a bit
        log_result("7. Server test complete - keeping server alive for manual testing...")
        log_result("   You can now test Chrome detection manually")
        log_result(f"   Server PID: {server_process.pid}")
        log_result("   Press Ctrl+C in this terminal to stop the server")
        
        # Wait for user interrupt
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log_result("8. Stopping server...")
            server_process.terminate()
            server_process.wait(timeout=10)
            log_result("✅ Server stopped")
            
    except Exception as e:
        log_result(f"❌ Critical error: {e}")
        import traceback
        log_result(f"Traceback: {traceback.format_exc()}")

def test_server():
    """Test the running OmniParser server with screenshot analysis"""
    try:
        import requests
        import base64
        import pyautogui
        from io import BytesIO
        
        log_result("Testing server with screenshot analysis...")
        
        # Take screenshot
        screenshot = pyautogui.screenshot()
        log_result(f"✅ Screenshot taken: {screenshot.size[0]}x{screenshot.size[1]}")
        
        # Convert to base64
        buffer = BytesIO()
        screenshot.save(buffer, format="PNG")
        image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        log_result(f"✅ Image converted to base64: {len(image_data)} chars")
        
        # Send to server
        response = requests.post(
            "http://localhost:8111/parse/",
            json={"base64_image": image_data},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            log_result("✅ Server analysis successful!")
            
            if "parsed_content_list" in result:
                items = result["parsed_content_list"]
                log_result(f"📊 Found {len(items)} screen elements")
                
                # Look for Chrome
                chrome_found = False
                for i, item in enumerate(items):
                    content = str(item.get("content", "")).lower()
                    if "chrome" in content or "google" in content:
                        log_result(f"🎯 CHROME FOUND in item {i}: {item}")
                        chrome_found = True
                
                if not chrome_found and len(items) > 0:
                    log_result("🟡 Chrome not found, but other elements detected:")
                    for i, item in enumerate(items[:3]):  # Show first 3
                        log_result(f"   Item {i}: {item}")
                elif not chrome_found:
                    log_result("❌ No elements detected at all - server may not be working properly")
                else:
                    log_result("✅ Chrome detection successful!")
            else:
                log_result(f"⚠️  Unexpected response format: {list(result.keys())}")
        else:
            log_result(f"❌ Server request failed: {response.status_code}")
            log_result(f"Response: {response.text}")
            
    except Exception as e:
        log_result(f"❌ Test failed: {e}")

if __name__ == "__main__":
    main()
