# Bose SoundTouch REST API - Detaillierte Recherche

**Quelle:** Offizielle Bose SoundTouch Web API v1.0 (Januar 2026) + Lokale Implementation

---

## 1. Alle verfügbaren/möglichen Sources abrufen

### API Endpoint
```
GET http://{device_ip}:8090/sources
```

### XML Response Format
```xml
<sources deviceID="$MACADDR">
  <sourceItem source="$SOURCE" sourceAccount="$STRING" status="$SOURCE_STATUS">$STRING</sourceItem>
  ...
</sources>
```

### Attribute Beschreibung
- **`source`**: Source-Name (z.B. AUX, BLUETOOTH, PRODUCT, STORED_MUSIC, INTERNET_RADIO, etc.)
- **`sourceAccount`**: Account-Identifier für diese Source (optional, variiert je nach Source)
- **`status`**: `UNAVAILABLE` oder `READY` - zeigt ob Source nutzbar ist
- **Text-Content**: Name der Source (lesbar)

### Beispiel Response
```xml
<sources deviceID="A1B2C3D4E5F6">
  <sourceItem source="AUX" sourceAccount="AUX" status="READY">AUX</sourceItem>
  <sourceItem source="AUX" sourceAccount="AUX3" status="READY">AUX 3</sourceItem>
  <sourceItem source="BLUETOOTH" sourceAccount="" status="READY">Bluetooth</sourceItem>
  <sourceItem source="PRODUCT" sourceAccount="TV" status="READY">Product</sourceItem>
  <sourceItem source="STORED_MUSIC" sourceAccount="upnp_media_server" status="READY">Stored Music</sourceItem>
  <sourceItem source="INTERNET_RADIO" sourceAccount="iheartradio" status="READY">iHeartRadio</sourceItem>
</sources>
```

### Verfügbare Sources (typisch)
| Source | sourceAccount | Beschreibung |
|--------|---------------|--------------|
| AUX | AUX oder AUX3 | Auxiliary Eingänge (analog) |
| BLUETOOTH | (leer) | Bluetooth Geräte |
| PRODUCT | TV, etc. | Eingebaute Speaker/Eingänge |
| STORED_MUSIC | UPnP Server ID | Lokale Musik via DLNA/UPnP |
| INTERNET_RADIO | Service-ID | Internet Radio Services |
| SPOTIFY | (service) | Spotify Integration |
| PANDORA | (service) | Pandora Integration |
| DEEZER | (service) | Deezer Integration |

### Wichtig
⚠️ **Die `/sources` API gibt NUR die konfigurierten/erkannten Sources zurück!**
- Es gibt KEINE API um alle *theoretisch möglichen* Sources zu erfragen
- Verfügbare Sources hängen ab von:
  - Gerättyp und Hardware
  - Firmware-Version
  - Konfigurierte Cloud-Konten
  - Verfügbare DLNA/UPnP Server im Netzwerk

---

## 2. Sources für lokales Musik-Streaming von HTTP-Server

### Unterstützte Source: STORED_MUSIC
```
Source: STORED_MUSIC
Location Protocol: HTTP URLs
Format: http://{server_ip}:{port}/{path/to/file.mp3}
```

### API Endpoint zum Abspielen
```
POST http://{device_ip}:8090/select
```

### XML Request Format
```xml
<ContentItem source="STORED_MUSIC" sourceAccount="{upnp_server_account}" type="TRACK" location="{http_url}">
  <itemName>{file_name}</itemName>
</ContentItem>
```

### Detaillierte ContentItem Parameter
| Parameter | Typ | Beschreibung | Erforderlich |
|-----------|-----|--------------|-------------|
| source | String | "STORED_MUSIC" | ✓ |
| sourceAccount | String | UPnP Server Account ID vom Gerät | ✓ |
| type | String | "TRACK" (für einzelne Dateien) | ✓ |
| location | String | HTTP-URL zur Audiodatei (URL-encoded) | ✓ |
| itemName | Element | Dateiname/Display-Name | ✓ |
| isPresetable | Boolean | "true" oder "false" (optional) | - |

### Beispiel Request
```xml
<ContentItem source="STORED_MUSIC" sourceAccount="upnp_media_server" type="TRACK" location="http://192.168.1.100:8200/music/song.mp3">
  <itemName>Schönes Lied</itemName>
</ContentItem>
```

### Unterstützte Audio-Formate (via HTTP)
- MP3 (audio/mpeg)
- M4A (audio/mp4)
- AAC (audio/aac)
- FLAC (audio/flac)
- WAV (audio/wav)
- OGG (audio/ogg)
- WMA (audio/x-ms-wma)

### HTTP Server Anforderungen
✓ Range-Request Support (`Accept-Ranges: bytes`) für Seeking/Scrubbing
✓ Korrekte MIME-Types
✓ CORS Headers (optional, aber empfohlen):
  ```
  Access-Control-Allow-Origin: *
  Access-Control-Allow-Methods: GET, HEAD, OPTIONS
  Accept-Ranges: bytes
  ```

---

## 3. API zur Source-Capabilities Abfrage

### API Endpoint
```
GET http://{device_ip}:8090/capabilities
```

### XML Response Format
```xml
<capabilities deviceID="$MACADDR">
  <capability name="$STRING" url="/$STRING" info="$STRING"/>
  <capability name="$STRING" url="/$STRING" info="$STRING"/>
  ...
</capabilities>
```

### Beispiel Response
```xml
<capabilities deviceID="A1B2C3D4E5F6">
  <capability name="audiodspcontrols" url="/audiodspcontrols" info=""/>
  <capability name="audioproducttonecontrols" url="/audioproducttonecontrols" info=""/>
  <capability name="audioproductlevelcontrols" url="/audioproductlevelcontrols" info=""/>
</capabilities>
```

### Wichtig
⚠️ **Die `/capabilities` API queried GERÄTFÄHIGKEITEN, nicht Source-Capabilities!**

**Es gibt KEINE dedizierte API um Source-Capabilities zu erfragen!**

Workarounds:
1. **Try-and-Catch Ansatz**: Einfach den `/select` API mit der Source aufrufen und auf Fehler prüfen
2. **Status prüfen**: Nutze `/sources`, um zu sehen ob `status="READY"` ist
3. **Trial**: Bei bekanntem Gerättyp: Dokumentation des Herstellers durchsuchen

---

## 4. STORED_MUSIC korrekt mit minidlna nutzen

### minidlna Setup
```bash
# Installation
sudo apt install minidlna

# Konfiguration: /etc/minidlna.conf
media_dir=A,/home/user/Music
db_dir=/var/cache/minidlna
log_dir=/var/log
port=8200
friendly_name=MyMusicServer
inotify=yes
```

### Funktionsweise mit Bose SoundTouch
1. **minidlna lädt Musikverzeichnis** und indexiert Dateien
2. **UPnP/DLNA Server läuft** auf Port 8200 mit HTTP Backend
3. **Bose gerät findet Server** via UPnP Discovery und erstellt sourceAccount
4. **HTTP Stream-URLs** werden von minidlna generiert

### Protokoll
```
minidlna Index: /home/user/Music/
        ↓
UPnP Server läuft auf http://localhost:8200
        ↓
Gerät findet Server (UPnP Discovery) → sourceAccount = "upnp_media_server"
        ↓
App sendet HTTP URL: http://server_ip:8200/MediaItems/file_id.mp3
        ↓
minidlna serviert Datei über HTTP mit Range-Support
```

### minidlna URL Schema
```
Standard Format: http://{server_ip}:8200/MediaItems/{id}.{ext}
Beispiel:       http://192.168.1.100:8200/MediaItems/22.mp3
```

### Bose Request mit minidlna
```xml
<ContentItem source="STORED_MUSIC" sourceAccount="upnp_media_server" type="TRACK" location="http://192.168.1.100:8200/MediaItems/song.mp3">
  <itemName>Song Name</itemName>
</ContentItem>
```

### Wichtige Punkte
⚠️ **sourceAccount muss exakt matchen!** Wird vom Gerät ermittelt via `/sources`
⚠️ **File-ID muss korrekt sein** - minidlna muss Datei indexed haben
✓ **Path ist relativ zum Media-Dir** in minidlna.conf
✓ **Range Requests** automatisch unterstützt für Seeking

### Debug
```bash
# minidlna neu starten
sudo systemctl restart minidlna

# Logs prüfen
sudo tail -f /var/log/minidlna.log

# UPnP Discovery testen
upnp-inspector  # oder similar tool

# HTTP Test
curl -H "Range: bytes=0-1023" http://localhost:8200/MediaItems/22.mp3
```

---

## 5. SMB-Pfade (smb://ip/path/file.mp3) als location

### Antwort: ❌ NICHT DIREKT UNTERSTÜTZT

Die Bose SoundTouch API unterstützt **KEINE SMB/CIFS Protokolle** direkt in der `location` Parameter!

### Warum nicht?
- `/select` API erwartet **HTTP URLs** für `location`
- SMB ist ein Netzwerk-Filehosting-Protokoll, keine HTTP-basiert
- Gerät kann nicht mit SMB-Clients arbeiten

### Lösungen

#### Option 1: SMB → HTTP Brücke (HTTP Server auf SMB-Share)
```
SMB Share (smb://192.168.1.50/music/)
    ↓
Mount lokal: mount -t cifs //192.168.1.50/music /mnt/smb
    ↓
HTTP Server serviert /mnt/smb/
    ↓
Bose Request: location="http://server_ip:8000/song.mp3"
```

#### Option 2: Python HTTP Server mit SMB
```python
from http.server import SimpleHTTPRequestHandler, HTTPServer
from smb.SMBConnection import SMBConnection
import os

# 1. SMB Share mounten
os.system("mount -t cifs //smbhost/share /mnt/smb -o username=user,password=pass")

# 2. HTTP Server auf gemountetes Verzeichnis
class SMBHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="/mnt/smb", **kwargs)

httpd = HTTPServer(('0.0.0.0', 8888), SMBHTTPHandler)
httpd.serve_forever()

# 3. Bose request
location = "http://server_ip:8888/subfolder/file.mp3"
```

#### Option 3: DLNA/UPnP mit SMB Backend
```bash
# minidlna mit SMB Mount
sudo mount -t cifs //smbhost/music /mnt/smb -o username=user,password=pass

# Dann minidlna.conf
media_dir=A,/mnt/smb

# Bose nutzt dann DLNA statt SMB
location="http://dlna_server:8200/MediaItems/id.mp3"
```

### Empfehlung
✓ **Nutze DLNA/UPnP Backend (minidlna)** - ist die Standard-Integration für Musik auf Bose Geräten
✓ Montiere SMB-Share lokal, konfiguriere minidlna darauf
✓ Gerät spricht nur HTTP mit dem DLNA Server

---

## API Übersicht (Zusammenfassung)

| Endpoint | Methode | Beschreibung | Returns |
|----------|---------|--------------|---------|
| `/sources` | GET | Verfügbare Sources abfragen | XML mit Source-Liste |
| `/select` | POST | Source wechseln / Musik abspielen | Status 200 OK |
| `/capabilities` | GET | Gerätfähigkeiten erfragen | XML mit Capability-List |
| `/now playing` | GET | Aktuelle Wiedergabe | XML mit Metadaten |
| `/presets` | GET | Gespeicherte Presets | XML mit Preset-Liste |
| `/key` | POST | Remote-Taste drücken (PLAY, PAUSE, etc.) | Status 200 OK |

---

## ContentItem XML Struktur (Vollständig)

```xml
<ContentItem 
  source="STORED_MUSIC|INTERNET_RADIO|SPOTIFY|..."
  sourceAccount="account_identifier"
  type="TRACK|PLAYLIST|ALBUM"
  location="http://server/path/to/file.ext"
  isPresetable="true|false">
  
  <itemName>Display Name</itemName>
  <itemDescription>Beschreibung (optional)</itemDescription>
  <itemImage>http://image-url (optional)</itemImage>
  
</ContentItem>
```

---

## Praktisches Code-Beispiel (Python)

```python
import requests
from xml.sax.saxutils import escape

def stream_to_soundtouch(device_ip, file_url, file_name):
    """Stream Datei zu Bose SoundTouch Gerät via HTTP"""
    
    # 1. Sources abfragen
    sources_resp = requests.get(f"http://{device_ip}:8090/sources", timeout=5, verify=False)
    sources_xml = sources_resp.text
    
    # 2. STORED_MUSIC sourceAccount finden
    import xml.etree.ElementTree as ET
    root = ET.fromstring(sources_xml)
    stored_music_account = None
    
    for item in root.findall('sourceItem'):
        if item.get('source') == 'STORED_MUSIC' and item.get('status') == 'READY':
            stored_music_account = item.get('sourceAccount')
            break
    
    if not stored_music_account:
        raise Exception("STORED_MUSIC nicht verfügbar!")
    
    # 3. ContentItem XML erstellen
    xml_body = (
        f'<ContentItem source="STORED_MUSIC" sourceAccount="{escape(stored_music_account)}" '
        f'type="TRACK" location="{escape(file_url)}">'
        f'<itemName>{escape(file_name)}</itemName>'
        f'</ContentItem>'
    )
    
    # 4. An Gerät senden
    headers = {'Content-Type': 'application/xml'}
    response = requests.post(
        f"http://{device_ip}:8090/select",
        data=xml_body,
        headers=headers,
        timeout=5,
        verify=False
    )
    
    if response.status_code == 200:
        print("✓ Stream gesendet!")
        
        # 5. Optional: PLAY schicken
        requests.post(
            f"http://{device_ip}:8090/key",
            data='<key state="press" sender="App">PLAY</key>',
            headers=headers,
            timeout=5,
            verify=False
        )
        return True
    else:
        print(f"✗ Fehler: {response.status_code}")
        return False

# Verwendung
stream_to_soundtouch("192.168.1.156", "http://192.168.1.100:8200/music/song.mp3", "Song")
```

---

## Wichtige Erkenntnisse

1. **Alle Sources**: Nur via `/sources` abfragbar, keine vollständige Liste in API dokumentiert
2. **HTTP-Streaming**: Einzige Option für lokale Musik (via STORED_MUSIC)
3. **SMB nicht möglich**: Gerät versteht nur HTTP - braucht Brücke
4. **Keine Source-Capabilities API**: Muss experimentell oder via Status prüfen
5. **minidlna Standard**: De-facto Standard für Bose Geräte (UPnP/DLNA)
6. **sourceAccount kritisch**: Muss exakt vom `/sources` Response matchen!

---

**Dokumentation erstellt:** Januar 11, 2026  
**Basis:** Bose SoundTouch Web API v1.0 + Lokale Implementation
