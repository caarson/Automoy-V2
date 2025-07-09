#!/usr/bin/env python3
"""Simple test for PyTorch import"""

try:
    import torch
    print("✅ PyTorch imported successfully")
    print(f"   Version: {torch.__version__}")
    print(f"   CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   CUDA device count: {torch.cuda.device_count()}")
except Exception as e:
    print(f"❌ PyTorch import failed: {e}")

try:
    from PIL import Image
    print(f"✅ Pillow imported successfully")
except Exception as e:
    print(f"❌ Pillow import failed: {e}")

try:
    import easyocr
    print(f"✅ EasyOCR imported successfully")
except Exception as e:
    print(f"❌ EasyOCR import failed: {e}")

try:
    import ultralytics
    print(f"✅ Ultralytics imported successfully")
except Exception as e:
    print(f"❌ Ultralytics import failed: {e}")

print("Import test complete.")
