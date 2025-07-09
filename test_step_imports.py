"""Test imports step by step to find where it's hanging."""
import sys
import os

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("Step 1: Testing basic imports...")
try:
    import asyncio
    import json
    print("✓ Standard library imports OK")
except Exception as e:
    print(f"✗ Standard library imports failed: {e}")
    exit(1)

print("Step 2: Testing config import...")
try:
    from config.config import Config
    print("✓ Config import OK")
except Exception as e:
    print(f"✗ Config import failed: {e}")
    exit(1)

print("Step 3: Testing LLM handlers import...")
try:
    from core.lm.handlers.openai_handler import call_openai_model
    print("✓ OpenAI handler import OK")
except Exception as e:
    print(f"✗ OpenAI handler import failed: {e}")

try:
    from core.lm.handlers.lmstudio_handler import call_lmstudio_model
    print("✓ LMStudio handler import OK")
except Exception as e:
    print(f"✗ LMStudio handler import failed: {e}")

print("Step 4: Testing exceptions import...")
try:
    from core.exceptions import ModelNotRecognizedException, LLMResponseError
    print("✓ Exceptions import OK")
except Exception as e:
    print(f"✗ Exceptions import failed: {e}")

print("Step 5: Testing prompts import...")
try:
    from core.prompts.prompts import FORMULATE_OBJECTIVE_SYSTEM_PROMPT, FORMULATE_OBJECTIVE_USER_PROMPT_TEMPLATE
    print("✓ Prompts import OK")
except Exception as e:
    print(f"✗ Prompts import failed: {e}")

print("Step 6: Testing LLM interface import...")
try:
    from core.lm.lm_interface import MainInterface
    print("✓ MainInterface import OK")
except Exception as e:
    print(f"✗ MainInterface import failed: {e}")
    import traceback
    traceback.print_exc()

print("All import tests completed!")
