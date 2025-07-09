#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from core.data_models import GOAL_REQUEST_FILE

print(f"GOAL_REQUEST_FILE path: {GOAL_REQUEST_FILE}")
print(f"Absolute path: {os.path.abspath(GOAL_REQUEST_FILE)}")
print(f"Path exists: {os.path.exists(GOAL_REQUEST_FILE)}")

if os.path.exists(GOAL_REQUEST_FILE):
    print(f"File size: {os.path.getsize(GOAL_REQUEST_FILE)} bytes")
    with open(GOAL_REQUEST_FILE, 'r') as f:
        content = f.read()
        print(f"File content: {content}")
