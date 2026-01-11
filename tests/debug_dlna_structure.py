#!/usr/bin/env python3
"""Debug DLNA browse to inspect returned DIDL-Lite structure."""

import requests
import xml.etree.ElementTree as ET
import html

MINIDLNA_IP = "192.168.50.218"
MINIDLNA_PORT = 8200

def browse_dlna_debug(object_id="1"):
    """Browse and print raw DIDL-Lite."""
    
    soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Browse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
      <ObjectID>{object_id}</ObjectID>
      <BrowseFlag>BrowseDirectChildren</BrowseFlag>
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
    
    response = requests.post(url, data=soap_body, headers=headers, timeout=5)
    root = ET.fromstring(response.text)
    
    result_elem = root.find('.//{*}Result')
    if result_elem is None:
        print(f"[!] No Result for ObjectID={object_id}")
        return
    
    result_xml = html.unescape(result_elem.text)
    print(f"\n=== ObjectID {object_id} ===")
    print(result_xml[:2000])
    print("\n--- Parsed elements ---")
    
    didl_root = ET.fromstring(result_xml)
    
    # Show all items and containers
    for item in didl_root.findall('.//{*}item'):
        item_id = item.get('id')
        title_elem = item.find('.//{*}title')
        title = title_elem.text if title_elem is not None else "?"
        
        # Check res elements
        for res in item.findall('.//{*}res'):
            proto = res.get('protocolInfo', 'unknown')
            res_text = res.text
            print(f"  item id={item_id}: {title}")
            print(f"    → {proto}")
            print(f"    → {res_text[:80]}")
    
    for container in didl_root.findall('.//{*}container'):
        container_id = container.get('id')
        title_elem = container.find('.//{*}title')
        title = title_elem.text if title_elem is not None else "?"
        print(f"  container id={container_id}: {title}")

# Explore structure
print("Browsing ObjectID=0 (root)...")
browse_dlna_debug("0")

print("\nBrowsing ObjectID=1 (Musik)...")
browse_dlna_debug("1")

print("\nBrowsing ObjectID=1$4 (Alle Titel - all songs)...")
browse_dlna_debug("1$4")
