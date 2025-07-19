import os
import time
import subprocess
import requests
import json
import tempfile
from PIL import Image
import io

print("🔍 Simple Chrome Check")
print("=" * 50)

# First, let's see if OmniParser is running
try:
    response = requests.get("http://localhost:8111", timeout=5)
    print("✅ OmniParser server is running")
except:
    print("❌ OmniParser server is not running")
    print("Let's start it first...")
    exit(1)

# Show desktop
print("1. Showing desktop...")
subprocess.run(['powershell', '-Command', '(New-Object -comObject Shell.Application).minimizeall()'], 
               capture_output=True, text=True)
time.sleep(2)

# Take screenshot
print("2. Taking screenshot...")
try:
    # Create temp file for screenshot  
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
        temp_path = temp_file.name
    
    # Take screenshot using OmniParser
    files = {'image': ('screenshot.png', open('current_screenshot.png', 'rb'), 'image/png')}
    response = requests.post('http://localhost:8111/process_image', files=files, timeout=30)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Screenshot processed! Found {len(result.get('elements', []))} elements")
        
        # Search for Chrome
        chrome_elements = []
        for i, elem in enumerate(result.get('elements', [])):
            text = elem.get('text', '').lower()
            if any(keyword in text for keyword in ['chrome', 'google', 'browser']):
                chrome_elements.append({
                    'index': i,
                    'text': elem.get('text', ''),
                    'bbox': elem.get('bbox', []),
                    'type': elem.get('type', '')
                })
        
        print(f"\n🔍 Chrome-related elements found: {len(chrome_elements)}")
        for elem in chrome_elements:
            print(f"  - Element {elem['index']}: '{elem['text']}' at {elem['bbox']}")
        
        # Show first few elements for debugging
        print(f"\n📋 First 10 elements detected:")
        for i, elem in enumerate(result.get('elements', [])[:10]):
            print(f"  {i}: '{elem.get('text', '')}' - Type: {elem.get('type', '')} - BBox: {elem.get('bbox', [])}")
            
    else:
        print(f"❌ Screenshot processing failed: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n✅ Simple check complete!")
