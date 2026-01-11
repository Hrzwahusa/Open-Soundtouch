#!/usr/bin/env python3
"""
Quick Network Test für SoundTouch Discovery
Hilft bei Multi-Interface Problemen
"""

import socket
import netifaces
import ipaddress

print("=" * 60)
print("   Netzwerk-Interfaces Übersicht")
print("=" * 60)
print()

# Alle Interfaces anzeigen
try:
    interfaces = netifaces.interfaces()
    print(f"[*] Gefundene Interfaces: {len(interfaces)}")
    print()
    
    for iface in interfaces:
        addrs = netifaces.ifaddresses(iface)
        
        # IPv4 Adressen
        if netifaces.AF_INET in addrs:
            for addr in addrs[netifaces.AF_INET]:
                ip = addr.get('addr')
                netmask = addr.get('netmask')
                
                if ip and ip != '127.0.0.1':
                    print(f"Interface: {iface}")
                    print(f"  IP:      {ip}")
                    print(f"  Netmask: {netmask}")
                    
                    # Berechne Netzwerk
                    try:
                        network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                        print(f"  Network: {network}")
                    except:
                        pass
                    print()
except ImportError:
    print("[!] netifaces nicht installiert")
    print("    Install: pip install netifaces")
    print()
    
    # Alternative: einfache Socket-Methode
    print("[*] Fallback: Default Route Detection")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        print(f"  Default Route IP: {local_ip}")
        
        # Berechne /24 Netzwerk
        parts = local_ip.split('.')
        network = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
        print(f"  Assumed Network:  {network}")
    except Exception as e:
        print(f"  Error: {e}")

print()
print("=" * 60)
print("   Empfohlene Netzwerke zum Scannen")
print("=" * 60)
print()

print("Wenn deine SoundTouch-Geräte NICHT gefunden werden:")
print()
print("1. In der GUI, Feld 'Netzwerk' ausfüllen:")
print("   192.168.50.0/24")
print()
print("2. Oder mehrere Netzwerke scannen:")
print("   192.168.0.0/24, 192.168.50.0/24")
print()
print("3. Oder in GUI leer lassen für Auto-Scan über:")
print("   - Auto-Detect")
print("   - 192.168.0.0/24")
print("   - 192.168.1.0/24")
print("   - 192.168.50.0/24")
print("   - 192.168.178.0/24")
print("   - 10.0.0.0/24")
print()
