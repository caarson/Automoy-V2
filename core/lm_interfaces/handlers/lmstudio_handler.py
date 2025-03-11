import os
import sys
import requests
import json
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from operate.config import Config  # Corrected import path

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

    try:
        with requests.post(api_url, json=payload, headers=headers, stream=True) as response:
            response.raise_for_status()

            full_response = ""
            # Stream and print tokens as they arrive.
            for line in response.iter_lines():
                if not line:
                    continue
                decoded_line = line.decode("utf-8").strip()
                if decoded_line.startswith("data: "):
                    try:
                        # Parse the JSON chunk to extract the token.
                        json_data = json.loads(decoded_line[6:])
                        token = json_data["choices"][0].get("delta", {}).get("content", "")
                        # Print token as it's generated.
                        print(token, end="", flush=True)
                        full_response += token
                        # Stop when finish_reason is provided.
                        if json_data["choices"][0].get("finish_reason") is not None:
                            break
                    except json.JSONDecodeError:
                        print("[ERROR] Failed to parse streamed JSON chunk:", decoded_line)
            print("\n[DEBUG] Full Response Received:", full_response)
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
