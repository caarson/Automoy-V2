#!/usr/bin/env python3
print("=== Testing Automoy V2 imports step by step ===")

try:
    print("1. Testing basic imports...")
    import sys
    import os
    print("   ✓ Basic imports successful")
except Exception as e:
    print(f"   ✗ Basic imports failed: {e}")
    exit(1)

try:
    print("2. Testing project path setup...")
    PROJECT_ROOT_FOR_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
    if PROJECT_ROOT_FOR_PATH not in sys.path:
        sys.path.insert(0, PROJECT_ROOT_FOR_PATH)
    print(f"   ✓ Project root: {PROJECT_ROOT_FOR_PATH}")
except Exception as e:
    print(f"   ✗ Project path setup failed: {e}")
    exit(1)

try:
    print("3. Testing config import...")
    import config.config as app_config
    print("   ✓ Config import successful")
except Exception as e:
    print(f"   ✗ Config import failed: {e}")
    exit(1)

try:
    print("4. Testing data models import...")
    from core.data_models import AutomoyStatus, OperatorState
    print("   ✓ Data models import successful")
except Exception as e:
    print(f"   ✗ Data models import failed: {e}")
    exit(1)

try:
    print("5. Testing operate import...")
    from core.operate import AutomoyOperator
    print("   ✓ Operate import successful")
except Exception as e:
    print(f"   ✗ Operate import failed: {e}")
    print(f"   Error details: {type(e).__name__}: {e}")
    exit(1)

try:
    print("6. Testing process utils import...")
    from core.utils.operating_system.process_utils import is_process_running_on_port, kill_process_on_port
    print("   ✓ Process utils import successful")
except Exception as e:
    print(f"   ✗ Process utils import failed: {e}")
    exit(1)

print("\n=== All imports successful! ===")
print("The main.py file should be able to run.")
