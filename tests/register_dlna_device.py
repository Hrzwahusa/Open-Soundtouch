#!/usr/bin/env python3
"""
DLNA Device Registration Tool
Registriert Bose SoundTouch Geräte beim minidlna Server über X_MS_MediaReceiverRegistrar
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
            device_type = root.findtext('type', 'Unknown')
            
            # MAC Adresse
            network_info = root.find('networkInfo')
            mac_address = 'Unknown'
            if network_info is not None:
                mac_address = network_info.findtext('macAddress', 'Unknown')
            
            return {
                'deviceID': device_id,
                'name': name,
                'type': device_type,
                'mac': mac_address,
                'ip': bose_ip
            }
        return None
    except Exception as e:
        print(f"❌ Fehler beim Abrufen der Geräte-Info: {e}")
        return None


def get_dlna_server_info(dlna_ip: str, dlna_port: int = 8200) -> dict:
    """Hole DLNA Server Informationen."""
    try:
        url = f"http://{dlna_ip}:{dlna_port}/rootDesc.xml"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            
            # Namespace handling
            ns = {'upnp': 'urn:schemas-upnp-org:device-1-0'}
            
            device = root.find('.//upnp:device', ns)
            if device is None:
                device = root.find('.//device')
            
            if device:
                friendly_name = device.findtext('.//{urn:schemas-upnp-org:device-1-0}friendlyName', 'Unknown')
                udn = device.findtext('.//{urn:schemas-upnp-org:device-1-0}UDN', '')
                
                if not friendly_name or friendly_name == 'Unknown':
                    friendly_name = device.findtext('.//friendlyName', 'Unknown')
                if not udn:
                    udn = device.findtext('.//UDN', '')
                
                # Entferne "uuid:" Präfix falls vorhanden
                uuid = udn.replace('uuid:', '') if udn else ''
                
                return {
                    'friendlyName': friendly_name,
                    'UDN': udn,
                    'UUID': uuid,
                    'ip': dlna_ip,
                    'port': dlna_port
                }
        return None
    except Exception as e:
        print(f"❌ Fehler beim Abrufen der DLNA Server-Info: {e}")
        return None


def register_device_with_dlna(bose_info: dict, dlna_info: dict) -> bool:
    """
    Registriert das Bose Gerät beim DLNA Server.
    Sendet RegisterDevice SOAP Request an X_MS_MediaReceiverRegistrar Service.
    """
    try:
        dlna_ip = dlna_info['ip']
        dlna_port = dlna_info['port']
        
        # SOAP Envelope für RegisterDevice
        soap_action = '"urn:microsoft.com:service:X_MS_MediaReceiverRegistrar:1#RegisterDevice"'
        
        # Device Friendly Name und Message für die Registrierung
        device_name = bose_info['name']
        device_id = bose_info['deviceID']
        
        soap_body = f'''<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
    <s:Body>
        <u:RegisterDevice xmlns:u="urn:microsoft.com:service:X_MS_MediaReceiverRegistrar:1">
            <RegistrationReqMsg>
                &lt;?xml version="1.0"?&gt;
                &lt;RegistrationRequest xmlns="urn:microsoft.com:service:X_MS_MediaReceiverRegistrar:1"&gt;
                    &lt;DeviceID&gt;{escape(device_id)}&lt;/DeviceID&gt;
                    &lt;FriendlyName&gt;{escape(device_name)}&lt;/FriendlyName&gt;
                &lt;/RegistrationRequest&gt;
            </RegistrationReqMsg>
        </u:RegisterDevice>
    </s:Body>
</s:Envelope>'''
        
        url = f"http://{dlna_ip}:{dlna_port}/ctl/X_MS_MediaReceiverRegistrar"
        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPAction': soap_action,
        }
        
        print(f"\n📤 Sende RegisterDevice Request an DLNA Server...")
        print(f"   URL: {url}")
        print(f"   Device: {device_name} ({device_id})")
        
        response = requests.post(url, data=soap_body, headers=headers, timeout=10)
        
        print(f"\n📥 Server Antwort: HTTP {response.status_code}")
        print(f"   Response: {response.text[:500]}...")
        
        if response.status_code == 200:
            print(f"\n✅ Registrierung erfolgreich!")
            return True
        else:
            print(f"\n⚠️  Unerwarteter Status Code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Fehler bei der Registrierung: {e}")
        return False


def check_if_authorized(dlna_info: dict, device_id: str) -> bool:
    """
    Prüft ob das Gerät bereits autorisiert ist.
    Sendet IsAuthorized SOAP Request.
    """
    try:
        dlna_ip = dlna_info['ip']
        dlna_port = dlna_info['port']
        
        soap_action = '"urn:microsoft.com:service:X_MS_MediaReceiverRegistrar:1#IsAuthorized"'
        
        soap_body = f'''<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
    <s:Body>
        <u:IsAuthorized xmlns:u="urn:microsoft.com:service:X_MS_MediaReceiverRegistrar:1">
            <DeviceID>{escape(device_id)}</DeviceID>
        </u:IsAuthorized>
    </s:Body>
</s:Envelope>'''
        
        url = f"http://{dlna_ip}:{dlna_port}/ctl/X_MS_MediaReceiverRegistrar"
        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPAction': soap_action,
        }
        
        response = requests.post(url, data=soap_body, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Parse SOAP Response
            root = ET.fromstring(response.text)
            result = root.findtext('.//{urn:microsoft.com:service:X_MS_MediaReceiverRegistrar:1}Result')
            if result == "1":
                print(f"✅ Gerät ist bereits autorisiert")
                return True
            else:
                print(f"⚠️  Gerät ist NICHT autorisiert (Result={result})")
                return False
        else:
            print(f"⚠️  IsAuthorized Check fehlgeschlagen: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"⚠️  Fehler beim Authorization Check: {e}")
        return False


def main():
    """Main function."""
    print("="*80)
    print("DLNA Device Registration Tool")
    print("Registriert Bose SoundTouch Geräte beim minidlna Server")
    print("="*80)
    
    # Parameter
    if len(sys.argv) < 3:
        print("\nUsage: python register_dlna_device.py <bose_ip> <dlna_server_ip> [dlna_port]")
        print("\nBeispiel:")
        print("  python register_dlna_device.py 192.168.50.19 192.168.50.218")
        print("  python register_dlna_device.py 192.168.50.19 192.168.50.218 8200")
        sys.exit(1)
    
    bose_ip = sys.argv[1]
    dlna_ip = sys.argv[2]
    dlna_port = int(sys.argv[3]) if len(sys.argv) > 3 else 8200
    
    # 1. Hole Bose Geräte-Info
    print(f"\n🔍 Suche Bose Gerät unter {bose_ip}:8090...")
    bose_info = get_device_info(bose_ip)
    
    if not bose_info:
        print(f"❌ Konnte Bose Gerät nicht finden!")
        sys.exit(1)
    
    print(f"✅ Bose Gerät gefunden:")
    print(f"   Name:      {bose_info['name']}")
    print(f"   Type:      {bose_info['type']}")
    print(f"   Device ID: {bose_info['deviceID']}")
    print(f"   MAC:       {bose_info['mac']}")
    
    # 2. Hole DLNA Server-Info
    print(f"\n🔍 Suche DLNA Server unter {dlna_ip}:{dlna_port}...")
    dlna_info = get_dlna_server_info(dlna_ip, dlna_port)
    
    if not dlna_info:
        print(f"❌ Konnte DLNA Server nicht finden!")
        sys.exit(1)
    
    print(f"✅ DLNA Server gefunden:")
    print(f"   Name: {dlna_info['friendlyName']}")
    print(f"   UDN:  {dlna_info['UDN']}")
    print(f"   UUID: {dlna_info['UUID']}")
    
    # 3. Prüfe ob bereits autorisiert
    print(f"\n🔍 Prüfe Authorization Status...")
    is_authorized = check_if_authorized(dlna_info, bose_info['deviceID'])
    
    if is_authorized:
        print(f"\n✅ Gerät ist bereits beim DLNA Server registriert!")
        print(f"\n💡 Du kannst jetzt versuchen, Musik mit STORED_MUSIC zu spielen:")
        print(f"   sourceAccount: {dlna_info['UUID']}")
        sys.exit(0)
    
    # 4. Registriere Gerät
    print(f"\n🔧 Registriere Gerät beim DLNA Server...")
    success = register_device_with_dlna(bose_info, dlna_info)
    
    if success:
        print(f"\n" + "="*80)
        print(f"✅ ERFOLG!")
        print(f"="*80)
        print(f"\nDas Bose Gerät '{bose_info['name']}' wurde erfolgreich beim")
        print(f"DLNA Server '{dlna_info['friendlyName']}' registriert!")
        print(f"\n💡 Nutze folgende sourceAccount für STORED_MUSIC:")
        print(f"   {dlna_info['UUID']}")
    else:
        print(f"\n❌ Registrierung fehlgeschlagen!")
        sys.exit(1)


if __name__ == "__main__":
    main()
