#!/usr/bin/env python3
"""
Analysiert SSDP Discovery und folgende Requests beim DLNA Server Löschen
"""

import socket
import time

def send_ssdp_discovery(target_ip='239.255.255.250', target_port=1900):
    """Sendet SSDP M-SEARCH wie die Bose App."""
    
    # M-SEARCH Request (wie Bose App)
    ssdp_request = (
        'M-SEARCH * HTTP/1.1\r\n'
        'HOST: 239.255.255.250:1900\r\n'
        'MAN: "ssdp:discover"\r\n'
        'MX: 3\r\n'
        'ST: urn:schemas-upnp-org:device:MediaServer:1\r\n'
        '\r\n'
    )
    
    print("🔍 Sende SSDP M-SEARCH (wie Bose App)...")
    print("=" * 80)
    print(ssdp_request)
    print("=" * 80)
    
    # Socket erstellen
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(5)
    
    # Senden
    sock.sendto(ssdp_request.encode(), (target_ip, target_port))
    
    print("\n📥 Warte auf Antworten...\n")
    
    responses = []
    start_time = time.time()
    
    try:
        while time.time() - start_time < 5:
            try:
                data, addr = sock.recvfrom(2048)
                response = data.decode('utf-8', errors='ignore')
                
                print(f"✅ Antwort von {addr[0]}:{addr[1]}")
                print("-" * 80)
                print(response)
                print("-" * 80)
                print()
                
                responses.append({
                    'addr': addr,
                    'data': response
                })
                
                # LOCATION Header extrahieren
                for line in response.split('\n'):
                    if line.startswith('LOCATION:') or line.startswith('Location:'):
                        location = line.split(':', 1)[1].strip()
                        print(f"📍 Device Description XML: {location}")
                        print()
                        
            except socket.timeout:
                break
    except Exception as e:
        print(f"❌ Fehler: {e}")
    finally:
        sock.close()
    
    return responses


def fetch_device_description(location_url):
    """Holt die Device Description XML vom DLNA Server."""
    import urllib.request
    
    print(f"\n🔍 Hole Device Description von {location_url}...")
    print("=" * 80)
    
    try:
        with urllib.request.urlopen(location_url, timeout=5) as response:
            xml = response.read().decode('utf-8')
            print(xml)
            print("=" * 80)
            
            # UDN (Unique Device Name = UUID) extrahieren
            import re
            udn_match = re.search(r'<UDN>(.*?)</UDN>', xml)
            if udn_match:
                udn = udn_match.group(1)
                print(f"\n🆔 UDN gefunden: {udn}")
                
            # Services extrahieren
            services = re.findall(r'<serviceType>(.*?)</serviceType>', xml)
            if services:
                print(f"\n📋 Services:")
                for service in services:
                    print(f"   - {service}")
                    
            return xml
    except Exception as e:
        print(f"❌ Fehler: {e}")
        return None


def main():
    print("=" * 80)
    print("SSDP Discovery Analyzer - Wie Bose App beim Löschen")
    print("=" * 80)
    print()
    
    responses = send_ssdp_discovery()
    
    if responses:
        print(f"\n✅ {len(responses)} Geräte gefunden")
        print("\n💡 Die Bose App:")
        print("   1. Sendet M-SEARCH für MediaServer")
        print("   2. Prüft ob der zu löschende Server antwortet")
        print("   3. Wenn gefunden: Holt Device Description XML")
        print("   4. Dann: ??? (was passiert dann?)")
        print()
        
        # Erste LOCATION abrufen
        for resp in responses:
            for line in resp['data'].split('\n'):
                if 'LOCATION' in line.upper():
                    location = line.split(':', 1)[1].strip()
                    fetch_device_description(location)
                    break
            break
    else:
        print("❌ Keine DLNA Server gefunden")
        print("   → Server muss laufen für SSDP Discovery")


if __name__ == "__main__":
    main()
