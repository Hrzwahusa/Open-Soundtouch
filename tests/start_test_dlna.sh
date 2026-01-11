#!/bin/bash
# Startet einen Test-DLNA-Server mit neuer UUID für Wireshark-Analyse

# Neue UUID generieren
NEW_UUID=$(uuidgen | tr '[:upper:]' '[:lower:]')

echo "🆔 Neue UUID: $NEW_UUID"

# Temporäres Config-Verzeichnis
TEST_DIR="/tmp/minidlna_test"
mkdir -p "$TEST_DIR/db" "$TEST_DIR/logs" "$TEST_DIR/pid"

# Config-Datei erstellen
cat > "$TEST_DIR/minidlna_test.conf" <<EOF
# Test DLNA Server für Wireshark-Analyse
port=8202
media_dir=A,/home/hans/Open-Soundtouch/test_music
friendly_name=TEST-DLNA-Server
db_dir=$TEST_DIR/db
log_dir=$TEST_DIR/logs
log_level=general,artwork,database,inotify,scanner,metadata,http,ssdp,tivo=warn
root_container=.
enable_subtitles=no
strict_dlna=no
notify_interval=30
inotify=yes
uuid=$NEW_UUID
EOF

# UUID in Datei speichern
echo "$NEW_UUID" > "$TEST_DIR/test_uuid.txt"

echo "📝 Config erstellt: $TEST_DIR/minidlna_test.conf"
echo ""

# Alten Test-Server stoppen falls vorhanden
sudo pkill -f "minidlnad.*8202" 2>/dev/null

# Server starten
echo "🚀 Starte Test-DLNA-Server auf Port 8202..."
sudo minidlnad -f "$TEST_DIR/minidlna_test.conf" -P "$TEST_DIR/pid/minidlna.pid"

sleep 2

# Prüfen ob läuft
if pgrep -f "minidlnad.*8202" > /dev/null; then
    echo "✅ Test-DLNA-Server läuft auf Port 8202"
    echo ""
    echo "📍 Details:"
    echo "   UUID:          $NEW_UUID"
    echo "   Port:          8202"
    echo "   Friendly Name: TEST-DLNA-Server"
    echo "   Config:        $TEST_DIR/minidlna_test.conf"
    echo ""
    echo "🔧 Nächste Schritte:"
    echo "   1. Wireshark starten und auf dein Netzwerk-Interface filtern"
    echo "   2. Filter setzen: http or ssdp"
    echo "   3. Gerät registrieren mit:"
    echo "      python register_dlna_device.py 192.168.50.19 192.168.50.218 8202"
    echo "   4. In offizieller Bose App 'TEST-DLNA-Server' hinzufügen"
    echo "   5. In App wieder löschen"
    echo "   6. Wireshark-Traffic analysieren"
    echo ""
    echo "🛑 Server stoppen mit:"
    echo "   sudo pkill -f 'minidlnad.*8202'"
else
    echo "❌ Server konnte nicht gestartet werden"
    exit 1
fi
