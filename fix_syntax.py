"""
Quick fix script to correct the syntax error in main.py
"""
import re

def fix_main_py():
    """Fix the syntax error in main.py"""
    with open('core/main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix the specific syntax error
    content = content.replace(
        "# --- End URL and title section ---    logger.info(f\"Attempting to create PyWebview window",
        "# --- End URL and title section ---\n    \n    logger.info(f\"Attempting to create PyWebview window"
    )
    
    # Write back the corrected content
    with open('core/main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Fixed syntax error in main.py")

if __name__ == "__main__":
    fix_main_py()
