#!/usr/bin/env python3
"""
Liste alle Audio-Dateien im minidlna Index auf
"""

import requests
import xml.etree.ElementTree as ET

def browse_container(object_id="64", max_results=50):
    """Browse minidlna container."""
    browse_request = f'''<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
 <s:Body>
  <u:Browse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
   <ObjectID>{object_id}</ObjectID>
   <BrowseFlag>BrowseDirectChildren</BrowseFlag>
   <Filter>*</Filter>
   <StartingIndex>0</StartingIndex>
   <RequestedCount>{max_results}</RequestedCount>
   <SortCriteria></SortCriteria>
  </u:Browse>
 </s:Body>
</s:Envelope>'''

    headers = {
        'Content-Type': 'text/xml; charset="utf-8"',
        'SOAPACTION': '"urn:schemas-upnp-org:service:ContentDirectory:1#Browse"',
    }

    try:
        response = requests.post(
            'http://192.168.50.218:8200/ctl/ContentDir', 
            data=browse_request, 
            headers=headers, 
            timeout=5
        )

        if response.status_code == 200:
            root = ET.fromstring(response.text)
            ns = {
                's': 'http://schemas.xmlsoap.org/soap/envelope/',
                'u': 'urn:schemas-upnp-org:service:ContentDirectory:1'
            }
            result_elem = root.find('.//u:BrowseResponse/Result', ns)
            
            if result_elem is not None and result_elem.text:
                didl_root = ET.fromstring(result_elem.text)
                didl_ns = {'didl': 'urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/'}
                
                items = []
                
                # Containers (Ordner)
                for container in didl_root.findall('.//didl:container', didl_ns):
                    container_id = container.get('id', '')
                    title_elem = container.find('didl:title', didl_ns)
                    if title_elem is not None:
                        items.append(('FOLDER', container_id, title_elem.text, None))
                
                # Items (Dateien)
                for item in didl_root.findall('.//didl:item', didl_ns):
                    title_elem = item.find('didl:title', didl_ns)
                    res_elem = item.find('didl:res', didl_ns)
                    if title_elem is not None and res_elem is not None:
                        items.append(('FILE', None, title_elem.text, res_elem.text))
                
                return items
    except Exception as e:
        print(f"Fehler beim Browse: {e}")
    
    return []


print("=" * 80)
print("minidlna Index Browser")
print("=" * 80)

# Root-Container (64 = All Music)
print("\n📁 Root Container (ObjectID=64 - All Music):")
items = browse_container("64", 100)

folders = [item for item in items if item[0] == 'FOLDER']
files = [item for item in items if item[0] == 'FILE']

if folders:
    print(f"\n📂 Ordner ({len(folders)}):")
    for typ, container_id, title, url in folders:
        print(f"  [{container_id}] {title}")

if files:
    print(f"\n🎵 Dateien ({len(files)}):")
    for i, (typ, _, title, url) in enumerate(files[:20], 1):
        print(f"  {i}. {title}")
        print(f"     URL: {url}")

# Browse ersten Ordner falls vorhanden
if folders:
    first_folder = folders[0]
    print(f"\n📂 Browse Ordner: {first_folder[2]}")
    print("=" * 80)
    
    sub_items = browse_container(first_folder[1], 20)
    sub_files = [item for item in sub_items if item[0] == 'FILE']
    
    if sub_files:
        print(f"\n🎵 Dateien im Ordner ({len(sub_files)}):")
        for i, (typ, _, title, url) in enumerate(sub_files[:10], 1):
            print(f"  {i}. {title}")
            print(f"     URL: {url}")
    else:
        print("Keine Dateien im Ordner gefunden")

print("\n" + "=" * 80)
