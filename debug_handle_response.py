#!/usr/bin/env python3
"""
Debug the handle_llm_response function step by step.
"""

import json
import re
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def debug_handle_llm_response():
    """Debug handle_llm_response step by step."""
    
    # The exact problematic JSON from the task output
    raw_response_text = r'{"type": "key", "key": "win", "summary": "Press Windows key to open Start menu\", \"confidence": 80}'
    context_description = "action_generation"
    is_json = True
    
    print(f"Input: {raw_response_text}")
    print(f"Context: {context_description}")
    print(f"is_json: {is_json}")
    
    # Step 1: Strip tags (like <think>...</think>)
    def strip_tags(text):
        if not isinstance(text, str):
            return ""
        # Remove <think>...</think> tags
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        # Remove any simple, standalone XML/HTML tag like <tag_name> or <tag_name/>
        text = re.sub(r"<\w+/?>(?!</\w+>)", "", text)
        text = re.sub(r"<([A-Za-z][A-Za-z0-9]*)\b[^>]*>(.*?)</\1>", r"\2", text, flags=re.DOTALL)
        return text.strip()
    
    text_to_search_json_in = strip_tags(str(raw_response_text))
    print(f"After strip_tags: {text_to_search_json_in}")
    
    # Step 2: Check if it's already valid JSON
    json_str_to_parse = None
    try:
        stripped_text = text_to_search_json_in.strip()
        test_parse = json.loads(stripped_text)
        json_str_to_parse = stripped_text
        print(f"✅ Already valid JSON detected")
    except json.JSONDecodeError:
        print(f"❌ Not valid JSON, trying extraction methods")
    
    # Step 3: Try extraction methods if not already valid JSON
    if not json_str_to_parse:
        # Method 1: Look for ```json code blocks
        json_match = re.search(r"```json\s*(.*?)\s*```", text_to_search_json_in, re.DOTALL)
        if json_match:
            json_str_to_parse = json_match.group(1).strip()
            print(f"✅ Found JSON in markdown code block")
        else:
            print("❌ No markdown code block found")
            
            # Method 2: Look for any code blocks that might contain JSON
            code_match = re.search(r"```\s*(.*?)\s*```", text_to_search_json_in, re.DOTALL)
            if code_match:
                potential_json = code_match.group(1).strip()
                if (potential_json.startswith("{") and potential_json.endswith("}")) or \
                   (potential_json.startswith("[") and potential_json.endswith("]")):
                    json_str_to_parse = potential_json
                    print(f"✅ Found JSON in generic code block")
                else:
                    print("❌ Code block doesn't contain JSON-like content")
            else:
                print("❌ No code blocks found")
            
            # Method 3: Look for JSON objects/arrays in the text
            if not json_str_to_parse:
                print("Trying to find JSON object pattern...")
                # Find JSON objects { ... }
                json_obj_match = re.search(r'\{.*\}', text_to_search_json_in, re.DOTALL)
                if json_obj_match:
                    json_str_to_parse = json_obj_match.group(0).strip()
                    print(f"✅ Found JSON object pattern: {json_str_to_parse[:50]}...")
                else:
                    print("❌ No JSON object pattern found")
                    # Find JSON arrays [ ... ]
                    json_arr_match = re.search(r'\[.*\]', text_to_search_json_in, re.DOTALL)
                    if json_arr_match:
                        json_str_to_parse = json_arr_match.group(0).strip()
                        print(f"✅ Found JSON array pattern")
                    else:
                        print("❌ No JSON array pattern found either")
    
    if json_str_to_parse:
        print(f"✅ JSON string extracted: {json_str_to_parse}")
        return True
    else:
        print(f"❌ No JSON found - this is the problem!")
        return False

if __name__ == "__main__":
    success = debug_handle_llm_response()
    if success:
        print("\n✅ JSON extraction should work!")
    else:
        print("\n❌ JSON extraction is failing.")
