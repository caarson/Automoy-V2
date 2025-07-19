#!/usr/bin/env python3
"""
Direct test of JSON parsing logic without full LLM interface.
"""

import json
import re
import sys
import os

def test_json_parsing_directly():
    """Test the JSON parsing logic directly."""
    
    # The exact problematic JSON from the task output
    raw_response_text = r'{"type": "key", "key": "win", "summary": "Press Windows key to open Start menu\", \"confidence": 80}'
    context_description = "action_generation"
    
    print(f"Testing: {raw_response_text}")
    
    # Step 1: Strip tags (simplified)
    def strip_tags(text):
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        return text.strip()
    
    text_to_search_json_in = strip_tags(raw_response_text)
    print(f"After strip_tags: {text_to_search_json_in}")
    
    # Step 2: Check if already valid JSON
    json_str_to_parse = None
    try:
        stripped_text = text_to_search_json_in.strip()
        test_parse = json.loads(stripped_text)
        json_str_to_parse = stripped_text
        print(f"✅ Already valid JSON")
    except json.JSONDecodeError:
        print(f"❌ Not valid JSON directly")
    
    # Step 3: Extract JSON if not already valid
    if not json_str_to_parse:
        # Try JSON object pattern
        json_obj_match = re.search(r'\{.*\}', text_to_search_json_in, re.DOTALL)
        if json_obj_match:
            json_str_to_parse = json_obj_match.group(0).strip()
            print(f"✅ Found JSON object: {json_str_to_parse}")
        else:
            print(f"❌ No JSON object found")
            return False
    
    # Step 4: Apply cleaning and try to parse
    if json_str_to_parse:
        print(f"Applying fixes to: {json_str_to_parse}")
        
        # Apply our specific fixes
        fixed_json = json_str_to_parse
        
        # Remove comments and basic cleanup
        fixed_json = re.sub(r"//.*?\n", "\n", fixed_json)
        fixed_json = re.sub(r"#.*?\n", "\n", fixed_json)
        fixed_json = re.sub(r',(\s*[}\]])', r'\1', fixed_json)
        fixed_json = fixed_json.replace('{{', '{').replace('}}', '}')
        fixed_json = re.sub(r'(\w+)(\s*:\s*)', r'"\1"\2', fixed_json)
        fixed_json = fixed_json.replace("'", '"')
        fixed_json = re.sub(r'```json\s*', '', fixed_json)
        fixed_json = re.sub(r'```\s*', '', fixed_json)
        fixed_json = fixed_json.strip()
        fixed_json = re.sub(r'([^\\])\\+"', r'\1"', fixed_json)
        fixed_json = re.sub(r'([^\\])\\([^\\nt"])', r'\1\2', fixed_json)
        fixed_json = fixed_json.replace('"', '"').replace('"', '"')
        fixed_json = fixed_json.replace(''', "'").replace(''', "'")
        
        # Apply our specific quote fixes
        fixed_json = re.sub(r'\\"\s*,\s*\\"([^"]+)":', r'", "\1":', fixed_json)
        fixed_json = re.sub(r'([^\\])\\"\s*,', r'\1",', fixed_json)
        fixed_json = re.sub(r'([^\\])\\"\s*}', r'\1"}', fixed_json)
        
        print(f"After fixes: {fixed_json}")
        
        try:
            parsed_json = json.loads(fixed_json)
            print(f"✅ Successfully parsed: {parsed_json}")
            return parsed_json
        except json.JSONDecodeError as e:
            print(f"❌ Parse failed even after fixes: {e}")
            return False
    
    return False

if __name__ == "__main__":
    result = test_json_parsing_directly()
    if result:
        print("\n✅ JSON parsing works!")
    else:
        print("\n❌ JSON parsing failed.")
