#!/usr/bin/env python3
"""
TuneIn Radio Helper - Works WITHOUT TUNEIN activation!

This helper automatically detects the best method to play TuneIn radio:
1. TUNEIN source (if activated)
2. LOCAL_INTERNET_RADIO (works without activation!)  
3. DLNA fallback (always works)

KEY INSIGHT: LOCAL_INTERNET_RADIO is available on ALL devices and doesn't
require the TUNEIN service to be activated. This solves the activation problem!
"""

import requests
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from typing import Dict, Optional


class TuneInHelper:
    """Helper class for playing TuneIn radio without requiring TUNEIN activation."""
    
    def __init__(self, device_ip: str, port: int = 8090, timeout: int = 5):
        """
        Initialize TuneIn helper.
        
        Args:
            device_ip: IP address of SoundTouch device
            port: API port (default: 8090)
            timeout: Request timeout in seconds
        """
        self.ip = device_ip
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{device_ip}:{port}"
        
    def check_available_methods(self) -> Dict[str, any]:
        """
        Check which TuneIn playback methods are available on this device.
        
        Returns:
            Dict with: 
                - 'tunein_active': bool (TUNEIN in /sources)
                - 'local_radio_available': bool (LOCAL_INTERNET_RADIO available)
                - 'best_method': str ('TUNEIN', 'LOCAL_INTERNET_RADIO', or 'DLNA')
        """
        result = {
            'tunein_active': False,
            'local_radio_available': False,
            'best_method': 'DLNA'  # Safe fallback
        }
        
        try:
            # Check active sources
            response = requests.get(f"{self.base_url}/sources", timeout=self.timeout)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                sources = [s.get('source') for s in root.findall('.//sourceItem')]
                
                if 'TUNEIN' in sources:
                    result['tunein_active'] = True
                    result['best_method'] = 'TUNEIN'
                elif 'LOCAL_INTERNET_RADIO' in sources:
                    result['local_radio_available'] = True
                    result['best_method'] = 'LOCAL_INTERNET_RADIO'
                    
            # Also check serviceAvailability
            response = requests.get(f"{self.base_url}/serviceAvailability", timeout=self.timeout)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                for service in root.findall('.//service'):
                    stype = service.get('type')
                    available = service.get('isAvailable') == 'true'
                    
                    if stype == 'LOCAL_INTERNET_RADIO' and available:
                        result['local_radio_available'] = True
                        if result['best_method'] == 'DLNA':
                            result['best_method'] = 'LOCAL_INTERNET_RADIO'
                            
        except Exception as e:
            print(f"Error checking methods: {e}")
            
        return result
    
    def get_stream_url(self, guide_id_or_location: str) -> Optional[str]:
        """
        Resolve a TuneIn ID or /v1/playback/station/... location to a direct stream URL.
        Accepts:
          - 's125937' (guide ID)
          - '/v1/playback/station/s125937' (Bose-style location)
          - 'http(s)://...' (already a stream URL)
        """
        try:
            # Already a direct URL (not a TuneIn API URL)
            if guide_id_or_location.startswith("http://") or guide_id_or_location.startswith("https://"):
                if "opml.radiotime.com" not in guide_id_or_location and "tunein.com" not in guide_id_or_location:
                    return guide_id_or_location

            # Extract guide ID from Bose location form
            guide_id = guide_id_or_location
            if "/playback/station/" in guide_id_or_location:
                guide_id = guide_id_or_location.rsplit("/", 1)[-1]

            tune_url = f"http://opml.radiotime.com/Tune.ashx?id={guide_id}"

            # Get OPML response
            response = requests.get(tune_url, timeout=self.timeout)
            if response.status_code != 200:
                print(f"TuneIn returned status {response.status_code}")
                return None

            # Decode response
            content = response.content.decode('utf-8', errors='ignore').strip()
            
            # Check if it's a simple plaintext URL list (one per line)
            if content.startswith('http://') or content.startswith('https://'):
                # Take the first HTTPS URL if available, otherwise first HTTP
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                https_urls = [line for line in lines if line.startswith('https://')]
                http_urls = [line for line in lines if line.startswith('http://')]
                
                stream_url = None
                if http_urls:
                    stream_url = http_urls[0]
                elif https_urls:
                    stream_url = https_urls[0]
                
                # Remove TuneIn tracking parameters
                if stream_url:
                    # Remove ?aw_0_1st.playerid=tunein.com and similar tracking params
                    if '?' in stream_url:
                        base_url = stream_url.split('?')[0]
                        print(f"Found stream URL (cleaned): {base_url}")
                        return base_url
                    print(f"Found stream URL: {stream_url}")
                    return stream_url
            
            # Otherwise try to parse as XML/OPML
            if content.startswith('<?xml') or content.startswith('<opml'):
                try:
                    root = ET.fromstring(response.content)
                    
                    # Find audio outline element with actual stream URL
                    for outline in root.findall('.//outline[@type="audio"]'):
                        url = outline.get('URL')
                        if url:
                            print(f"Found stream URL: {url}")
                            return url
                    
                    # Fallback: check for link type that might redirect
                    for outline in root.findall('.//outline[@type="link"]'):
                        url = outline.get('URL')
                        if url and 'Tune.ashx' in url:
                            # Recursive call to follow the link (max 1 level)
                            print(f"Following link: {url}")
                            return self.get_stream_url(url)
                            
                except ET.ParseError as pe:
                    print(f"XML parse error: {pe}")
                    print(f"Response content: {content[:500]}")

            print(f"No stream URL found in response")
            return None

        except Exception as e:
            print(f"Error getting stream URL: {e}")

        return None

    def _ensure_stream_url(self, value: str) -> Optional[str]:
        """Return a direct stream URL, resolving TuneIn IDs or playback paths if needed."""
        return self.get_stream_url(value)
    
    def play_station(self, guide_id: str, station_name: str = "Radio", 
                     image_url: str = "", force_method: Optional[str] = None) -> Dict[str, any]:
        """
        Play a TuneIn station using the best available method.
        
        Args:
            guide_id: TuneIn station ID (e.g., 's296439' for BBC Radio 1)
            station_name: Display name for the station
            image_url: Optional station logo URL
            force_method: Force specific method ('TUNEIN', 'LOCAL_INTERNET_RADIO', 'DLNA')
            
        Returns:
            Dict with 'success': bool, 'method': str, 'message': str
        """
        result = {
            'success': False,
            'method': None,
            'message': ''
        }
        
        try:
            # Get stream URL (accept guide ID or playback location)
            stream_url = self._ensure_stream_url(guide_id)
            if not stream_url:
                result['message'] = "Could not resolve station stream URL"
                return result
            
            # Determine which method to use
            if force_method:
                methods = [force_method]
            else:
                available = self.check_available_methods()
                if available['tunein_active']:
                    methods = ['TUNEIN', 'LOCAL_INTERNET_RADIO', 'DLNA']
                elif available['local_radio_available']:
                    methods = ['LOCAL_INTERNET_RADIO', 'DLNA']
                else:
                    methods = ['DLNA']
            
            # Try each method in order
            for method in methods:
                if method == 'TUNEIN':
                    if self._play_via_tunein(stream_url, station_name, image_url):
                        result['success'] = True
                        result['method'] = 'TUNEIN'
                        result['message'] = 'Playing via TUNEIN source'
                        return result
                        
                elif method == 'LOCAL_INTERNET_RADIO':
                    if self._play_via_local_radio(stream_url, station_name, image_url):
                        result['success'] = True
                        result['method'] = 'LOCAL_INTERNET_RADIO'
                        result['message'] = 'Playing via LOCAL_INTERNET_RADIO (no activation needed!)'
                        return result
                        
                elif method == 'DLNA':
                    if self._play_via_dlna(stream_url, station_name, image_url):
                        result['success'] = True
                        result['method'] = 'DLNA'
                        result['message'] = 'Playing via DLNA fallback'
                        return result
            
            result['message'] = 'All playback methods failed'
            
        except Exception as e:
            result['message'] = f"Error: {e}"
            
        return result
    
    def _play_via_tunein(self, stream_url: str, name: str, image: str) -> bool:
        """Play via TUNEIN source (requires activation)."""
        try:
            resolved = self._ensure_stream_url(stream_url)
            if not resolved:
                return False
            xml = f'''<ContentItem source="TUNEIN" location="{escape(resolved)}" isPresetable="true">
                <itemName>{escape(name)}</itemName>
                {f'<containerArt>{escape(image)}</containerArt>' if image else ''}
            </ContentItem>'''
            
            response = requests.post(f"{self.base_url}/select", data=xml, timeout=self.timeout)
            return response.status_code == 200
            
        except Exception:
            return False
    
    def _play_via_local_radio(self, stream_url: str, name: str, image: str) -> bool:
        """
        Play via LOCAL_INTERNET_RADIO source.
        THIS WORKS WITHOUT ACTIVATION! This is the key solution.
        """
        try:
            resolved = self._ensure_stream_url(stream_url)
            if not resolved:
                return False
            xml = f'''<ContentItem source="LOCAL_INTERNET_RADIO" location="{escape(resolved)}" isPresetable="true">
                <itemName>{escape(name)}</itemName>
                {f'<containerArt>{escape(image)}</containerArt>' if image else ''}
            </ContentItem>'''
            
            response = requests.post(f"{self.base_url}/select", data=xml, timeout=self.timeout)
            return response.status_code == 200
            
        except Exception:
            return False
    
    def _play_via_dlna(self, stream_url: str, name: str, image: str) -> bool:
        """Play via DLNA (last resort, always works)."""
        try:
            from dlna_helper import DLNAHelper
            dlna = DLNAHelper(self.ip, self.port)
            return dlna.play_url(stream_url, name, image)
        except Exception:
            return False
    
    def store_preset(self, preset_id: int, guide_id: str, station_name: str = "Radio",
                     image_url: str = "") -> Dict[str, any]:
        """
        Store TuneIn station as preset, automatically choosing best source.
        
        Args:
            preset_id: Preset number (1-6)
            guide_id: TuneIn station ID
            station_name: Station display name
            image_url: Optional station logo
            
        Returns:
            Dict with 'success': bool, 'method': str, 'message': str
        """
        result = {
            'success': False,
            'method': None,
            'message': ''
        }
        
        if not 1 <= preset_id <= 6:
            result['message'] = f"Invalid preset number: {preset_id} (must be 1-6)"
            return result
        
        try:
            # Get stream URL
            stream_url = self._ensure_stream_url(guide_id)
            if not stream_url:
                result['message'] = "Could not resolve station stream URL"
                return result
            
            # Check which source to use
            available = self.check_available_methods()
            
            if available['tunein_active']:
                source = 'TUNEIN'
            elif available['local_radio_available']:
                source = 'LOCAL_INTERNET_RADIO'
            else:
                result['message'] = "No suitable source available for presets"
                return result
            
            # Build preset XML
            import time
            timestamp = int(time.time())
            
            xml = f'''<Preset id="{preset_id}" createdOn="{timestamp}" updatedOn="{timestamp}">
                <ContentItem source="{source}" location="{escape(stream_url)}" isPresetable="true">
                    <itemName>{escape(station_name)}</itemName>
                    {f'<containerArt>{escape(image_url)}</containerArt>' if image_url else ''}
                </ContentItem>
            </Preset>'''
            
            response = requests.post(f"{self.base_url}/select", data=xml, timeout=self.timeout)
            if response.status_code != 200:
                result['message'] = f'Failed to store preset: HTTP {response.status_code}'
                return result
            
            # Now store as preset
            preset_xml = f'''<presets><preset id="{preset_id}">{xml}</preset></presets>'''
            response = requests.post(f"{self.base_url}/storePreset", data=preset_xml, timeout=self.timeout)
            
            if response.status_code == 200:
                result['success'] = True
                result['method'] = source
                result['message'] = f'Preset stored using {source}'
            else:
                result['message'] = f'Failed to store preset: HTTP {response.status_code}'
                
        except Exception as e:
            result['message'] = f"Error: {e}"
            
        return result


def test_tunein_helper():
    """Test the TuneIn helper on a device."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python tunein_helper.py <device_ip>")
        print("Example: python tunein_helper.py 192.168.50.19")
        sys.exit(1)
    
    device_ip = sys.argv[1]
    helper = TuneInHelper(device_ip)
    
    # Check available methods
    print(f"\n🔍 Checking TuneIn playback methods on {device_ip}...")
    methods = helper.check_available_methods()
    print(f"\nAvailable methods:")
    print(f"  TUNEIN active: {methods['tunein_active']}")
    print(f"  LOCAL_INTERNET_RADIO available: {methods['local_radio_available']}")
    print(f"  Best method: {methods['best_method']}")
    
    # Test playing a station (BBC Radio 1)
    print(f"\n▶️  Testing playback (BBC Radio 1)...")
    result = helper.play_station('s296439', 'BBC Radio 1', 
                                 'http://cdn-radiotime-logos.tunein.com/s24939q.png')
    
    print(f"\nResult:")
    print(f"  Success: {result['success']}")
    print(f"  Method: {result['method']}")
    print(f"  Message: {result['message']}")
    
    # Test storing as preset
    if result['success']:
        print(f"\n💾 Testing preset storage (slot 6)...")
        preset_result = helper.store_preset(6, 's296439', 'BBC Radio 1',
                                           'http://cdn-radiotime-logos.tunein.com/s24939q.png')
        print(f"\nPreset result:")
        print(f"  Success: {preset_result['success']}")
        print(f"  Method: {preset_result['method']}")
        print(f"  Message: {preset_result['message']}")


if __name__ == '__main__':
    test_tunein_helper()
