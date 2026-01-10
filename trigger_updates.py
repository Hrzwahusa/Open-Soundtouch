#!/usr/bin/env python3
"""Send REST commands to trigger WebSocket updates."""

import time
import requests

device_ip = "192.168.50.19"
base_url = f"http://{device_ip}:8090"

# Small delay to let WebSocket test start
time.sleep(5)

print("\n[Volume Test] Changing volume to trigger updates...")

# Try changing volume a few times
for i in range(3):
    try:
        # Set volume to different values
        volume = 30 + (i * 5)
        print(f"[{i+1}] Setting volume to {volume}...")
        resp = requests.post(f"{base_url}/volume", 
                            data=f"<volume>{volume}</volume>",
                            timeout=5)
        print(f"    Status: {resp.status_code}")
        time.sleep(3)
    except Exception as e:
        print(f"    Error: {e}")

print("\n[Play Test] Playing a preset...")
try:
    resp = requests.post(f"{base_url}/select",
                        data='<ContentItem source="PRESETS" location="1"/>',
                        timeout=5)
    print(f"    Status: {resp.status_code}")
    time.sleep(3)
except Exception as e:
    print(f"    Error: {e}")

print("\nDone! Check WebSocket test output above for updates.")
