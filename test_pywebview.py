#!/usr/bin/env python3
"""
Test script to install and verify pywebview functionality
"""
import sys
import subprocess

def install_pywebview():
    """Install pywebview using pip"""
    print("Installing pywebview...")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "install", "pywebview"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ pywebview installed successfully!")
            print(result.stdout)
            return True
        else:
            print("✗ Failed to install pywebview")
            print("STDERR:", result.stderr)
            return False
    except Exception as e:
        print(f"✗ Error during installation: {e}")
        return False

def test_pywebview():
    """Test pywebview import and basic functionality"""
    try:
        import pywebview
        print(f"✓ pywebview {pywebview.__version__} imported successfully!")
        
        # Test window creation (don't start it, just create)
        window = pywebview.create_window('Test', 'about:blank', width=400, height=300)
        print("✓ Window creation test passed!")
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import pywebview: {e}")
        return False
    except Exception as e:
        print(f"✗ Error testing pywebview: {e}")
        return False

def main():
    print("=== PyWebview Test ===")
    print(f"Python executable: {sys.executable}")
    
    # Test if pywebview is already available
    if test_pywebview():
        print("\n🎉 pywebview is ready!")
        return True
    
    # Try to install it
    print("\nAttempting to install pywebview...")
    if install_pywebview():
        if test_pywebview():
            print("\n🎉 pywebview is now ready!")
            return True
    
    print("\n❌ pywebview setup failed")
    return False

if __name__ == "__main__":
    main()