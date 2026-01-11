# 🎵 SoundTouch Multi-Room & Media Player - Feature Update

## ✨ Neue Features hinzugefügt!

### 1. Multi-Room Gruppen-Verwaltung 👥
Erstelle und verwalte Lautsprechergruppen für synchronisierte Wiedergabe:
- **Master/Slave Konfiguration** - Ein Gerät als Master, mehrere als Slaves
- **Gruppen erstellen** - Beliebig viele Geräte zu einer Gruppe kombinieren
- **Synchronisierte Steuerung** - Alle Geräte gleichzeitig steuern (Play, Pause, Volume)
- **Flexible Verwaltung** - Geräte zur Gruppe hinzufügen/entfernen

### 2. Integrierter Media Player 🎵
Lokale Musikdateien direkt an SoundTouch-Geräte streamen:
- **Lokaler Datei-Browser** - Musikordner durchsuchen und scannen
- **Unterstützte Formate** - MP3, FLAC, WAV, M4A, OGG, WMA, AAC
- **Vorschau-Funktion** - Lokales Pre-Listening vor dem Streaming
- **HTTP-Server** - Automatischer Streaming-Server (Port 8888)
- **Direktes Streaming** - Musik direkt an SoundTouch-Geräte senden
- **Fortschrittsanzeige** - Zeitbalken und Kontrollen

---

## 📁 Neue Dateien

### Core Library
- **soundtouch_lib.py** - Erweitert um `SoundTouchGroupManager` Klasse

### Desktop GUI (Linux/Windows)
- **gui_linux_windows.py** - Haupt-GUI mit neuen Tabs
- **gui_media_player.py** - Media Player Widget (PyQt5)
- **gui_group_manager.py** - Gruppen-Manager Widget (PyQt5)

### Android GUI
- **gui_android.py** - Erweitert um Gruppen-Tab (vereinfacht)

### Tools
- **start_gui.sh** - Quick-Start Script mit Dependency-Check

### Dokumentation
- **GUI_README.md** - Aktualisiert mit allen neuen Features

---

## 🚀 Schnellstart

### Desktop (Linux/Windows)
```bash
# 1. Dependencies installieren
pip install PyQt5 PyQt5-multimedia requests

# 2. GUI starten (empfohlen)
./start_gui.sh

# Oder direkt:
python gui_linux_windows.py
```

### Features nutzen:

#### Multi-Room Gruppen:
1. Gehe zum **"Gruppen"** Tab
2. Klicke **"➕ Neue Gruppe"**
3. Wähle ein Master-Gerät
4. Wähle Slave-Geräte
5. Gib einen Namen ein
6. Gruppe wird erstellt und synchronisiert!

#### Media Player:
1. Gehe zum **"🎵 Media Player"** Tab
2. Klicke **"Durchsuchen"** und wähle Musik-Ordner
3. Klicke **"Scannen"** um Dateien zu laden
4. Doppelklick auf Datei zum Auswählen
5. **"🔊 Vorschau"** für lokales Anhören
6. **"📡 An Gerät streamen"** zum Streamen

---

## 🔧 API-Nutzung

### Gruppen erstellen (Python):
```python
from soundtouch_lib import SoundTouchGroupManager

# Geräte laden
devices = [
    {'name': 'Wohnzimmer', 'ip': '192.168.50.156', 'mac': 'A81B6A632A40'},
    {'name': 'Küche', 'ip': '192.168.50.19', 'mac': 'F45EAB2E1B67'},
    {'name': 'Schlafzimmer', 'ip': '192.168.50.34', 'mac': '506583625D9D'}
]

# Group Manager erstellen
manager = SoundTouchGroupManager(devices)

# Gruppe erstellen (Wohnzimmer = Master, Rest = Slaves)
master = devices[0]
slaves = devices[1:]
success = manager.create_group(master, slaves, "Ganze Wohnung")

# Gruppe steuern
manager.send_command_to_group(0, "PLAY")  # Group Index 0
manager.set_group_volume(0, 50)  # Alle auf 50%
```

### Streaming (manuell):
```python
import requests
from xml.sax.saxutils import escape

# Stream URL erstellen
stream_url = "http://192.168.1.100:8888/music/song.mp3"

# An Gerät senden
xml_body = f'''<ContentItem source="INTERNET_RADIO" location="{escape(stream_url)}">
    <itemName>{escape("Mein Song")}</itemName>
</ContentItem>'''

url = "http://192.168.50.156:8090/select"
headers = {'Content-Type': 'application/xml'}
response = requests.post(url, data=xml_body, headers=headers)
```

---

## 📊 Technische Details

### SoundTouchGroupManager Klasse
**Datei:** `soundtouch_lib.py`

**Methoden:**
- `create_group(master, slaves, name)` - Neue Gruppe erstellen
- `add_to_group(group_index, device)` - Gerät hinzufügen
- `remove_from_group(group_index, device)` - Gerät entfernen
- `send_command_to_group(group_index, key)` - Befehl an Gruppe
- `set_group_volume(group_index, volume)` - Gruppen-Lautstärke
- `get_groups()` - Liste aller Gruppen

### MediaPlayerWidget Klasse
**Datei:** `gui_media_player.py`

**Features:**
- `MediaScanner` Thread - Asynchrones Scannen
- `StreamServer` Thread - HTTP-Server (Port 8888)
- `QMediaPlayer` - Lokale Vorschau
- Unterstützte Formate über `audio_extensions`

### GroupManagerWidget Klasse
**Datei:** `gui_group_manager.py`

**Features:**
- `CreateGroupDialog` - Dialog zur Gruppenerstellung
- Master/Slave Auswahl mit Checkboxen
- Gruppen-Details Anzeige
- Synchronisierte Steuerung

---

## 🎯 Anwendungsfälle

### 1. Party-Modus
```
Erstelle Gruppe "Party" mit allen Lautsprechern
→ Musik spielt synchron in der ganzen Wohnung
→ Eine Lautstärke für alle
```

### 2. Musik-Streaming
```
Lokale FLAC-Sammlung
→ Media Player durchsuchen
→ An hochwertiges Gerät streamen
→ Vorher lokal testen
```

### 3. Multi-Zone Audio
```
Gruppe "Erdgeschoss" (Küche + Wohnzimmer)
Gruppe "Oben" (Schlafzimmer + Bad)
→ Verschiedene Musik pro Zone
```

---

## 🐛 Bekannte Einschränkungen

1. **Streaming-Format:** 
   - SoundTouch unterstützt bestimmte Audio-Codecs
   - MP3 funktioniert am besten
   - FLAC kann Probleme machen

2. **Gruppen-Synchronisation:**
   - Kleine Latenzen möglich (< 100ms)
   - Alle Geräte sollten gleiche Firmware haben
   - Netzwerk-Qualität wichtig

3. **Media Server:**
   - Port 8888 muss frei sein
   - Firewall muss Verbindungen erlauben
   - Nur lokales Netzwerk

---

## 📝 Changelog

### v2.0.0 - Multi-Room & Media Player Update
**Hinzugefügt:**
- ✅ SoundTouchGroupManager Klasse
- ✅ Multi-Room Gruppen-Verwaltung
- ✅ Media Player Widget (PyQt5)
- ✅ HTTP-Streaming-Server
- ✅ Lokale Media-Vorschau
- ✅ Gruppen-Manager Widget (PyQt5)
- ✅ Android Gruppen-Tab (Kivy)
- ✅ Start-Script mit Dependency-Check
- ✅ Umfangreiche Dokumentation

**Geändert:**
- 🔄 GUI-Struktur mit modularen Widgets
- 🔄 Tab-basierte Navigation
- 🔄 Verbesserte Fehlerbehandlung

**Behoben:**
- 🐛 Scan-Parameter korrekt (max_threads)
- 🐛 Device-Updates in allen Widgets

---

## 💡 Tipps & Tricks

### Media Player
- **Große Bibliotheken:** Scanning kann dauern - Geduld!
- **Server-Start:** Server automatisch beim ersten Stream gestartet
- **Vorschau:** Teste Dateien lokal bevor du streamst
- **Formate:** MP3 @ 320kbps für beste Qualität

### Gruppen
- **Master wählen:** Nimm das leistungsstärkste Gerät als Master
- **Netzwerk:** Alle Geräte im gleichen WLAN
- **Firmware:** Aktualisiere alle Geräte auf gleichen Stand
- **Testen:** Starte mit 2 Geräten zum Testen

### Performance
- **Scan-Threads:** Standard 50 ist gut, bei Problemen reduzieren
- **Server-Port:** 8888 belegt? Ändere in `gui_media_player.py`
- **Auto-Refresh:** 2 Sekunden ist Standard, erhöhe bei Bedarf

---

## 🙏 Credits

**Entwickelt mit:**
- **PyQt5** - Desktop GUI Framework
- **PyQt5-multimedia** - Audio Playback
- **Kivy** - Android GUI Framework
- **Python http.server** - Streaming Server
- **Bose SoundTouch API** - Device Control

---

**Viel Spaß mit Multi-Room Audio und lokalem Musik-Streaming! 🎵🎉**
