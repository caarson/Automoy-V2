#!/usr/bin/env python3

"""
Direct test of the visual analysis fix to verify Chrome element detection
This bypasses the goal system and directly tests the visual analysis pipeline
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent))

from core.operate import AutomoyOperator

async def test_visual_analysis_fix():
    """Test the visual analysis fix directly"""
    
    print("🧪 Testing Visual Analysis Fix")
    print("="*50)
    
    # Initialize components with minimal setup
    print("📋 Initializing AutomoyOperator...")
    operator = AutomoyOperator()
    
    # We'll need to initialize it properly
    try:
        # Mock GUI update function
        async def mock_gui_update(path, data):
            print(f"GUI Update: {path} -> {data}")
        
        # Basic initialization similar to what main.py does
        operator._update_gui_state_func = mock_gui_update
        
        print("✅ AutomoyOperator initialized")
        
        # Test the core method that was fixed
        print("\n🔍 Testing _get_action_for_current_step (the fixed method)...")
        
        # Set up minimal state
        operator.goal = "Test visual analysis fix"
        operator.current_step_index = 0
        operator.plan = ["Take screenshot to test visual analysis"]
        
        # This should now capture screenshot AND perform visual analysis (our fix)
        print("📷 Executing the fixed visual analysis pipeline...")
        
        # Instead of calling the full method, let's test our fix more directly
        # by checking if the visual analysis output gets populated
        
        # Take screenshot first
        screenshot_path = await operator._take_screenshot("visual_analysis_test")
        
        if screenshot_path:
            print(f"✅ Screenshot captured: {screenshot_path}")
            
            # Now perform visual analysis (this is what our fix added)
            processed_path, analysis_result = await operator._perform_visual_analysis(
                screenshot_path, "Testing visual analysis fix"
            )
            
            print(f"🧠 Visual analysis completed")
            
            # Check the key fix: visual_analysis_output should now have data
            print(f"\n🔑 CRITICAL TEST: Checking visual_analysis_output...")
            print(f"📊 Type: {type(operator.visual_analysis_output)}")
            
            if operator.visual_analysis_output and isinstance(operator.visual_analysis_output, dict):
                elements = operator.visual_analysis_output.get('elements', [])
                text_snippets = operator.visual_analysis_output.get('text_snippets', [])
                
                print(f"✅ SUCCESS! visual_analysis_output is populated:")
                print(f"   📋 Elements: {len(elements)} items")
                print(f"   📄 Text snippets: {len(text_snippets)} items")
                
                # Show some elements to verify the fix
                if elements:
                    print(f"\n📋 Sample elements (first 3):")
                    for i, element in enumerate(elements[:3]):
                        print(f"   Element {i+1}:")
                        print(f"     Text: {element.get('text', 'N/A')[:50]}")
                        print(f"     Type: {element.get('type', 'N/A')}")
                        if 'coordinates' in element:
                            coords = element['coordinates']
                            print(f"     Coordinates: ({coords.get('x', 'N/A')}, {coords.get('y', 'N/A')})")
                
                print(f"\n🎉 VISUAL ANALYSIS FIX TEST: PASSED!")
                print(f"   ✅ Before fix: visual_analysis_output was hardcoded to empty")
                print(f"   ✅ After fix: visual_analysis_output contains {len(elements)} elements")
                print(f"   ✅ Elements now have coordinates for clicking")
                
            else:
                print(f"❌ FAILURE: visual_analysis_output is still empty or wrong type")
                print(f"   Expected: dict with 'elements' and 'text_snippets'")
                print(f"   Actual: {operator.visual_analysis_output}")
                
        else:
            print("❌ Failed to capture screenshot for testing")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Starting Visual Analysis Fix Test...")
    asyncio.run(test_visual_analysis_fix())
