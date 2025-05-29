#!/usr/bin/env python3
"""
Test script to verify that the syntax fixes are working correctly.
This script tests the import and basic initialization of the fixed classes.
"""

import sys
import os

# Add the project root to Python path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def test_imports():
    """Test that all modules can be imported without syntax errors."""
    print("🔍 Testing imports...")
    
    try:
        from core.operate import AutomoyOperator, OperationParser
        print("✅ Successfully imported AutomoyOperator and OperationParser")
    except Exception as e:
        print(f"❌ Failed to import operate module: {e}")
        return False
    
    try:
        import core.main
        print("✅ Successfully imported main module")
    except Exception as e:
        print(f"❌ Failed to import main module: {e}")
        return False
    
    return True

def test_config_initialization():
    """Test that AutomoyOperator can be initialized with config."""
    print("\n🔍 Testing AutomoyOperator config initialization...")
    
    try:
        from core.operate import AutomoyOperator
        import asyncio
        
        # Create mock dependencies
        async def mock_manage_gui(visible):
            pass
        
        async def mock_update_gui_state(endpoint, data):
            pass
        
        class MockOmniParser:
            def parse_screenshot(self, path):
                return {}
        
        # Test initialization
        pause_event = asyncio.Event()
        operator = AutomoyOperator(
            objective="Test objective",
            manage_gui_window_func=mock_manage_gui,
            omniparser=MockOmniParser(),
            pause_event=pause_event,
            update_gui_state_func=mock_update_gui_state
        )
        
        # Check if config is properly initialized
        if hasattr(operator, 'config') and operator.config is not None:
            print("✅ AutomoyOperator config initialized successfully")
            print(f"   - Config type: {type(operator.config)}")
            print(f"   - Has get_max_retries_per_step: {hasattr(operator.config, 'get_max_retries_per_step')}")
            return True
        else:
            print("❌ AutomoyOperator config not properly initialized")
            return False
            
    except Exception as e:
        print(f"❌ Failed to initialize AutomoyOperator: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_operation_parser():
    """Test that OperationParser can be initialized properly."""
    print("\n🔍 Testing OperationParser initialization...")
    
    try:
        from core.operate import OperationParser
        from core.utils.operating_system.os_interface import OSInterface
        from core.utils.operating_system.desktop_utils import DesktopUtils
        
        os_interface = OSInterface()
        desktop_utils = DesktopUtils()
        
        parser = OperationParser(os_interface, desktop_utils)
        
        if hasattr(parser, 'os_interface') and hasattr(parser, 'desktop_utils'):
            print("✅ OperationParser initialized successfully")
            print(f"   - OS Interface type: {type(parser.os_interface)}")
            print(f"   - Desktop Utils type: {type(parser.desktop_utils)}")
            return True
        else:
            print("❌ OperationParser not properly initialized")
            return False
            
    except Exception as e:
        print(f"❌ Failed to initialize OperationParser: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🧪 Testing Automoy V2 fixes...")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_config_initialization, 
        test_operation_parser
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The fixes are working correctly.")
        print("\n📋 Summary of fixes applied:")
        print("   ✅ Fixed missing newline between statements in AutomoyOperator constructor")
        print("   ✅ Fixed missing newline between class docstring and __init__ method")
        print("   ✅ Fixed config initialization issue (self.config now properly set)")
        print("   ✅ Fixed zoom function syntax error in main.py")
        print("   ✅ All syntax errors resolved")
        return True
    else:
        print("❌ Some tests failed. Additional fixes may be needed.")
        return False

if __name__ == "__main__":
    main()
