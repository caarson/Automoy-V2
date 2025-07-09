"""Test if formulate_objective is working after fixes."""
import asyncio
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

async def test_fixed_llm():
    print("Testing fixed LLM interface...")
    
    from core.lm.lm_interface import MainInterface
    llm = MainInterface()
    print(f"✓ MainInterface created (API: {llm.api_source})")
    
    # Check method
    print(f"✓ Has get_llm_response: {hasattr(llm, 'get_llm_response')}")
    
    # Test formulate_objective
    try:
        result = await asyncio.wait_for(
            llm.formulate_objective("open notepad", "test-123"),
            timeout=10.0
        )
        print(f"✓ formulate_objective result: {result}")
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_fixed_llm())
