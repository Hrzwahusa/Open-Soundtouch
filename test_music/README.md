# 🎵 Test Musikbibliothek

Diese Verzeichnis enthält Sample-MP3-Dateien zum Testen des Media Players.

## 📁 Verzeichnisstruktur

```
test_music/
├── Jazz/              (5 Dateien)
│   ├── Charlie_Parker_Ornithology.mp3
│   ├── Herbie_Hancock_Maiden_Voyage.mp3
│   ├── John_Coltrane_A_Love_Supreme.mp3
│   ├── Miles_Davis_Kind_of_Blue.mp3
│   └── Thelonius_Monk_Round_Midnight.mp3
│
├── Klassik/           (3 Dateien)
│   ├── Bach_Invention.mp3
│   ├── Beethoven_Symphonie.mp3
│   └── Mozart_Requiem.mp3
│
└── Rock/              (4 Dateien)
    ├── Led_Zeppelin_Whole_Lotta_Love.mp3
    ├── Pink_Floyd_Comfortably_Numb.mp3
    ├── Queen_Bohemian.mp3
    └── The_Beatles_Hey_Jude.mp3
```

## 🎧 Technische Details

- **Format:** MP3 (MPEG-1 Audio Layer III)
- **Bitrate:** 128-192 kbps
- **Sample Rate:** 44,1 kHz (CD-Qualität)
- **Dauer:** 3 Sekunden pro Datei
- **Codec:** libmp3lame
- **Dateigröße:** ~13 KB pro Datei
- **Gesamt:** 12 Dateien = ~156 KB

## 🎹 Frequenzen (zur schnellen Unterscheidung)

### Klassik
- **Beethoven:** 440 Hz (A4 - Kammerton)
- **Mozart:** 523 Hz (C5)
- **Bach:** 587 Hz (D5)

### Jazz
- **Miles Davis:** 220 Hz (A3)
- **John Coltrane:** 246 Hz (B3)
- **Herbie Hancock:** 277 Hz (C#4)
- **Thelonious Monk:** 261 Hz (C4)
- **Charlie Parker:** 293 Hz (D4)

### Rock
- **Led Zeppelin:** 300 Hz
- **Queen:** 350 Hz
- **Pink Floyd:** 400 Hz
- **The Beatles:** 329 Hz (E4)

## 🎯 Verwendung

### Mit Media Player GUI:
1. Öffne `gui_linux_windows.py`
2. Gehe zum **"🎵 Media Player"** Tab
3. Klicke **"Durchsuchen"**
4. Navigiere zu diesem `test_music` Ordner
5. Klicke **"Scannen"**
6. Dateien sollten in hierarchischer Baumansicht erscheinen
7. **Doppelklick** zum Auswählen
8. **"🔊 Vorschau"** zum Anhören
9. **"📡 An Gerät streamen"** zum Streamen

### Mit kommandozeile:
```bash
# Alle MP3s auflisten
find ./test_music -name "*.mp3" -type f

# Nach Genre filtern
ls ./test_music/Jazz/
ls ./test_music/Rock/
ls ./test_music/Klassik/

# Metadaten anschauen
ffprobe "./test_music/Jazz/Miles_Davis_Kind_of_Blue.mp3"
```

## 🔧 Mehr Dateien hinzufügen

Du kannst leicht mehr Test-Dateien generieren:

```bash
# Neue Kategorie erstellen
mkdir -p ./test_music/Pop

# MP3 generieren (3 Sekunden, 440 Hz Sinus-Ton)
ffmpeg -f lavfi -i "sine=frequency=440:duration=3" \
  -q:a 9 -codec:a libmp3lame -ar 44100 -b:a 128k \
  "./test_music/Pop/Song_Name.mp3" -y

# Mit eigener WAV-Datei (wenn vorhanden)
ffmpeg -i "input.wav" -q:a 9 -codec:a libmp3lame \
  "./test_music/Pop/Song_Name.mp3" -y
```

## 📝 Dateitypen die der Media Player unterstützt

```python
# Aus gui_media_player.py
audio_extensions = {
    '.mp3',   # ✅ MPEG-1 Audio Layer III
    '.m4a',   # ✅ MPEG-4 Audio
    '.flac',  # ✅ Free Lossless Audio Codec
    '.wav',   # ✅ Waveform Audio File Format
    '.ogg',   # ✅ Ogg Vorbis
    '.wma',   # ✅ Windows Media Audio
    '.aac'    # ✅ Advanced Audio Coding
}
```

## 💡 Tipps

1. **Für realistisches Testen:** Nutze echte Musikdateien statt diese Sine-Wellen
2. **Performance-Test:** Füge mehrere Hundert Dateien hinzu
3. **Format-Test:** Konvertiere Dateien in verschiedene Formate
4. **Bitrate-Test:** Generiere Dateien mit verschiedenen Bitraten (128k, 192k, 320k)

## 🗑️ Cleanup

Falls du die Test-Musikbibliothek löschen möchtest:

```bash
rm -rf ./test_music/
```

---

**Zum Testen des Media Players bereit! 🎵**
