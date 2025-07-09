"""Test specifically the LLM interface and formulate_objective method."""
import asyncio
import sys
import os

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

async def test_llm_interface():
    """Test the LLM interface formulate_objective method."""
    print("=== LLM INTERFACE TEST ===")
    
    try:
        from core.lm.lm_interface import MainInterface
        print("✓ MainInterface imported successfully")
        
        llm_interface = MainInterface()
        print("✓ MainInterface instantiated successfully")
        print(f"  API source: {getattr(llm_interface, 'api_source', 'Unknown')}")
        
        # Test model access
        try:
            model = llm_interface.config.get_model()
            print(f"✓ Model from config: {model}")
        except Exception as e:
            print(f"✗ Failed to get model: {e}")
            return
        
        # Test formulate_objective
        test_goal = "open a text editor"
        print(f"\nTesting formulate_objective with goal: '{test_goal}'")
        
        # Add timeout to see if it's hanging
        try:
            objective_text, error = await asyncio.wait_for(
                llm_interface.formulate_objective(goal=test_goal, session_id="test-123"),
                timeout=60.0  # 60 second timeout
            )
            
            print(f"✓ formulate_objective completed")
            print(f"  Result: {objective_text}")
            print(f"  Error: {error}")
            
        except asyncio.TimeoutError:
            print("✗ formulate_objective timed out after 60 seconds")
        except Exception as e:
            print(f"✗ Exception in formulate_objective: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"✗ Failed to test LLM interface: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm_interface())
