#!/usr/bin/env python3
"""
Einfacher Test für DLNA Playback
"""

from soundtouch_lib import SoundTouchController
import time

# Geräte-IP
DEVICE_IP = "192.168.50.19"
DLNA_UUID = "1d335f1c-a118-43ea-8c05-e92f50e76882/0"

# Erstelle Controller
controller = SoundTouchController(DEVICE_IP)

# Test 1: Hole Sources
print("=" * 60)
print("Test 1: Verfügbare Sources")
print("=" * 60)
sources = controller.get_sources()
if sources:
    for s in sources:
        if 'STORED_MUSIC' in s.get('source', ''):
            print(f"✓ {s['source']}: {s.get('sourceAccount', '')} - Status: {s.get('status', '')}")
else:
    print("❌ Konnte Sources nicht abrufen")

# Test 2: Hole aktuellen Status
print("\n" + "=" * 60)
print("Test 2: Aktueller Wiedergabe-Status")
print("=" * 60)
status = controller.get_nowplaying()
if status:
    print(f"Source: {status.get('source', '?')}")
    print(f"Track: {status.get('track', '?')}")
    print(f"Artist: {status.get('artist', '?')}")
    print(f"PlayStatus: {status.get('playStatus', '?')}")
else:
    print("❌ Konnte Status nicht abrufen")

# Test 3: Spiele eine Datei
print("\n" + "=" * 60)
print("Test 3: Spiele Test-Track")
print("=" * 60)

test_url = "http://192.168.50.218:8200/MediaItems/1.mp3"
print(f"URL: {test_url}")
print(f"SourceAccount: {DLNA_UUID}")

success = controller.select_source_with_location(
    source="STORED_MUSIC",
    source_account=DLNA_UUID,
    location=test_url,
    item_name="Test Track"
)

if success:
    print("✓ Playback-Request gesendet")
    
    # Warte kurz und prüfe Status
    time.sleep(2)
    
    # Sende PLAY
    print("\nSende PLAY Command...")
    controller.send_key("PLAY")
    
    time.sleep(2)
    
    # Prüfe Status
    status = controller.get_nowplaying()
    if status:
        print(f"\n✓ Aktueller Status:")
        print(f"  Source: {status.get('source', '?')}")
        print(f"  Track: {status.get('track', '?')}")
        print(f"  PlayStatus: {status.get('playStatus', '?')}")
    else:
        print("❌ Konnte Status nach Playback nicht abrufen")
else:
    print("❌ Playback-Request fehlgeschlagen")

print("\n" + "=" * 60)
print("Test abgeschlossen")
print("=" * 60)
