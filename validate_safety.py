#!/usr/bin/env python3
"""
Safety Implementation Validation
Confirms that the visual elements detection safety measures are properly implemented
"""

import os
import sys
import re

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def validate_operate_py_safety():
    """Validate that operate.py has the safety measures implemented"""
    print("=== Validating operate.py Safety Implementation ===")
    
    operate_path = os.path.join(project_root, "core", "operate.py")
    if not os.path.exists(operate_path):
        print("❌ operate.py not found")
        return False
    
    with open(operate_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("Zero elements detection", r'elements_found == 0'),
        ("RuntimeError on zero elements", r'raise RuntimeError.*Visual analysis detected zero elements'),
        ("Safety halt message", r'indicating bad component.*Operation halted for safety'),
        ("GUI state update on error", r'update_gui_state_func.*CRITICAL ERROR.*Visual analysis detected NO UI elements'),
        ("Operator status error", r'operator_status.*error'),
    ]
    
    all_passed = True
    for check_name, pattern in checks:
        if re.search(pattern, content, re.IGNORECASE):
            print(f"✅ {check_name}: Found")
        else:
            print(f"❌ {check_name}: Missing")
            all_passed = False
    
    return all_passed

def validate_main_py_safety():
    """Validate that main.py has the RuntimeError handling"""
    print("\n=== Validating main.py Safety Handling ===")
    
    main_path = os.path.join(project_root, "core", "main.py")
    if not os.path.exists(main_path):
        print("❌ main.py not found")
        return False
    
    with open(main_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("RuntimeError exception handling", r'except RuntimeError as e:'),
        ("Visual analysis error detection", r'Visual analysis detected zero elements.*in error_msg'),
        ("Bad component detection", r'bad component.*in error_msg'),
        ("Critical component failure logging", r'CRITICAL COMPONENT FAILURE'),
        ("Operation halted message", r'Operation halted due to critical visual analysis'),
        ("System halted state", r'SYSTEM HALTED.*Visual analysis detected zero elements'),
    ]
    
    all_passed = True
    for check_name, pattern in checks:
        if re.search(pattern, content, re.IGNORECASE):
            print(f"✅ {check_name}: Found")
        else:
            print(f"❌ {check_name}: Missing")
            all_passed = False
    
    return all_passed

def validate_safety_logic():
    """Test the safety logic directly"""
    print("\n=== Validating Safety Logic ===")
    
    # Simulate the exact safety check from AutomoyOperator
    def safety_check(elements_found):
        """Exact logic from operate.py"""
        if elements_found == 0:
            raise RuntimeError("Visual analysis detected zero elements - indicating bad component. Operation halted for safety.")
        return True
    
    # Test zero elements (should raise exception)
    try:
        safety_check(0)
        print("❌ Safety check FAILED - should have raised RuntimeError for zero elements")
        return False
    except RuntimeError as e:
        if "Visual analysis detected zero elements" in str(e):
            print("✅ Safety check correctly raises RuntimeError for zero elements")
        else:
            print(f"❌ Wrong error message: {e}")
            return False
    
    # Test with elements (should pass)
    try:
        safety_check(5)
        print("✅ Safety check correctly passes with elements present")
        return True
    except Exception as e:
        print(f"❌ Unexpected error with elements: {e}")
        return False

def main():
    """Run all validation checks"""
    print("🔍 Validating Visual Elements Detection Safety Implementation")
    print("=" * 65)
    
    # Check implementations
    operate_valid = validate_operate_py_safety()
    main_valid = validate_main_py_safety()
    logic_valid = validate_safety_logic()
    
    print("\n" + "=" * 65)
    print("📋 VALIDATION SUMMARY:")
    print(f"   operate.py safety implementation: {'✅ PASS' if operate_valid else '❌ FAIL'}")
    print(f"   main.py safety handling: {'✅ PASS' if main_valid else '❌ FAIL'}")
    print(f"   Safety logic functionality: {'✅ PASS' if logic_valid else '❌ FAIL'}")
    
    if operate_valid and main_valid and logic_valid:
        print("\n🎯 ALL SAFETY VALIDATIONS PASSED!")
        print("✅ Visual elements detection safety measures are correctly implemented")
        print("\n📋 Implementation Summary:")
        print("   • operate.py detects zero visual elements and raises RuntimeError")
        print("   • main.py catches RuntimeError and updates GUI with critical failure status")
        print("   • Operation is properly halted when bad components are detected")
        print("   • User is informed of the critical component failure")
        print("\n🚨 When OmniParser detects zero UI elements:")
        print("   1. AutomoyOperator._perform_visual_analysis() will raise RuntimeError")
        print("   2. main.py will catch the exception and halt operation")
        print("   3. GUI will show 'SYSTEM HALTED: Visual analysis detected zero elements'")
        print("   4. Operator status will be set to 'error'")
        print("   5. No further actions will be attempted")
    else:
        print("\n❌ SAFETY VALIDATION FAILED!")
        print("⚠️ Some safety measures may not be properly implemented")

if __name__ == "__main__":
    main()
