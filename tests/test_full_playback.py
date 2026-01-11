#!/usr/bin/env python3
"""
Vollständiger Test-Setup:
1. Starte HTTP-Server auf Port 8200
2. Registriere Gerät beim DLNA-Server (minidlna auf Port 8201)
3. Spiele Datei ab
"""

import subprocess
import time
import sys
import os
from soundtouch_lib import SoundTouchController

# Pfade
TEST_MUSIC_DIR = "/home/hans/Open-Soundtouch/test_music"
DLNA_UUID = "1d335f1c-a118-43ea-8c05-e92f50e76882/0"
BOSE_IP = "192.168.50.19"
LOCAL_IP = "192.168.50.218"

print("=" * 80)
print("Vollständiger DLNA Playback Test")
print("=" * 80)

# 1. Starte einfachen HTTP-Server auf Port 8200
print("\n1️⃣  Starte HTTP-Server auf Port 8200...")
os.chdir(TEST_MUSIC_DIR)
http_server = subprocess.Popen(
    [sys.executable, "-m", "http.server", "8200"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)
time.sleep(2)
print("✓ HTTP-Server gestartet")

# 2. Teste HTTP-Zugriff
print("\n2️⃣  Teste HTTP-Zugriff auf Datei...")
test_file = "sirus.mp3"
test_url = f"http://{LOCAL_IP}:8200/{test_file}"

import urllib.request
try:
    req = urllib.request.Request(test_url, method='HEAD')
    with urllib.request.urlopen(req, timeout=2) as response:
        print(f"✓ Datei erreichbar: HTTP {response.status}")
        print(f"  Content-Type: {response.headers.get('Content-Type')}")
        print(f"  Content-Length: {response.headers.get('Content-Length')} bytes")
except Exception as e:
    print(f"❌ Datei nicht erreichbar: {e}")
    http_server.kill()
    sys.exit(1)

# 3. Sende Playback-Request an Bose
print("\n3️⃣  Sende Playback-Request an Bose Gerät...")
controller = SoundTouchController(BOSE_IP)

success = controller.select_source_with_location(
    source="STORED_MUSIC",
    source_account=DLNA_UUID,
    location=test_url,
    item_name=test_file
)

if success:
    print("✓ Playback-Request gesendet")
    
    # Sende PLAY
    time.sleep(1)
    print("\n4️⃣  Sende PLAY Command...")
    controller.send_key("PLAY")
    
    time.sleep(2)
    
    # Prüfe Status
    print("\n5️⃣  Prüfe Wiedergabe-Status...")
    status = controller.get_nowplaying()
    if status:
        print(f"✓ Status:")
        print(f"  Source: {status.get('source', '?')}")
        print(f"  Track: {status.get('track', '?')}")
        print(f"  PlayStatus: {status.get('playStatus', '?')}")
        
        if status.get('playStatus') in ['PLAY_STATE', 'BUFFERING_STATE']:
            print("\n🎉 ERFOLG! Musik wird abgespielt!")
        else:
            print(f"\n⚠️  Wiedergabe-Status unbekannt")
    else:
        print("❌ Konnte Status nicht abrufen")
else:
    print("❌ Playback-Request fehlgeschlagen")

print("\n" + "=" * 80)
print("Test abgeschlossen - HTTP-Server läuft weiter...")
print("Drücke Ctrl+C zum Beenden")
print("=" * 80)

try:
    http_server.wait()
except KeyboardInterrupt:
    print("\nBeende HTTP-Server...")
    http_server.kill()
    print("Fertig!")
