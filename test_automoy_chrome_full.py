#!/usr/bin/env python3
"""
Automated Chrome clicking test using full Automoy system
This script will:
1. Start the Automoy GUI system
2. Automatically submit the goal "Open Google Chrome by clicking its icon"
3. Let Automoy's LLM and visual analysis handle the clicking
4. Monitor the process and verify Chrome opens
"""

import os
import sys
import time
import json
import asyncio
import subprocess
import psutil
import threading
from pathlib import Path

# Add project root to Python path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def is_chrome_running():
    """Check if Chrome is running"""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if 'chrome' in proc.info['name'].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

def submit_goal_to_automoy(goal_text):
    """Submit a goal to Automoy by creating the goal request file"""
    from core.data_models import GOAL_REQUEST_FILE
    
    goal_data = {
        "goal": goal_text,
        "timestamp": time.time(),
        "automated_test": True
    }
    
    print(f"📝 Submitting goal to Automoy: '{goal_text}'")
    
    try:
        with open(GOAL_REQUEST_FILE, 'w', encoding='utf-8') as f:
            json.dump(goal_data, f, indent=2)
        print(f"✅ Goal file created: {GOAL_REQUEST_FILE}")
        return True
    except Exception as e:
        print(f"❌ Error creating goal file: {e}")
        return False

def monitor_automoy_progress():
    """Monitor Automoy's progress by reading the GUI state"""
    try:
        from core.data_models import read_state
        state = read_state()
        
        status = state.get('operator_status', 'unknown')
        thinking = state.get('thinking', '')
        current_op = state.get('current_operation', '')
        error_msg = state.get('llm_error_message', '')
        
        print(f"🤖 Status: {status}")
        if thinking:
            print(f"💭 Thinking: {thinking}")
        if current_op:
            print(f"⚙️ Current Operation: {current_op}")
        if error_msg:
            print(f"❌ Error: {error_msg}")
            
        return status, error_msg
        
    except Exception as e:
        print(f"⚠️ Error reading Automoy state: {e}")
        return "unknown", str(e)

def start_automoy_process():
    """Start the Automoy main process"""
    print("🚀 Starting Automoy main process...")
    
    try:
        # Start Automoy main.py
        main_script = os.path.join(project_root, "core", "main.py")
        
        # Use the correct Python executable path
        python_exe = r"C:\Users\imitr\anaconda3\envs\automoy_env\python.exe"
        
        cmd = [python_exe, main_script]
        
        print(f"🔧 Command: {' '.join(cmd)}")
        
        # Start the process
        automoy_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=project_root,
            env=dict(os.environ, PYTHONPATH=project_root)
        )
        
        print(f"✅ Automoy process started with PID: {automoy_process.pid}")
        return automoy_process
        
    except Exception as e:
        print(f"❌ Error starting Automoy process: {e}")
        return None

def wait_for_automoy_ready(timeout=60):
    """Wait for Automoy to be ready to accept goals"""
    print(f"⏳ Waiting for Automoy to be ready (timeout: {timeout}s)...")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            status, error = monitor_automoy_progress()
            
            if status == "idle":
                print("✅ Automoy is ready and idle!")
                return True
            elif status == "error":
                print(f"❌ Automoy encountered an error: {error}")
                return False
            elif status in ["thinking", "running"]:
                print("⚠️ Automoy is already processing something, waiting...")
                
        except Exception as e:
            pass  # State file might not exist yet
            
        time.sleep(2)
        
    print(f"⏰ Timeout waiting for Automoy to be ready")
    return False

def monitor_chrome_opening(timeout=120):
    """Monitor for Chrome opening while Automoy processes the goal"""
    print(f"👀 Monitoring for Chrome opening (timeout: {timeout}s)...")
    
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < timeout:
        # Check if Chrome is running
        if is_chrome_running():
            print("🎉 SUCCESS! Chrome is now running!")
            return True
            
        # Monitor Automoy progress
        try:
            status, error = monitor_automoy_progress()
            
            if status != last_status:
                print(f"📊 Status changed to: {status}")
                last_status = status
                
            if status == "error":
                print(f"❌ Automoy encountered an error: {error}")
                break
            elif status == "idle":
                print("⚠️ Automoy returned to idle without opening Chrome")
                break
                
        except Exception:
            pass  # Continue monitoring
            
        time.sleep(3)
        
    if is_chrome_running():
        print("🎉 Chrome is running!")
        return True
    else:
        print("❌ Chrome did not open within timeout")
        return False

def automated_chrome_test():
    """Run the automated Chrome opening test"""
    print("=" * 60)
    print("🧪 AUTOMATED CHROME CLICKING TEST USING FULL AUTOMOY SYSTEM")
    print("=" * 60)
    
    # Check initial Chrome status
    initial_chrome_status = is_chrome_running()
    print(f"📋 Initial Chrome status: {'Running' if initial_chrome_status else 'Not running'}")
    
    if initial_chrome_status:
        print("⚠️ Chrome is already running - test results may be ambiguous")
    
    # Start Automoy process
    automoy_process = start_automoy_process()
    if not automoy_process:
        print("❌ Failed to start Automoy process")
        return False
        
    try:
        # Wait for Automoy to be ready
        if not wait_for_automoy_ready(timeout=90):
            print("❌ Automoy did not become ready in time")
            return False
            
        # Submit the Chrome opening goal
        goal_text = "Open Google Chrome by clicking its icon"
        if not submit_goal_to_automoy(goal_text):
            print("❌ Failed to submit goal to Automoy")
            return False
            
        print("⏳ Goal submitted, waiting for Automoy to process...")
        time.sleep(3)  # Give Automoy time to pick up the goal
        
        # Monitor for Chrome opening
        success = monitor_chrome_opening(timeout=180)  # 3 minutes
        
        # Final status
        final_chrome_status = is_chrome_running()
        print(f"\n📊 FINAL RESULTS:")
        print(f"   Initial Chrome status: {'Running' if initial_chrome_status else 'Not running'}")
        print(f"   Final Chrome status: {'Running' if final_chrome_status else 'Not running'}")
        print(f"   Test result: {'SUCCESS' if success else 'FAILED'}")
        
        return success
        
    finally:
        # Clean up Automoy process
        print("🧹 Cleaning up Automoy process...")
        try:
            automoy_process.terminate()
            automoy_process.wait(timeout=10)
            print("✅ Automoy process terminated gracefully")
        except subprocess.TimeoutExpired:
            print("⚠️ Automoy process didn't terminate gracefully, killing...")
            automoy_process.kill()
        except Exception as e:
            print(f"⚠️ Error terminating Automoy process: {e}")

def main():
    """Main function"""
    print("Starting automated Chrome clicking test with full Automoy system...")
    
    try:
        success = automated_chrome_test()
        
        if success:
            print("\n🎉 TEST PASSED: Chrome was successfully opened by Automoy!")
        else:
            print("\n❌ TEST FAILED: Chrome was not opened successfully")
            print("\n🔧 TROUBLESHOOTING SUGGESTIONS:")
            print("   1. Check if Chrome icon is visible on desktop")
            print("   2. Verify OmniParser server is running for visual analysis")
            print("   3. Check LMStudio connection for LLM responses")
            print("   4. Review Automoy logs for specific errors")
            
        return success
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = main()
    exit_code = 0 if result else 1
    print(f"\nExiting with code: {exit_code}")
    sys.exit(exit_code)
