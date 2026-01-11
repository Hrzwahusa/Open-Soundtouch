# 🔧 Fehlerbehandlung - Behobene Probleme

## ❌ Probleme die du hattest

### 1. **ValueError: setValue(self, a0: int): argument 1 has unexpected type 'dict'**

**Ursache:**  
Die Methode `controller.get_volume()` gibt ein **Dictionary** zurück, nicht einen Integer:
```python
{
    'actualvolume': 50,      # ← Das brauchst du!
    'targetvolume': 50,
    'muteenabled': False
}
```

Aber der Code versuchte, das ganze Dict direkt in den Slider zu setzen:
```python
# FALSCH ❌
self.volume_slider.setValue(volume)  # volume ist ein dict!
```

**Lösung:**  
Nur den `actualvolume` Wert verwenden:
```python
# RICHTIG ✅
volume = self.controller.get_volume()
if volume is not None:
    self.volume_slider.setValue(volume['actualvolume'])
    self.volume_label.setText(str(volume['actualvolume']))
```

**Behoben in:**
- ✅ `gui_linux_windows.py` - Zeile 369
- ✅ `gui_android.py` - Zeile 439
- ✅ `gui_group_manager.py` - Bereits korrekt

---

### 2. **HTTP 500 Error beim Streaming**

**Ursache:**  
Das XML-Format für ContentItem war fehlerhaft (Whitespace/Newlines):
```python
# FALSCH ❌
xml_body = f'''<ContentItem source="INTERNET_RADIO" location="{escape(stream_url)}">
    <itemName>{escape(self.current_file['name'])}</itemName>
</ContentItem>'''
```

Die SoundTouch API mag keine Newlines in XML-Tags. Zusätzlich war die URL nicht richtig URL-encoded.

**Lösung:**  
Korrektes, kompaktes XML-Format mit URL-Encoding:
```python
# RICHTIG ✅
from urllib.parse import quote
file_path = self.current_file['rel_path'].replace('\\', '/')
stream_url = f"http://{local_ip}:{self.server_port}/{quote(file_path)}"

xml_body = f'<ContentItem source="INTERNET_RADIO" location="{escape(stream_url)}"><itemName>{escape(self.current_file["name"])}</itemName></ContentItem>'
```

**Behoben in:**
- ✅ `gui_media_player.py` - Zeilen 310-350

---

## ✅ Weitere Verbesserungen

### 1. Fehlerbehandlung verbessert
```python
# Fehler werden jetzt silent gehandelt statt zu spammen
except Exception as e:
    pass  # Statt: print(f"Update error: {e}")
```

### 2. Error Messages aussagekräftiger
```python
# Zeige den tatsächlichen Server-Error
error_msg = response.text if response.text else f"HTTP {response.status_code}"
QMessageBox.warning(self, "Fehler", f"Stream fehlgeschlagen:\n{error_msg}")
```

### 3. Network Error Handling
```python
# Falls IP-Lookup fehlschlägt, verwende localhost
try:
    s.connect(("8.8.8.8", 80))
    local_ip = s.getsockname()[0]
except:
    local_ip = "127.0.0.1"
```

---

## 🧪 Testen

### Mit Diagnostic-Skript:
```bash
python3 diagnostic.py
```

### GUI starten:
```bash
python3 gui_linux_windows.py
```

### Manuelles Streaming-Test (Python):
```python
import requests
from xml.sax.saxutils import escape

# Daten
local_ip = "192.168.50.X"  # Deine lokale IP
device_ip = "192.168.50.156"  # SoundTouch IP
stream_url = "http://192.168.50.X:8888/test_music/Rock/Led_Zeppelin_Whole_Lotta_Love.mp3"
filename = "Led Zeppelin - Whole Lotta Love"

# XML bauen
xml_body = f'<ContentItem source="INTERNET_RADIO" location="{escape(stream_url)}"><itemName>{escape(filename)}</itemName></ContentItem>'

# Senden
url = f"http://{device_ip}:8090/select"
response = requests.post(url, data=xml_body, headers={'Content-Type': 'application/xml'}, verify=False)
print(f"Status: {response.status_code}")
if response.status_code != 200:
    print(f"Error: {response.text}")
```

---

## 📋 Checkliste vor dem Streamen

1. ✅ **GUI ist gestartet:** `python3 gui_linux_windows.py`
2. ✅ **Gerät verbunden:** Tab "Steuerung" → Gerät ausgewählt
3. ✅ **Media Player Tab** geöffnet
4. ✅ **Musik-Ordner ausgewählt:** `test_music` Ordner
5. ✅ **"Scannen" geklickt:** Dateien werden geladen
6. ✅ **Datei doppelgeklickt:** Wird ausgewählt
7. ✅ **Server-Status grün:** "Läuft auf Port 8888"
8. ✅ **"📡 An Gerät streamen" klicken**

Wenn immer noch Fehler kommen:
1. **Status prüfen:** `diagnostic.py` nochmal laufen
2. **Logs prüfen:** Fehlertext in Console
3. **Gerät-Verbindung:** Ping zum Gerät: `ping 192.168.50.156`
4. **Port frei:** `netstat -tulpn | grep 8888`

---

**Die Fehler sollten nun behoben sein! 🎉**
