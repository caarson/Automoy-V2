from operate.config import Config
import json
import traceback
import re
import tiktoken

config = Config()

def extract_json_from_text(content):
    """
    Extracts JSON from OpenAI response text using regex.
    Returns an empty list if no JSON is found.
    """
    json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if json_match:
        json_text = json_match.group(1)
        return json_text.strip()
    else:
        print("[ERROR] No JSON block detected in OpenAI response.")
        return "[]"

def fix_json_format(raw_response):
    """
    Cleans up OpenAI's raw response to ensure it's valid JSON before parsing.
    """
    try:
        return json.loads(raw_response)  # Try parsing first
    except json.JSONDecodeError:
        print("[WARNING] OpenAI response has incorrect JSON formatting. Attempting auto-fix...")
        
        cleaned_response = re.sub(r'[^a-zA-Z0-9:{}\[\],"\'.\s]', '', raw_response)
        cleaned_response = re.sub(r',?\s*{}\s*', '', cleaned_response)
        cleaned_response = re.sub(r'"done"\s*:\s*{(.*?)\s*}', r'"done": {"summary": "\1"}', cleaned_response)
        cleaned_response = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1 "\2":', cleaned_response)
        
        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON Decode Failed After Fixing: {e}")
            return []

def count_tokens(messages, model_name="gpt-4o"):
    """Estimates the token count for OpenAI messages."""
    enc = tiktoken.encoding_for_model(model_name)
    return sum(len(enc.encode(msg["content"])) for msg in messages)

def truncate_messages(messages, max_tokens=7000, model_name="gpt-4o"):
    """Truncates messages to fit within OpenAI's context length limit."""
    total_tokens = count_tokens(messages, model_name)
    
    while total_tokens > max_tokens and len(messages) > 1:
        messages.pop(1)  # Remove oldest user messages first
        total_tokens = count_tokens(messages, model_name)

    return messages

def transform_operations(response_list):
    """
    Transforms OpenAI's response into the correct format.
    """
    transformed_operations = []
    for item in response_list:
        if isinstance(item, dict) and "operation" in item:
            transformed_operations.append(item)  # Keep the valid operation format
        else:
            print(f"[WARNING] Unexpected operation format: {item}")
    
    return transformed_operations

async def call_openai_model(messages, objective, model_name="gpt-4o"):
    """
    Calls OpenAI's GPT-based models and ensures JSON is formatted correctly.
    Directly truncates preprocessed data without additional parsing.
    """
    try:
        # Log the input being sent to GPT
        print(f"[DEBUG] Messages Sent to GPT Before Modification:\n{json.dumps(messages, indent=2)}")

        # Directly truncate preprocessed data
        preprocessed_data = messages[-1]["content"] if messages and "content" in messages[-1] else ""

        # Truncate the preprocessed data before adding it to messages
        def truncate_text(text, max_tokens=2000, model_name="gpt-4o"):
            enc = tiktoken.encoding_for_model(model_name)
            tokenized = enc.encode(text)
            return enc.decode(tokenized[:max_tokens]) if len(tokenized) > max_tokens else text

        preprocessed_data = truncate_text(preprocessed_data, max_tokens=2000)

        # Ensure preprocessed data does not exceed the limit before sending
        truncated_data = truncate_messages([{"role": "system", "content": preprocessed_data}], max_tokens=6000, model_name=model_name)
        
        messages = messages[:-1] + truncated_data

        print(f"[DEBUG] Messages Sent to GPT After Modification:\n{json.dumps(messages, indent=2)}")

        # Initialize OpenAI client and make the request
        client = config.initialize_openai()
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            presence_penalty=1,
            frequency_penalty=1,
        )

        if not response or not response.choices:
            print("[ERROR] OpenAI response is empty or invalid.")
            return []

        content = response.choices[0].message.content

        # Log the raw response from GPT
        print(f"[DEBUG] Raw GPT Response:\n{content}")

        try:
            parsed_response = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON Decode Error: {e}")
            return []

        parsed_response = fix_json_format(content)
        formatted_response = transform_operations(parsed_response)

        print(f"[DEBUG] Transformed OpenAI Response: {formatted_response}")

        return formatted_response if isinstance(formatted_response, list) else []

    except Exception as e:
        print(f"[ERROR] Exception in call_openai_model: {e}")
        if config.verbose:
            traceback.print_exc()
        return []
