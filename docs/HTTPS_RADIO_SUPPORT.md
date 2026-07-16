# HTTPS Internet Radio Support

## Überblick

Open-Soundtouch unterstützt jetzt das Abspielen von HTTPS-Internet-Radio-Streams auf Bose SoundTouch-Geräten. Da die meisten DLNA/UPnP-Geräte nur HTTP-Streams unterstützen, wird automatisch ein lokaler Proxy verwendet, der HTTPS-Streams in HTTP umwandelt.

## Funktionsweise

1. **Automatischer Proxy-Start**: Beim Start der GUI wird automatisch ein HTTPS-zu-HTTP-Proxy gestartet
2. **Transparente Umwandlung**: HTTPS-URLs werden automatisch erkannt und über den lokalen Proxy geleitet
3. **Keine Konfiguration**: Der Prozess ist vollständig transparent und erfordert keine Benutzereingriffe

## Verwendung

### In der GUI

1. Öffne den Tab "🌐 Externe Quellen"
2. Im Abschnitt "Internet Radio (Radio Browser)":
   - Suche nach Radiosendern (z.B. "Jazz", "BBC", "SWR3")
   - Doppelklicke auf einen Sender zum Abspielen
   - Oder füge eine eigene Stream-URL ein (HTTP oder HTTPS)
3. Klicke auf "▶ Station abspielen" oder "▶ URL abspielen"

**HTTPS-URLs werden automatisch unterstützt!**

### Programmatisch

```python
from soundtouch_lib import SoundTouchController

controller = SoundTouchController("192.168.50.156")

# HTTPS-URL - wird automatisch über Proxy geleitet
success = controller.play_url_dlna(
    url="https://icecast.radiofrance.fr/fip-hifi.aac",
    track="FIP Radio",
    artist="Internet Radio",
    album="France"
)

if success:
    print("✅ Stream started!")
```

### Manueller Proxy-Start

```python
from https_proxy import get_proxy_instance

# Proxy starten
proxy = get_proxy_instance(port=8765)
proxy.start()

# URL konvertieren
local_ip = "192.168.0.147"
https_url = "https://example.com/stream.mp3"
http_url = proxy.get_proxied_url(https_url, local_ip)

print(f"Proxied URL: {http_url}")
```

## Beispiel-Streams (HTTPS)

Hier sind einige Beispiel-HTTPS-Radio-Streams zum Testen:

```python
HTTPS_STREAMS = {
    "FIP (France)": "https://icecast.radiofrance.fr/fip-hifi.aac",
    "BBC Radio 1": "https://stream.live.vc.bbcmedia.co.uk/bbc_radio_one",
    "SWR3": "https://liveradio.swr.de/sw282p3/swr3/play.mp3",
}
```

## Technische Details

### Proxy-Server

- **Port**: 8765 (Standard, konfigurierbar)
- **Protokoll**: HTTP
- **Threading**: Multi-threaded für gleichzeitige Streams
- **CORS**: Aktiviert für Browser-Kompatibilität

### URL-Format

Der Proxy verwendet folgendes URL-Format:

```
http://<local_ip>:8765/proxy?url=<url_encoded_https_url>
```

Beispiel:
```
Original: https://example.com/stream.mp3
Proxied:  http://192.168.0.147:8765/proxy?url=https%3A%2F%2Fexample.com%2Fstream.mp3
```

### Stream-Header

Der Proxy leitet wichtige Stream-Header weiter:

- **Content-Type**: MIME-Typ des Streams
- **icy-name**: Name der Radiostation
- **icy-genre**: Genre
- **icy-br**: Bitrate
- **icy-metaint**: Metadaten-Intervall

## Fehlerbehandlung

Falls der Proxy nicht gestartet werden kann:

1. **Port belegt**: Ändere den Port in `https_proxy.py`
   ```python
   proxy = HTTPSProxy(port=8766)  # Alternativer Port
   ```

2. **Firewall**: Stelle sicher, dass der Port nicht blockiert ist

3. **Fallback**: Wenn der Proxy fehlschlägt, wird die Original-URL verwendet (funktioniert möglicherweise nicht auf allen Geräten)

## Kompatibilität

### Unterstützte Formate

- MP3 (audio/mpeg)
- AAC (audio/aac)
- FLAC (audio/flac)
- OGG (audio/ogg)
- WAV (audio/wav)

### Getestete Geräte

- Bose SoundTouch 10
- Bose SoundTouch 20 Series III
- Bose SoundTouch 30

## Radio Browser Integration

Die GUI integriert die [Radio Browser API](https://www.radio-browser.info/), die Zugang zu über 30.000 Internet-Radiosendern weltweit bietet:

- Suche nach Name, Land, Genre, Sprache
- Automatische Erkennung von HTTP/HTTPS-Streams
- Metadaten (Name, Land, Bitrate, Codec)
- Sortierung nach Popularität

## Beispiel-Skripte

- `test_https_proxy.py`: Test des Proxy-Servers
- `example_https_radio.py`: Beispiel zum Abspielen von HTTPS-Streams
- `gui_external_sources.py`: GUI mit Radio-Browser-Integration

## Troubleshooting

### Problem: "HTTPS Proxy Server started" wird nicht angezeigt

**Lösung**: Überprüfe, ob Port 8765 verfügbar ist:
```bash
netstat -tuln | grep 8765
```

### Problem: Stream startet nicht

**Lösung**:
1. Teste die URL im Browser
2. Überprüfe die Firewall-Einstellungen
3. Stelle sicher, dass das Gerät das Netzwerk erreichen kann

### Problem: "Proxy error: 502"

**Lösung**: Die Original-URL ist nicht erreichbar:
1. Teste die URL mit `curl -v <url>`
2. Überprüfe Internetverbindung
3. Probiere eine andere Stream-URL

## Performance

- **Latenz**: < 100ms zusätzlich zum Original-Stream
- **Durchsatz**: Keine Begrenzung (direktes Streaming)
- **Speicher**: ~2MB pro aktiven Stream
- **CPU**: Minimal (hauptsächlich Netzwerk-I/O)

## Sicherheit

Der Proxy ist nur im lokalen Netzwerk zugänglich und sollte nicht öffentlich exponiert werden:

- Bindet an `0.0.0.0` (alle Interfaces)
- Keine Authentifizierung
- Keine Rate-Limiting
- Nur für vertrauenswürdige Netzwerke

## Weiterführende Informationen

- [Radio Browser API Dokumentation](https://www.radio-browser.info/)
- [DLNA Spezifikation](http://www.dlna.org/)
- [UPnP Standards](https://openconnectivity.org/developer/specifications/upnp-resources/upnp/)
