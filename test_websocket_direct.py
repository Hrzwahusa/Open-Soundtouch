#!/usr/bin/env python3
"""Direct WebSocket test to debug message receiving."""

import time
from soundtouch_websocket import SoundTouchWebSocket

# Test device
device_ip = "192.168.50.19"  # Küche

print(f"Testing WebSocket connection to {device_ip}")
print("=" * 50)

# Create WebSocket client
ws = SoundTouchWebSocket(device_ip)

# Connect
print("Connecting...")
if ws.connect():
    print("✓ Connected!")
    
    # Now let's wait for messages
    print("\nWaiting for WebSocket messages (60 seconds)...")
    print("Try changing volume or playing something on the device...")
    print("-" * 50)
    
    start_time = time.time()
    messages_received = 0
    
    while time.time() - start_time < 60:
        # Check for events
        event = ws.get_next_event(timeout=1)
        if event:
            messages_received += 1
            print(f"\n✓ Event #{messages_received}: {event.get('type')}")
            print(f"  Data: {event}")
        else:
            # Just waiting, print dot
            elapsed = int(time.time() - start_time)
            print(f".", end="", flush=True)
    
    print(f"\n\nTest completed.")
    print(f"Messages received: {messages_received}")
    
    ws.disconnect()
else:
    print("✗ Connection failed!")
