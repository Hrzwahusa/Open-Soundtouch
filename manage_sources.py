#!/usr/bin/env python3
"""
Tool zum Verwalten von STORED_MUSIC Sources auf Bose SoundTouch
"""

import requests
import xml.etree.ElementTree as ET
import sys


def list_stored_music_sources(device_ip: str):
    """Liste alle STORED_MUSIC Sources auf."""
    try:
        url = f"http://{device_ip}:8090/sources"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            sources = []
            
            for item in root.findall('sourceItem'):
                source = item.get('source', '')
                if 'STORED_MUSIC' in source:
                    sources.append({
                        'source': source,
                        'sourceAccount': item.get('sourceAccount', ''),
                        'status': item.get('status', ''),
                        'name': item.text or '',
                    })
            
            return sources
        return []
    except Exception as e:
        print(f"❌ Fehler: {e}")
        return []


def main():
    """Main function."""
    print("=" * 80)
    print("Bose SoundTouch - STORED_MUSIC Source Manager")
    print("=" * 80)
    
    if len(sys.argv) < 2:
        print("\nUsage: python manage_sources.py <device_ip>")
        print("\nBeispiel:")
        print("  python manage_sources.py 192.168.50.19")
        sys.exit(1)
    
    device_ip = sys.argv[1]
    
    print(f"\n📋 STORED_MUSIC Sources auf {device_ip}:")
    print("-" * 80)
    
    sources = list_stored_music_sources(device_ip)
    
    if not sources:
        print("Keine STORED_MUSIC Sources gefunden.")
        sys.exit(0)
    
    for i, source in enumerate(sources, 1):
        status_icon = "✅" if source['status'] == 'READY' else "❌"
        print(f"\n{i}. {status_icon} {source['name']}")
        print(f"   Source:        {source['source']}")
        print(f"   SourceAccount: {source['sourceAccount']}")
        print(f"   Status:        {source['status']}")
    
    print("\n" + "=" * 80)
    print("💡 Tipps zum Entfernen von Sources:")
    print("=" * 80)
    print("""
1. Neu registrieren (überschreibt alte UUID):
   python register_dlna_device.py {ip} {dlna_ip} {port}

2. DLNA-Server stoppen:
   - Sources werden automatisch UNAVAILABLE
   - Nach längerer Zeit entfernt das Gerät sie selbst

3. Gerät zurücksetzen (löscht ALLE Sources):
   - Halte "1" und "Volume -" für 10 Sekunden gedrückt
   - Oder über Bose App: Settings → Factory Reset

4. Andere Source wählen (deaktiviert STORED_MUSIC):
   curl -X POST http://{ip}:8090/select \\
     -H "Content-Type: application/xml" \\
     -d '<ContentItem source="AUX" sourceAccount="AUX"></ContentItem>'
""".format(ip=device_ip, dlna_ip="192.168.50.218", port="8201"))


if __name__ == "__main__":
    main()
