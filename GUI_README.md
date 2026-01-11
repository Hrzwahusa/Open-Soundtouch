# SoundTouch GUI Anwendungen

Dieses Projekt enthält drei GUI-Implementierungen zur Steuerung von Bose SoundTouch Geräten für verschiedene Plattformen mit **Multi-Room Support** und **integriertem Media Player**.

## 🎯 Neue Features

### ✨ Multi-Room Gruppen-Verwaltung
- Erstelle Lautsprechergruppen für synchronisierte Wiedergabe
- Master/Slave Konfiguration
- Gruppen-Steuerung (Play, Pause, Volume für alle Geräte)
- Geräte zur Gruppe hinzufügen/entfernen

### 🎵 Integrierter Media Player
- Lokale Musikdateien abspielen
- Direkt an SoundTouch-Geräte streamen
- Eingebauter HTTP-Streaming-Server
- Unterstützt MP3, FLAC, WAV, M4A, OGG, WMA, AAC
- Ordner-basierte Mediathek mit Vorschau

---

## 📱 Verfügbare GUIs

### 1. Linux/Windows GUI (PyQt5)
**Datei:** `gui_linux_windows.py`

Moderne Desktop-Anwendung mit vollem Funktionsumfang für Linux und Windows.

#### Features:
- ✨ Automatische Geräte-Erkennung im Netzwerk
- 🎵 Echtzeit-Anzeige aktueller Wiedergabe
- 🎚️ Lautstärkeregler
- ⏯️ Vollständige Wiedergabesteuerung (Play, Pause, Skip)
- 🔢 6 Preset-Buttons
- 📊 Detaillierte Geräteinformationen
- 💾 Speichert gefundene Geräte automatisch
- 🔄 Auto-Refresh alle 2 Sekunden
- **🎵 Media Player Tab:**
  - Lokale Musikordner durchsuchen und scannen
  - Hierarchische Dateiansicht
  - Lokale Vorschau (Pre-Listen)
  - Direktes Streaming an SoundTouch-Geräte
  - Eingebauter HTTP-Server für Streaming
  - Fortschrittsanzeige und Zeitsteuerung
- **👥 Gruppen Tab:**
  - Neue Gruppen erstellen (Master + Slaves)
  - Geräte zur Gruppe hinzufügen/entfernen
  - Synchronisierte Wiedergabesteuerung
  - Gruppen-Lautstärkeregelung
  - Übersicht aller Gruppenmitglieder

#### Installation:
```bash
# Dependencies installieren
pip install PyQt5>=5.15.0 PyQt5-multimedia>=5.15.0 requests

# Oder alle Requirements:
pip install -r requirements.txt
```

#### Verwendung:
```bash
python gui_linux_windows.py
```

#### Screenshots der Funktionen:
- **Geräteauswahl:** Dropdown-Menü mit allen gefundenen Geräten
- **Steuerung:** Alle Standard-Tasten (Play, Pause, Next, Previous)
- **Info-Tab:** Zeigt alle Geräteinformationen und Firmware-Versionen
- **Media Player Tab:** Musik-Browser mit Streaming-Funktionalität
- **Gruppen Tab:** Multi-Room Gruppen erstellen und verwalten

---

### 2. Android GUI (Kivy)
**Datei:** `gui_android.py`

Touch-optimierte Anwendung für Android-Geräte.

#### Features:
- 📱 Touch-optimiertes Interface
- 🎵 Gleiche Funktionen wie Desktop-Version
- 💾 Persistente Gerätespeicherung
- 🔄 Background-Threading für Network-Scans
- 📊 Scrollbare Ansichten für kleine Displays
- **👥 Gruppen Tab:** Vereinfachte Multi-Room Steuerung
  - Checkbox-basierte Geräteauswahl
  - Schnelle Gruppenerstellung
  - Mobile-optimierte Bedienung

#### Installation (Entwicklung):
```bash
# Kivy installieren
pip install kivy>=2.2.0

# Zum Testen auf dem Desktop:
python gui_android.py
```

#### Android APK erstellen:
```bash
# Buildozer installieren (nur Linux!)
pip install buildozer

# Android-SDK wird automatisch heruntergeladen
buildozer android debug

# APK befindet sich dann in: bin/soundtouch-1.0.0-arm64-v8a-debug.apk
```

#### Installation auf Android:
1. APK auf Android-Gerät kopieren
2. "Unbekannte Quellen" in Android-Einstellungen erlauben
3. APK installieren
4. App öffnen und mit WLAN verbinden
5. "Scan" drücken um Geräte zu finden

---

## 🚀 Schnellstart

### Desktop (Linux/Windows)
```bash
# 1. Dependencies installieren
pip install PyQt5 PyQt5-multimedia requests

# 2. GUI starten
python gui_linux_windows.py

# 3. "Scan" klicken um Geräte zu finden
# 4. Gerät auswählen und steuern!
# 5. Media Player Tab: Musik-Ordner auswählen und streamen
# 6. Gruppen Tab: Multi-Room Gruppen erstellen
```

### Android
```bash
# Auf Linux-System:
# 1. Dependencies installieren
pip install kivy buildozer

# 2. APK bauen
buildozer android debug

# 3. APK auf Handy installieren
adb install bin/soundtouch-*.apk

# Oder APK per USB/Cloud übertragen
```

---

## 🎮 Funktionsübersicht

### Alle GUIs unterstützen:

#### Wiedergabesteuerung:
- ▶️ Play
- ⏸️ Pause  
- ⏭️ Next Track
- ⏮️ Previous Track
- 🔀 Shuffle
- 🔁 Repeat

#### Lautstärke:
- 🔊 Lautstärke-Slider (0-100)
- 🔇 Mute/Unmute

#### Presets:
- 🔢 Preset 1-6 (Schnellzugriff)

#### Weitere Funktionen:
- ⚡ Power On/Off
- 📻 Quellenauswahl (Radio, Bluetooth, AUX)
- 📊 Geräteinformationen anzeigen

### Desktop GUI (Linux/Windows) zusätzlich:

#### 🎵 Media Player:
- Lokale Musikordner durchsuchen
- Unterstützte Formate: MP3, FLAC, WAV, M4A, OGG, WMA, AAC
- Lokale Vorschau mit Fortschrittsbalken
- HTTP-Streaming-Server (automatisch gestartet)
- Direktes Streaming an SoundTouch-Geräte
- Hierarchische Dateiansicht (Ordner/Dateien)

#### 👥 Gruppen-Verwaltung:
- **Gruppe erstellen:**
  - Master-Gerät auswählen
  - Beliebig viele Slave-Geräte hinzufügen
  - Gruppen-Name vergeben
- **Gruppen-Steuerung:**
  - Synchronisierte Wiedergabe
  - Gemeinsame Lautstärkeregelung
  - Play/Pause/Skip für alle Geräte
- **Gruppen-Details:**
  - Liste aller Gruppenmitglieder
  - Master/Slave Übersicht
  - Geräte hinzufügen/entfernen

### Android GUI zusätzlich:

#### 👥 Vereinfachte Gruppen:
- Touch-optimierte Geräteauswahl
- Checkbox-basierte Gruppenerstellung
- Mobile-freundliche Bedienung

---

## 📋 Voraussetzungen

### Desktop (Linux/Windows):
- Python 3.7+
- PyQt5 + PyQt5-multimedia
- requests
- Netzwerkverbindung im gleichen Netz wie SoundTouch-Geräte
- Für Media Player: Lokale Musikdateien

### Android:
- Linux-System zum Bauen (Buildozer läuft nur auf Linux)
- Python 3.7+
- Kivy
- Buildozer (für APK-Erstellung)
- Android 5.0+ (API Level 21+) auf Zielgerät
- Ca. 1-2 GB freier Speicher für Build-Tools

---

## 🛠️ Entwicklung

### Projekt-Struktur:
```
Open-Soundtouch/
├── gui_linux_windows.py    # Desktop GUI (PyQt5) - Hauptanwendung
├── gui_media_player.py     # Media Player Widget (PyQt5)
├── gui_group_manager.py    # Gruppen-Manager Widget (PyQt5)
├── gui_android.py           # Android GUI (Kivy)
├── buildozer.spec          # Android Build-Konfiguration
├── soundtouch_lib.py       # Core Library + Group Manager
├── soundtouch_api.py       # REST API Server
├── soundtouch_devices.json # Gespeicherte Geräte
└── requirements.txt        # Python Dependencies
```

### Desktop GUI anpassen:
Die PyQt5-GUI kann leicht angepasst werden:
- **Farben:** In `apply_style()` Methode
- **Buttons:** In `create_control_tab()` hinzufügen
- **Layout:** Alle UI-Elemente in `init_ui()`
- **Media Player:** In `gui_media_player.py` - Server-Port, Dateiformate
- **Gruppen:** In `gui_group_manager.py` - Gruppen-Logik anpassen

### Android GUI anpassen:
Die Kivy-GUI:
- **Layout:** In `build_control_panel()` und `build_tabs()`
- **Farben:** Direkt in Button-Definitionen
- **Schriftgrößen:** Via `font_size` Parameter
- **Gruppen:** In `build_groups_panel()` - vereinfachte Logik

---

## 🐛 Troubleshooting

### Desktop GUI startet nicht:
```bash
# PyQt5 neu installieren
pip uninstall PyQt5 PyQt5-multimedia
pip install PyQt5>=5.15.0 PyQt5-multimedia>=5.15.0
```

### Media Player startet nicht:
```bash
# Prüfe, ob PyQt5-multimedia installiert ist
pip install PyQt5-multimedia

# Port bereits belegt?
# Ändere Port in gui_media_player.py, Zeile ~35:
self.server_port = 8888  # Zu anderem Port ändern
```

### Streaming funktioniert nicht:
1. ✅ Server muss gestartet sein (grüner Status)
2. ✅ Firewall prüfen (Port 8888 erlauben)
3. ✅ Gerät muss im gleichen Netzwerk sein
4. ✅ Musikdatei muss ausgewählt sein

### Keine Geräte gefunden:
1. ✅ Prüfen, ob im gleichen WLAN/Netzwerk
2. ✅ Firewall-Einstellungen prüfen (Port 8090)
3. ✅ SoundTouch-Geräte sind eingeschaltet
4. ✅ Netzwerk-Scanner mit höherer Thread-Zahl versuchen

### Gruppe erstellen schlägt fehl:
1. ✅ Alle Geräte müssen erreichbar sein
2. ✅ Geräte müssen auf gleicher Firmware-Version sein
3. ✅ Master-Gerät muss Multi-Room unterstützen
4. ✅ Keine Geräte doppelt in Gruppen verwenden

### Android APK Build schlägt fehl:
```bash
# Buildozer Cache löschen
buildozer android clean

# Neu bauen
buildozer android debug

# Bei Problemen: -v für verbose output
buildozer -v android debug
```

### Android App abstürzt:
- Logcat prüfen: `adb logcat | grep python`
- Permissions in Android-Einstellungen prüfen
- WLAN-Verbindung sicherstellen

---

## 🔧 Erweiterte Optionen

### Custom Port:
Die GUIs suchen standardmäßig auf Port 8090. Zum Ändern:
```python
# In soundtouch_lib.py, Zeile ~20
DEFAULT_PORT = 8091  # Dein Port
```

### Media Player Server Port:
```python
# In gui_media_player.py, Zeile ~35
self.server_port = 8888  # Ändere zu anderem Port
```

### Unterstützte Audio-Formate:
```python
# In gui_media_player.py, Zeile ~25
self.audio_extensions = {'.mp3', '.m4a', '.flac', '.wav', '.ogg', '.wma', '.aac'}
# Weitere Formate hinzufügen nach Bedarf
```

### Scan-Geschwindigkeit:
```python
# In gui_linux_windows.py, Zeile ~222
devices = discovery.scan(threads=100)  # Mehr Threads = schneller

# In gui_android.py, Zeile ~260  
devices = discovery.scan(threads=50)  # Für Android weniger Threads
```

### Auto-Refresh Intervall:
```python
# Desktop GUI, Zeile ~37
self.refresh_timer.start(5000)  # 5 Sekunden statt 2

# Android GUI, Zeile ~49
Clock.schedule_interval(self.update_now_playing, 5)  # 5 Sekunden
```

---

## 📝 API Integration

Alle GUIs nutzen die gleiche `soundtouch_lib.py`:

```python
from soundtouch_lib import SoundTouchController, SoundTouchGroupManager

# Gerät verbinden
controller = SoundTouchController("192.168.50.156")

# Befehle senden
controller.send_key("PLAY")
controller.set_volume(50)

# Status abfragen
info = controller.get_nowplaying()
print(f"Track: {info['track']}")

# Gruppen erstellen
devices = [...]  # Liste von Device-Dicts
group_manager = SoundTouchGroupManager(devices)

master = devices[0]
slaves = devices[1:3]
group_manager.create_group(master, slaves, "Meine Gruppe")

# Gruppe steuern
group_manager.send_command_to_group(0, "PLAY")
group_manager.set_group_volume(0, 50)
```

---

## 🎯 Geplante Features

- [x] Multiroom-Synchronisation ✅
- [x] Lokaler Media Player mit Streaming ✅
- [ ] Playlist-Verwaltung
- [ ] Equalizer-Steuerung
- [ ] Timer/Wecker-Funktion
- [ ] iOS App (KivyMD oder native)
- [ ] Web-Interface (bereits vorhanden als REST API!)
- [ ] Spotify/TuneIn Integration
- [ ] Album-Cover Anzeige

---

## 📄 Lizenz

Siehe Haupt-README des Projekts.

---

## 🙏 Credits

Entwickelt für Bose SoundTouch Geräte mit:
- **PyQt5** für Desktop GUIs
- **Kivy** für Android GUI  
- **Buildozer** für Android Packaging

---

## 💬 Support

Bei Fragen oder Problemen:
1. Prüfe diese README
2. Schaue in `docs/BOSE SOUNDTOUCH WEB API.md`
3. Teste die CLI-Tools zuerst: `python soundtouch_controller.py <IP> --status`

---

**Viel Spaß mit deinen SoundTouch-Geräten! 🎵**
