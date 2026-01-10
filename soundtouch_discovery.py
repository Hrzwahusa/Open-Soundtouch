#!/usr/bin/env python3
"""
SoundTouch Discovery CLI
Command-line tool for discovering Bose SoundTouch devices.
Uses soundtouch_lib.py for core functionality.
"""

import argparse
import json
from pathlib import Path
from soundtouch_lib import SoundTouchDiscovery


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Discover Bose SoundTouch devices on your network"
    )
    parser.add_argument(
        "--network",
        help="Network to scan (CIDR notation, e.g., 192.168.1.0/24). Auto-detect if not specified.",
        default=None
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8090,
        help="Port to scan (default: 8090)"
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=50,
        help="Number of concurrent threads (default: 50)"
    )
    
    args = parser.parse_args()
    
    print(f"[*] Starting discovery...")
    if args.network:
        print(f"[*] Network: {args.network}")
    else:
        print(f"[*] Network: Auto-detect")
    
    # Create scanner and run
    scanner = SoundTouchDiscovery(network=args.network, port=args.port)
    devices = scanner.scan(max_threads=args.threads)
    
    # Print results
    print(f"\n[*] Found {len(devices)} SoundTouch device(s)")
    
    if devices:
        print("\n" + "="*80)
        print("DISCOVERED BOSE SOUNDTOUCH DEVICES")
        print("="*80)
        
        for i, device in enumerate(devices, 1):
            print(f"\n[Device {i}]")
            print(f"  Name:         {device['name']}")
            print(f"  Type:         {device['type']}")
            print(f"  IP:           {device['ip']}")
            print(f"  MAC:          {device['mac']}")
            print(f"  Device ID:    {device['deviceID']}")
            print(f"  API URL:      {device['url']}")
            
            if device['margeAccount']:
                print(f"  Cloud ID:     {device['margeAccount']}")
            
            if device['components']:
                print(f"  Components:")
                for comp in device['components']:
                    print(f"    - {comp['category']:20} v{comp['version']:10} (SN: {comp['serialNumber']})")
        
        print("\n" + "="*80)
        
        # Export to JSON
        output_file = Path("soundtouch_devices.json")
        with open(output_file, 'w') as f:
            json.dump(devices, f, indent=2)
        print(f"\n[*] Device list exported to: {output_file}")


if __name__ == "__main__":
    main()
