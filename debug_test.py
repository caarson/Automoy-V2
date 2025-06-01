"""
Debug script to test the three main issues:
1. GUI hiding during screenshots
2. Operations display in GUI
3. OmniParser status indicator
"""

import asyncio
import httpx
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import app_config

async def test_gui_endpoints():
    """Test GUI endpoints to see what data is being returned"""
    print("=== TESTING GUI ENDPOINTS ===")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Test the state endpoint
            print("1. Testing /state endpoint...")
            response = await client.get(f"http://{app_config.GUI_HOST}:{app_config.GUI_PORT}/state")
            if response.status_code == 200:
                data = response.json()
                print("✅ /state endpoint working")
                print(f"Operations generated data: {data.get('current_operations_generated', 'NOT FOUND')}")
                print(f"Thinking process: {data.get('current_thinking_process', 'NOT FOUND')}")
            else:
                print(f"❌ /state endpoint failed: {response.status_code}")
                
            # Test OmniParser probe
            print("\n2. Testing OmniParser probe...")
            try:
                omni_response = await client.get(f"http://localhost:{app_config.OMNIPARSER_PORT}/probe/")
                if omni_response.status_code == 200:
                    print("✅ OmniParser is responding")
                else:
                    print(f"❌ OmniParser probe failed: {omni_response.status_code}")
            except Exception as e:
                print(f"❌ OmniParser connection failed: {e}")
                
            # Test operations_generated endpoint by sending test data
            print("\n3. Testing operations_generated endpoint...")
            test_operations = {
                "operations": [
                    {"type": "click", "summary": "Click test button", "details": "Test operation"}
                ],
                "thinking_process": "This is a test thinking process"
            }
            
            ops_response = await client.post(
                f"http://{app_config.GUI_HOST}:{app_config.GUI_PORT}/state/operations_generated",
                json=test_operations
            )
            if ops_response.status_code == 200:
                print("✅ Operations endpoint accepting data")
                
                # Check if the data is now available in state
                state_response = await client.get(f"http://{app_config.GUI_HOST}:{app_config.GUI_PORT}/state")
                if state_response.status_code == 200:
                    state_data = state_response.json()
                    current_ops = state_data.get('current_operations_generated', {})
                    print(f"Operations now in state: {current_ops}")
                else:
                    print("❌ Could not verify operations in state")
            else:
                print(f"❌ Operations endpoint failed: {ops_response.status_code} - {ops_response.text}")
                
    except Exception as e:
        print(f"❌ HTTP test failed: {e}")

async def test_gui_management():
    """Test if GUI management functions are working"""
    print("\n=== TESTING GUI MANAGEMENT ===")
    
    try:
        # Import the GUI management function
        from core.main import async_manage_gui_window
        
        print("1. Testing GUI hide...")
        result = await async_manage_gui_window("hide")
        print(f"Hide result: {result}")
        
        await asyncio.sleep(2)
        
        print("2. Testing GUI show...")
        result = await async_manage_gui_window("show")
        print(f"Show result: {result}")
        
    except Exception as e:
        print(f"❌ GUI management test failed: {e}")

if __name__ == "__main__":
    print("Starting debug tests...")
    asyncio.run(test_gui_endpoints())
    asyncio.run(test_gui_management())
    print("Debug tests completed!")
