# Stream Metadata Extraction

## Überblick

Open-Soundtouch kann jetzt automatisch Metadaten (Track, Artist, Album, etc.) von Internet-Radio-Streams extrahieren und in Echtzeit anzeigen.

## Funktionsweise

### ICY Metadata Protocol

Internet-Radio-Streams verwenden oft das **ICY Metadata Protocol** (auch bekannt als Shoutcast/Icecast Metadata), um Informationen über den aktuell gespielten Track zu übertragen:

1. Client sendet `Icy-MetaData: 1` Header
2. Server antwortet mit `icy-metaint` Header (z.B. 16000 Bytes)
3. Nach jeweils `icy-metaint` Bytes Audio-Daten folgt ein Metadaten-Block
4. Metadaten-Block enthält Informationen wie `StreamTitle='Artist - Track'`

### Automatische Extraktion

Der HTTPS-Proxy extrahiert automatisch:
- **StreamTitle**: Wird geparst in Artist und Track
- **icy-name**: Stationsname
- **icy-genre**: Genre
- **icy-br**: Bitrate
- **icy-url**: Website der Station

## Verwendung

### In der GUI

Die Metadaten werden automatisch aktualisiert:

1. Starte einen Internet-Radio-Stream im Tab "🌐 Externe Quellen"
2. Die Status-Anzeige zeigt initial den Stationsnamen
3. Nach ~5-10 Sekunden wird die Anzeige mit dem aktuellen Track aktualisiert
4. Die Metadaten werden alle 5 Sekunden aktualisiert

**Beispiel-Anzeige:**
```
▶ Daft Punk - One More Time
```

### Programmatisch

```python
from soundtouch_lib import SoundTouchController

controller = SoundTouchController("192.168.50.156")

# Stream starten
controller.play_url_dlna(
    url="https://icecast.radiofrance.fr/fip-hifi.aac",
    track="FIP Radio",
    artist="Radio France"
)

# Warten bis Stream läuft
import time
time.sleep(10)

# Metadaten abrufen
metadata = controller.get_stream_metadata()
if metadata:
    print(f"Track: {metadata['track']}")
    print(f"Artist: {metadata['artist']}")
    print(f"Station: {metadata['station_name']}")
    print(f"Genre: {metadata['genre']}")
    print(f"Bitrate: {metadata['bitrate']} kbps")
```

### Automatische Updates

Die GUI aktualisiert Metadaten automatisch:

```python
# In gui_linux_windows.py
def update_now_playing(self):
    # Aktualisiert Stream-Metadaten
    self.controller.update_nowplaying_from_stream()
    
    # Holt aktualisierte Metadaten
    info = self.controller.get_nowplaying()
    if info:
        self.track_label.setText(f"Track: {info.track}")
        self.artist_label.setText(f"Artist: {info.artist}")
```

## API Referenz

### HTTPSProxy

```python
from https_proxy import get_proxy_instance

proxy = get_proxy_instance()

# Metadaten für URL abrufen
metadata = proxy.get_stream_metadata("https://example.com/stream.mp3")

# Rückgabewert:
{
    'url': 'http://...',
    'title': 'Artist - Track',
    'artist': 'Artist Name',
    'track': 'Track Name',
    'album': 'Internet Radio',
    'genre': 'Jazz',
    'bitrate': '128',
    'station_name': 'Cool Radio',
    'last_update': 1705234567.89  # Unix timestamp
}
```

### SoundTouchController

```python
from soundtouch_lib import SoundTouchController

controller = SoundTouchController("192.168.50.156")

# Metadaten vom aktuellen Stream abrufen
metadata = controller.get_stream_metadata()

# Metadaten aktualisieren und in override_nowplaying speichern
controller.update_nowplaying_from_stream()

# Aktuellen Status abrufen (inkl. Stream-Metadaten)
status = controller.get_nowplaying()
```

## Metadata-Objekt

### StreamMetadata Klasse

```python
class StreamMetadata:
    url: str              # Stream URL
    title: str            # Voller Titel (Artist - Track)
    artist: str           # Artist Name
    track: str            # Track Name
    album: str            # Album (meist "Internet Radio")
    genre: str            # Genre
    bitrate: str          # Bitrate (z.B. "128")
    station_name: str     # Stationsname
    last_update: float    # Letztes Update (Unix timestamp)
    
    def update_from_icy(self, icy_metadata: str):
        """Parse ICY metadata string."""
        # StreamTitle='Artist - Track'
        # StreamUrl='http://...'
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
```

## Beispiel: Live-Metadaten anzeigen

```python
#!/usr/bin/env python3
import time
from soundtouch_lib import SoundTouchController

def monitor_stream_metadata(device_ip: str, stream_url: str, duration: int = 60):
    """Monitor stream metadata for specified duration."""
    controller = SoundTouchController(device_ip)
    
    # Start stream
    print(f"▶️  Starting stream: {stream_url}")
    controller.play_url_dlna(url=stream_url, track="Radio", artist="Internet Radio")
    
    print(f"⏱️  Monitoring for {duration} seconds...")
    print()
    
    last_track = None
    
    for i in range(duration):
        time.sleep(1)
        
        # Get current metadata
        metadata = controller.get_stream_metadata()
        
        if metadata:
            current_track = f"{metadata.get('artist')} - {metadata.get('track')}"
            
            # Only print when track changes
            if current_track != last_track:
                print(f"🎵 Now Playing: {current_track}")
                print(f"   Station: {metadata.get('station_name', 'Unknown')}")
                print(f"   Genre: {metadata.get('genre', 'Unknown')}")
                print()
                last_track = current_track
        
        # Show progress
        print(f"\r   [{i+1}/{duration}s]", end="", flush=True)
    
    print()
    print("✅ Monitoring complete!")

if __name__ == "__main__":
    # Example usage
    DEVICE_IP = "192.168.50.156"  # ⚠️ Change this!
    STREAM_URL = "https://icecast.radiofrance.fr/fip-hifi.aac"
    
    monitor_stream_metadata(DEVICE_IP, STREAM_URL, duration=120)
```

## Supported Formats

### Audio Codecs
- MP3 (audio/mpeg)
- AAC (audio/aac, audio/aacp)
- OGG Vorbis (audio/ogg)
- FLAC (audio/flac)
- WAV (audio/wav)

### Metadata Formats
- **ICY/Shoutcast**: `StreamTitle='...'`
- **Icecast**: HTTP headers (`icy-name`, `icy-genre`, etc.)

## Troubleshooting

### Problem: Keine Metadaten erkennbar

**Ursachen:**
1. Stream sendet keine ICY-Metadaten
2. Stream verwendet anderes Metadaten-Format
3. Zu kurze Wartezeit

**Lösung:**
```python
# Längere Wartezeit für Metadaten
import time
time.sleep(15)  # Warte 15 Sekunden

metadata = controller.get_stream_metadata()
if not metadata or not metadata.get('track'):
    print("⚠️ Stream sendet keine Metadaten")
```

### Problem: Metadaten veraltet

**Lösung:**
```python
# Prüfe last_update timestamp
metadata = controller.get_stream_metadata()
if metadata:
    age = time.time() - metadata.get('last_update', 0)
    if age > 60:
        print(f"⚠️ Metadaten sind {age:.0f}s alt")
```

### Problem: Artist/Track nicht korrekt getrennt

**Ursache:** Stream verwendet anderes Format als `Artist - Track`

**Lösung:**
```python
# Manuelles Parsing
title = metadata.get('title', '')
if ':' in title:
    parts = title.split(':', 1)
    artist = parts[0].strip()
    track = parts[1].strip()
```

## Debug-Modus

Um die Metadaten-Extraktion zu debuggen:

```python
# Aktiviere Debug-Ausgabe in https_proxy.py
class HTTPSProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(format % args)  # Zeige Logs

# Dann wird jedes ICY-Metadaten-Update ausgegeben:
# 📻 ICY Metadata: StreamTitle='Daft Punk - One More Time';
```

## Performance

- **Latenz**: < 5 Sekunden für erste Metadaten
- **Update-Frequenz**: Abhängig vom Stream (meist 10-30 Sekunden)
- **Speicher**: ~100 Bytes pro Stream
- **CPU**: Minimal (nur beim Parsen von Metadaten)

## Bekannte Einschränkungen

1. **Keine Duration/Position**: Internet-Radio-Streams haben keine feste Länge
2. **Nur Text-Metadaten**: Cover-Art wird nicht unterstützt
3. **Format-Abhängig**: Nicht alle Streams senden Metadaten
4. **Verzögerung**: Metadaten können bis zu 30 Sekunden verzögert sein

## Beispiel-Streams mit ICY-Metadaten

Zum Testen der Metadaten-Extraktion:

```python
TEST_STREAMS = {
    "FIP (France)": {
        "url": "https://icecast.radiofrance.fr/fip-hifi.aac",
        "metadata": "✅ Excellent (Artist, Track, Genre, Bitrate)"
    },
    "SomaFM Groove Salad": {
        "url": "https://ice1.somafm.com/groovesalad-256-mp3",
        "metadata": "✅ Good (Artist, Track)"
    },
    "BBC Radio 1": {
        "url": "https://stream.live.vc.bbcmedia.co.uk/bbc_radio_one",
        "metadata": "⚠️ Limited (Only station name)"
    },
}
```

## Integration mit GUI

Die GUI zeigt Metadaten automatisch an mehreren Stellen:

1. **Tab "Steuerung"**: Aktuelle Wiedergabe
   - Track Label
   - Artist Label
   - Album Label

2. **Tab "Externe Quellen"**: Stream-Status
   - Live-Update des aktuellen Tracks
   - Farbcodierung (Grün = läuft, Rot = Fehler)

3. **Media Player**: Playlist-Info
   - Zeigt Metadaten von lokalen und Stream-Dateien

## Weiterführende Informationen

- [ICY Protocol Specification](http://www.smackfu.com/stuff/programming/shoutcast.html)
- [Icecast Streaming Media Server](https://icecast.org/)
- [Shoutcast Documentation](https://wiki.shoutcast.com/)
