"""
Bose SoundTouch Device Library
Core functionality for discovering and controlling SoundTouch devices.
Can be used in CLI, REST API, Android apps, or other frontends.
"""

import socket
import ipaddress
import threading
import requests
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from typing import List, Dict, Optional
from dlna_helper import DLNAHelper

# Suppress SSL warnings
requests.packages.urllib3.disable_warnings()


class SoundTouchDiscovery:
    """Discovers Bose SoundTouch devices on the network."""
    
    DEFAULT_PORT = 8090
    TIMEOUT = 2
    
    def __init__(self, network: Optional[str] = None, port: int = DEFAULT_PORT):
        """
        Initialize the discovery scanner.
        
        Args:
            network: Network CIDR (e.g., "192.168.1.0/24"). If None, auto-detect.
            port: Port to scan (default: 8090)
        """
        self.port = port
        self.network = network
        self.devices = []
        self.lock = threading.Lock()
        
        if network is None:
            self.network = self._get_local_network()
    
    def _get_local_network(self) -> str:
        """Auto-detect local network using socket."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Convert to /24 subnet
            parts = local_ip.split('.')
            return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
        except Exception:
            return "192.168.1.0/24"
    
    def _scan_host(self, ip: str) -> None:
        """Scan a single host for SoundTouch API."""
        try:
            url = f"http://{ip}:{self.port}/info"
            response = requests.get(url, timeout=self.TIMEOUT, verify=False)
            
            if response.status_code == 200:
                device_info = self._parse_info_response(response.text, ip)
                if device_info:
                    with self.lock:
                        self.devices.append(device_info)
        except (requests.ConnectionError, requests.Timeout, Exception):
            pass
    
    def _parse_info_response(self, xml_text: str, ip: str) -> Optional[Dict]:
        """Parse the /info XML response."""
        try:
            root = ET.fromstring(xml_text)
            
            name = root.findtext('name', 'Unknown')
            device_type = root.findtext('type', 'Unknown')
            device_id = root.get('deviceID', 'Unknown')
            marge_account = root.findtext('margeAccountUUID', '')
            
            network_info = root.find('networkInfo')
            mac_address = 'Unknown'
            if network_info is not None:
                mac_address = network_info.findtext('macAddress', 'Unknown')
            
            components = []
            for component in root.findall('components/component'):
                comp_data = {
                    'category': component.findtext('componentCategory', ''),
                    'version': component.findtext('softwareVersion', ''),
                    'serialNumber': component.findtext('serialNumber', '')
                }
                if comp_data['category']:
                    components.append(comp_data)
            
            # Verify it's a Bose SoundTouch device
            if self._is_soundtouch_device(device_type, root):
                return {
                    'name': name,
                    'type': device_type,
                    'ip': ip,
                    'mac': mac_address,
                    'deviceID': device_id,
                    'margeAccount': marge_account,
                    'components': components,
                    'url': f"http://{ip}:{self.port}"
                }
        except ET.ParseError:
            pass
        
        return None
    
    def _is_soundtouch_device(self, device_type: str, root: ET.Element) -> bool:
        """Check if device is a Bose SoundTouch device."""
        if 'soundtouch' in device_type.lower() or 'bose' in device_type.lower():
            return True
        
        if root.find('margeAccountUUID') is not None:
            return True
        
        return False
    
    def scan(self, max_threads: int = 50, timeout: int = 60) -> List[Dict]:
        """
        Scan the network for SoundTouch devices.
        
        Args:
            max_threads: Maximum number of concurrent threads
            timeout: Maximum time to wait for all threads (seconds)
            
        Returns:
            List of discovered devices
        """
        try:
            import time
            network = ipaddress.ip_network(self.network, strict=False)
            ips = list(network.hosts())
            
            print(f"Scanning {len(ips)} IPs in {self.network}...")
            
            threads = []
            start_time = time.time()
            
            for ip in ips:
                # Check timeout
                if time.time() - start_time > timeout:
                    print(f"Scan timeout reached after {timeout}s")
                    break
                
                # Wait if too many threads
                wait_count = 0
                while len(threading.enumerate()) > max_threads + 1:
                    time.sleep(0.1)
                    wait_count += 1
                    # Prevent infinite wait
                    if wait_count > 50:  # 5 seconds max wait
                        break
                
                thread = threading.Thread(target=self._scan_host, args=(str(ip),))
                thread.daemon = True
                thread.start()
                threads.append(thread)
            
            # Wait for threads with timeout
            remaining_time = timeout - (time.time() - start_time)
            for thread in threads:
                if remaining_time <= 0:
                    break
                thread.join(timeout=max(0.5, remaining_time / max(len(threads), 1)))
            
            print(f"Scan complete. Found {len(self.devices)} devices.")
            return self.devices
        
        except ValueError:
            return []


class SoundTouchController:
    """Control Bose SoundTouch devices."""
    
    # Available key commands
    KEYS = {
        'power': 'POWER',
        'play': 'PLAY',
        'pause': 'PAUSE',
        'stop': 'STOP',
        'next': 'NEXT_TRACK',
        'next_track': 'NEXT_TRACK',
        'previous': 'PREV_TRACK',
        'prev': 'PREV_TRACK',
        'prev_track': 'PREV_TRACK',
        'mute': 'MUTE',
        'volume_up': 'VOLUME_UP',
        'vol_up': 'VOLUME_UP',
        'volume_down': 'VOLUME_DOWN',
        'vol_down': 'VOLUME_DOWN',
        'preset1': 'PRESET_1',
        'preset2': 'PRESET_2',
        'preset3': 'PRESET_3',
        'preset4': 'PRESET_4',
        'preset5': 'PRESET_5',
        'preset6': 'PRESET_6',
        'thumbsup': 'THUMBS_UP',
        'thumbsdown': 'THUMBS_DOWN',
    }
    
    def __init__(self, ip: str, port: int = 8090, timeout: int = 5):
        """
        Initialize the controller.
        
        Args:
            ip: IP address of the SoundTouch device
            port: Port (default: 8090)
            timeout: HTTP timeout in seconds (default: 5)
        """
        self.ip = ip
        self.port = port
        self.base_url = f"http://{ip}:{port}"
        self.timeout = timeout
        self.dlna_port = 8091  # Bose DLNA/UPnP AVTransport port

    def is_reachable(self, timeout: int = 2) -> bool:
        """
        Quick check if device is reachable.
        
        Args:
            timeout: Timeout in seconds (default: 2)
            
        Returns:
            True if device responds to /info request
        """
        try:
            url = f"{self.base_url}/info"
            response = requests.get(url, timeout=timeout, verify=False)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_info(self) -> Optional[Dict]:
        """Get device info from /info.
        Returns parsed dict with name, type, ip, mac and components.
        """
        try:
            url = f"{self.base_url}/info"
            response = requests.get(url, timeout=self.timeout, verify=False)
            if response.status_code != 200:
                return None

            root = ET.fromstring(response.text)

            name = root.findtext('name', 'Unknown')
            device_type = root.findtext('type', 'Unknown')
            device_id = root.get('deviceID', 'Unknown')

            network_info = root.find('networkInfo')
            mac_address = 'Unknown'
            if network_info is not None:
                mac_address = network_info.findtext('macAddress', 'Unknown')

            components = []
            for component in root.findall('components/component'):
                comp_data = {
                    'category': component.findtext('componentCategory', ''),
                    'version': component.findtext('softwareVersion', ''),
                    'serialNumber': component.findtext('serialNumber', '')
                }
                if comp_data['category']:
                    components.append(comp_data)

            # verify type contains "SoundTouch" or known categories
            return {
                'name': name,
                'type': device_type,
                'ip': self.ip,
                'mac': mac_address,
                'deviceID': device_id,
                'components': components,
            }
        except Exception:
            return None
    
    def send_key(self, key: str, sender: str = "Gabbo") -> bool:
        """
        Send a key press to the device.
        
        Args:
            key: Key name (see KEYS dict for available keys)
            sender: Sender identifier (must be "Gabbo" for compatibility)
            
        Returns:
            True if successful, False otherwise
        """
        if key.lower() not in self.KEYS:
            return False
        
        key_value = self.KEYS[key.lower()]
        
        try:
            url = f"{self.base_url}/key"
            headers = {'Content-Type': 'application/xml'}
            
            # Send press and release as two separate calls (best practice)
            for state in ['press', 'release']:
                xml_body = f'<key state="{state}" sender="{sender}">{key_value}</key>'
                
                response = requests.post(
                    url,
                    data=xml_body,
                    headers=headers,
                    timeout=self.timeout,
                    verify=False
                )
                
                if response.status_code != 200:
                    return False
            
            return True
        
        except Exception:
            return False
    
    def get_nowplaying(self) -> Optional[dict]:
        """Get currently playing info."""
        try:
            url = f"{self.base_url}/now_playing"
            response = requests.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                return {
                    'source': root.get('source', 'Unknown'),
                    'sourceAccount': root.get('sourceAccount', ''),
                    'artist': root.findtext('artist', 'Unknown'),
                    'track': root.findtext('track', 'Unknown'),
                    'album': root.findtext('album', 'Unknown'),
                    'playStatus': root.get('playStatus', 'UNKNOWN'),
                }
            return None
        except Exception:
            return None
    
    def get_volume(self) -> Optional[dict]:
        """Get current volume settings."""
        try:
            url = f"{self.base_url}/volume"
            response = requests.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                return {
                    'targetvolume': int(root.findtext('targetvolume', '0')),
                    'actualvolume': int(root.findtext('actualvolume', '0')),
                    'muteenabled': root.findtext('muteenabled', 'false').lower() == 'true',
                }
            return None
        except Exception:
            return None
    
    def set_volume(self, volume: int, mute: bool = False) -> bool:
        """
        Set volume level.
        
        Args:
            volume: Volume level 0-100
            mute: Mute status (optional)
            
        Returns:
            True if successful
        """
        try:
            if not 0 <= volume <= 100:
                return False
            
            url = f"{self.base_url}/volume"
            headers = {'Content-Type': 'application/xml'}
            
            mute_str = 'true' if mute else 'false'
            xml_body = f'<volume><targetvolume>{volume}</targetvolume><muteenabled>{mute_str}</muteenabled></volume>'
            
            response = requests.post(url, data=xml_body, headers=headers, timeout=self.timeout, verify=False)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_bass_capabilities(self) -> Optional[dict]:
        """Get bass capabilities of the device."""
        try:
            url = f"{self.base_url}/bassCapabilities"
            response = requests.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                return {
                    'bassAvailable': root.findtext('bassAvailable', 'false').lower() == 'true',
                    'bassMin': int(root.findtext('bassMin', '0')),
                    'bassMax': int(root.findtext('bassMax', '0')),
                    'bassDefault': int(root.findtext('bassDefault', '0')),
                }
            return None
        except Exception:
            return None
    
    def get_bass(self) -> Optional[dict]:
        """Get current bass setting."""
        try:
            url = f"{self.base_url}/bass"
            response = requests.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                return {
                    'targetbass': int(root.findtext('targetbass', '0')),
                    'actualbass': int(root.findtext('actualbass', '0')),
                }
            return None
        except Exception:
            return None
    
    def set_bass(self, bass: int) -> bool:
        """
        Set bass level.
        
        Args:
            bass: Bass level value
            
        Returns:
            True if successful
        """
        try:
            url = f"{self.base_url}/bass"
            headers = {'Content-Type': 'application/xml'}
            xml_body = f'<bass>{bass}</bass>'
            
            response = requests.post(url, data=xml_body, headers=headers, timeout=self.timeout, verify=False)
            return response.status_code == 200
        except Exception:
            return False

    def play_url_dlna_simple(self, url: str) -> bool:
        """
        Simple DLNA playback: just send URL without metadata.
        
        Args:
            url: HTTP URL to media file (DLNA does NOT support HTTPS)
            
        Returns:
            True if successful
        """
        if not url or not url.startswith("http://"):
            return False
        
        try:
            dlna = DLNAHelper(dlna_server_ip=self.ip, device_ip=self.ip, device_dlna_port=self.dlna_port)
            return dlna.set_av_transport_uri(url) and dlna.play()
        except Exception:
            return False
    
    def play_dlna_track_from_server(self, dlna_server_ip: str, container_id: str = "1$4") -> bool:
        """
        Browse DLNA server, find first playable track, and play it on this device.
        
        Args:
            dlna_server_ip: IP of DLNA server (e.g., MiniDLNA)
            container_id: DLNA container ID to browse (default "1$4" for MiniDLNA Musik/Alle Titel)
        
        Returns:
            True if successful
        """
        try:
            dlna = DLNAHelper(dlna_server_ip=dlna_server_ip, device_ip=self.ip, device_dlna_port=self.dlna_port)
            
            # Find first playable track
            res_url, title, protocol_info = dlna.find_first_playable_track(container_id)
            if not res_url:
                print(f"[DLNA] No playable tracks found in {dlna_server_ip}:{container_id}")
                return False
            
            print(f"[DLNA] Found track: {title}")
            
            # Play it
            if not dlna.set_av_transport_uri(res_url, title=title, protocol_info=protocol_info):
                print(f"[DLNA] Failed to set transport URI")
                return False
            
            if not dlna.play():
                print(f"[DLNA] Failed to send play command")
                return False
            
            print(f"[DLNA] ✅ Playback started: {title}")
            return True
            
        except Exception as e:
            print(f"[DLNA] Exception: {e}")
            return False
    
    def dlna_stop(self) -> bool:
        """Stop DLNA playback."""
        try:
            dlna = DLNAHelper(dlna_server_ip=self.ip, device_ip=self.ip, device_dlna_port=self.dlna_port)
            return dlna.stop()
        except Exception:
            return False
    
    def get_sources(self) -> Optional[List[dict]]:
        """Get list of available sources."""
        try:
            url = f"{self.base_url}/sources"
            response = requests.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                sources = []
                
                for item in root.findall('sourceItem'):
                    sources.append({
                        'source': item.get('source', ''),
                        'sourceAccount': item.get('sourceAccount', ''),
                        'status': item.get('status', ''),
                        'name': item.text or '',
                    })
                
                return sources if sources else None
            return None
        except Exception:
            return None
    
    def select_source(self, source: str, source_account: str = '') -> bool:
        """
        Select a source/input.
        
        Args:
            source: Source name (AUX, BLUETOOTH, PRODUCT, etc.)
            source_account: Account for the source (optional)
            
        Returns:
            True if successful
        """
        try:
            url = f"{self.base_url}/select"
            headers = {'Content-Type': 'application/xml'}
            xml_body = f'<ContentItem source="{source}" sourceAccount="{source_account}"></ContentItem>'
            
            response = requests.post(url, data=xml_body, headers=headers, timeout=self.timeout, verify=False)
            return response.status_code == 200
        except Exception:
            return False
    
    def select_source_with_location(self, source: str, source_account: str, location: str, item_name: str = '', item_type: str = 'track', artist: str = '', album: str = '') -> bool:
        """
        Select a source with location (e.g., STORED_MUSIC with HTTP URL, LOCAL_INTERNET_RADIO with stream URL).
        
        Args:
            source: Source name (e.g., STORED_MUSIC, LOCAL_INTERNET_RADIO)
            source_account: Account for the source (e.g., DLNA server UUID, empty for LOCAL_INTERNET_RADIO)
            location: URL or location of the media
            item_name: Display name for the item
            item_type: Type of item (track, album, playlist, stationurl, etc.)
            artist: Artist name (for metadata)
            album: Album name (for metadata)
            
        Returns:
            True if successful
        """
        try:
            url = f"{self.base_url}/select"
            headers = {'Content-Type': 'application/xml'}
            
            # Build ContentItem with location and type
            # For stationurl and radio sources, include metadata nested inside itemName
            artist_xml = f'<artist>{escape(artist)}</artist>' if artist else ''
            album_xml = f'<album>{escape(album)}</album>' if album else ''
            track_xml = f'<track>{escape(item_name)}</track>' if item_name else ''
            
            # Metadata goes INSIDE itemName tag
            itemName_content = f'{artist_xml}{album_xml}{track_xml}'
            item_name_xml = f'<itemName>{itemName_content}</itemName>' if itemName_content else ''
            
            # Build source account attribute only if not empty
            source_account_attr = f' sourceAccount="{escape(source_account)}"' if source_account else ''
            
            xml_body = (
                f'<ContentItem source="{escape(source)}" '
                f'type="{escape(item_type)}" '
                f'{source_account_attr} '
                f'location="{escape(location)}">'
                f'{item_name_xml}'
                f'</ContentItem>'
            )
            
            response = requests.post(url, data=xml_body, headers=headers, timeout=self.timeout, verify=False)
            if response.status_code == 200:
                # Give the device a moment to process the selection
                import time
                time.sleep(1.0)
                # Send PLAY key twice to ensure playback starts (some devices need this)
                self.send_key('play')
                time.sleep(0.3)
                self.send_key('play')
                return True
            return False
        except Exception:
            return False
    
    def play_url_dlna(self, url: str, artist: str = "Unknown Artist", album: str = "Unknown Album", 
                      track: str = "Unknown Track", dlna_server_ip: str = None) -> bool:
        """
        Play media from URL via DLNA/UPNP (port 8091).
        Uses DLNAHelper to properly handle SOAP requests with metadata.
        
        Args:
            url: HTTP URL to media file (DLNA does NOT support HTTPS!)
            artist: Artist name for metadata
            album: Album name for metadata
            track: Track name for metadata
            dlna_server_ip: DLNA server IP (optional, for future extensions)
            
        Returns:
            True if successful
            
        Note: This sends a SOAP request to the DLNA AVTransport service,
              which is the correct way to play UPNP/DLNA content.
        """
        if not url or not url.startswith("http://"):
            return False
        
        try:
            # Detect MIME type from URL extension
            mime = "audio/mpeg"
            lowered = url.lower()
            if lowered.endswith(".flac"):
                mime = "audio/flac"
            elif lowered.endswith(".wav"):
                mime = "audio/wav"
            elif lowered.endswith(".m4a") or lowered.endswith(".mp4"):
                mime = "audio/mp4"
            elif lowered.endswith(".aac"):
                mime = "audio/aac"
            elif lowered.endswith(".ogg") or lowered.endswith(".oga"):
                mime = "audio/ogg"
            
            # Build protocol info with DLNA extensions for MP3
            dlna_flags = "DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01500000000000000000000000000000"
            protocol_info = f"http-get:*:{mime}:*"
            if mime == "audio/mpeg":
                pn = "DLNA.ORG_PN=MP3"
                protocol_info = f"http-get:*:{mime};{pn};{dlna_flags}"
            
            # Use DLNAHelper to send SOAP commands
            dlna = DLNAHelper(dlna_server_ip=self.ip, device_ip=self.ip, device_dlna_port=self.dlna_port)
            
            # Set URI with metadata
            if not dlna.set_av_transport_uri(url, title=track, protocol_info=protocol_info):
                return False
            
            # Send Play
            if not dlna.play():
                return False
            
            print(f"✅ DLNA playback started: {track} by {artist}")
            return True
                
        except Exception as e:
            print(f"❌ DLNA exception: {e}")
            return False
    
    def get_presets(self) -> Optional[List[dict]]:
        """Get list of presets."""
        try:
            url = f"{self.base_url}/presets"
            response = requests.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                presets = []
                
                for preset in root.findall('preset'):
                    preset_id = preset.get('id', '')
                    item = preset.find('ContentItem')
                    if item is not None:
                        presets.append({
                            'id': preset_id,
                            'source': item.get('source', ''),
                            'sourceAccount': item.get('sourceAccount', ''),
                            'itemName': item.findtext('itemName', ''),
                        })
                
                return presets if presets else None
            return None
        except Exception:
            return None
    
    def get_capabilities(self) -> Optional[List[dict]]:
        """Get device capabilities."""
        try:
            url = f"{self.base_url}/capabilities"
            response = requests.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                capabilities = []
                
                for cap in root.findall('capability'):
                    capabilities.append({
                        'name': cap.get('name', ''),
                        'url': cap.get('url', ''),
                        'info': cap.get('info', ''),
                    })
                
                return capabilities if capabilities else None
            return None
        except Exception:
            return None
    
    def get_audio_dsp_controls(self) -> Optional[dict]:
        """Get audio DSP settings (audio mode, video sync delay, etc.)."""
        try:
            url = f"{self.base_url}/audiodspcontrols"
            response = requests.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                return {
                    'audiomode': root.get('audiomode', ''),
                    'videosyncaudiodelay': int(root.get('videosyncaudiodelay', '0')),
                    'supportedaudiomodes': root.get('supportedaudiomodes', '').split('|'),
                }
            return None
        except Exception:
            return None
    
    def set_audio_dsp_controls(self, audiomode: str = None, videosyncaudiodelay: int = None) -> bool:
        """
        Set audio DSP controls.
        
        Args:
            audiomode: Audio mode (AUDIO_MODE_DIRECT, AUDIO_MODE_NORMAL, AUDIO_MODE_DIALOG, AUDIO_MODE_NIGHT)
            videosyncaudiodelay: Video sync audio delay
            
        Returns:
            True if successful
        """
        try:
            url = f"{self.base_url}/audiodspcontrols"
            headers = {'Content-Type': 'application/xml'}
            
            attrs = []
            if audiomode:
                attrs.append(f'audiomode="{audiomode}"')
            if videosyncaudiodelay is not None:
                attrs.append(f'videosyncaudiodelay="{videosyncaudiodelay}"')
            
            attrs_str = ' '.join(attrs)
            xml_body = f'<audiodspcontrols {attrs_str} />'
            
            response = requests.post(url, data=xml_body, headers=headers, timeout=self.timeout, verify=False)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_tone_controls(self) -> Optional[dict]:
        """Get bass and treble settings."""
        try:
            url = f"{self.base_url}/audioproducttonecontrols"
            response = requests.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                bass_elem = root.find('bass')
                treble_elem = root.find('treble')
                
                return {
                    'bass': {
                        'value': int(bass_elem.get('value', '0')) if bass_elem is not None else 0,
                        'minValue': int(bass_elem.get('minValue', '0')) if bass_elem is not None else 0,
                        'maxValue': int(bass_elem.get('maxValue', '0')) if bass_elem is not None else 0,
                        'step': int(bass_elem.get('step', '1')) if bass_elem is not None else 1,
                    },
                    'treble': {
                        'value': int(treble_elem.get('value', '0')) if treble_elem is not None else 0,
                        'minValue': int(treble_elem.get('minValue', '0')) if treble_elem is not None else 0,
                        'maxValue': int(treble_elem.get('maxValue', '0')) if treble_elem is not None else 0,
                        'step': int(treble_elem.get('step', '1')) if treble_elem is not None else 1,
                    },
                }
            return None
        except Exception:
            return None
    
    def set_tone_controls(self, bass: int = None, treble: int = None) -> bool:
        """
        Set bass and treble.
        
        Args:
            bass: Bass value
            treble: Treble value
            
        Returns:
            True if successful
        """
        try:
            url = f"{self.base_url}/audioproducttonecontrols"
            headers = {'Content-Type': 'application/xml'}
            
            parts = []
            if bass is not None:
                parts.append(f'<bass value="{bass}" />')
            if treble is not None:
                parts.append(f'<treble value="{treble}" />')
            
            xml_body = f'<audioproducttonecontrols>{"".join(parts)}</audioproducttonecontrols>'
            
            response = requests.post(url, data=xml_body, headers=headers, timeout=self.timeout, verify=False)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_level_controls(self) -> Optional[dict]:
        """Get front-center and rear-surround speaker levels."""
        try:
            url = f"{self.base_url}/audioproductlevelcontrols"
            response = requests.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                front_elem = root.find('frontCenterSpeakerLevel')
                rear_elem = root.find('rearSurroundSpeakersLevel')
                
                return {
                    'frontCenterSpeakerLevel': {
                        'value': int(front_elem.get('value', '0')) if front_elem is not None else 0,
                        'minValue': int(front_elem.get('minValue', '0')) if front_elem is not None else 0,
                        'maxValue': int(front_elem.get('maxValue', '0')) if front_elem is not None else 0,
                        'step': int(front_elem.get('step', '1')) if front_elem is not None else 1,
                    },
                    'rearSurroundSpeakersLevel': {
                        'value': int(rear_elem.get('value', '0')) if rear_elem is not None else 0,
                        'minValue': int(rear_elem.get('minValue', '0')) if rear_elem is not None else 0,
                        'maxValue': int(rear_elem.get('maxValue', '0')) if rear_elem is not None else 0,
                        'step': int(rear_elem.get('step', '1')) if rear_elem is not None else 1,
                    },
                }
            return None
        except Exception:
            return None
    
    def set_level_controls(self, front: int = None, rear: int = None) -> bool:
        """
        Set speaker levels.
        
        Args:
            front: Front center speaker level
            rear: Rear surround speaker level
            
        Returns:
            True if successful
        """
        try:
            url = f"{self.base_url}/audioproductlevelcontrols"
            headers = {'Content-Type': 'application/xml'}
            
            parts = []
            if front is not None:
                parts.append(f'<frontCenterSpeakerLevel value="{front}" />')
            if rear is not None:
                parts.append(f'<rearSurroundSpeakersLevel value="{rear}" />')
            
            xml_body = f'<audioproductlevelcontrols>{"".join(parts)}</audioproductlevelcontrols>'
            
            response = requests.post(url, data=xml_body, headers=headers, timeout=self.timeout, verify=False)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_zone(self) -> Optional[dict]:
        """Get current multi-room zone configuration."""
        try:
            url = f"{self.base_url}/getZone"
            response = requests.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                members = []
                
                for member in root.findall('member'):
                    members.append({
                        'ipaddress': member.get('ipaddress', ''),
                        'macaddr': member.text or '',
                    })
                
                return {
                    'master': root.get('master', ''),
                    'members': members,
                }
            return None
        except Exception:
            return None
    
    def set_zone(self, master_mac: str, members: List[tuple]) -> bool:
        """
        Create a multi-room zone.
        
        Args:
            master_mac: MAC address of master device
            members: List of (ip, mac) tuples for zone members
            
        Returns:
            True if successful
        """
        try:
            url = f"{self.base_url}/setZone"
            headers = {'Content-Type': 'application/xml'}
            
            members_xml = ''.join([f'<member ipaddress="{ip}">{mac}</member>' for ip, mac in members])
            xml_body = f'<zone master="{master_mac}" senderIPAddress="{self.ip}">{members_xml}</zone>'
            
            response = requests.post(url, data=xml_body, headers=headers, timeout=self.timeout, verify=False)
            return response.status_code == 200
        except Exception:
            return False
    
    def add_zone_slave(self, master_mac: str, slave_ip: str, slave_mac: str) -> bool:
        """
        Add a slave device to a zone.
        
        Args:
            master_mac: MAC address of master device
            slave_ip: IP address of slave device
            slave_mac: MAC address of slave device
            
        Returns:
            True if successful
        """
        try:
            url = f"{self.base_url}/addZoneSlave"
            headers = {'Content-Type': 'application/xml'}
            xml_body = f'<zone master="{master_mac}"><member ipaddress="{slave_ip}">{slave_mac}</member></zone>'
            
            response = requests.post(url, data=xml_body, headers=headers, timeout=self.timeout, verify=False)
            return response.status_code == 200
        except Exception:
            return False
    
    def remove_zone_slave(self, master_mac: str, slave_mac: str) -> bool:
        """
        Remove a slave device from a zone.
        
        Args:
            master_mac: MAC address of master device
            slave_mac: MAC address of slave device to remove
            
        Returns:
            True if successful
        """
        try:
            url = f"{self.base_url}/removeZoneSlave"
            headers = {'Content-Type': 'application/xml'}
            xml_body = f'<zone master="{master_mac}"><member>{slave_mac}</member></zone>'
            
            response = requests.post(url, data=xml_body, headers=headers, timeout=self.timeout, verify=False)
            return response.status_code == 200
        except Exception:
            return False
    
    def set_device_name(self, name: str) -> bool:
        """
        Set the device name.
        
        Args:
            name: New device name
            
        Returns:
            True if successful
        """
        try:
            url = f"{self.base_url}/name"
            headers = {'Content-Type': 'application/xml'}
            xml_body = f'<name>{name}</name>'
            
            response = requests.post(url, data=xml_body, headers=headers, timeout=self.timeout, verify=False)
            return response.status_code == 200
        except Exception:
            return False

    def set_setup_state(self, state: str, timeout_ms: Optional[int] = None) -> bool:
        """Post a setup state change (e.g. SETUP_WIFI, SETUP_WIFI_LEAVE)."""
        try:
            attrs = [f'state="{escape(state)}"']
            if timeout_ms is not None:
                attrs.append(f'timeout="{timeout_ms}"')
            xml_body = f"<setupState {' '.join(attrs)} />"

            url = f"{self.base_url}/setup"
            headers = {'Content-Type': 'application/xml'}
            response = requests.post(url, data=xml_body, headers=headers, timeout=self.timeout, verify=False)
            return response.status_code == 200
        except Exception:
            return False

    def add_wireless_profile(self, ssid: str, password: str, security_type: str = "wpa_or_wpa2", timeout_secs: int = 30) -> bool:
        """Add a WiFi profile so the speaker can join the network. Automatically exits setup mode and power-cycles."""
        try:
            if timeout_secs < 5 or timeout_secs > 60:
                timeout_secs = 30

            xml_body = (
                f'<AddWirelessProfile timeout="{timeout_secs}">' \
                f'<profile ssid="{escape(ssid)}" password="{escape(password)}" securityType="{escape(security_type)}" />' \
                f'</AddWirelessProfile>'
            )

            url = f"{self.base_url}/addWirelessProfile"
            headers = {'Content-Type': 'application/xml'}
            response = requests.post(url, data=xml_body, headers=headers, timeout=self.timeout, verify=False)
            
            if response.status_code != 200:
                return False
            
            # Give speaker time to process
            import time
            time.sleep(2)
            
            # Exit setup mode
            self.set_setup_state("SETUP_LEAVE")
            
            # Power cycle (press + release)
            time.sleep(1)
            self.send_key("power", sender="Gabbo")
            
            return True
        except Exception:
            return False

    def get_wireless_profile(self) -> Optional[dict]:
        """Return the active wireless profile (SSID)."""
        try:
            url = f"{self.base_url}/getActiveWirelessProfile"
            response = requests.get(url, timeout=self.timeout, verify=False)

            if response.status_code != 200:
                return None

            root = ET.fromstring(response.text)
            ssid = root.findtext('ssid', '')
            if not ssid:
                ssid = root.get('ssid', '')

            return {
                'ssid': ssid,
                'raw': response.text
            }
        except Exception:
            return None

    def perform_wireless_site_survey(self) -> Optional[dict]:
        """Scan for visible WiFi networks and return parsed results when possible."""
        try:
            url = f"{self.base_url}/performWirelessSiteSurvey"
            response = requests.get(url, timeout=self.timeout, verify=False)

            if response.status_code != 200:
                return None

            root = ET.fromstring(response.text)
            networks = []
            for network in root.findall('.//wirelessNetwork'):
                networks.append({
                    'ssid': network.get('ssid') or network.findtext('ssid', ''),
                    'signal': network.get('signalStrength') or network.findtext('signalStrength', ''),
                    'security': network.get('securityType') or network.findtext('securityType', '')
                })

            return {
                'networks': networks,
                'raw': response.text
            }
        except Exception:
            return None
    
    @staticmethod
    def get_available_keys() -> List[str]:
        """Get list of available keys."""
        return sorted(SoundTouchController.KEYS.keys())


class SoundTouchGroupManager:
    """Helper class for managing multi-room groups."""
    
    def __init__(self, devices: List[dict]):
        """
        Initialize group manager.
        
        Args:
            devices: List of device dictionaries with 'ip', 'mac', 'name' keys
        """
        self.devices = devices
        self.groups = []
        
    def create_group(self, master_device: dict, slave_devices: List[dict], group_name: str = "") -> bool:
        """
        Create a new multi-room group.
        
        Args:
            master_device: Device dict to be the master
            slave_devices: List of device dicts to be slaves
            group_name: Optional name for the group
            
        Returns:
            True if successful
        """
        try:
            master_controller = SoundTouchController(master_device['ip'])
            master_mac = master_device['mac']
            
            # Prepare members list
            members = [(dev['ip'], dev['mac']) for dev in slave_devices]
            
            # Create zone
            success = master_controller.set_zone(master_mac, members)
            
            if success:
                group = {
                    'name': group_name or f"Group {master_device['name']}",
                    'master': master_device,
                    'slaves': slave_devices,
                    'all_devices': [master_device] + slave_devices
                }
                self.groups.append(group)
                
            return success
        except Exception as e:
            print(f"Error creating group: {e}")
            return False
    
    def add_to_group(self, group_index: int, device: dict) -> bool:
        """
        Add a device to existing group.
        
        Args:
            group_index: Index of group in self.groups
            device: Device dict to add
            
        Returns:
            True if successful
        """
        try:
            if group_index >= len(self.groups):
                return False
                
            group = self.groups[group_index]
            master = group['master']
            
            controller = SoundTouchController(master['ip'])
            success = controller.add_zone_slave(master['mac'], device['ip'], device['mac'])
            
            if success:
                group['slaves'].append(device)
                group['all_devices'].append(device)
                
            return success
        except Exception as e:
            print(f"Error adding to group: {e}")
            return False
    
    def remove_from_group(self, group_index: int, device: dict) -> bool:
        """
        Remove a device from group.
        
        Args:
            group_index: Index of group in self.groups
            device: Device dict to remove
            
        Returns:
            True if successful
        """
        try:
            if group_index >= len(self.groups):
                return False
                
            group = self.groups[group_index]
            master = group['master']
            
            controller = SoundTouchController(master['ip'])
            success = controller.remove_zone_slave(master['mac'], device['mac'])
            
            if success:
                group['slaves'] = [d for d in group['slaves'] if d['mac'] != device['mac']]
                group['all_devices'] = [master] + group['slaves']
                
            return success
        except Exception as e:
            print(f"Error removing from group: {e}")
            return False
    
    def get_groups(self) -> List[dict]:
        """Get list of all groups."""
        return self.groups
    
    def send_command_to_group(self, group_index: int, key: str) -> bool:
        """
        Send command to all devices in group.
        
        Args:
            group_index: Index of group
            key: Key command to send
            
        Returns:
            True if all successful
        """
        try:
            if group_index >= len(self.groups):
                return False
                
            group = self.groups[group_index]
            success = True
            
            # Send to master first
            master_controller = SoundTouchController(group['master']['ip'])
            if not master_controller.send_key(key):
                success = False
                
            return success
        except Exception:
            return False
    
    def set_group_volume(self, group_index: int, volume: int) -> bool:
        """
        Set volume for all devices in group.
        
        Args:
            group_index: Index of group
            volume: Volume level 0-100
            
        Returns:
            True if all successful
        """
        try:
            if group_index >= len(self.groups):
                return False
                
            group = self.groups[group_index]
            success = True
            
            for device in group['all_devices']:
                controller = SoundTouchController(device['ip'])
                if not controller.set_volume(volume):
                    success = False
                    
            return success
        except Exception:
            return False
