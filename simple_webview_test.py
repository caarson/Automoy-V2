"""Simple webview test using Windows Edge WebView2."""
import sys
import os
import subprocess
import time
import webbrowser

def open_native_window(url, title="Automoy GUI", width=1200, height=800):
    """Open a native window using different methods."""
    
    print(f"Attempting to open native window for: {url}")
    
    # Method 1: Try to use pywebview if available
    try:
        import pywebview
        print("✓ PyWebView is available, using it...")
        
        window = pywebview.create_window(
            title=title,
            url=url,
            width=width,
            height=height,
            resizable=True,
            on_top=False
        )
        
        print(f"Window object created: {window}")
        print("Calling webview.start()... Window should appear now!")
        
        # This will show the window and block until it's closed
        webview.start(debug=True)
        
        print("✓ Window test completed successfully!")
        
    except ImportError as e:
        print(f"✗ Cannot import pywebview: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error with pywebview: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("=== Simple PyWebview Test ===")
    main()
