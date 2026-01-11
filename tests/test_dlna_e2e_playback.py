#!/usr/bin/env python3
"""
End-to-end DLNA playback test:
1. Browse MiniDLNA ContentDirectory to find an MP3
2. Extract res URL and DIDL-Lite metadata
3. Send SetAVTransportURI to Bose device (port 8091)
4. Send Play command
"""

import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
import sys

# Configuration
MINIDLNA_IP = "192.168.50.218"
MINIDLNA_PORT = 8200
BOSE_DEVICE_IP = "192.168.50.184"
BOSE_DLNA_PORT = 8091

# Namespaces
NS = {
    'upnp': 'urn:schemas-upnp-org:metadata-1-0:upnp',
    'didl': 'urn:schemas-dlna-org:metadata-1-0:didl-lite',
    's': 'http://schemas.xmlsoap.org/soap/envelope/',
}

def browse_dlna(object_id="0", browse_flag="BrowseDirectChildren"):
    """Browse MiniDLNA ContentDirectory via SOAP."""
    print(f"[*] Browsing ObjectID={object_id}, BrowseFlag={browse_flag}")
    
    soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Browse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
      <ObjectID>{object_id}</ObjectID>
      <BrowseFlag>{browse_flag}</BrowseFlag>
      <Filter></Filter>
      <StartingIndex>0</StartingIndex>
      <RequestedCount>100</RequestedCount>
      <SortCriteria></SortCriteria>
    </u:Browse>
  </s:Body>
</s:Envelope>"""

    headers = {
        'HOST': f'{MINIDLNA_IP}:{MINIDLNA_PORT}',
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPACTION': '"urn:schemas-upnp-org:service:ContentDirectory:1#Browse"',
    }
    
    url = f"http://{MINIDLNA_IP}:{MINIDLNA_PORT}/ctl/ContentDir"
    
    try:
        response = requests.post(url, data=soap_body, headers=headers, timeout=5)
        if response.status_code != 200:
            print(f"[!] Browse failed: HTTP {response.status_code}")
            return None
        
        # Parse SOAP response
        root = ET.fromstring(response.text)
        
        # Check for SOAP Fault first
        fault = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Fault')
        if fault is not None:
            fault_str = fault.findtext('{http://schemas.xmlsoap.org/soap/envelope/}faultstring')
            print(f"[!] SOAP Fault: {fault_str}")
            print(f"[!] Response:\n{response.text[:1000]}")
            return None
        
        # Try various namespace combinations to find Result
        result_elem = None
        for ns in [
            './/{urn:schemas-upnp-org:service:ContentDirectory:1}Result',
            './/{*}Result',  # wildcard namespace
        ]:
            result_elem = root.find(ns)
            if result_elem is not None:
                break
        
        if result_elem is None:
            print("[!] No Result element found in SOAP response")
            print(f"[!] Response (first 1500 chars):\n{response.text[:1500]}")
            return None
        
        result_xml = result_elem.text
        if not result_xml:
            print("[!] Result is empty")
            return None
        
        # Unescape HTML entities
        import html
        result_xml = html.unescape(result_xml)
        
        print(f"[+] Browse returned {len(result_xml)} bytes of DIDL-Lite")
        return result_xml
    
    except Exception as e:
        print(f"[!] Browse error: {e}")
        return None

def find_mp3_in_didl(didl_xml):
    """Extract the first playable MP3 res URL from DIDL-Lite XML."""
    try:
        root = ET.fromstring(didl_xml)
        
        # Use wildcard namespace matching to handle different DIDL-Lite namespace variants
        for item in root.findall('.//{*}item'):
            # Try both with and without namespace
            title_elem = item.find('{http://purl.org/dc/elements/1.1/}title')
            if title_elem is None:
                title_elem = item.find('.//{*}title')
            
            title = title_elem.text if title_elem is not None else "Unknown"
            
            # Find res element
            for res in item.findall('.//{*}res'):
                protocol_info = res.get('protocolInfo', '')
                res_url = res.text
                
                if res_url and ('192.168' in res_url or 'MediaItems' in res_url):
                    print(f"[+] Found playable item: {title}")
                    print(f"    URL: {res_url}")
                    print(f"    ProtocolInfo: {protocol_info[:60]}...")
                    
                    # Return URL, title, full item XML, and protocol info
                    item_xml = ET.tostring(item, encoding='unicode')
                    return res_url, title, item_xml, protocol_info
        
        print("[!] No playable items found in DIDL-Lite")
        return None, None, None, None
    
    except Exception as e:
        print(f"[!] DIDL parsing error: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None

def set_av_transport_uri(resource_url, didl_metadata, protocol_info):
    """Send SetAVTransportURI SOAP command to Bose device."""
    print(f"[*] Setting AV Transport URI on {BOSE_DEVICE_IP}:{BOSE_DLNA_PORT}")
    
    # Build DIDL-Lite metadata
    # The resource must have proper protocolInfo and include the item XML
    didl_object = f"""<item id="0" parentID="-1" restricted="1">
  <dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Remote Content</dc:title>
  <upnp:class xmlns:upnp="urn:schemas-upnp-org:metadata-1-0:upnp">object.item.audioItem.musicTrack</upnp:class>
  <res protocolInfo="{protocol_info}" duration="00:00:00">{resource_url}</res>
</item>"""
    
    soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <CurrentURI>{resource_url}</CurrentURI>
      <CurrentURIMetaData>&lt;DIDL-Lite xmlns="urn:schemas-dlna-org:metadata-1-0:didl-lite" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0:upnp"&gt;{didl_object}&lt;/DIDL-Lite&gt;</CurrentURIMetaData>
    </u:SetAVTransportURI>
  </s:Body>
</s:Envelope>"""
    
    headers = {
        'HOST': f'{BOSE_DEVICE_IP}:{BOSE_DLNA_PORT}',
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPACTION': '"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI"',
    }
    
    url = f"http://{BOSE_DEVICE_IP}:{BOSE_DLNA_PORT}/AVTransport/Control"
    
    try:
        response = requests.post(url, data=soap_body, headers=headers, timeout=5)
        if response.status_code == 200:
            print(f"[+] SetAVTransportURI success (HTTP {response.status_code})")
            return True
        else:
            print(f"[!] SetAVTransportURI failed: HTTP {response.status_code}")
            if response.text:
                print(f"    Response: {response.text[:500]}")
            return False
    
    except Exception as e:
        print(f"[!] SetAVTransportURI error: {e}")
        return False

def play_device():
    """Send Play SOAP command to Bose device."""
    print(f"[*] Sending Play command to {BOSE_DEVICE_IP}:{BOSE_DLNA_PORT}")
    
    soap_body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <Speed>1</Speed>
    </u:Play>
  </s:Body>
</s:Envelope>"""
    
    headers = {
        'HOST': f'{BOSE_DEVICE_IP}:{BOSE_DLNA_PORT}',
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPACTION': '"urn:schemas-upnp-org:service:AVTransport:1#Play"',
    }
    
    url = f"http://{BOSE_DEVICE_IP}:{BOSE_DLNA_PORT}/AVTransport/Control"
    
    try:
        response = requests.post(url, data=soap_body, headers=headers, timeout=5)
        if response.status_code == 200:
            print(f"[+] Play success (HTTP {response.status_code})")
            print("[+] 🎵 Playback should start now!")
            return True
        else:
            print(f"[!] Play failed: HTTP {response.status_code}")
            if response.text:
                print(f"    Response: {response.text[:500]}")
            return False
    
    except Exception as e:
        print(f"[!] Play error: {e}")
        return False

def main():
    print("=" * 70)
    print("DLNA E2E Playback Test: MiniDLNA → Bose SoundTouch 10")
    print("=" * 70)
    print()
    
    # Step 1: Browse root
    didl_root = browse_dlna("0", "BrowseDirectChildren")
    if not didl_root:
        print("[!] Failed to browse root")
        return False
    
    # Step 2: Look for a music folder (e.g., "Musik" or "Ordner durchsuchen")
    music_folder_id = None
    try:
        root = ET.fromstring(didl_root)
        for container in root.findall('.//container'):
            title_elem = container.find('{urn:schemas-upnp-org:metadata-1-0:upnp}title')
            if title_elem is not None:
                title = title_elem.text
                obj_id = container.get('id')
                print(f"    Container: {title} (ID={obj_id})")
                if 'Musik' in title or 'Musik' in (title or ''):
                    music_folder_id = obj_id
                    print(f"    → Selected music folder: {title}")
                    break
    except Exception as e:
        print(f"[!] Error parsing containers: {e}")
    
    if not music_folder_id:
        print("[!] No music folder found; trying ObjectID=1 (Musik)")
        music_folder_id = "1"
    
    # Step 3: Browse music folder for files
    print()
    
    # MiniDLNA structure: Musik (1) → Alle Titel (1$4) → actual songs
    if music_folder_id == "1":
        music_folder_id = "1$4"
        print(f"[*] Using MiniDLNA standard path: Musik → Alle Titel ({music_folder_id})")
    
    didl_music = browse_dlna(music_folder_id, "BrowseDirectChildren")
    if not didl_music:
        print(f"[!] Failed to browse {music_folder_id}")
        return False
    
    # Step 4: Find first MP3
    print()
    res_url, title, item_xml, protocol_info = find_mp3_in_didl(didl_music)
    if not res_url:
        print("[!] No MP3 found")
        return False
    
    # Step 5: Set URI and Play
    print()
    if not set_av_transport_uri(res_url, item_xml, protocol_info):
        print("[!] Failed to set transport URI")
        return False
    
    print()
    if not play_device():
        print("[!] Failed to send play command")
        return False
    
    print()
    print("=" * 70)
    print("✓ E2E DLNA playback sequence completed successfully!")
    print("=" * 70)
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
