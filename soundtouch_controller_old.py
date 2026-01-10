#!/usr/bin/env python3
"""
Bose SoundTouch Keypress Controller
Send key presses and control commands to SoundTouch devices.
"""

import requests
import xml.etree.ElementTree as ET
from typing import Optional, List
import argparse

# Suppress SSL warnings
requests.packages.urllib3.disable_warnings()


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
            sender: Sender identifier (default: "Gabbo" - must be this value)
            
        Returns:
            True if successful
        """
        if key.lower() not in self.KEYS:
            print(f"[!] Unknown key: {key}")
            print(f"[*] Available keys: {', '.join(self.KEYS.keys())}")
            return False
        
        key_value = self.KEYS[key.lower()]
        
        try:
            url = f"{self.base_url}/key"
            headers = {'Content-Type': 'application/xml'}
            
            # Send press and release as two separate calls (best practice)
            for state in ['press', 'release']:
                xml_body = f'<key state="{state}" sender="{sender}">{key_value}</key>'
                
                print(f"[*] Sending {state}: {xml_body}")
                
                response = requests.post(
                    url,
                    data=xml_body,
                    headers=headers,
                    timeout=self.timeout,
                    verify=False
                )
                
                if response.status_code != 200:
                    print(f"[!] Failed to send {state}. Status: {response.status_code}")
                    print(f"[!] Response: {response.text}")
                    return False
            
            print(f"[+] Key '{key}' sent successfully to {self.ip}")
            return True
        
        except Exception as e:
            print(f"[!] Error sending key: {e}")
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
        except Exception as e:
            print(f"[!] Error getting now playing: {e}")
            return None
    
    def list_keys(self) -> None:
        """List all available keys."""
        print("\n[*] Available Keys:")
        print("="*40)
        for key in sorted(self.KEYS.keys()):
            print(f"  {key:20} -> {self.KEYS[key]}")
        print("="*40)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Send key presses to Bose SoundTouch devices"
    )
    parser.add_argument(
        "ip",
        help="IP address of the SoundTouch device (e.g., 192.168.50.156)"
    )
    parser.add_argument(
        "--key",
        "-k",
        help="Key to send (see --list for available keys)",
        default=None
    )
    parser.add_argument(
        "--sender",
        "-s",
        help="Sender identifier (default: 'Gabbo')",
        default="Gabbo"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available keys"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Get currently playing info"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8090,
        help="Port (default: 8090)"
    )
    
    args = parser.parse_args()
    
    controller = SoundTouchController(args.ip, args.port)
    
    if args.list:
        controller.list_keys()
        return
    
    if args.status:
        info = controller.get_nowplaying()
        if info:
            print("\n[*] Now Playing:")
            print(f"  Source:  {info['source']}")
            if info['sourceAccount']:
                print(f"  Account: {info['sourceAccount']}")
            print(f"  Artist:  {info['artist']}")
            print(f"  Track:   {info['track']}")
            print(f"  Album:   {info['album']}")
        return
    
    if args.key:
        controller.send_key(args.key, sender=args.sender)
    else:
        print("[!] Please specify a key with --key or use --list to see available keys")
        print("[*] Example: python soundtouch_controller.py 192.168.50.156 --key play")


if __name__ == "__main__":
    main()
