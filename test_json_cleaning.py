#!/usr/bin/env python3
"""
Test JSON cleaning function
"""
import json
import re

def test_json_cleaning():
    """Test various JSON cleaning scenarios"""
    
    test_cases = [
        # Case 1: Invalid escape sequence
        '{"action_type": "click\", "description": "Click button"}',
        
        # Case 2: Unescaped quotes in description
        '{"action_type": "click", "description": "Click the "Start" button"}',
        
        # Case 3: Apostrophes
        '{"action_type": "click", "description": "Open the Start menu\'s search"}',
        
        # Case 4: Multiple issues
        '{"action_type": "keyboard\", "description": "Press Win + S to open search"}',
        
        # Case 5: Valid JSON (should not break)
        '{"action_type": "click", "description": "Click button", "target": "button"}'
    ]
    
    for i, test_json in enumerate(test_cases, 1):
        print(f"\n=== Test Case {i} ===")
        print(f"Original: {test_json}")
        
        # Apply cleaning logic
        json_str_to_parse = test_json
        
        # Remove trailing commas
        json_str_to_parse = re.sub(r',(\s*[}\]])', r'\1', json_str_to_parse)
        
        # Fix invalid escape sequences like "action_type": "click\"
        json_str_to_parse = re.sub(r'": "([^"]*)\\"', r'": "\1"', json_str_to_parse)
        
        # Fix unescaped quotes in description strings
        def fix_unescaped_quotes_in_field(match):
            field_name = match.group(1)
            content = match.group(2)
            # Count quotes to see if they are properly escaped
            if content.count('"') > 0 and content.count('\\"') == 0:
                # There are unescaped quotes, fix them
                escaped_content = content.replace('"', '\\"')
                return f'"{field_name}": "{escaped_content}"'
            return match.group(0)  # Return original if already escaped
        
        # Apply quote fixing to common string fields
        json_str_to_parse = re.sub(r'"(description|summary|text|target|input_text)": "([^"]*(?:"[^"]*)*)"', fix_unescaped_quotes_in_field, json_str_to_parse)
        
        # Fix apostrophes in possessives - be more careful
        json_str_to_parse = re.sub(r"([a-zA-Z])'([a-zA-Z])", r"\1\\'\2", json_str_to_parse)
        
        print(f"Cleaned:  {json_str_to_parse}")
        
        # Test parsing
        try:
            parsed = json.loads(json_str_to_parse)
            print(f"✅ SUCCESS: {parsed}")
        except json.JSONDecodeError as e:
            print(f"❌ FAILED: {e}")

if __name__ == "__main__":
    test_json_cleaning()
