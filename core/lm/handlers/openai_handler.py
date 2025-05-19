import sys
import pathlib
import json
import traceback
import re
import tiktoken

# Load Config
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent.parent / "config"))
from config import Config

config = Config()

def extract_json_from_text(content):
    json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    print("[ERROR] No JSON block detected in OpenAI response. Returning raw content.")
    return content.strip()  # fallback to raw content

def fix_json_format(raw_response):
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        print("[WARNING] Attempting to fix JSON format...")
        cleaned_response = re.sub(r'[^a-zA-Z0-9:{}\[\],"\'.\s]', '', raw_response)
        cleaned_response = re.sub(r',?\s*{}\s*', '', cleaned_response)
        cleaned_response = re.sub(r'"done"\s*:\s*{(.*?)\s*}', r'"done": {"summary": "\1"}', cleaned_response)
        cleaned_response = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1 "\2":', cleaned_response)
        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON Decode Failed After Fixing: {e}")
            return []

def count_tokens(messages, model_name):
    try:
        enc = tiktoken.encoding_for_model(model_name)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return sum(len(enc.encode(msg["content"])) for msg in messages)

def truncate_messages(messages, max_tokens, model_name):
    while count_tokens(messages, model_name) > max_tokens and len(messages) > 1:
        messages.pop(1)  # remove oldest user message first
    return messages

def transform_operations(response_list):
    transformed = []
    for item in response_list:
        if isinstance(item, dict) and "operation" in item:
            transformed.append(item)
        else:
            print(f"[WARNING] Unexpected operation format: {item}")
    return transformed

async def call_openai_model(messages, objective, model_name=None):
    try:
        model_name = model_name or config.get_model()
        temperature = config.get_temperature()

        if config.get("DEBUG", False):
            print(f"[DEBUG] Raw messages:\n{json.dumps(messages, indent=2)}")

        content = messages[-1]["content"] if messages and "content" in messages[-1] else ""

        def truncate_text(text, max_tokens, model_name):
            try:
                enc = tiktoken.encoding_for_model(model_name)
            except KeyError:
                enc = tiktoken.get_encoding("cl100k_base")
            tokenized = enc.encode(text)
            return enc.decode(tokenized[:max_tokens]) if len(tokenized) > max_tokens else text

        content = truncate_text(content, max_tokens=2000, model_name=model_name)
        truncated_data = truncate_messages([{"role": "system", "content": content}], max_tokens=6000, model_name=model_name)
        messages = messages[:-1] + truncated_data

        if config.get("DEBUG", False):
            print(f"[DEBUG] Truncated messages:\n{json.dumps(messages, indent=2)}")

        import openai
        client = openai.OpenAI(api_key=config.get("OPENAI_API_KEY"))

        stream = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            presence_penalty=1,
            frequency_penalty=1,
            stream=True,
        )

        collected_content = ""
        for chunk in stream:
            delta = getattr(chunk.choices[0].delta, "content", None)
            if delta:
                if config.get("DEBUG", False):
                    print(delta, end="", flush=True)
                collected_content += delta

        if config.get("DEBUG", False):
            print(f"\n[DEBUG] Raw GPT Response Content (streamed):\n{repr(collected_content)}")

        raw_json = extract_json_from_text(collected_content)
        parsed = fix_json_format(raw_json)
        transformed = transform_operations(parsed)
        return transformed if isinstance(transformed, list) else []

    except Exception as e:
        print(f"[ERROR] Exception in call_openai_model: {e}")
        if config.get("DEBUG", False):
            traceback.print_exc()
        return []
