"""Quick test of the corrected pywebview import."""
try:
    import webview as pywebview  # Use the correct import
    print(f"✓ PyWebView imported successfully (aliased as pywebview)")
    print(f"Available functions: {[attr for attr in dir(pywebview) if not attr.startswith('_')][:10]}")
    
    # Test window creation
    window = pywebview.create_window(
        'Test Window',
        'data:text/html,<h1>PyWebView Test</h1><p>Working correctly!</p>',
        width=600,
        height=400
    )
    print(f"✓ Window created: {type(window)}")
    
    print("Starting pywebview (close window to continue)...")
    pywebview.start(debug=True)
    print("✓ PyWebView test completed!")
    
except ImportError as e:
    print(f"✗ Import failed: {e}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
