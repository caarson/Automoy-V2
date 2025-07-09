"""
Fix the specific syntax error in main.py
"""

def fix_syntax_error():
    """Fix the missing newline issue"""
    main_file = "core/main.py"
    
    # Read the file
    with open(main_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find and fix the problematic line
    for i, line in enumerate(lines):
        if "# --- End URL and title section ---    logger.info" in line:
            # Split the line into two
            lines[i] = "    # --- End URL and title section ---\n"
            lines.insert(i+1, "    \n")
            lines.insert(i+2, "    " + line.split("---    ")[1])
            print(f"Fixed syntax error on line {i+1}")
            break
    
    # Write the file back
    with open(main_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("Syntax error fixed!")

if __name__ == "__main__":
    fix_syntax_error()
