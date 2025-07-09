#!/usr/bin/env python3
"""
Test script to verify main.py can import correctly.
"""

import sys
import os

# Add project root to path (same as main.py)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    # Test the imports that main.py uses
    from config.config import VERSION, DEBUG_MODE, GUI_HOST, GUI_PORT
    from core.data_models import get_initial_state, read_state, write_state
    from core.lm.lm_interface import MainInterface
    from core.operate import AutomoyOperator
    
    print("✅ All imports successful!")
    print(f"Version: {VERSION}")
    print(f"GUI Host: {GUI_HOST}, Port: {GUI_PORT}")
    print(f"Debug Mode: {DEBUG_MODE}")
    print("Main.py should be able to run without import errors.")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
    
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    sys.exit(1)
