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

async def call_lmstudio_model(messages, objective, model):
    """
    Calls the LMStudio API with streaming enabled.
    The function prints tokens as they arrive (so text appears as it's generated)
    and only returns the full response after the model finishes generating.
    
    We also increase the allowed size for preprocessed data.
    """
    config = Config()
    api_source, api_value = config.get_api_source()  # e.g., ("lmstudio", "http://localhost:8020")
    
    if api_source == "lmstudio":
        api_url = api_value.rstrip("/") + "/v1/chat/completions"
    else:
        raise RuntimeError("No valid API source found for LMStudio.")

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
        with requests.post(api_url, json=payload, headers=headers, stream=True) as response:
            response.raise_for_status()

            full_response = ""
            printed_any_token = False
            print("[Waiting for streamed output...]")  # Always print before streaming starts
            # Stream and print tokens as they arrive.
            for line in response.iter_lines():
                if not line:
                    continue
                decoded_line = line.decode("utf-8").strip()
                if decoded_line.startswith("data: "):
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
                        full_response += token if token is not None else ""
                        if json_data["choices"][0].get("finish_reason") is not None:
                            break
                    except json.JSONDecodeError:
                        print("[ERROR] Failed to parse streamed JSON chunk:", decoded_line)
                else:
                    print(f"[LMStudio stream] {decoded_line}")
            print("\n[DEBUG] Full Response Received:", full_response)
            
            # --- Attempt to extract and parse JSON action --- 
            if full_response:
                # Try to find a JSON code block
                match = re.search(r"```json\s*([\s\S]*?)\s*```", full_response)
                if match:
                    json_str = match.group(1).strip()
                    try:
                        parsed_json = json.loads(json_str)
                        # Check if it's a list of actions (as per DEFAULT_PROMPT)
                        if isinstance(parsed_json, list) and len(parsed_json) > 0:
                            # Return the first action object as a JSON string
                            # This makes it consistent with how openai_handler might return a string to be parsed later
                            action_to_return = parsed_json[0]
                            print(f"[DEBUG] Extracted JSON action from LMStudio: {action_to_return}")
                            return json.dumps([action_to_return]) # Return as a JSON string list
                        # Check if it's a single action object (less ideal but possible)
                        elif isinstance(parsed_json, dict) and "operation" in parsed_json:
                            print(f"[DEBUG] Extracted single JSON action object from LMStudio: {parsed_json}")
                            return json.dumps([parsed_json]) # Return as a JSON string list
                        else:
                            print("[DEBUG] Parsed JSON from LMStudio is not in the expected action format. Returning full response.")
                    except json.JSONDecodeError as e:
                        print(f"[ERROR] Failed to decode JSON from LMStudio response: {e}. Raw JSON string: {json_str}")
                else:
                    print("[DEBUG] No JSON code block found in LMStudio response. Returning full response.")
            # --- End JSON extraction attempt ---

            return full_response if full_response.strip() else "[ERROR] No valid response from the model."
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
