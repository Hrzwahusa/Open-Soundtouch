# Open-Soundtouch 🎵

> **⚠️ WORK IN PROGRESS**  
> Dieses Projekt befindet sich in aktiver Entwicklung. Features und APIs können sich noch ändern.  
> Beiträge und Feedback sind willkommen!

Vollständige Python-Implementierung der Bose SoundTouch Web API v1.0 mit erweiterten Features: GUI-Anwendung, DLNA-Streaming, Multi-Room-Verwaltung und Echtzeit-Updates via WebSocket.

---

## 📋 Überblick

Open-Soundtouch ist eine umfassende Python-Bibliothek zur Steuerung von Bose SoundTouch-Geräten über das lokale Netzwerk. Das Projekt implementiert die gesamte offizielle REST-API und bietet zusätzlich:

- 🔍 **Automatische Geräte-Erkennung** via SSDP/UPnP
- 🎵 **DLNA Media Streaming** mit minidlna Integration
- 🏠 **Multi-Room Zonen-Verwaltung** für synchrone Wiedergabe
- 🖥️ **GUI-Anwendung** mit PyQt5 (Linux/Windows/Android)
- 🔌 **WebSocket-Support** für Echtzeit-Status-Updates
- 🌐 **FastAPI REST-Server** mit 40+ Endpoints

---

## 📁 Architektur

Das Projekt ist modular aufgebaut für maximale Wiederverwendbarkeit und Erweiterbarkeit:

```
Core Library
├── soundtouch_lib.py          - API-Wrapper (30+ Methoden)
│   ├── SoundTouchDiscovery    - Netzwerk-Scanning
│   └── SoundTouchController   - Geräte-Kontrolle
├── soundtouch_websocket.py    - WebSocket-Client
├── soundtouch_media.py        - Media Player
└── dlna_helper.py             - DLNA Server Management

CLI Tools
├── soundtouch_discovery.py    - Geräte suchen
└── soundtouch_controller.py   - Geräte steuern

REST API
└── soundtouch_api.py          - FastAPI Server (40+ Endpoints)

GUI Anwendungen
├── gui_linux_windows.py       - Desktop GUI (PyQt5)
├── gui_android.py             - Android GUI (Kivy)
├── gui_media_player.py        - Media Player mit DLNA
└── gui_group_manager.py       - Multi-Room Manager
```

### Neueste Features (WIP)

- ⚡ **Fast Polling**: 300ms Schnell-Update nach Stream-Start für sofortige Status-Synchronisation
- 📊 **DLNA Metadata Sync**: Automatische Synchronisation von Titel, Künstler und Duration aus minidlna DB
- 🔄 **Verbesserter Status-Parser**: Unterstützung für XML-Attribute und Child-Elemente
- 💿 **Lokale Media-Verwaltung**: Integrierte minidlna-Datenbank im Anwendungsverzeichnis

---

## 🚀 Quick Start

### Installation

```bash
# Repository klonen
git clone https://github.com/Hrzwahusa/Open-Soundtouch.git
cd Open-Soundtouch

# Abhängigkeiten installieren
pip install -r requirements.txt

# Optional: Vollständige Installation mit GUI
chmod +x install_all.sh
./install_all.sh
```

### Grundlegende Verwendung

**Geräte finden:**
```bash
python soundtouch_discovery.py
```

**Geräte steuern:**
```bash
# Lautstärke setzen
python soundtouch_controller.py --ip 192.168.50.156 --volume 50

# Musik abspielen
python soundtouch_controller.py --ip 192.168.50.156 --key play
```

**GUI starten:**
```bash
./start_gui.sh
# oder
python gui_linux_windows.py
```

---

## ✨ Features

### 🌐 Netzwerk & Erkennung
- SSDP/UPnP-basierte Geräte-Erkennung im lokalen Netzwerk
- Paralleles Multi-Threading für schnelles Scanning (bis zu 254 IPs)
- Automatische Extraktion von IP, MAC-Adresse und Gerätename
- Persistente Geräteverwaltung über `soundtouch_devices.json`

### 🎵 Media & DLNA
- **DLNA-Server Integration** via minidlna
- Lokale Musik-Bibliothek mit automatischem Rescan (5s Intervall)
- Echtzeit-Metadaten-Synchronisation (Titel, Künstler, Duration)
- SQLite-basierte Media-Datenbank
- Support für MP3, FLAC, WAV und weitere Formate
- Fast-Polling (300ms) für sofortige Status-Updates nach Stream-Start

### 🎮 Geräte-Steuerung
- **Playback-Kontrolle**: Play, Pause, Stop, Next, Previous
- **Lautstärke**: Volume 0-100, Mute/Unmute
- **Audio-Einstellungen**: Bass & Treble (Tone Controls)
- **Audio-DSP-Modi**: Normal, Dialog, Night, Direct
- **Source-Wechsel**: Bluetooth, AUX, Spotify, TuneIn, DLNA, etc.
- **Presets**: Favoriten speichern und abrufen (6 Slots)
- **Tastatur-Simulation**: Navigation über virtuelle Tasten

### 🏠 Multi-Room (Zonen)
- Zonen-Erstellung für synchrone Wiedergabe auf mehreren Geräten
- Master/Slave-Architektur
- Dynamisches Hinzufügen/Entfernen von Slaves
- Gruppensteuerung über GUI
- MAC-Adress-basierte Identifikation

### 🔌 Echtzeit-Updates
- **WebSocket-Client** für Live-Status-Updates
- **Fast-Polling-Modus** (300ms) nach Stream-Start
- Automatische Synchronisation zwischen Geräten
- Push-Benachrichtigungen für Statusänderungen

### 🌐 WiFi & Konfiguration
- WiFi-Netzwerk-Scanning und -Auswahl
- WPA2-Authentifizierung
- WiFi-Profil-Management
- Netzwerk-Diagnose

---

## 📖 Dokumentation

### CLI-Tools

#### Geräte-Erkennung

```bash
# Standard-Netzwerk scannen
python soundtouch_discovery.py

# Benutzerdefiniertes Netzwerk
python soundtouch_discovery.py --network 192.168.100.0/24

# Schnelleres Scanning
python soundtouch_discovery.py --threads 200
```

#### Geräte-Steuerung

```bash
# Lautstärke
python soundtouch_controller.py --ip 192.168.50.156 --volume 50
python soundtouch_controller.py --ip 192.168.50.156 --volume 30 --mute

# Tasten
python soundtouch_controller.py --ip 192.168.50.156 --key play
python soundtouch_controller.py --ip 192.168.50.156 --key next

# Bass
python soundtouch_controller.py --ip 192.168.50.156 --bass 5

# Source wechseln
python soundtouch_controller.py --ip 192.168.50.156 --source BLUETOOTH

# Status abrufen
python soundtouch_controller.py --ip 192.168.50.156 --nowplaying
python soundtouch_controller.py --ip 192.168.50.156 --info
```

### Python Library

#### Discovery & Connection

```python
from soundtouch_lib import SoundTouchDiscovery, SoundTouchController

# Geräte im Netzwerk finden
scanner = SoundTouchDiscovery()
devices = scanner.scan()

for device in devices:
    print(f"{device['name']} - {device['ip']} - {device['mac']}")

# Mit Gerät verbinden
controller = SoundTouchController("192.168.50.156")
```

#### Playback Control

```python
# Musik steuern
controller.send_key("play")
controller.send_key("pause")
controller.send_key("stop")
controller.send_key("next")
controller.send_key("previous")

# Lautstärke
controller.set_volume(50)
controller.set_volume(30, mute=True)

# Status abrufen
status = controller.get_nowplaying()
if status:
    print(f"🎵 {status['artist']} - {status['track']}")
    print(f"   Album: {status['album']}")
    print(f"   Source: {status['source']}")
```

#### Audio Settings

```python
# Bass & Treble
controller.set_bass(5)
controller.set_tone_controls(bass=5, treble=3)

# Audio-Modus
controller.set_audio_dsp_controls(audiomode="AUDIO_MODE_NIGHT")

# Level Controls
controller.set_level_controls(front=7, rear=5)
```

#### Multi-Room Zones

```python
# Zone erstellen
master_mac = "A81B6A632A40"
members = [
    {"ip": "192.168.50.156", "mac": "A81B6A632A40"},  # Master
    {"ip": "192.168.50.157", "mac": "A81B6A632A41"},  # Slave 1
    {"ip": "192.168.50.158", "mac": "A81B6A632A42"},  # Slave 2
]

controller.set_zone(master_mac, members)

# Slave hinzufügen
controller.add_zone_slave(master_mac, "192.168.50.159", "A81B6A632A43")

# Slave entfernen
controller.remove_zone_slave(master_mac, "A81B6A632A43")
```

#### DLNA Media Streaming

```python
from soundtouch_media import SoundTouchMedia
from dlna_helper import DLNAHelper

# DLNA-Server starten
dlna = DLNAHelper()
dlna.start_server()

# Media Player initialisieren
media_player = SoundTouchMedia(controller_ip="192.168.50.156")

# Musik abspielen
media_player.play_file("/path/to/music.mp3")

# Stream-Status
status = media_player.get_stream_status()
print(f"Playing: {status['title']} - {status['artist']}")
print(f"Duration: {status['duration']}")
```

### REST API

#### Server starten

```bash
python soundtouch_api.py
# Server läuft auf http://localhost:8000
```

#### Endpoints (Auswahl)

```bash
# Discovery
GET  /api/discover                    # Geräte finden
GET  /api/devices/{ip}/info           # Geräte-Info

# Playback
POST /api/devices/{ip}/play           # Play
POST /api/devices/{ip}/pause          # Pause
POST /api/devices/{ip}/key/{key}      # Taste drücken
GET  /api/devices/{ip}/nowplaying     # Aktueller Status

# Volume
GET  /api/devices/{ip}/volume         # Lautstärke abrufen
POST /api/devices/{ip}/volume         # Lautstärke setzen

# Audio
GET  /api/devices/{ip}/bass           # Bass abrufen
POST /api/devices/{ip}/bass           # Bass setzen
POST /api/devices/{ip}/tone           # Bass & Treble setzen
POST /api/devices/{ip}/audio-mode     # Audio-Modus wechseln

# Sources
GET  /api/devices/{ip}/sources        # Verfügbare Quellen
POST /api/devices/{ip}/source         # Source wechseln

# Zones
GET  /api/devices/{ip}/zone           # Zone abrufen
POST /api/devices/{ip}/zone           # Zone erstellen
POST /api/devices/{ip}/zone/add       # Slave hinzufügen
POST /api/devices/{ip}/zone/remove    # Slave entfernen

# Vollständige API-Dokumentation: http://localhost:8000/docs
```

---

## 🎯 Anwendungsbeispiele

### Morgen-Routine

```python
import time
from soundtouch_lib import SoundTouchController

def morning_routine(ip, target_volume=20):
    """Sanftes Aufwachen mit Musik"""
    controller = SoundTouchController(ip)
    
    # Langsam lauter werden
    for vol in range(10, target_volume + 1, 5):
        controller.set_volume(vol)
        time.sleep(1)
    
    # Radio starten
    controller.select_source("TUNEIN")
    controller.send_key("play")

morning_routine("192.168.50.156")
```

### Party-Modus (Multi-Room)

```python
def party_mode(device_ips, volume=70):
    """Alle Geräte synchronisieren"""
    if not device_ips:
        return
    
    master_controller = SoundTouchController(device_ips[0])
    master_controller.set_volume(volume)
    master_controller.select_source("SPOTIFY")
    master_controller.send_key("play")
    
    # Slaves folgen Master
    for ip in device_ips[1:]:
        controller = SoundTouchController(ip)
        controller.set_volume(volume)
        controller.select_source("SPOTIFY")
        time.sleep(0.5)
        controller.send_key("play")

party_mode(["192.168.50.156", "192.168.50.157", "192.168.50.158"])
```

### Nacht-Routine

```python
def night_routine(ip, duration_minutes=30):
    """Entspanntes Einschlafen mit Timer"""
    controller = SoundTouchController(ip)
    
    # Nacht-Modus aktivieren
    controller.set_audio_dsp_controls(audiomode="AUDIO_MODE_NIGHT")
    controller.set_volume(15)
    controller.set_bass(-3)
    
    # Entspannende Musik starten
    controller.select_source("TUNEIN")
    controller.send_key("play")
    
    # Nach X Minuten ausschalten
    time.sleep(duration_minutes * 60)
    controller.send_key("stop")

night_routine("192.168.50.156", duration_minutes=30)
```

---

## 🛠️ Systemanforderungen

### Python-Pakete

```
Python 3.7+
requests>=2.28.0
fastapi>=0.100.0
uvicorn>=0.23.0
PyQt5>=5.15.0          # Für GUI
websocket-client       # Für WebSocket-Updates
sqlite3                # Für DLNA-DB (meist vorinstalliert)
```

### Optional: DLNA-Streaming

**Linux:**
```bash
sudo apt-get install minidlna
```

**Konfiguration:**
```bash
# minidlna-Konfiguration anpassen
cp minidlna/minidlna.conf /etc/minidlna.conf

# Musik-Verzeichnis hinzufügen
media_dir=/path/to/your/music

# Server starten
sudo service minidlna restart
```

---

## 📚 API-Referenz

### Implementierte Bose SoundTouch API v1.0 Endpoints

#### ✅ Basis-Kontrolle (3 Methoden)
- `send_key()` - Virtuelle Tasteneingaben
- `get_nowplaying()` - Aktueller Wiedergabe-Status
- `get_available_keys()` - Verfügbare Tasten

#### ✅ Lautstärke (2 Methoden)
- `get_volume()` - Lautstärke abrufen
- `set_volume()` - Lautstärke setzen (0-100)

#### ✅ Bass (3 Methoden)
- `get_bass_capabilities()` - Bass-Fähigkeiten prüfen
- `get_bass()` - Bass-Wert abrufen
- `set_bass()` - Bass setzen (-9 bis +9)

#### ✅ Sources (2 Methoden)
- `get_sources()` - Verfügbare Quellen auflisten
- `select_source()` - Quelle wechseln

#### ✅ Presets (1 Methode)
- `get_presets()` - Favoriten abrufen

#### ✅ System (2 Methoden)
- `get_capabilities()` - Geräte-Fähigkeiten
- `set_device_name()` - Gerätename ändern

#### ✅ Audio DSP (2 Methoden)
- `get_audio_dsp_controls()` - Audio-Modi abrufen
- `set_audio_dsp_controls()` - Audio-Modus setzen

#### ✅ Tone Controls (2 Methoden)
- `get_tone_controls()` - Bass & Treble abrufen
- `set_tone_controls()` - Bass & Treble setzen

#### ✅ Level Controls (2 Methoden)
- `get_level_controls()` - Lautsprecher-Level abrufen
- `set_level_controls()` - Lautsprecher-Level setzen

#### ✅ Zones (4 Methoden)
- `get_zone()` - Zone-Konfiguration abrufen
- `set_zone()` - Zone erstellen
- `add_zone_slave()` - Slave hinzufügen
- `remove_zone_slave()` - Slave entfernen

**Gesamt: 30+ Methoden implementiert**

---

## 🐛 Troubleshooting

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

### Scanning zu langsam?

```python
# Mehr Threads verwenden
scanner = SoundTouchDiscovery()
devices = scanner.scan(max_threads=200)

# Oder Netzwerk einschränken
scanner = SoundTouchDiscovery(network="192.168.50.0/25")
devices = scanner.scan()
```

### DLNA-Streaming funktioniert nicht?

```bash
# minidlna-Status prüfen
sudo service minidlna status

# Datenbank neu aufbauen
sudo service minidlna force-reload

# Logs prüfen
tail -f /var/log/minidlna.log
```

### XML Parse Fehler?

- Gerät neustarten (Firmware-Bug)
- Port 8090 prüfen
- Netzwerk-Konnektivität testen
- Eventuell hat sich in neuerer Firmware das XML-Format geändert

---

## 📂 Projektstruktur

```
Open-Soundtouch/
├── soundtouch_lib.py              # Core API-Library
├── soundtouch_websocket.py        # WebSocket-Client
├── soundtouch_media.py            # Media Player
├── soundtouch_discovery.py        # CLI Discovery Tool
├── soundtouch_controller.py       # CLI Control Tool
├── soundtouch_api.py              # REST API Server
├── dlna_helper.py                 # DLNA Integration
├── gui_linux_windows.py           # Desktop GUI
├── gui_android.py                 # Android GUI
├── gui_media_player.py            # Media Player GUI
├── gui_group_manager.py           # Multi-Room GUI
├── gui_device_setup.py            # Device Setup GUI
├── soundtouch_devices.json        # Persistente Geräteliste
├── requirements.txt               # Python-Abhängigkeiten
├── install_all.sh                 # Installations-Script
├── start_gui.sh                   # GUI-Starter
├── buildozer.spec                 # Android Build Config
├── docs/                          # Dokumentation
│   ├── BOSE SOUNDTOUCH WEB API.md
│   └── DLNA_SSDP_Summary.md
├── tests/                         # Test-Scripts
│   ├── test_dlna_playback.py
│   ├── test_websocket_direct.py
│   └── ...
└── test_music/                    # Test-Musik und DLNA-Config
    └── minidlna_opensoundtouch/
        ├── minidlna_opensoundtouch.conf
        └── minidlna_db/           # DLNA-Datenbank
```

---

## 🤝 Mitwirken

Dieses Projekt ist Work in Progress und freut sich über Beiträge!

**Wie kann ich helfen?**
- 🐛 Bugs melden via GitHub Issues
- 💡 Feature-Vorschläge einreichen
- 🔧 Pull Requests erstellen
- 📖 Dokumentation verbessern
- ✅ Tests hinzufügen

**Development Setup:**
```bash
git clone https://github.com/Hrzwahusa/Open-Soundtouch.git
cd Open-Soundtouch
pip install -r requirements.txt
# Happy Coding! 🚀
```

---

## 📄 Lizenz & Credits

**API-Dokumentation:** Bose SoundTouch Web API v1.0

**Hinweis:** Dieses Projekt wird inoffiziell entwickelt und ist nicht mit der Bose Corporation verbunden oder von ihr unterstützt.

---

## 🔗 Links

- **GitHub Repository**: https://github.com/Hrzwahusa/Open-Soundtouch
- **Bose SoundTouch API Docs**: [docs/BOSE SOUNDTOUCH WEB API.md](docs/BOSE%20SOUNDTOUCH%20WEB%20API.md)
- **DLNA/SSDP Summary**: [docs/DLNA_SSDP_Summary.md](docs/DLNA_SSDP_Summary.md)

---

**Made with ❤️ for the SoundTouch Community**
