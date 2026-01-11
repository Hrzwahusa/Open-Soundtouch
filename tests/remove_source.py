#!/usr/bin/env python3
"""
Versucht STORED_MUSIC Source von Bose SoundTouch zu entfernen.
"""

import requests
import xml.etree.ElementTree as ET
import sys


def try_remove_source(device_ip: str, source_account: str):
    """
    Versucht verschiedene Methoden um eine Source zu entfernen.
    """
    base_url = f"http://{device_ip}:8090"
    
    print(f"🔍 Versuche Source {source_account} zu entfernen...")
    print("=" * 80)
    
    # Methode 1: POST /select mit leerem ContentItem
    print("\n1️⃣  Versuch: Leere Source senden...")
    try:
        response = requests.post(
            f"{base_url}/select",
            headers={'Content-Type': 'application/xml'},
            data='<ContentItem source="" sourceAccount=""></ContentItem>',
            timeout=5
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Möglicherweise erfolgreich!")
        else:
            print(f"   ❌ Fehlgeschlagen: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
    
    # Methode 2: POST mit STANDBY source
    print("\n2️⃣  Versuch: STANDBY mode setzen...")
    try:
        response = requests.post(
            f"{base_url}/select",
            headers={'Content-Type': 'application/xml'},
            data='<ContentItem source="STANDBY"></ContentItem>',
            timeout=5
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Möglicherweise erfolgreich!")
        else:
            print(f"   ❌ Fehlgeschlagen: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
    
    # Methode 3: POST mit isPresetable="false"
    print("\n3️⃣  Versuch: isPresetable=false setzen...")
    try:
        response = requests.post(
            f"{base_url}/select",
            headers={'Content-Type': 'application/xml'},
            data=f'<ContentItem source="STORED_MUSIC" sourceAccount="{source_account}" isPresetable="false"></ContentItem>',
            timeout=5
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Möglicherweise erfolgreich!")
        else:
            print(f"   ❌ Fehlgeschlagen: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
    
    # Methode 4: Andere Source auswählen (BLUETOOTH oder AUX)
    print("\n4️⃣  Versuch: Zu BLUETOOTH wechseln (deaktiviert STORED_MUSIC)...")
    try:
        response = requests.post(
            f"{base_url}/select",
            headers={'Content-Type': 'application/xml'},
            data='<ContentItem source="BLUETOOTH"></ContentItem>',
            timeout=5
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ BLUETOOTH aktiviert - STORED_MUSIC deaktiviert")
        else:
            print(f"   ❌ Fehlgeschlagen: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
    
    # Status prüfen
    print("\n" + "=" * 80)
    print("📋 Aktuelle Sources nach Löschversuchen:")
    print("-" * 80)
    try:
        response = requests.get(f"{base_url}/sources", timeout=5)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            for item in root.findall('sourceItem'):
                source = item.get('source', '')
                if 'STORED_MUSIC' in source:
                    status = item.get('status', '')
                    name = item.text or ''
                    sa = item.get('sourceAccount', '')
                    icon = "✅" if status == 'READY' else "❌"
                    print(f"{icon} {source}")
                    print(f"   Status:        {status}")
                    print(f"   SourceAccount: {sa}")
                    print(f"   Name:          {name}")
                    print()
    except Exception as e:
        print(f"❌ Fehler beim Abrufen: {e}")
    
    print("=" * 80)
    print("💡 Zusammenfassung:")
    print("=" * 80)
    print("""
Die Bose API hat KEINEN DELETE-Endpunkt für Sources.

Einzige zuverlässige Methoden:

1. ⚡ DLNA-Server stoppen:
   sudo pkill minidlnad
   → Sources werden UNAVAILABLE
   → Gerät entfernt sie nach einiger Zeit

2. 🔄 Neu-Registrierung mit neuer UUID:
   python register_dlna_device.py (mit neuem FriendlyName)
   → Alte Source bleibt, aber neue kommt dazu

3. 🏭 Factory Reset (löscht ALLES):
   Halte "1" + "Volume -" für 10 Sekunden
   → ALLE Sources und Einstellungen weg
   
4. ✋ Andere Source wählen:
   Wähle BLUETOOTH/AUX → STORED_MUSIC wird inaktiv
   → Source bleibt gespeichert, ist aber nicht aktiv
""")


def main():
    if len(sys.argv) < 2:
        print("Usage: python remove_source.py <device_ip> [source_account]")
        print("\nBeispiel:")
        print("  python remove_source.py 192.168.50.19")
        print("  python remove_source.py 192.168.50.19 1d335f1c-a118-43ea-8c05-e92f50e76882/0")
        sys.exit(1)
    
    device_ip = sys.argv[1]
    source_account = sys.argv[2] if len(sys.argv) > 2 else ""
    
    try_remove_source(device_ip, source_account)


if __name__ == "__main__":
    main()
