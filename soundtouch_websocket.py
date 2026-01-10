"""
SoundTouch WebSocket client for asynchronous notifications.
Receives real-time updates from SoundTouch devices over WebSocket.
"""

import websocket
import json
import threading
import xml.etree.ElementTree as ET
from typing import Callable, Optional, Dict, Any
from queue import Queue
import time


class SoundTouchWebSocket:
    """WebSocket client for SoundTouch device notifications."""
    
    def __init__(self, device_ip: str, port: int = 8080):
        """
        Initialize WebSocket client.
        
        Args:
            device_ip: IP address of the SoundTouch device
            port: WebSocket port (default: 8080)
        """
        self.device_ip = device_ip
        self.port = port
        # WebSocket URL: ws://IP:PORT (no path)
        self.ws_url = f"ws://{device_ip}:{port}"
        self.ws = None
        self.connected = False
        self.running = False
        
        # Callback functions for different events
        self.callbacks: Dict[str, Callable] = {}
        
        # Queue for events
        self.event_queue = Queue()
        
        # Thread for WebSocket
        self.ws_thread = None
    
    def on_message(self, ws, message):
        """Handle incoming WebSocket message."""
        try:
            # Parse XML notification
            root = ET.fromstring(message)
            
            # Determine notification type and extract data
            notification = self._parse_notification(root)
            
            if notification:
                # Add to queue
                self.event_queue.put(notification)
                
                # Call appropriate callback
                event_type = notification.get('type')
                if event_type in self.callbacks:
                    self.callbacks[event_type](notification)
        
        except Exception as e:
            print(f"ERROR: Error parsing WebSocket message: {e}")
    
    def on_error(self, ws, error):
        """Handle WebSocket error."""
        print(f"WebSocket error: {error}")
        self.connected = False
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        print(f"WebSocket closed: {close_msg}")
        self.connected = False
    
    def on_open(self, ws):
        """Handle WebSocket open."""
        print(f"WebSocket connected to {self.device_ip}:{self.port}")
        self.connected = True
    
    def _parse_notification(self, root: ET.Element) -> Optional[Dict[str, Any]]:
        """Parse XML notification into a dict."""
        notification_type = root.tag
        
        # Handle SDK info message (sent on connection)
        if notification_type == 'SoundTouchSdkInfo':
            return {
                'type': 'SoundTouchSdkInfo',
                'serverVersion': root.get('serverVersion', ''),
                'serverBuild': root.get('serverBuild', ''),
            }
        
        # Handle updates wrapper (contains child notification nodes)
        if notification_type == 'updates':
            # Process child nodes - could have multiple updates in one message
            results = []
            device_id = root.get('deviceID', '')
            
            for child in root:
                child_notification = self._parse_notification(child)
                if child_notification:
                    # Add deviceID to each update
                    child_notification['deviceID'] = device_id
                    results.append(child_notification)
            
            # Return the updates
            if len(results) == 1:
                return results[0]
            elif len(results) > 1:
                return {'type': 'multipleUpdates', 'updates': results, 'deviceID': device_id}
            return None
        
        # Handle specific update types that come inside <updates> wrapper
        if notification_type == 'connectionStateUpdated':
            return {
                'type': 'connectionStateUpdated',
                'state': root.get('state', ''),
                'up': root.get('up', 'false').lower() == 'true',
                'signal': root.get('signal', ''),
            }
        
        # User activity (button presses, volume changes from device)
        if notification_type == 'userActivityUpdate':
            return {
                'type': 'userActivityUpdate',
            }
        
        if notification_type == 'nowPlayingUpdated':
            return self._parse_now_playing(root)
        elif notification_type == 'volumeUpdated':
            return self._parse_volume(root)
        elif notification_type == 'bassUpdated':
            return self._parse_bass(root)
        elif notification_type == 'connectionStatusChanged':
            return self._parse_connection_status(root)
        elif notification_type == 'zoneUpdated':
            return self._parse_zone(root)
        elif notification_type == 'presetsUpdated':
            return self._parse_presets(root)
        
        return None
    
    def _parse_now_playing(self, root: ET.Element) -> Dict[str, Any]:
        """Parse nowPlayingUpdated notification."""
        # Data can be nested: <nowPlayingUpdated><nowPlaying>...</nowPlaying></nowPlayingUpdated>
        now_playing_elem = root.find('nowPlaying')
        if now_playing_elem is None:
            now_playing_elem = root
        
        return {
            'type': 'nowPlayingUpdated',
            'source': now_playing_elem.get('source', now_playing_elem.findtext('source', '')),
            'track': now_playing_elem.findtext('track', ''),
            'artist': now_playing_elem.findtext('artist', ''),
            'album': now_playing_elem.findtext('album', ''),
            'station': now_playing_elem.findtext('station', ''),
        }
    
    def _parse_volume(self, root: ET.Element) -> Dict[str, Any]:
        """Parse volumeUpdated notification."""
        # Volume data can be nested: <volumeUpdated><volume>...</volume></volumeUpdated>
        # Or direct: <volumeUpdated>...</volumeUpdated>
        volume_elem = root.find('volume')
        if volume_elem is None:
            volume_elem = root
        
        return {
            'type': 'volumeUpdated',
            'actualvolume': int(volume_elem.findtext('actualvolume', '0')),
            'targetvolume': int(volume_elem.findtext('targetvolume', '0')),
            'muteenabled': volume_elem.findtext('muteenabled', 'false').lower() == 'true',
        }
    
    def _parse_bass(self, root: ET.Element) -> Dict[str, Any]:
        """Parse bassUpdated notification."""
        # Bass data can be nested: <bassUpdated><bass>...</bass></bassUpdated>
        bass_elem = root.find('bass')
        if bass_elem is None:
            bass_elem = root
        
        return {
            'type': 'bassUpdated',
            'actualbass': int(bass_elem.findtext('actualbass', '0')),
            'targetbass': int(bass_elem.findtext('targetbass', '0')),
        }
    
    def _parse_connection_status(self, root: ET.Element) -> Dict[str, Any]:
        """Parse connectionStatusChanged notification."""
        # Check for nested element first
        conn_elem = root.find('connectionStatus')
        if conn_elem is not None:
            status_text = conn_elem.text or ''
        else:
            status_text = root.findtext('connectionStatus', '')
        
        return {
            'type': 'connectionStatusChanged',
            'status': status_text,
        }
    
    def _parse_zone(self, root: ET.Element) -> Dict[str, Any]:
        """Parse zoneUpdated notification."""
        # Data can be nested: <zoneUpdated><zone>...</zone></zoneUpdated>
        zone_elem = root.find('zone')
        if zone_elem is None:
            zone_elem = root
        
        return {
            'type': 'zoneUpdated',
            'master': zone_elem.findtext('master', zone_elem.get('master', '')),
            'members': len(zone_elem.findall('member')),
        }
    
    def _parse_presets(self, root: ET.Element) -> Dict[str, Any]:
        """Parse presetsUpdated notification."""
        return {
            'type': 'presetsUpdated',
            'preset_count': len(root.findall('preset')),
        }
    
    def connect(self):
        """Connect to WebSocket."""
        if self.connected:
            return True
        
        try:
            websocket.enableTrace(False)
            print(f"DEBUG: Connecting to {self.ws_url} with subprotocol 'gabbo'")
            
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                subprotocols=["gabbo"]  # Required protocol per Bose docs
            )
            
            # Run in background thread
            self.ws_thread = threading.Thread(target=self._run_ws, daemon=True)
            self.ws_thread.start()
            
            # Wait for connection (5 second timeout)
            timeout = 5
            for i in range(timeout * 10):
                if self.connected:
                    self.running = True
                    print(f"DEBUG: WebSocket connected successfully!")
                    return True
                time.sleep(0.1)
            
            print(f"DEBUG: WebSocket connection timeout after {timeout} seconds")
            if self.ws:
                self.ws.close()
            return False
        
        except Exception as e:
            print(f"DEBUG: WebSocket exception: {type(e).__name__}: {e}")
            return False
    
    def _run_ws(self):
        """Run WebSocket (handles reconnection)."""
        try:
            # Per Bose API: use keepalive pings to maintain connection
            self.ws.run_forever(
                ping_interval=30,  # Send ping every 30 seconds
                ping_timeout=10    # Wait 10 seconds for pong response
            )
        except Exception as e:
            print(f"DEBUG: WebSocket run_forever exception: {e}")
    
    def disconnect(self):
        """Disconnect from WebSocket."""
        self.running = False
        if self.ws:
            self.ws.close()
        self.connected = False
    
    def add_callback(self, event_type: str, callback: Callable):
        """
        Add callback for specific event type.
        
        Args:
            event_type: Type of event ('volumeUpdated', 'nowPlayingUpdated', etc.)
            callback: Function to call with notification dict
        """
        self.callbacks[event_type] = callback
    
    def remove_callback(self, event_type: str):
        """Remove callback for specific event type."""
        if event_type in self.callbacks:
            del self.callbacks[event_type]
    
    def get_next_event(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Get next event from queue (blocking).
        
        Args:
            timeout: Timeout in seconds (None = block forever)
            
        Returns:
            Notification dict or None if timeout
        """
        try:
            return self.event_queue.get(timeout=timeout)
        except:
            return None
    
    def get_pending_events(self) -> list:
        """Get all pending events from queue (non-blocking)."""
        events = []
        while not self.event_queue.empty():
            try:
                events.append(self.event_queue.get_nowait())
            except:
                break
        return events


class SoundTouchNotificationManager:
    """Manages WebSocket connections for multiple devices."""
    
    def __init__(self):
        """Initialize notification manager."""
        self.devices: Dict[str, SoundTouchWebSocket] = {}
    
    def add_device(self, device_ip: str, device_name: str = None) -> SoundTouchWebSocket:
        """
        Add a device and connect its WebSocket.
        
        Args:
            device_ip: IP address of device
            device_name: Optional name for the device
            
        Returns:
            SoundTouchWebSocket instance
        """
        if device_ip in self.devices:
            return self.devices[device_ip]
        
        ws = SoundTouchWebSocket(device_ip)
        if ws.connect():
            self.devices[device_ip] = ws
            print(f"✓ Connected to {device_name or device_ip}")
            return ws
        else:
            print(f"✗ Failed to connect to {device_name or device_ip}")
            return None
    
    def remove_device(self, device_ip: str):
        """Remove a device and disconnect its WebSocket."""
        if device_ip in self.devices:
            self.devices[device_ip].disconnect()
            del self.devices[device_ip]
    
    def get_device(self, device_ip: str) -> Optional[SoundTouchWebSocket]:
        """Get WebSocket for a specific device."""
        return self.devices.get(device_ip)
    
    def disconnect_all(self):
        """Disconnect all devices."""
        for ws in self.devices.values():
            ws.disconnect()
        self.devices.clear()
    
    def get_all_events(self) -> Dict[str, list]:
        """Get all pending events from all devices."""
        all_events = {}
        for ip, ws in self.devices.items():
            events = ws.get_pending_events()
            if events:
                all_events[ip] = events
        return all_events
