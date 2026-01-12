# Bose SoundTouch Device Control

Eine umfassende Python-Anwendung zur Erkennung und Steuerung von Bose SoundTouch Geräten im lokalen WLAN-Netzwerk mit vollständiger API-Implementierung aller 30+ Endpoints.

## Architektur

Das Projekt ist modular aufgebaut, um maximale Wiederverwendbarkeit zu ermöglichen:

```
soundtouch_lib.py          - Core Library (reusable)
├── SoundTouchDiscovery     - Network scanning & device detection
└── SoundTouchController    - Device control & status (30+ Methoden)

soundtouch_discovery.py    - CLI Tool (Discovery)
soundtouch_controller.py   - CLI Tool (Control)
soundtouch_api.py          - REST API Server (FastAPI mit 40+ Endpoints)
```

## Installation

```bash
pip install -r requirements.txt
```

## Features

### 🌐 Netzwerk
- **Automatische Netzwerk-Erkennung**: Findet automatisch das lokale Subnetz
- **Multi-Threading**: Scannt mehrere IPs gleichzeitig (configurable threads)
- **JSON-Export**: Speichert gefundene Geräte für spätere Nutzung

### 📶 WiFi Setup
- **Setup-Steuerung**: `SETUP_WIFI` starten/beenden ohne Bose-App
- **WiFi-Profile hinzufügen**: SSID/Passwort/Sicherheit direkt hinterlegen
- **Site Survey**: Verfügbare Netzwerke am Speaker scannen

### 🎮 Basis-Steuerung
- **Remote Keypresses**: Play, Pause, Next, Previous, Volume, Mute, etc.
- **Presets**: Direkter Preset-Zugriff (Preset 1-6)
- **Status Abfrage**: Aktuelle Musik-Info (Artist, Track, Album, Source)

### 🔊 Audio-Kontrolle
- **Lautstärke**: 0-100%, mit Stummschaltung
- **Bass/Treble**: Feineinstellung wenn unterstützt
- **Audio-Modi**: NORMAL, DIALOG, NACHT, DIRECT
- **Lautsprecher-Level**: Front/Rear Separate Kontrolle
- **Audio DSP**: Video Sync Delay (für Heimkino)

### 🎵 Musik-Kontrolle
- **Source/Input-Auswahl**: AUX, Bluetooth, Spotify, TuneIn, etc.
- **Presets**: Auflisten und Zugriff auf gespeicherte Favoriten
- **Bass-Fähigkeiten**: Dynamisches Auslesen von Bass-Min/Max

### 🏠 Multi-Room Audio
- **Zone Management**: Verbinde mehrere Geräte
- **Master/Slave**: Definiere Master-Gerät
- **Synchronized Playback**: Alle Geräte spielen gleiche Musik
- **Dynamische Slave-Verwaltung**: Hinzufügen/Entfernen von Geräten

### 📡 DLNA / Lokales Streaming
- **DLNA-Playback (8091)** über `soundtouch_lib` + `DLNAHelper`
- **MiniDLNA (8200)** für lokales Medien-Serving; Ordner `test_music/` & `minidlna/` bleiben lokal
- **GUI Media Player Tab**: Streams per HTTP-Server + DLNA an das Gerät senden
- **Playlist-Cycling**: Bei DLNA-Quelle navigieren „Zurück/Weiter“ im Steuerungs-Tab durch den gecachten Ordner
- **Fallback**: Bei anderen Quellen senden die Buttons normale Key-Befehle

### 📱 API & Integration
- **REST API**: FastAPI Server mit 40+ Endpoints
- **Swagger Docs**: Auto-generierte API Dokumentation (/docs)
- **Python Library**: Reusable für eigene Projekte
- **Error Handling**: Robuste Fehlerbehandlung mit Status Codes

---

## CLI Verwendung

### Discovery - Geräte finden

```bash
# Auto-Detect (erkennt Netzwerk automatisch)
python soundtouch_discovery.py

# Mit spezifischem Netzwerk
python soundtouch_discovery.py --network 192.168.1.0/24

# Mit benutzerdefinierten Optionen
python soundtouch_discovery.py --port 8090 --threads 50

# Output: soundtouch_devices.json
```

### Controller - Geräte steuern

```bash
# Tastaturpresse senden
python soundtouch_controller.py 192.168.50.156 --key play
python soundtouch_controller.py 192.168.50.156 --key volume_up
python soundtouch_controller.py 192.168.50.156 --key next

# Verfügbare Tasten anzeigen
python soundtouch_controller.py 192.168.50.156 --list

# Aktuelle Status abfragen
python soundtouch_controller.py 192.168.50.156 --status
```

**Verfügbare Keys:**
play, pause, stop, power, next, previous, mute, volume_up, volume_down, preset1-6, thumbsup, thumbsdown, shuffle, repeat, add_favorite, remove_favorite, bookmark, bookmark_add, bookmark_remove, language

---

## REST API Server

### Starten

```bash
python soundtouch_api.py
```

**Zugriff:**
- API: http://localhost:8000
- Swagger Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 📡 Discovery Endpoints

```bash
GET /api/discover
  ?network=192.168.1.0/24
  &port=8090
  &threads=50

Response:
{
  "devices": [
    {
      "ip": "192.168.50.156",
      "mac": "A81B6A632A40",
      "name": "Wohnzimmer",
      "type": "SoundTouch 20",
      "status": "OK"
    }
  ]
}
```

### 🎮 Control Endpoints

```bash
# Taste senden
POST /api/control/{ip}/key
  ?key=play

# Alle Tasten auflisten
GET /api/keys

# Health Check
GET /api/health
```

### 🔊 Volume Endpoints

```bash
# Lautstärke auslesen
GET /api/control/{ip}/volume

Response: {
  "targetvolume": 30,
  "actualvolume": 30,
  "muteenabled": false
}

# Lautstärke setzen
POST /api/control/{ip}/volume
  ?volume=50
  &mute=false
```

### 🎼 Bass Endpoints

```bash
# Bass-Fähigkeiten auslesen
GET /api/control/{ip}/bass-capabilities

Response: {
  "bassAvailable": true,
  "bassMin": -10,
  "bassMax": 10,
  "bassDefault": 0
}

# Bass-Wert auslesen
GET /api/control/{ip}/bass

Response: {
  "actualbassnow": 5,
  "bassmutable": false
}

# Bass setzen
POST /api/control/{ip}/bass?bass=5
```

### 📡 Source Endpoints

```bash
# Verfügbare Quellen auflisten
GET /api/control/{ip}/sources

Response: {
  "sources": [
    {
      "source": "AUX",
      "sourceAccount": "AUX",
      "status": "READY",
      "name": "Aux Input"
    }
  ]
}

# Source wechseln
POST /api/control/{ip}/source
  ?source=AUX
  &source_account=AUX

POST /api/control/{ip}/source?source=BLUETOOTH
```

### 🎚️ Presets Endpoint

```bash
# Presets auflisten
GET /api/control/{ip}/presets

Response: {
  "presets": [
    {
      "id": "1",
      "source": "SPOTIFY",
      "sourceAccount": "user@spotify",
      "itemName": "My Playlist"
    }
  ]
}
```

### 🎛️ Audio Control Endpoints

```bash
# Audio DSP Settings (Audio-Modi)
GET /api/control/{ip}/audio-dsp

Response: {
  "audiomode": "AUDIO_MODE_NORMAL",
  "videosyncaudiodelay": 0,
  "supportedaudiomodes": [
    "AUDIO_MODE_DIRECT",
    "AUDIO_MODE_NORMAL",
    "AUDIO_MODE_DIALOG",
    "AUDIO_MODE_NIGHT"
  ]
}

# Audio-Modus wechseln
POST /api/control/{ip}/audio-dsp
  ?audiomode=AUDIO_MODE_DIALOG

# Bass & Treble (Tone Controls)
GET /api/control/{ip}/tone-controls
POST /api/control/{ip}/tone-controls
  ?bass=5
  &treble=3

# Lautsprecher-Level (Vorne/Hinten)
GET /api/control/{ip}/level-controls
POST /api/control/{ip}/level-controls
  ?front=5
  &rear=3
```

### 🏠 Zone Management Endpoints

```bash
# Zone auslesen
GET /api/control/{ip}/zone

Response: {
  "master": "A81B6A632A40",
  "members": [
    {
      "ipaddress": "192.168.50.156",
      "macaddress": "A81B6A632A40",
      "is_master": true
    }
  ]
}

# Multi-Room Zone erstellen
POST /api/control/{ip}/zone

Body: {
  "master_mac": "A81B6A632A40",
  "members": [
    {
      "ip": "192.168.50.156",
      "mac": "A81B6A632A40"
    },
    {
      "ip": "192.168.50.157",
      "mac": "A81B6A632A41"
    }
  ]
}

# Slave hinzufügen
POST /api/control/{ip}/zone/slave/add
  ?master_mac=A81B6A632A40
  &slave_ip=192.168.50.157
  &slave_mac=A81B6A632A41

# Slave entfernen
POST /api/control/{ip}/zone/slave/remove
  ?master_mac=A81B6A632A40
  &slave_mac=A81B6A632A41
```

### 🎵 Status & Info Endpoints

```bash
# Aktuelle Musik-Info
GET /api/control/{ip}/nowplaying

Response: {
  "source": "SPOTIFY",
  "artist": "Artist Name",
  "track": "Song Title",
  "album": "Album Name",
  "artwork": "http://..."
}

# Gerät-Fähigkeiten
GET /api/control/{ip}/capabilities

Response: [
  {
    "name": "productCapsQuery",
    "url": "/productcapsquery"
  }
]
```

### 🔧 Device Management

```bash
# Gerätename ändern
POST /api/control/{ip}/name?name=Wohnzimmer
```

### 📶 WiFi Setup & Onboarding

```bash
# WiFi-Setup starten/beenden (state z.B. SETUP_WIFI, SETUP_WIFI_LEAVE)
POST /api/control/{ip}/setup
Body: {"state": "SETUP_WIFI", "timeout_ms": 3000}

# WiFi-Profil hinzufügen
POST /api/control/{ip}/wifi-profile
Body: {"ssid": "MySSID", "password": "MyPass", "security_type": "wpa_or_wpa2", "timeout": 30}

# Aktives WiFi-Profil abfragen
GET /api/control/{ip}/wifi-profile

# Site Survey (sichtbare Netze in Speaker-Nähe)
GET /api/control/{ip}/wifi-site-survey
```

---

## Python Library - Detaillierte Beispiele

### Basis-Setup

```python
from soundtouch_lib import SoundTouchDiscovery, SoundTouchController

# Geräte finden
scanner = SoundTouchDiscovery()
devices = scanner.scan()  # Scannt automatisches Netzwerk

# Mit benutzerdefiniertem Netzwerk
scanner = SoundTouchDiscovery(network="192.168.1.0/24")
devices = scanner.scan(max_threads=100)

# Geräte durchlaufen
for device in devices:
    print(f"{device['name']} ({device['type']}) at {device['ip']}")

# Gerät steuern
controller = SoundTouchController("192.168.50.156")
```

### 🎮 Tastatureingaben

```python
from soundtouch_lib import SoundTouchController

controller = SoundTouchController("192.168.50.156")

# Playback-Kontrolle
controller.send_key("play")
controller.send_key("pause")
controller.send_key("stop")

# Navigation
controller.send_key("next")
controller.send_key("previous")

# Lautstärke (über Tasten)
controller.send_key("volume_up")
controller.send_key("volume_down")
controller.send_key("mute")

# Favoriten
controller.send_key("add_favorite")
controller.send_key("remove_favorite")

# Presets (direkter Zugriff)
controller.send_key("preset1")
controller.send_key("preset2")
controller.send_key("preset6")

# Alle verfügbaren Tasten anzeigen
keys = SoundTouchController.get_available_keys()
for key in keys:
    print(key)
```

### 🔊 Lautstärke-Kontrolle

```python
# Lautstärke auslesen
volume_data = controller.get_volume()
if volume_data:
    print(f"Aktuelle Lautstärke: {volume_data['actualvolume']}/100")
    print(f"Stummgeschaltet: {volume_data['muteenabled']}")

# Lautstärke setzen
controller.set_volume(50)              # 50%
controller.set_volume(30, mute=True)   # 30% + Stummschaltung
controller.set_volume(100, mute=False) # 100% + Laut
```

### 🎼 Bass & Treble

```python
# Bass-Fähigkeiten prüfen
caps = controller.get_bass_capabilities()
if caps and caps['bassAvailable']:
    print(f"Bass-Bereich: {caps['bassMin']} bis {caps['bassMax']}")
    print(f"Standard: {caps['bassDefault']}")
    
    # Bass auslesen
    bass_data = controller.get_bass()
    if bass_data:
        print(f"Aktueller Bass: {bass_data['actualbass']}")
    
    # Bass setzen
    if controller.set_bass(5):
        print("Bass auf 5 gesetzt")

# Bass & Treble zusammen
tone = controller.get_tone_controls()
if tone:
    print(f"Bass: {tone['bass']['value']}")
    print(f"Treble: {tone['treble']['value']}")

# Einstellen
if controller.set_tone_controls(bass=5, treble=3):
    print("Bass & Treble eingestellt")
```

### 📡 Source/Input-Kontrolle

```python
# Verfügbare Quellen auflisten
sources = controller.get_sources()
if sources:
    for source in sources['sources']:
        print(f"{source['source']}: {source['name']} ({source['status']})")

# Source wechseln
controller.select_source("AUX", "AUX")
controller.select_source("BLUETOOTH")
controller.select_source("SPOTIFY", "user@spotify")
controller.select_source("TUNEIN")
controller.select_source("LOCAL_INTERNET_RADIO")

# Prüfen ob erfolgreich
if controller.select_source("AUX"):
    print("Source gewechselt zu AUX")
```

### 🎚️ Audio-Modi

```python
# Audio DSP Settings auslesen
dsp = controller.get_audio_dsp_controls()
if dsp:
    print(f"Audio-Modus: {dsp['audiomode']}")
    print(f"Unterstützte Modi:")
    for mode in dsp['supportedaudiomodes']:
        print(f"  - {mode}")

# Audio-Modus wechseln
controller.set_audio_dsp_controls(audiomode="AUDIO_MODE_NORMAL")
controller.set_audio_dsp_controls(audiomode="AUDIO_MODE_DIALOG")
controller.set_audio_dsp_controls(audiomode="AUDIO_MODE_NIGHT")
controller.set_audio_dsp_controls(audiomode="AUDIO_MODE_DIRECT")

# Mit Delay (Heimkino Sync)
controller.set_audio_dsp_controls(
    audiomode="AUDIO_MODE_NORMAL",
    videosyncaudiodelay=100
)
```

### 🎼 Lautsprecher-Level

```python
# Front & Rear Speaker Levels auslesen
levels = controller.get_level_controls()
if levels:
    front_level = levels['frontCenterSpeakerLevel']
    rear_level = levels['rearSurroundSpeakersLevel']
    print(f"Front: {front_level['value']}")
    print(f"Rear: {rear_level['value']}")

# Levels anpassen
if controller.set_level_controls(front=5, rear=3):
    print("Lautsprecher-Level gesetzt")

# Nur Front anpassen
controller.set_level_controls(front=7, rear=3)
```

### 🎵 Presets

```python
# Presets auflisten
presets = controller.get_presets()
if presets:
    for preset in presets['presets']:
        print(f"Preset {preset['id']}: {preset['itemName']}")
        print(f"  Source: {preset['source']}")
        print(f"  Account: {preset['sourceAccount']}")
```

### 🏠 Multi-Room Zones

```python
# Zone auslesen
zone = controller.get_zone()
if zone:
    print(f"Master: {zone['master']}")
    print(f"Mitglieder:")
    for member in zone['members']:
        role = "Master" if member['is_master'] else "Slave"
        print(f"  {member['macaddress']} ({role})")

# Multi-Room Zone erstellen (alle Geräte synchronisieren)
master_mac = "A81B6A632A40"
members = [
    {"ip": "192.168.50.156", "mac": "A81B6A632A40"},  # Master
    {"ip": "192.168.50.157", "mac": "A81B6A632A41"},  # Slave 1
    {"ip": "192.168.50.158", "mac": "A81B6A632A42"},  # Slave 2
]

if controller.set_zone(master_mac, members):
    print("Zone erstellt!")

# Slave hinzufügen
slave_ip = "192.168.50.159"
slave_mac = "A81B6A632A43"

if controller.add_zone_slave(master_mac, slave_ip, slave_mac):
    print(f"Slave {slave_ip} hinzugefügt")

# Slave entfernen
if controller.remove_zone_slave(master_mac, slave_mac):
    print(f"Slave {slave_mac} entfernt")
```

### 📋 Status & Info

```python
# Aktuelle Musik-Info
playing = controller.get_nowplaying()
if playing:
    print(f"🎵 {playing['artist']} - {playing['track']}")
    print(f"   Album: {playing['album']}")
    print(f"   Source: {playing['source']}")
    if playing.get('artwork'):
        print(f"   Cover: {playing['artwork']}")

# Gerät-Fähigkeiten auslesen
capabilities = controller.get_capabilities()
if capabilities:
    for cap in capabilities:
        print(f"{cap['name']}: {cap['url']}")

# Gerätename ändern
if controller.set_device_name("Küche"):
    print("Gerätename aktualisiert")
```

---

## 🎯 Praktische Szenarien

### Morgen-Routine

```python
import time
from soundtouch_lib import SoundTouchController

def morning_routine(ip):
    """Sanftes Aufwachen mit Musik"""
    ctl = SoundTouchController(ip)
    
    # Langsam lauter werden lassen
    ctl.set_volume(10)
    time.sleep(1)
    ctl.set_volume(15)
    time.sleep(1)
    ctl.set_volume(20)
    
    # Radio einschalten
    ctl.select_source("TUNEIN")
    ctl.send_key("play")
    
    # Audio-Modus
    ctl.set_audio_dsp_controls(audiomode="AUDIO_MODE_NORMAL")

morning_routine("192.168.50.156")
```

### Party-Modus

```python
import time
from soundtouch_lib import SoundTouchController

def party_mode(device_ips, volume=70):
    """Alle Geräte synchronisieren für Party"""
    if not device_ips:
        return
    
    master_ip = device_ips[0]
    master_ctl = SoundTouchController(master_ip)
    
    # Master vorbereiten
    master_ctl.set_volume(volume)
    master_ctl.select_source("SPOTIFY")
    
    # Alle anderen Geräte folgen Master
    for ip in device_ips[1:]:
        ctl = SoundTouchController(ip)
        ctl.set_volume(volume)
        ctl.select_source("SPOTIFY")
    
    # Starte Musik auf Master
    master_ctl.send_key("play")
    
    # Kleine Verzögerung
    time.sleep(2)
    
    # Starte auf allen Slaves
    for ip in device_ips[1:]:
        ctl = SoundTouchController(ip)
        ctl.send_key("play")

party_mode([
    "192.168.50.156",
    "192.168.50.157",
    "192.168.50.158"
], volume=75)
```

### Nacht-Routine

```python
import time
from soundtouch_lib import SoundTouchController

def night_routine(ip):
    """Entspanntes Einschlafen"""
    ctl = SoundTouchController(ip)
    
    # Nacht-Audio-Modus
    ctl.set_audio_dsp_controls(audiomode="AUDIO_MODE_NIGHT")
    
    # Leise Musik
    ctl.set_volume(15)
    
    # Entspannende Quelle (zB. Natur-Sounds via TuneIn)
    ctl.select_source("TUNEIN")
    
    # Bass reduzieren
    ctl.set_bass(-3)
    
    # Musik nach 30 Minuten ausschalten
    time.sleep(1800)
    ctl.send_key("stop")

night_routine("192.168.50.156")
```

---

## Fehlerbehandlung

```python
from soundtouch_lib import SoundTouchController

controller = SoundTouchController("192.168.50.156")

# Alle Get-Methoden geben Optional[dict] zurück
volume = controller.get_volume()
if volume is None:
    print("❌ Fehler: Kann Lautstärke nicht auslesen")
    print("   - Gerät offline?")
    print("   - Falscher Port?")
else:
    print(f"✅ Lautstärke: {volume['actualvolume']}")

# Alle Set-Methoden geben bool zurück
success = controller.set_volume(50)
if not success:
    print("❌ Fehler: Kann Lautstärke nicht setzen")
else:
    print("✅ Lautstärke erfolgreich gesetzt")

# Try/Except für Netzwerk-Fehler
try:
    controller = SoundTouchController("192.168.50.156", port=8090)
    result = controller.get_volume()
except ConnectionError:
    print("❌ Keine Verbindung zum Gerät")
except Exception as e:
    print(f"❌ Fehler: {e}")
```

---

## Konfiguration & Netzwerk

```python
from soundtouch_lib import SoundTouchDiscovery, SoundTouchController

# Benutzerdefiniertes Netzwerk
scanner = SoundTouchDiscovery(network="192.168.100.0/24")
devices = scanner.scan()

# Schnelleres Scanning mit mehr Threads
devices = scanner.scan(max_threads=200)

# Benutzerdefinierter Port
controller = SoundTouchController(
    ip="192.168.50.156",
    port=8090  # Standard ist 8090
)

# Mit Timeout
import socket
socket.setdefaulttimeout(3)  # 3 Sekunden
```

---

## Anforderungen

```
Python 3.7+
requests>=2.28.0
fastapi>=0.100.0
uvicorn>=0.23.0
```

**Installation:**
```bash
pip install -r requirements.txt
```

---

## Implementierte API-Endpoints

Das Projekt implementiert alle 30+ Methoden der offiziellen Bose SoundTouch Web API v1.0:

✅ **Basis-Kontrolle** (3 Methoden)
- send_key() | get_nowplaying() | get_available_keys()

✅ **Lautstärke** (2 Methoden)
- get_volume() | set_volume()

✅ **Bass** (3 Methoden)
- get_bass_capabilities() | get_bass() | set_bass()

✅ **Sources** (2 Methoden)
- get_sources() | select_source()

✅ **Presets** (1 Methode)
- get_presets()

✅ **System** (1 Methode)
- get_capabilities()

✅ **Audio DSP** (2 Methoden)
- get_audio_dsp_controls() | set_audio_dsp_controls()

✅ **Tone Controls** (2 Methoden)
- get_tone_controls() | set_tone_controls()

✅ **Level Controls** (2 Methoden)
- get_level_controls() | set_level_controls()

✅ **Zones** (4 Methoden)
- get_zone() | set_zone() | add_zone_slave() | remove_zone_slave()

✅ **Device** (1 Methode)
- set_device_name()

---

## Troubleshooting

### Gerät nicht erreichbar?

```python
import socket

# IP prüfen
try:
    ip = socket.gethostbyname("192.168.50.156")
    print(f"✅ IP erreichbar: {ip}")
except socket.gaierror:
    print("❌ IP nicht auflösbar")

# Port prüfen
try:
    socket.create_connection(("192.168.50.156", 8090), timeout=2)
    print("✅ Port 8090 offen")
except socket.timeout:
    print("❌ Port 8090 nicht erreichbar")
except ConnectionRefusedError:
    print("❌ Port 8090 blockiert")
```

### Scanning langsam?

```python
# Threadzahl erhöhen
scanner = SoundTouchDiscovery()
devices = scanner.scan(max_threads=200)

# Oder Netzwerk verkleinern
scanner = SoundTouchDiscovery(network="192.168.50.0/25")
devices = scanner.scan()
```

### XML Parse Fehler?

- Gerät neustarten (Netzwerk-Fehler)
- Port 8090 prüfen
- Netzwerk-Konnektivität prüfen
- In neuerer API-Version hat sich möglicherweise das XML-Format geändert

---

## Lizenz & Credits

API-Dokumentation: Bose SoundTouch Web API v1.0 (Januar 7, 2026)

**Hinweis:** Dieses Projekt wird inoffiziell entwickelt und ist nicht mit Bose Corporation verbunden.
