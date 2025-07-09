#!/usr/bin/env python3

import sys
import os
import base64
import io
from PIL import Image

# Add the OmniParser directory to Python path
omniparser_path = os.path.join(os.getcwd(), 'dependencies', 'OmniParser-master')
sys.path.insert(0, omniparser_path)

# Change to OmniParser directory for relative paths to work
original_cwd = os.getcwd()
os.chdir(omniparser_path)

print(f"Current working directory: {os.getcwd()}")

# Create a mock Omniparser class that bypasses model loading
class MockOmniparser:
    def __init__(self, config):
        self.config = config
        print('MockOmniparser initialized (bypassing model loading)')

    def parse(self, image_base64: str):
        print('Starting mock image parsing...')
        try:
            # Decode the image to verify it's valid
            image_bytes = base64.b64decode(image_base64)
            print(f'Decoded image: {len(image_bytes)} bytes')
            
            image = Image.open(io.BytesIO(image_bytes))
            print('Image size:', image.size)
            
            # Return mock results
            mock_parsed_content_list = [
                {'type': 'text', 'bbox': [0.1, 0.1, 0.9, 0.2], 'content': 'Mock text element'},
                {'type': 'icon', 'bbox': [0.2, 0.3, 0.4, 0.5], 'content': 'Mock icon element'}
            ]
            
            # Create a simple mock image (just encode the original)
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            mock_encoded_image = base64.b64encode(buffered.getvalue()).decode('ascii')
            
            print('Mock parsing completed successfully')
            return mock_encoded_image, mock_parsed_content_list
            
        except Exception as e:
            print(f'Error in mock parse method: {e}')
            import traceback
            traceback.print_exc()
            raise

# Replace the original Omniparser with our mock
try:
    # Patch the omniparser module
    import util.omniparser
    util.omniparser.Omniparser = MockOmniparser
    print("✓ Omniparser patched with mock version")
    
    # Test the mock
    config = {
        'som_model_path': 'weights/icon_detect/model.pt',
        'caption_model_name': 'florence2',
        'caption_model_path': 'weights/icon_caption_florence',
        'device': 'cpu',
        'BOX_TRESHOLD': 0.05
    }
    
    omniparser = MockOmniparser(config)
    
    # Test with a simple image
    test_image = Image.new('RGB', (100, 100), color='red')
    buffered = io.BytesIO()
    test_image.save(buffered, format="PNG")
    test_image_base64 = base64.b64encode(buffered.getvalue()).decode('ascii')
    
    print("Testing mock parsing...")
    result_image, parsed_content = omniparser.parse(test_image_base64)
    print(f"✓ Mock parsing successful, found {len(parsed_content)} elements")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    # Restore original working directory
    os.chdir(original_cwd)

print("\nMock test completed!")
