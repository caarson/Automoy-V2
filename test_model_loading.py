#!/usr/bin/env python3

import sys
import os

# Add the OmniParser directory to Python path
omniparser_path = os.path.join(os.getcwd(), 'dependencies', 'OmniParser-master')
sys.path.insert(0, omniparser_path)

# Change to OmniParser directory for relative paths to work
original_cwd = os.getcwd()
os.chdir(omniparser_path)

print(f"Current working directory: {os.getcwd()}")
print(f"Python path includes: {omniparser_path}")

try:
    print("1. Testing basic imports...")
    import torch
    print("   ✓ PyTorch imported successfully")
    
    from util.utils import get_yolo_model, get_caption_model_processor
    print("   ✓ Model functions imported successfully")
    
    print("2. Testing YOLO model loading...")
    som_model_path = 'weights/icon_detect/model.pt'
    print(f"   Loading model from: {som_model_path}")
    if os.path.exists(som_model_path):
        print("   ✓ Model file exists")
        try:
            som_model = get_yolo_model(model_path=som_model_path)
            print("   ✓ YOLO model loaded successfully")
        except Exception as e:
            print(f"   ✗ YOLO model loading failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"   ✗ Model file does not exist: {som_model_path}")
    
    print("3. Testing caption model loading...")
    caption_model_name = 'florence2'
    caption_model_path = 'weights/icon_caption_florence'
    device = 'cpu'
    print(f"   Loading model {caption_model_name} from: {caption_model_path}")
    if os.path.exists(caption_model_path):
        print("   ✓ Caption model directory exists")
        try:
            caption_model_processor = get_caption_model_processor(
                model_name=caption_model_name, 
                model_name_or_path=caption_model_path, 
                device=device
            )
            print("   ✓ Caption model loaded successfully")
        except Exception as e:
            print(f"   ✗ Caption model loading failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"   ✗ Caption model directory does not exist: {caption_model_path}")
    
    print("4. Testing Omniparser initialization...")
    try:
        from util.omniparser import Omniparser
        config = {
            'som_model_path': som_model_path,
            'caption_model_name': caption_model_name,
            'caption_model_path': caption_model_path,
            'device': device,
            'BOX_TRESHOLD': 0.05
        }
        print("   Initializing Omniparser...")
        omniparser = Omniparser(config)
        print("   ✓ Omniparser initialized successfully")
    except Exception as e:
        print(f"   ✗ Omniparser initialization failed: {e}")
        import traceback
        traceback.print_exc()

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    # Restore original working directory
    os.chdir(original_cwd)

print("\nModel loading test completed!")
