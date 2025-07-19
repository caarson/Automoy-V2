import time
import subprocess
import requests
import json
import os

print("🔍 Quick OmniParser Desktop Test")
print("=" * 50)

# First ensure we're showing the desktop
print("1. Showing desktop...")
subprocess.run(['powershell', '-Command', '(New-Object -comObject Shell.Application).minimizeall()'], 
               capture_output=True, text=True)
time.sleep(3)

# Take a direct screenshot using Windows
print("2. Taking direct screenshot...")
subprocess.run(['powershell', '-Command', 
    'Add-Type -AssemblyName System.Windows.Forms; '
    '[System.Windows.Forms.Application]::SetCompatibleTextRenderingDefault($false); '
    '$Screen = [System.Windows.Forms.SystemInformation]::VirtualScreen; '
    '$Width = $Screen.Width; $Height = $Screen.Height; '
    '$Left = $Screen.Left; $Top = $Screen.Top; '
    '$bitmap = New-Object System.Drawing.Bitmap $Width, $Height; '
    '$graphic = [System.Drawing.Graphics]::FromImage($bitmap); '
    '$graphic.CopyFromScreen($Left, $Top, 0, 0, $bitmap.Size); '
    '$bitmap.Save("desktop_test.png"); '
    '$graphic.Dispose(); $bitmap.Dispose()'], 
    capture_output=True, text=True)

# Test OmniParser connection
print("3. Testing OmniParser...")
try:
    response = requests.get("http://localhost:8111", timeout=5)
    print("✅ OmniParser server is running")
    
    # Process the desktop screenshot
    if os.path.exists("desktop_test.png"):
        print("4. Processing desktop screenshot with OmniParser...")
        with open("desktop_test.png", "rb") as f:
            files = {'image': ('desktop.png', f, 'image/png')}
            response = requests.post('http://localhost:8111/process_image', files=files, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Screenshot processed successfully!")
                print(f"📊 Found {len(result.get('elements', []))} total elements")
                
                # Look for ANY text or elements (not just Chrome)
                elements = result.get('elements', [])
                print(f"\n📋 First 10 elements found:")
                for i, elem in enumerate(elements[:10]):
                    text = elem.get('text', '').strip()
                    bbox = elem.get('bbox', [])
                    elem_type = elem.get('type', '')
                    print(f"  {i+1}: '{text}' | Type: {elem_type} | BBox: {bbox}")
                
                # Search specifically for Chrome
                chrome_elements = []
                for i, elem in enumerate(elements):
                    text = elem.get('text', '').lower()
                    if any(keyword in text for keyword in ['chrome', 'google', 'browser']):
                        chrome_elements.append({
                            'index': i,
                            'text': elem.get('text', ''),
                            'bbox': elem.get('bbox', []),
                            'type': elem.get('type', '')
                        })
                
                if chrome_elements:
                    print(f"\n🎯 Chrome-related elements found: {len(chrome_elements)}")
                    for elem in chrome_elements:
                        print(f"  - Element {elem['index']}: '{elem['text']}' | Type: {elem['type']} | BBox: {elem['bbox']}")
                else:
                    print(f"\n❌ No Chrome-related elements found")
                    print("This means Chrome icon is either:")
                    print("  - Not visible on the desktop")
                    print("  - Not being detected by OmniParser")
                    print("  - Hidden or covered by other windows")
                    
            else:
                print(f"❌ OmniParser processing failed: {response.status_code}")
                print(response.text)
    else:
        print("❌ Failed to create desktop screenshot")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n✅ Test complete!")
