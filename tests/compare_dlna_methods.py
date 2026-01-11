#!/usr/bin/env python3
"""
Compare old REST method vs new DLNA/SOAP method
"""

import time
from soundtouch_lib import SoundTouchController

# Configuration
DEVICE_IP = "192.168.50.19"
DLNA_SERVER_IP = "192.168.50.218"
DLNA_SERVER_PORT = "8201"
DLNA_SERVER_UUID = "1d335f1c-a118-43ea-8c05-e92f50e76882"

# Test media URLs
HTTP_SERVER_URL = f"http://{DLNA_SERVER_IP}:8200/test_music/Jazz/Bossa%20Antigua.mp3"
DLNA_SERVER_URL = f"http://{DLNA_SERVER_IP}:{DLNA_SERVER_PORT}/music/test.mp3"

def test_old_method(controller):
    """Test old REST API method with source selection"""
    print("\n" + "=" * 60)
    print("METHOD 1: Old REST API (/select endpoint)")
    print("=" * 60)
    
    success = controller.select_source_with_location(
        source="STORED_MUSIC",
        source_account=DLNA_SERVER_UUID + "/0",
        location=HTTP_SERVER_URL,
        item_name="Bossa Antigua"
    )
    
    if success:
        print("✅ Command sent successfully")
        print("   (but might return INVALID_SOURCE...)")
    else:
        print("❌ Command failed")
    
    time.sleep(2)
    
    # Check now playing
    now_playing = controller.get_now_playing()
    if now_playing and 'ContentItem' in now_playing:
        content = now_playing['ContentItem']
        source = content.get('@source', 'N/A')
        print(f"\n   Now Playing Source: {source}")
        
        if source == "INVALID_SOURCE":
            print("   ❌ INVALID_SOURCE error!")
        elif 'itemName' in content:
            print(f"   ✅ Playing: {content['itemName']}")
    
    return success


def test_new_method(controller):
    """Test new DLNA/SOAP method"""
    print("\n" + "=" * 60)
    print("METHOD 2: New DLNA/SOAP (AVTransport service)")
    print("=" * 60)
    
    success = controller.play_url_dlna(
        url=HTTP_SERVER_URL,
        artist="Jobim",
        album="Jazz Collection",
        track="Bossa Antigua"
    )
    
    if success:
        print("✅ DLNA playback started")
    else:
        print("❌ DLNA playback failed")
    
    time.sleep(2)
    
    # Check now playing
    now_playing = controller.get_now_playing()
    if now_playing and 'ContentItem' in now_playing:
        content = now_playing['ContentItem']
        source = content.get('@source', 'N/A')
        print(f"\n   Now Playing Source: {source}")
        
        if 'itemName' in content:
            print(f"   Track: {content['itemName']}")
    
    return success


def main():
    """Compare both methods"""
    print("🎵 DLNA Playback Method Comparison")
    print(f"   Device: {DEVICE_IP}")
    print(f"   Media: {HTTP_SERVER_URL}")
    
    controller = SoundTouchController(DEVICE_IP)
    
    # Get device info
    info = controller.get_info()
    if info:
        print(f"   Speaker: {info['name']}")
    
    print()
    input("Press ENTER to test OLD method (might fail)...")
    test_old_method(controller)
    
    print()
    input("\nPress ENTER to test NEW DLNA method (should work)...")
    test_new_method(controller)
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print()
    print("OLD METHOD (REST /select):")
    print("  ❌ Returns INVALID_SOURCE error")
    print("  ❌ Requires source registration")
    print("  ❌ Complex ContentItem structure needed")
    print()
    print("NEW METHOD (DLNA/SOAP):")
    print("  ✅ Works directly")
    print("  ✅ No source registration needed")
    print("  ✅ Simple URL-based playback")
    print("  ✅ Standard UPNP/DLNA protocol")
    print()


if __name__ == "__main__":
    main()
