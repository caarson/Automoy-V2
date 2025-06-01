#!/usr/bin/env python3
"""
Test script to verify the coordinate conversion fix in operate.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.operate import AutomoyOperator
import asyncio
import json
from pathlib import Path

async def test_coordinate_conversion():
    """Test the coordinate conversion functionality"""
    print("🧪 Testing coordinate conversion fix...")
    
    # Mock visual analysis data similar to what OmniParser would return
    mock_coords_data = [
        {
            "content": "Chrome",
            "bbox": [0.1, 0.2, 0.3, 0.4]  # Normalized coordinates
        },
        {
            "content": "Google Chrome",
            "bbox": [0.5, 0.6, 0.7, 0.8]  # Normalized coordinates
        }
    ]
    
    # Create a mock AutomoyOperator instance (we only need the coordinate finding method)
    from unittest.mock import Mock
    
    # Mock the necessary dependencies
    mock_omniparser = Mock()
    mock_manage_gui = Mock()
    mock_update_gui = Mock()
    mock_pause_event = Mock()
    
    try:
        operator = AutomoyOperator(
            objective="test",
            manage_gui_window_func=mock_manage_gui,
            omniparser=mock_omniparser,
            pause_event=mock_pause_event,
            update_gui_state_func=mock_update_gui
        )
        
        # Test the coordinate finding method directly
        coords = operator._find_text_coordinates("Chrome", mock_coords_data)
        
        if coords:
            print(f"✅ Coordinate conversion successful: {coords}")
            print(f"   Found coordinates for 'Chrome': x={coords[0]}, y={coords[1]}")
            
            # Test with second item
            coords2 = operator._find_text_coordinates("Google Chrome", mock_coords_data)
            if coords2:
                print(f"✅ Second coordinate conversion successful: {coords2}")
                print(f"   Found coordinates for 'Google Chrome': x={coords2[0]}, y={coords2[1]}")
            else:
                print("❌ Second coordinate conversion failed")
                
        else:
            print("❌ Coordinate conversion failed - returned None")
            
    except Exception as e:
        print(f"❌ Error during coordinate conversion test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_coordinate_conversion())
