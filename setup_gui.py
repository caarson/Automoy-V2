#!/usr/bin/env python3
"""
Comprehensive script to:
1. Install pywebview
2. Fix syntax error in main.py
3. Test the application
"""
import subprocess
import sys
import os
import re

def install_pywebview():
    """Install pywebview using pip"""
    print("Installing pywebview...")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "install", "pywebview"], 
                              capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            print("✓ pywebview installed successfully!")
            return True
        else:
            print("✗ Failed to install pywebview")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
            
    except Exception as e:
        print(f"ERROR: Exception during installation: {e}")
        return False

def fix_main_py_syntax():
    """Fix the syntax error in main.py"""
    print("Fixing syntax error in main.py...")
    try:
        main_py_path = os.path.join('core', 'main.py')
        
        # Read the file
        with open(main_py_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Fix the specific syntax error - replace problematic line
        content = content.replace(
            "# --- End URL and title section ---    logger.info(f\"Attempting to create PyWebview window",
            "# --- End URL and title section ---\n    \n    logger.info(f\"Attempting to create PyWebview window"
        )
        
        # Write back the corrected content
        with open(main_py_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✓ Fixed syntax error in main.py")
        return True
        
    except Exception as e:
        print(f"✗ Error fixing main.py: {e}")
        return False

def test_import():
    """Test if pywebview can be imported"""
    print("Testing pywebview import...")
    try:
        import pywebview
        print(f"✓ pywebview {pywebview.__version__} is available!")
        return True
    except ImportError as e:
        print(f"✗ Failed to import pywebview: {e}")
        return False

def main():
    """Main function"""
    print("=== Automoy Setup Script ===")
    
    # Install pywebview
    if install_pywebview():
        if test_import():
            print("✓ pywebview is ready!")
        else:
            print("✗ pywebview installation failed")
            return False
    
    # Fix syntax error
    if fix_main_py_syntax():
        print("✓ main.py syntax fixed!")
    else:
        print("✗ Failed to fix main.py syntax")
        return False
    
    print("\n=== Setup Complete ===")
    print("You can now run: python core/main.py")
    print("This should open a native GUI window!")
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 Setup completed successfully!")
    else:
        print("\n❌ Setup failed. Please check the errors above.")
