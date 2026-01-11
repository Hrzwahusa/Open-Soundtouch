#!/usr/bin/env python3
"""
Test DLNA Playback auf Bose SoundTouch
Testet ob registrierte DLNA-Server Musik abspielen können
"""

import requests
import sys
from xml.sax.saxutils import escape

def play_dlna_track(bose_ip: str, source_account: str, file_url: str, item_name: str):
    """
    Spiele einen Track vom DLNA Server ab.
    
    Args:
        bose_ip: IP des Bose Geräts
        source_account: UUID des DLNA Servers (mit /0 Suffix)
        file_url: HTTP URL zur Musikdatei
        item_name: Anzeigename des Tracks
    """
    try:
        # Erstelle ContentItem XML
        xml_body = (
            f'<ContentItem source="STORED_MUSIC" '
            f'sourceAccount="{escape(source_account)}" '
            f'location="{escape(file_url)}">'
            f'<itemName>{escape(item_name)}</itemName>'
            f'</ContentItem>'
        )
        
        url = f"http://{bose_ip}:8090/select"
        headers = {'Content-Type': 'application/xml'}
        
        print(f"\n📤 Sende Playback-Request an Bose Gerät...")
        print(f"   Device IP:     {bose_ip}")
        print(f"   Source:        STORED_MUSIC")
        print(f"   SourceAccount: {source_account}")
        print(f"   File URL:      {file_url}")
        print(f"   Item Name:     {item_name}")
        print(f"\n   XML Body:\n   {xml_body}\n")
        
        response = requests.post(url, data=xml_body, headers=headers, timeout=10)
        
        print(f"📥 Response: HTTP {response.status_code}")
        if response.text:
            print(f"   Body: {response.text[:500]}")
        
        if response.status_code == 200:
            print(f"\n✅ Playback-Request erfolgreich gesendet!")
            print(f"   Das Gerät sollte jetzt den Track abspielen.")
            return True
        else:
            print(f"\n❌ Playback-Request fehlgeschlagen!")
            return False
            
    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        return False


def main():
    """Main function."""
    print("="*80)
    print("DLNA Playback Test")
    print("="*80)
    
    if len(sys.argv) < 5:
        print("\nUsage: python test_dlna_playback.py <bose_ip> <source_account> <file_url> <item_name>")
        print("\nBeispiel:")
        print("  python test_dlna_playback.py 192.168.50.19 \\")
        print("    '1d335f1c-a118-43ea-8c05-e92f50e76882/0' \\")
        print("    'http://192.168.50.218:8200/MediaItems/1.mp3' \\")
        print("    'Test Song'")
        sys.exit(1)
    
    bose_ip = sys.argv[1]
    source_account = sys.argv[2]
    file_url = sys.argv[3]
    item_name = sys.argv[4]
    
    success = play_dlna_track(bose_ip, source_account, file_url, item_name)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
