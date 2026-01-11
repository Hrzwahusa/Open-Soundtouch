#!/usr/bin/env python3
"""
DLNA Device Unregistration Tool
Entfernt die Registrierung eines Bose SoundTouch Geräts vom DLNA-Server
"""

import requests
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
import sys


def get_device_info(bose_ip: str, bose_port: int = 8090) -> dict:
    """Hole Geräte-Informationen vom Bose Gerät."""
    try:
        url = f"http://{bose_ip}:{bose_port}/info"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            
            device_id = root.get('deviceID', '')
            name = root.findtext('name', 'Unknown')
            
            return {
                'deviceID': device_id,
                'name': name,
                'ip': bose_ip
            }
        return None
    except Exception as e:
        print(f"❌ Fehler beim Abrufen der Geräte-Info: {e}")
        return None


def unregister_device_from_dlna(bose_info: dict, dlna_ip: str, dlna_port: int = 8201) -> bool:
    """
    Entfernt die Registrierung des Bose Geräts vom DLNA Server.
    Sendet DeregisterDevice SOAP Request an X_MS_MediaReceiverRegistrar Service.
    """
    try:
        device_id = bose_info['deviceID']
        device_name = bose_info['name']
        
        # SOAP Envelope für DeregisterDevice
        soap_action = '"urn:microsoft.com:service:X_MS_MediaReceiverRegistrar:1#DeregisterDevice"'
        
        soap_body = f'''<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
    <s:Body>
        <u:DeregisterDevice xmlns:u="urn:microsoft.com:service:X_MS_MediaReceiverRegistrar:1">
            <DeviceID>{escape(device_id)}</DeviceID>
        </u:DeregisterDevice>
    </s:Body>
</s:Envelope>'''
        
        url = f"http://{dlna_ip}:{dlna_port}/ctl/X_MS_MediaReceiverRegistrar"
        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPAction': soap_action,
        }
        
        print(f"\n📤 Sende DeregisterDevice Request an DLNA Server...")
        print(f"   URL: {url}")
        print(f"   Device: {device_name} ({device_id})")
        
        response = requests.post(url, data=soap_body, headers=headers, timeout=10)
        
        print(f"\n📥 Server Antwort: HTTP {response.status_code}")
        if response.text:
            print(f"   Response: {response.text[:500]}...")
        
        if response.status_code == 200:
            print(f"\n✅ Deregistrierung erfolgreich!")
            return True
        else:
            print(f"\n⚠️  Unerwarteter Status Code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Fehler bei der Deregistrierung: {e}")
        return False


def main():
    """Main function."""
    print("=" * 80)
    print("DLNA Device Unregistration Tool")
    print("Entfernt Bose SoundTouch Registrierung vom DLNA Server")
    print("=" * 80)
    
    # Parameter
    if len(sys.argv) < 3:
        print("\nUsage: python unregister_dlna_device.py <bose_ip> <dlna_server_ip> [dlna_port]")
        print("\nBeispiel:")
        print("  python unregister_dlna_device.py 192.168.50.19 192.168.50.218")
        print("  python unregister_dlna_device.py 192.168.50.19 192.168.50.218 8201")
        sys.exit(1)
    
    bose_ip = sys.argv[1]
    dlna_ip = sys.argv[2]
    dlna_port = int(sys.argv[3]) if len(sys.argv) > 3 else 8201
    
    # Hole Bose Geräte-Info
    print(f"\n🔍 Suche Bose Gerät unter {bose_ip}:8090...")
    bose_info = get_device_info(bose_ip)
    
    if not bose_info:
        print(f"❌ Konnte Bose Gerät nicht finden!")
        sys.exit(1)
    
    print(f"✅ Bose Gerät gefunden:")
    print(f"   Name:      {bose_info['name']}")
    print(f"   Device ID: {bose_info['deviceID']}")
    
    # Deregistriere Gerät
    print(f"\n🔧 Entferne Registrierung vom DLNA Server...")
    success = unregister_device_from_dlna(bose_info, dlna_ip, dlna_port)
    
    if success:
        print(f"\n" + "=" * 80)
        print(f"✅ ERFOLG!")
        print(f"=" * 80)
        print(f"\nDas Bose Gerät '{bose_info['name']}' wurde erfolgreich vom")
        print(f"DLNA Server deregistriert!")
        print(f"\n💡 Das Gerät kann sich jederzeit wieder neu registrieren.")
    else:
        print(f"\n❌ Deregistrierung fehlgeschlagen!")
        sys.exit(1)


if __name__ == "__main__":
    main()
