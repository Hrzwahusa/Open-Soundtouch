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
    
    def scan(self, max_threads: int = 50) -> List[Dict]:
        """
        Scan the network for SoundTouch devices.
        
        Args:
            max_threads: Maximum number of concurrent threads
            
        Returns:
            List of discovered devices
        """
        try:
            network = ipaddress.ip_network(self.network, strict=False)
            ips = list(network.hosts())
            
            threads = []
            for ip in ips:
                while len(threading.enumerate()) > max_threads + 1:
                    pass
                
                thread = threading.Thread(target=self._scan_host, args=(str(ip),))
                thread.daemon = True
                thread.start()
                threads.append(thread)
            
            for thread in threads:
                thread.join()
            
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
    
    def __init__(self, ip: str, port: int = 8090):
        """
        Initialize the controller.
        
        Args:
            ip: IP address of the SoundTouch device
            port: Port (default: 8090)
        """
        self.ip = ip
        self.port = port
        self.base_url = f"http://{ip}:{port}"
        self.timeout = 5
    
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
