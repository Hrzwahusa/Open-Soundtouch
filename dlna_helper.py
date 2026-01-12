"""
DLNA/UPnP Helper for Bose SoundTouch Devices
Handles ContentDirectory browsing and AVTransport playback
"""

import requests
import xml.etree.ElementTree as ET
import html
from typing import Tuple, Optional


class DLNAHelper:
    """DLNA ContentDirectory and AVTransport helper for local media playback."""
    
    def __init__(self, dlna_server_ip: str, dlna_server_port: int = 8200, 
                 device_ip: str = None, device_dlna_port: int = 8091):
        """
        Initialize DLNA helper.
        
        Args:
            dlna_server_ip: IP of DLNA server (e.g., MiniDLNA at 192.168.50.218)
            dlna_server_port: DLNA server HTTP port (default: 8200 for MiniDLNA)
            device_ip: IP of Bose device (for playback)
            device_dlna_port: Bose DLNA port (default: 8091)
        """
        self.server_ip = dlna_server_ip
        self.server_port = dlna_server_port
        self.device_ip = device_ip
        self.device_dlna_port = device_dlna_port
        self.timeout = 5
    
    def browse(self, object_id: str = "0", browse_flag: str = "BrowseDirectChildren") -> Optional[str]:
        """
        Browse DLNA ContentDirectory via SOAP.
        
        Returns unescaped DIDL-Lite XML string or None on error.
        """
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
            'HOST': f'{self.server_ip}:{self.server_port}',
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPACTION': '"urn:schemas-upnp-org:service:ContentDirectory:1#Browse"',
        }
        
        url = f"http://{self.server_ip}:{self.server_port}/ctl/ContentDir"
        
        try:
            response = requests.post(url, data=soap_body, headers=headers, timeout=self.timeout)
            if response.status_code != 200:
                return None
            
            root = ET.fromstring(response.text)
            result_elem = root.find('.//{*}Result')
            
            if result_elem is None or not result_elem.text:
                return None
            
            return html.unescape(result_elem.text)
        
        except Exception as e:
            print(f"[DLNA] Browse error: {e}")
            return None
    
    def find_music_container(self) -> Optional[str]:
        """
        Find the music container in MiniDLNA.
        Returns container ID (e.g., "1$4" for Musik → Alle Titel).
        """
        didl_root = self.browse("0", "BrowseDirectChildren")
        if not didl_root:
            return None
        
        try:
            root = ET.fromstring(didl_root)
            for container in root.findall('.//{*}container'):
                title_elem = container.find('.//{*}title')
                if title_elem is not None and "Musik" in (title_elem.text or ''):
                    # Found Musik folder; use standard MiniDLNA path to all songs
                    return "1$4"  # Alle Titel under Musik
        except Exception:
            pass
        
        return None
    
    def find_first_playable_track(self, container_id: str = "1$4") -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Find first playable MP3 in a container.
        
        Returns tuple of (res_url, title, protocol_info) or (None, None, None).
        """
        didl_music = self.browse(container_id, "BrowseDirectChildren")
        if not didl_music:
            return None, None, None
        
        try:
            root = ET.fromstring(didl_music)
            
            for item in root.findall('.//{*}item'):
                title_elem = item.find('.//{*}title')
                title = title_elem.text if title_elem is not None else "Unknown"
                
                for res in item.findall('.//{*}res'):
                    res_url = res.text
                    protocol_info = res.get('protocolInfo', '')
                    
                    if res_url and self.server_ip in res_url:
                        return res_url, title, protocol_info
        
        except Exception:
            pass
        
        return None, None, None
    
    def set_av_transport_uri(self, resource_url: str, title: str = "Unknown",
                             protocol_info: str = "http-get:*:audio/mpeg:*",
                             artist: str = "Unknown", album: str = "Unknown") -> bool:
        """
        Send SetAVTransportURI SOAP command to Bose device.

        Args:
            resource_url: Full HTTP URL to media file
            title: Friendly title for the track
            protocol_info: DLNA protocol info string
            artist: Artist name
            album: Album name

        Returns True if successful.
        """
        if not self.device_ip:
            print("[DLNA] Device IP not set")
            return False

        # Escape XML special characters in metadata and resource
        title_escaped = html.escape(title) if title else "Unknown"
        artist_escaped = html.escape(artist) if artist else "Unknown"
        album_escaped = html.escape(album) if album else "Unknown"
        res_url_escaped = html.escape(resource_url) if resource_url else ""
        protocol_info_escaped = html.escape(protocol_info) if protocol_info else ""

        # Build full DIDL-Lite and then escape once for SOAP payload
        didl_lite = f"""<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">
  <item id="0" parentID="-1" restricted="1">
    <dc:title>{title_escaped}</dc:title>
    <dc:creator>{artist_escaped}</dc:creator>
    <upnp:artist role="Performer">{artist_escaped}</upnp:artist>
    <upnp:album>{album_escaped}</upnp:album>
    <upnp:class>object.item.audioItem.musicTrack</upnp:class>
    <res protocolInfo="{protocol_info_escaped}">{res_url_escaped}</res>
  </item>
</DIDL-Lite>"""

        current_uri_metadata = html.escape(didl_lite)

        soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <CurrentURI>{resource_url}</CurrentURI>
      <CurrentURIMetaData>{current_uri_metadata}</CurrentURIMetaData>
    </u:SetAVTransportURI>
  </s:Body>
</s:Envelope>"""

        headers = {
            'HOST': f'{self.device_ip}:{self.device_dlna_port}',
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPACTION': '"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI"',
        }

        url = f"http://{self.device_ip}:{self.device_dlna_port}/AVTransport/Control"

        try:
            response = requests.post(url, data=soap_body, headers=headers, timeout=self.timeout)
            return response.status_code == 200
        except Exception as e:
            print(f"[DLNA] SetAVTransportURI error: {e}")
            return False
    
    def play(self) -> bool:
        """
        Send Play SOAP command to Bose device.
        
        Returns True if successful.
        """
        if not self.device_ip:
            print("[DLNA] Device IP not set")
            return False
        
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
            'HOST': f'{self.device_ip}:{self.device_dlna_port}',
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPACTION': '"urn:schemas-upnp-org:service:AVTransport:1#Play"',
        }
        
        url = f"http://{self.device_ip}:{self.device_dlna_port}/AVTransport/Control"
        
        try:
            response = requests.post(url, data=soap_body, headers=headers, timeout=self.timeout)
            return response.status_code == 200
        except Exception as e:
            print(f"[DLNA] Play error: {e}")
            return False
    
    def stop(self) -> bool:
        """Send Stop SOAP command to Bose device."""
        if not self.device_ip:
            return False
        
        soap_body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Stop xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
    </u:Stop>
  </s:Body>
</s:Envelope>"""
        
        headers = {
            'HOST': f'{self.device_ip}:{self.device_dlna_port}',
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPACTION': '"urn:schemas-upnp-org:service:AVTransport:1#Stop"',
        }
        
        url = f"http://{self.device_ip}:{self.device_dlna_port}/AVTransport/Control"
        
        try:
            response = requests.post(url, data=soap_body, headers=headers, timeout=self.timeout)
            return response.status_code == 200
        except Exception:
            return False
