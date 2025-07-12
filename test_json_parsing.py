#!/usr/bin/env python3
"""
Test script to verify JSON parsing in step generation
"""
import json
import asyncio
import sys
import os
import logging

# Add project root to path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from core.lm.lm_interface import MainInterface

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_step_generation():
    """Test step generation with Calculator goal"""
    print("\n" + "="*60)
    print("TESTING STEP GENERATION FOR CALCULATOR")
    print("="*60)
    
    try:
        # Initialize the LLM interface
        llm_interface = MainInterface()
        print("✓ LLM Interface initialized successfully")
        
        # Test objective
        objective = "Open the Start Menu, search for \"Calculator\" in the search box, and click on the Calculator app result to launch it."
        print(f"📋 Objective: {objective}")
        
        # Generate steps
        print("\n🔄 Generating steps...")
        steps_data = await llm_interface.generate_steps(
            objective=objective,
            visual_summary="No visual context - screenshot will be taken when needed during execution",
            thinking_summary="automoy-op-1752273578"
        )
        
        print(f"\n📊 Raw steps_data type: {type(steps_data)}")
        print(f"📊 Raw steps_data: {steps_data}")
        
        # Verify the format
        if isinstance(steps_data, list):
            print(f"✓ Received list with {len(steps_data)} steps")
            for i, step in enumerate(steps_data):
                if isinstance(step, dict):
                    step_num = step.get('step_number', i+1)
                    description = step.get('description', 'No description')
                    action_type = step.get('action_type', 'Unknown')
                    target = step.get('target', 'Unknown')
                    print(f"  Step {step_num}: {action_type} -> {target}")
                    print(f"    Description: {description}")
                else:
                    print(f"  Step {i+1}: {step} (non-dict format)")
        elif isinstance(steps_data, dict):
            if "error" in steps_data:
                print(f"❌ Error in response: {steps_data['error']}")
            else:
                print(f"❌ Unexpected dict format: {steps_data}")
        else:
            print(f"❌ Unexpected format: {type(steps_data)} - {steps_data}")
            
    except Exception as e:
        print(f"❌ Error during step generation test: {e}")
        import traceback
        traceback.print_exc()

async def test_action_generation():
    """Test action generation for a single step"""
    print("\n" + "="*60)
    print("TESTING ACTION GENERATION FOR SINGLE STEP")
    print("="*60)
    
    try:
        # Initialize the LLM interface
        llm_interface = MainInterface()
        print("✓ LLM Interface initialized successfully")
        
        # Test step
        step_description = "Open the Windows Start Menu by clicking the Start button or pressing the Windows key"
        print(f"📋 Step: {step_description}")
        
        # Generate action
        print("\n🔄 Generating action...")
        action_data = await llm_interface.get_action(
            step_description=step_description,
            current_step_index=0,
            visual_summary="No visual context available",
            steps_summary="First step in Calculator launch sequence"
        )
        
        print(f"\n📊 Raw action_data type: {type(action_data)}")
        print(f"📊 Raw action_data: {action_data}")
        
        # Verify the format
        if isinstance(action_data, dict):
            action_type = action_data.get('type', action_data.get('action_type', 'Unknown'))
            target = action_data.get('target', action_data.get('key', action_data.get('text', 'Unknown')))
            confidence = action_data.get('confidence', 'Unknown')
            print(f"✓ Action type: {action_type}")
            print(f"✓ Target: {target}")
            print(f"✓ Confidence: {confidence}")
        else:
            print(f"❌ Unexpected format: {type(action_data)} - {action_data}")
            
    except Exception as e:
        print(f"❌ Error during action generation test: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Run all tests"""
    print("🧪 JSON Parsing Test Suite Starting...")
    
    await test_step_generation()
    await test_action_generation()
    
    print("\n" + "="*60)
    print("🏁 TEST SUITE COMPLETED")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
