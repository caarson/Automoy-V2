#!/usr/bin/env python3
"""
Simple test to verify pywebview works
"""
import sys
import os

try:
    import webview
    print("✓ pywebview imported successfully")
    
    # Create a simple window
    print("Creating test window...")
    window = webview.create_window(
        'Test Window', 
        'https://www.google.com',
        width=800,
        height=600,
        resizable=True
    )
    
    print("Window created, starting webview...")
    webview.start(debug=True)
    print("Webview finished")
    
except ImportError as e:
    print(f"✗ Failed to import pywebview: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error running pywebview: {e}")
    sys.exit(1)
