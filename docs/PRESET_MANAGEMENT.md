# Preset Management - Store & Recall

## Übersicht

Die SoundTouch-Geräte unterstützen 6 Preset-Slots, in denen beliebige Inhalte gespeichert werden können (TuneIn Radio, Spotify Playlists, etc.). Mit den neuen Funktionen kannst du:

1. **Aktuell spielenden Inhalt als Preset speichern**
2. **Bestimmten Inhalt manuell als Preset speichern** (z.B. TuneIn Station)
3. **Gespeicherte Presets abrufen/abspielen**

## Python Library API

### 1. Presets abrufen

```python
from soundtouch_lib import SoundTouchController

device = SoundTouchController("192.168.1.100")

# Alle gespeicherten Presets abrufen
presets = device.get_presets()

for preset in presets:
    print(f"Preset {preset['id']}: {preset['itemName']}")
    print(f"  Source: {preset['source']}")
    print(f"  Location: {preset['location']}")
```

### 2. Aktuell spielenden Inhalt als Preset speichern

```python
# Aktuell spielende TuneIn-Station als Preset 1 speichern
device.store_preset(1)
```

### 3. Bestimmten Inhalt als Preset speichern

```python
# Spezifische TuneIn-Station als Preset speichern
content_item = {
    'source': 'TUNEIN',
    'location': '/v1/playback/station/s24939',  # Station ID
    'sourceAccount': 'your_tunein_account',     # Optional
    'itemName': 'Bayern 3',                      # Name für das Preset
    'isPresetable': 'true'
}

device.store_preset(2, content_item)
```

### 4. Preset abrufen/abspielen

```python
# Preset 1 abspielen
device.select_preset(1)
```

## REST API Endpoints

### GET /api/control/{device_ip}/presets

Alle gespeicherten Presets abrufen.

**Response:**
```json
{
  "presets": [
    {
      "id": "1",
      "source": "TUNEIN",
      "sourceAccount": "your_account",
      "itemName": "Bayern 3",
      "location": "/v1/playback/station/s24939",
      "isPresetable": "true"
    }
  ]
}
```

### POST /api/control/{device_ip}/presets

Preset speichern.

**Request Body (aktuell spielenden Inhalt speichern):**
```json
{
  "preset_id": 1
}
```

**Request Body (bestimmten Inhalt speichern):**
```json
{
  "preset_id": 2,
  "source": "TUNEIN",
  "location": "/v1/playback/station/s24939",
  "sourceAccount": "your_tunein_account",
  "itemName": "Bayern 3",
  "isPresetable": "true"
}
```

**Response:**
```json
{
  "status": "success",
  "device_ip": "192.168.1.100",
  "preset_id": 1
}
```

### POST /api/control/{device_ip}/presets/{preset_id}/select

Preset abrufen/abspielen.

**Response:**
```json
{
  "status": "success",
  "device_ip": "192.168.1.100",
  "preset_id": 1
}
```

## TuneIn Station IDs finden

### Methode 1: Aus Now Playing auslesen

1. Spiele die gewünschte Station auf dem SoundTouch-Gerät ab
2. Rufe die Now Playing Info ab:

```python
now_playing = device.get_now_playing()
print(f"Location: {now_playing.get('location')}")
# Output: /v1/playback/station/s24939
```

### Methode 2: Browser Developer Tools

1. Öffne die SoundTouch Web-App
2. Öffne Developer Tools (F12)
3. Gehe zum Network Tab
4. Spiele eine Station ab
5. Suche nach Requests an `/select` oder `/nowPlaying`
6. Schaue dir die XML-Payload an

## Beispiele

### TuneIn-Station als Preset speichern

```python
from soundtouch_lib import SoundTouchController

device = SoundTouchController("192.168.50.19")

# 1. Station abspielen (über TuneIn Browse oder direct)
device.select_content_item({
    'source': 'TUNEIN',
    'location': '/v1/playback/station/s24939'
})

# 2. Warte kurz bis Station läuft
import time
time.sleep(2)

# 3. Als Preset 1 speichern
device.store_preset(1)

# 4. Preset später abrufen
device.select_preset(1)
```

### Alle 6 Presets mit verschiedenen Sendern belegen

```python
stations = [
    {'name': 'Bayern 3', 'location': '/v1/playback/station/s24939'},
    {'name': 'WDR 2', 'location': '/v1/playback/station/s8007'},
    {'name': '1Live', 'location': '/v1/playback/station/s44491'},
    {'name': 'Bayern 1', 'location': '/v1/playback/station/s24941'},
    {'name': 'NDR 2', 'location': '/v1/playback/station/s8874'},
    {'name': 'SWR3', 'location': '/v1/playback/station/s8878'},
]

device = SoundTouchController("192.168.50.19")

for i, station in enumerate(stations, 1):
    print(f"Storing preset {i}: {station['name']}")
    
    content_item = {
        'source': 'TUNEIN',
        'location': station['location'],
        'itemName': station['name'],
        'isPresetable': 'true'
    }
    
    device.store_preset(i, content_item)
    time.sleep(0.5)  # Kurze Pause zwischen Requests

print("✅ All presets stored!")
```

## Test Script

Ein interaktives Test-Script ist verfügbar:

```bash
python test_preset_store.py 192.168.50.19
```

Das Script zeigt:
- Aktuell konfigurierte Presets
- Was gerade läuft
- Interaktive Optionen zum Speichern und Abrufen von Presets

## Wireshark-Analyse

Falls du weitere Details zur API benötigst, kannst du mit Wireshark den Traffic zwischen der Original SoundTouch App und dem Gerät mitschneiden:

1. **Wireshark starten** und auf das richtige Interface filtern
2. **Filter setzen:** `ip.addr == <device_ip> and tcp.port == 8090`
3. **In der SoundTouch App:** Station abspielen und als Preset speichern
4. **In Wireshark:** Nach `PUT /storePreset` suchen
5. **XML Payload ansehen** für exakte Struktur

Die Implementierung basiert auf:
- Offizieller Bose SoundTouch Web API Dokumentation
- Reverse Engineering der Original App
- BoseSoundTouchApi Library Reference Implementation

## Implementation Details

Die `store_preset()` Funktion:

1. Validiert Preset ID (1-6)
2. Falls kein Content Item übergeben wurde, holt sie die aktuell laufende Info via `/nowPlaying`
3. Baut XML-Payload mit allen erforderlichen Feldern
4. Sendet `PUT` Request an `/storePreset` Endpoint
5. Setzt automatisch `createdOn` und `updatedOn` Timestamps

Die `select_preset()` Funktion:

1. Validiert Preset ID (1-6)
2. Sendet `PRESET_X` Key Command an `/key` Endpoint
3. Gerät ruft gespeicherten Inhalt ab und startet Wiedergabe

## Limitations

- Maximal 6 Presets pro Gerät
- Nicht alle Sources sind als Preset speicherbar (prüfe `isPresetable` Attribut)
- Preset IDs müssen 1-6 sein (andere Werte werden abgelehnt)
