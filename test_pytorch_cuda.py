#!/usr/bin/env python3
"""Test PyTorch CUDA functionality"""

import torch
import sys

def test_pytorch_cuda():
    print("=== PyTorch CUDA Test ===")
    print(f"Python version: {sys.version}")
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    
    if torch.cuda.is_available():
        print(f"CUDA version: {torch.version.cuda}")
        print(f"GPU count: {torch.cuda.device_count()}")
        print(f"Current GPU: {torch.cuda.current_device()}")
        print(f"GPU name: {torch.cuda.get_device_name(0)}")
        print(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        
        # Test a simple CUDA operation
        print("\n=== Testing CUDA Operation ===")
        try:
            x = torch.randn(1000, 1000).cuda()
            y = torch.randn(1000, 1000).cuda()
            z = torch.matmul(x, y)
            print("✅ CUDA matrix multiplication successful!")
            print(f"Result device: {z.device}")
        except Exception as e:
            print(f"❌ CUDA operation failed: {e}")
    else:
        print("❌ CUDA not available")
        print("Available devices:")
        print("CPU only")

if __name__ == "__main__":
    test_pytorch_cuda()
