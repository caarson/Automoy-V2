"""Test the Edge app mode functionality."""
import subprocess
import os
import time

def test_edge_app_mode():
    """Test opening a window with Microsoft Edge in app mode."""
    
    # Test URL - we'll use a simple HTML page
    test_html = """
    <html>
    <head>
        <title>Automoy Test</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                text-align: center; 
                margin-top: 100px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            h1 { font-size: 2.5em; margin-bottom: 20px; }
            p { font-size: 1.2em; }
            .success { color: #4CAF50; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🚀 Automoy Native Window Test</h1>
        <p class="success">✓ Native window functionality is working!</p>
        <p>This window was opened using Microsoft Edge in app mode.</p>
        <p>You can close this window when ready.</p>
    </body>
    </html>
    """
    
    # Create a temporary HTML file
    test_file = "test_window.html"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(test_html)
    
    try:
        # Find Microsoft Edge executable
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        ]
        
        edge_exe = None
        for path in edge_paths:
            if os.path.exists(path):
                edge_exe = path
                break
                
        if edge_exe:
            print(f"✓ Found Microsoft Edge at: {edge_exe}")
            
            # Create file URL
            file_url = f"file:///{os.path.abspath(test_file).replace(os.sep, '/')}"
            print(f"Opening: {file_url}")
            
            cmd = [
                edge_exe,
                f"--app={file_url}",
                "--window-size=800,600",
                "--window-position=200,200",
                "--disable-web-security"
            ]
            
            print("Starting Edge in app mode...")
            process = subprocess.Popen(cmd)
            print(f"✓ Edge app mode started (PID: {process.pid})")
            print("ℹ A native-looking window should have appeared!")
            print("ℹ Close the window to continue...")
            
            # Wait for the process to finish (window closed)
            process.wait()
            print("✓ Window was closed")
            return True
            
        else:
            print("✗ Microsoft Edge not found")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        # Clean up
        if os.path.exists(test_file):
            os.remove(test_file)

if __name__ == "__main__":
    print("=== Testing Edge App Mode for Native Window ===")
    success = test_edge_app_mode()
    
    if success:
        print("\n✓ Edge app mode test successful!")
        print("This method can be used as a fallback for pywebview.")
    else:
        print("\n✗ Edge app mode test failed.")
        
    input("Press Enter to exit...")
