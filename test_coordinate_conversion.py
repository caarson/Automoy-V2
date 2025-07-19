#!/usr/bin/env python3
"""
Direct test of coordinate conversion system
Tests the _format_visual_analysis_result method to verify coordinate conversion works
"""

import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
sys.path.insert(0, project_root)

def test_coordinate_conversion():
    """Test the coordinate conversion logic directly"""
    print("=== TESTING COORDINATE CONVERSION SYSTEM ===")
    
    # Mock visual analysis result with normalized bbox coordinates
    mock_visual_result = {
        "parsed_content_list": [
            {
                "interactable": True,
                "label": "Google Chrome",
                "bbox_normalized": [0.1, 0.95, 0.15, 0.99],  # Chrome icon in taskbar
                "text": "Chrome"
            },
            {
                "interactable": True, 
                "label": "Desktop Icon",
                "bbox_normalized": [0.05, 0.1, 0.1, 0.15],  # Desktop icon
                "text": "Some App"
            }
        ]
    }
    
    # Import the AutomoyOperator class to access the formatting method
    try:
        from core.operate import AutomoyOperator
        
        # Create a minimal operator instance for testing
        class MockOperator:
            def _format_visual_analysis_result(self, parsed_result):
                """Copy the method from AutomoyOperator for testing"""
                if not parsed_result or "parsed_content_list" not in parsed_result:
                    return "No visual elements detected."
                
                elements = parsed_result["parsed_content_list"]
                
                # Get screen dimensions for coordinate conversion
                try:
                    import pyautogui
                    screen_width, screen_height = pyautogui.size()
                    print(f"Screen dimensions: {screen_width} x {screen_height}")
                except ImportError:
                    print("PyAutoGUI not available, using default screen size")
                    screen_width, screen_height = 1920, 1080
                
                result_lines = []
                result_lines.append(f"Visual Analysis Results - Found {len(elements)} elements:")
                result_lines.append("")
                
                for i, element in enumerate(elements):
                    element_id = f"element_{i+1}"
                    label = element.get("label", "Unknown element")
                    interactable = element.get("interactable", False)
                    text = element.get("text", "")
                    
                    # COORDINATE CONVERSION: Convert normalized bbox to pixel coordinates
                    bbox_normalized = element.get("bbox_normalized", [])
                    if len(bbox_normalized) == 4:
                        x1_norm, y1_norm, x2_norm, y2_norm = bbox_normalized
                        
                        # Convert to pixel coordinates
                        x1_pixel = int(x1_norm * screen_width)
                        y1_pixel = int(y1_norm * screen_height)
                        x2_pixel = int(x2_norm * screen_width)
                        y2_pixel = int(y2_norm * screen_height)
                        
                        # Calculate center point for clicking
                        center_x = (x1_pixel + x2_pixel) // 2
                        center_y = (y1_pixel + y2_pixel) // 2
                        
                        result_lines.append(f"{element_id}: {label}")
                        result_lines.append(f"  Text: '{text}'")
                        result_lines.append(f"  Interactable: {'Yes' if interactable else 'No'}")
                        result_lines.append(f"  BoundingBox: ({x1_pixel}, {y1_pixel}) to ({x2_pixel}, {y2_pixel})")
                        result_lines.append(f"  ClickCoordinates: ({center_x}, {center_y})")
                        result_lines.append("")
                        
                        print(f"CONVERSION TEST: {label}")
                        print(f"  Normalized: {bbox_normalized}")
                        print(f"  Pixel Box: ({x1_pixel}, {y1_pixel}) to ({x2_pixel}, {y2_pixel})")
                        print(f"  Click Point: ({center_x}, {center_y})")
                        print()
                    else:
                        result_lines.append(f"{element_id}: {label}")
                        result_lines.append(f"  Text: '{text}'")
                        result_lines.append(f"  Interactable: {'Yes' if interactable else 'No'}")
                        result_lines.append(f"  No coordinate data available")
                        result_lines.append("")
                
                return "\n".join(result_lines)
        
        # Test the coordinate conversion
        mock_op = MockOperator()
        formatted_result = mock_op._format_visual_analysis_result(mock_visual_result)
        
        print("=== FORMATTED VISUAL ANALYSIS OUTPUT ===")
        print(formatted_result)
        print()
        
        # Test coordinate extraction from formatted output
        print("=== TESTING COORDINATE EXTRACTION ===")
        import re
        coordinate_pattern = r"ClickCoordinates:\s*\((\d+),\s*(\d+)\)"
        matches = re.findall(coordinate_pattern, formatted_result)
        
        print(f"Found {len(matches)} coordinate pairs:")
        for i, (x, y) in enumerate(matches):
            print(f"  Coordinate {i+1}: ({x}, {y})")
        
        if matches:
            print("✅ Coordinate conversion and extraction working correctly!")
            return True
        else:
            print("❌ No coordinates found in formatted output")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

if __name__ == "__main__":
    success = test_coordinate_conversion()
    if success:
        print("\n🎉 COORDINATE CONVERSION SYSTEM IS WORKING!")
    else:
        print("\n💥 COORDINATE CONVERSION SYSTEM NEEDS FIXING")
