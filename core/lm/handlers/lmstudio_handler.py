import os
import sys
import pathlib
import requests
import json
import asyncio
import re  # Add re import for regex search

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent.parent / "config"))
from config import Config

# Helper function to format OCR & YOLO data into a readable string
def format_preprocessed_data(data):
    """
    Converts preprocessed OCR and YOLO data into a clean string format.
    Ensures it's properly formatted for LMStudio without breaking JSON parsing.
    """
    if not isinstance(data, dict):
        return "No valid preprocessed data."
    formatted_string = "\n".join(
        [f"{key}: {', '.join(map(str, value))}" for key, value in data.items()]
    )
    return f"Preprocessed data with OCR and YOLO:\n{formatted_string}"

# Ensures messages follow OpenAI's API format
def format_messages(messages):
    formatted = []
    for msg in messages:
        if "role" in msg and "content" in msg:
            if msg["content"] is None or not isinstance(msg["content"], str):
                print(f"[WARNING] Fixing malformed message: {msg}")  # Debugging
                msg["content"] = ""  # Convert None to empty string
            formatted.append({"role": msg["role"], "content": msg["content"]})
        else:
            print(f"[ERROR] Malformed message detected: {msg}")
    return formatted

async def call_lmstudio_model(messages, objective, model, thinking_callback=None):
    """
    Calls the LMStudio API with streaming enabled.
    The function prints tokens as they arrive (so text appears as it's generated)
    and only returns the full response after the model finishes generating.
    
    Args:
        thinking_callback: Optional async function to call with each streamed token
    
    We also increase the allowed size for preprocessed data.
    """
    config = Config()
    try:
        api_source, api_value = config.get_api_source()  # e.g., ("lmstudio", "http://localhost:8020")
        
        # Add enhanced error checking for API source and URL
        if api_source != "lmstudio":
            error_msg = f"[ERROR] Expected LMStudio API but got {api_source} instead"
            print(error_msg)
            return error_msg
            
        if not api_value or not api_value.strip():
            error_msg = "[ERROR] No LMStudio API URL specified in configuration"
            print(error_msg)
            return error_msg
            
        api_url = api_value.rstrip("/") + "/v1/chat/completions"
        
        # Test the API connection quickly before proceeding
        try:
            print(f"[DEBUG] Testing LMStudio API connection at {api_url}")
            test_response = requests.get(api_value.rstrip("/") + "/v1/models", timeout=3)
            if test_response.status_code != 200:
                error_msg = f"[ERROR] LMStudio API not available (status: {test_response.status_code})"
                print(error_msg)
                return error_msg
            print("[DEBUG] LMStudio API connection successful")
        except requests.RequestException as e:
            error_msg = f"[ERROR] Could not connect to LMStudio API: {e}"
            print(error_msg)
            return error_msg
    except Exception as e:
        error_msg = f"[ERROR] Failed to get LMStudio API configuration: {e}"
        print(error_msg)
        return error_msg

    headers = {"Content-Type": "application/json"}

    # Combine the objective and provided messages.
    formatted_messages = (
        [{"role": "system", "content": objective if objective else "Default objective"}] +
        format_messages(messages)
    )

    # --- Troubleshooting: Adjust truncation threshold ---
    # Increase threshold to allow more data (e.g., 5000 characters)
    for msg in formatted_messages:
        if msg["role"] == "system" and "Preprocessed data summary:" in msg["content"]:
            original_content = msg["content"]
            max_length = 5000  # Allow a larger amount of data
            if len(original_content) > max_length:
                print(f"[DEBUG] Preprocessed data message length: {len(original_content)} exceeds {max_length}. Truncating.")
                truncated_content = original_content[:max_length] + "\n... [truncated]"
                msg["content"] = truncated_content
            else:
                print(f"[DEBUG] Preprocessed data message length: {len(original_content)} is within limits.")

    # Log the sanitized preprocessed data for inspection.
    for msg in formatted_messages:
        if msg["role"] == "system" and "Preprocessed data summary:" in msg["content"]:
            print("[DEBUG] Sanitized preprocessed data message:")
            print(msg["content"])

    # Prepare payload with streaming enabled.
    payload = {
        "model": model,
        "messages": formatted_messages,
        "max_tokens": 2000,
        "temperature": 0.7,
        "top_p": 0.9,
        "stream": True  # Enable streaming so tokens appear as they're generated.
    }

    print(f"[DEBUG] Sending request to LMStudio API ({api_url}) with model: {model}")
    print(f"[DEBUG] Final Payload Before Sending:\n{json.dumps(payload, indent=2)}")
    payload_str = json.dumps(payload)
    print(f"[DEBUG] Payload size: {len(payload_str)} bytes")
    if len(payload_str) > 10000:
        print("[WARNING] Payload is very large and may cause timeouts or errors.")

    try:
        # Add timeout to prevent hanging requests
        with requests.post(api_url, json=payload, headers=headers, stream=True, timeout=45) as response:
            response.raise_for_status()

            full_response = ""
            printed_any_token = False
            print("[Waiting for streamed output...]")  # Always print before streaming starts
            
            # Using iter_content for more robust chunk handling
            for chunk in response.iter_content(chunk_size=None):
                if not chunk:
                    continue
                
                decoded_chunk = chunk.decode("utf-8")
                
                # Process each line in the chunk
                for line in decoded_chunk.splitlines():
                    decoded_line = line.strip()
                    if not decoded_line:
                        continue

                    if decoded_line.startswith("data: "):
                        # Handle the [DONE] marker which indicates end of stream
                        if decoded_line[6:].strip() == "[DONE]":
                            break
                        
                        try:
                            json_data = json.loads(decoded_line[6:])
                            if not isinstance(json_data, dict) or "choices" not in json_data:
                                print(f"[ERROR] Unexpected LMStudio chunk: {json_data}")
                                continue
                            token = json_data["choices"][0].get("delta", {}).get("content", "")
                            if token is not None and token != "":
                                printed_any_token = True
                                sys.stdout.write(token)
                                sys.stdout.flush()
                                
                                # Call the thinking callback if provided
                                if thinking_callback:
                                    try:
                                        await thinking_callback(token)
                                    except Exception as e:
                                        print(f"[ERROR] Thinking callback failed: {e}")
                                        
                            full_response += token if token is not None else ""
                            if json_data["choices"][0].get("finish_reason") is not None:
                                break
                        except json.JSONDecodeError:
                            print("[ERROR] Failed to parse streamed JSON chunk:", decoded_line)
                    else:
                        print(f"[LMStudio stream] {decoded_line}")
                
                if "data: [DONE]" in decoded_chunk:
                    break

            if not printed_any_token:
                print("\n[DEBUG] No tokens were received in the stream.")

            print("\n[DEBUG] Full Response Received:", full_response)
            
            # --- Attempt to extract and parse JSON action --- 
            if full_response:
                # First try to find a JSON code block
                match = re.search(r"```json\s*([\s\S]*?)\s*```", full_response)
                if match:
                    json_str = match.group(1).strip()
                    print(f"[DEBUG] Found JSON code block: {json_str[:100]}...")
                else:
                    # If no code block, try to extract raw JSON array from the response
                    # Look for JSON array pattern starting with [ and ending with ]
                    array_match = re.search(r'\[\s*\{[\s\S]*?\}\s*\]', full_response)
                    if array_match:
                        json_str = array_match.group(0).strip()
                        print(f"[DEBUG] Found raw JSON array: {json_str[:100]}...")
                    else:
                        # Look for single JSON object pattern with better brace matching
                        # This regex will properly match opening and closing braces
                        brace_count = 0
                        start_idx = -1
                        end_idx = -1
                        
                        for i, char in enumerate(full_response):
                            if char == '{':
                                if start_idx == -1:
                                    start_idx = i
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0 and start_idx != -1:
                                    end_idx = i + 1
                                    break
                        
                        if start_idx != -1 and end_idx != -1:
                            json_str = full_response[start_idx:end_idx].strip()
                            print(f"[DEBUG] Found raw JSON object: {json_str[:100]}...")
                        else:
                            json_str = None
                
                if json_str:
                    try:
                        parsed_json = json.loads(json_str)
                        print(f"[DEBUG] LMStudio parsed JSON type: {type(parsed_json)}")
                        if isinstance(parsed_json, list):
                            print(f"[DEBUG] LMStudio parsed list with {len(parsed_json)} items")
                            if len(parsed_json) > 0:
                                print(f"[DEBUG] First item type: {type(parsed_json[0])}")
                                if isinstance(parsed_json[0], dict):
                                    print(f"[DEBUG] First item keys: {list(parsed_json[0].keys())}")
                                    print(f"[DEBUG] Has step_number: {'step_number' in parsed_json[0]}")
                        elif isinstance(parsed_json, dict):
                            print(f"[DEBUG] LMStudio parsed dict with keys: {list(parsed_json.keys())}")
                        
                        # Check if it's a single action object (direct action format)
                        if isinstance(parsed_json, dict) and ("type" in parsed_json or "action_type" in parsed_json):
                            print(f"[DEBUG] Extracted single JSON action from LMStudio: {parsed_json}")
                            return json.dumps(parsed_json) # Return single action as JSON string
                        # Check if it's a list of steps (for step generation) - MOVED BEFORE general list check
                        elif isinstance(parsed_json, list) and len(parsed_json) > 0 and "step_number" in parsed_json[0]:
                            print(f"[DEBUG] Extracted JSON steps from LMStudio: {len(parsed_json)} steps")
                            return json.dumps(parsed_json) # Return the full steps array
                        # Check if it's a list of actions (as per DEFAULT_PROMPT)
                        elif isinstance(parsed_json, list) and len(parsed_json) > 0:
                            # For action generation, return the first action
                            action_to_return = parsed_json[0]
                            print(f"[DEBUG] Extracted JSON action from LMStudio list: {action_to_return}")
                            return json.dumps(action_to_return) # Return single action as JSON string
                        # Check if it's a single action object with "operation" field
                        elif isinstance(parsed_json, dict) and "operation" in parsed_json:
                            print(f"[DEBUG] Extracted single JSON action object from LMStudio: {parsed_json}")
                            return json.dumps(parsed_json) # Return as single action
                        else:
                            print(f"[DEBUG] Parsed JSON from LMStudio is not in expected format: {type(parsed_json)}, keys: {list(parsed_json.keys()) if isinstance(parsed_json, dict) else 'Not a dict'}")
                            print(f"[DEBUG] Returning extracted JSON anyway: {parsed_json}")
                            return json.dumps(parsed_json)
                    except json.JSONDecodeError as e:
                        print(f"[ERROR] Failed to decode JSON from LMStudio response: {e}. Raw JSON string: {json_str}")
                else:
                    print("[DEBUG] No JSON found in LMStudio response. Returning full response.")
            # --- End JSON extraction attempt ---

            return full_response if full_response.strip() else "[ERROR] No valid response from the model."
    except requests.Timeout:
        error_msg = "[ERROR] LMStudio API call timed out after 45 seconds. Check if LMStudio is running and responsive."
        print(error_msg)
        return error_msg
    except requests.ConnectionError:
        error_msg = "[ERROR] Cannot connect to LMStudio API. Check if LMStudio is running and accessible."
        print(error_msg)
        return error_msg
    except requests.RequestException as e:
        error_msg = f"[ERROR] API connection failed: {e}"
        print(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"[ERROR] Unexpected error in call_lmstudio_model: {e}"
        print(error_msg)
        return error_msg

async def test_lmstudio(model):
    test_messages = [{"role": "user", "content": "tell me about google"}]
    test_objective = "Answer the user's question."

    try:
        response = await call_lmstudio_model(test_messages, test_objective, model)
        print("\nTest Response:", response)
    except Exception as e:
        print("Error during test:", e)

if __name__ == "__main__":
    asyncio.run(test_lmstudio(model="deepseek-r1-distill-llama-8b"))
