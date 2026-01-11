#!/usr/bin/env python3
"""
SoundTouch Controller CLI
Command-line tool for controlling Bose SoundTouch devices.
Uses soundtouch_lib.py for core functionality.
"""

import argparse
from soundtouch_lib import SoundTouchController


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
        print("\n[*] Available Keys:")
        print("="*40)
        for key in SoundTouchController.get_available_keys():
            print(f"  {key}")
        print("="*40)
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
        else:
            print("[!] Could not get now playing info")
        return
    
    if args.key:
        success = controller.send_key(args.key)
        if success:
            print(f"[+] Key '{args.key}' sent successfully")
        else:
            print(f"[!] Failed to send key '{args.key}'")
    else:
        print("[!] Please specify a key with --key or use --list to see available keys")
        print("[*] Example: python soundtouch_controller.py 192.168.50.156 --key play")


if __name__ == "__main__":
    main()
