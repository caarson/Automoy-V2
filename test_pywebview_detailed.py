"""Detailed pywebview import test for automoy_env."""

import sys
import traceback

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")

try:
    print("\n--- Testing pywebview import ---")
    import pywebview
    print(f"✓ PyWebView imported successfully!")
    print(f"  Version: {pywebview.__version__}")
    print(f"  Module file: {pywebview.__file__}")
    
    print("\n--- Testing available backends ---")
    # Test different backends
    backends = ['mshtml', 'chromium', 'cef', 'qt']
    for backend in backends:
        try:
            print(f"Testing {backend} backend...")
            # This doesn't actually start the backend, just checks if it's available
            pywebview.platforms.detect()
            print(f"  Available platforms: {pywebview.platforms}")
            break
        except Exception as e:
            print(f"  {backend} backend error: {e}")
    
    print("\n--- Testing window creation ---")
    window = pywebview.create_window(
        'Test Window',
        'https://www.google.com',
        width=400,
        height=300
    )
    print(f"✓ Window object created: {type(window)}")
    
except ImportError as e:
    print(f"✗ PyWebView import failed: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    
    # Check site-packages for pywebview
    import os
    site_packages = r"C:\Users\imitr\anaconda3\envs\automoy_env\Lib\site-packages"
    if os.path.exists(site_packages):
        print(f"\nContents of {site_packages}:")
        items = [item for item in os.listdir(site_packages) if 'pywebview' in item.lower()]
        print(f"  pywebview-related items: {items}")

except Exception as e:
    print(f"✗ Unexpected error: {e}")
    print("\nFull traceback:")
    traceback.print_exc()

print("\nTest complete.")
