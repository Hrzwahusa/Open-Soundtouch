#!/bin/sh
# Preset Handler Daemon
# Fängt Preset-Tastendruck ab und spielt lokale Radio-Streams
# Läuft dauerhaft im Hintergrund auf der Box

DEVICE_IP="127.0.0.1"
DEVICE_PORT="8090"
CONFIG_FILE="/mnt/nv/preset_proxies.conf"
PROXY_MANAGER="/mnt/nv/preset_proxy_manager.sh"
LOG_FILE="/tmp/preset_handler.log"
PID_FILE="/tmp/preset_handler.pid"

log() {
    echo "[$(date '+%H:%M:%S')] $1" >> "$LOG_FILE"
}

play_preset() {
    PRESET_ID=$1

    # Load preset config
    if [ ! -f "$CONFIG_FILE" ]; then
        log "No config file: $CONFIG_FILE"
        return 1
    fi

    # Find preset in config. Format: N|URL|NAME  (N = 1..6)
    PRESET_LINE=$(grep "^$PRESET_ID|" "$CONFIG_FILE" | grep -v '^#' | head -1)
    if [ -z "$PRESET_LINE" ]; then
        log "Preset $PRESET_ID not configured"
        return 1
    fi

    URL=$(echo "$PRESET_LINE" | cut -d'|' -f2)
    NAME=$(echo "$PRESET_LINE" | cut -d'|' -f3)
    [ -z "$NAME" ] && NAME="Preset $PRESET_ID"

    if [ -z "$URL" ]; then
        log "Preset $PRESET_ID has no URL"
        return 1
    fi

    log "Playing Preset $PRESET_ID: $NAME -> $URL"

    # '&' in der URL für XML escapen (& -> &amp;)
    URL_ESC=$(echo "$URL" | sed 's/&/\&amp;/g')
    CTRL="http://127.0.0.1:8091/AVTransport/Control"

    # DIDL-Lite Metadaten (doppelt-escaped für das SOAP-Feld)
    META="&lt;DIDL-Lite xmlns=&quot;urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/&quot; xmlns:dc=&quot;http://purl.org/dc/elements/1.1/&quot; xmlns:upnp=&quot;urn:schemas-upnp-org:metadata-1-0/upnp/&quot;&gt;&lt;item id=&quot;0&quot; parentID=&quot;-1&quot; restricted=&quot;1&quot;&gt;&lt;dc:title&gt;$NAME&lt;/dc:title&gt;&lt;upnp:class&gt;object.item.audioItem.musicTrack&lt;/upnp:class&gt;&lt;res protocolInfo=&quot;http-get:*:audio/mpeg:*&quot;&gt;$URL_ESC&lt;/res&gt;&lt;/item&gt;&lt;/DIDL-Lite&gt;"

    # 1) SetAVTransportURI mit der DIREKTEN Stream-URL (kein lokaler Proxy nötig für http)
    SET_BODY="<?xml version=\"1.0\" encoding=\"utf-8\"?><s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body><u:SetAVTransportURI xmlns:u=\"urn:schemas-upnp-org:service:AVTransport:1\"><InstanceID>0</InstanceID><CurrentURI>$URL_ESC</CurrentURI><CurrentURIMetaData>$META</CurrentURIMetaData></u:SetAVTransportURI></s:Body></s:Envelope>"
    curl -s -m 8 -X POST \
        -H "Content-Type: text/xml; charset=utf-8" \
        -H "SOAPACTION: \"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI\"" \
        -d "$SET_BODY" "$CTRL" > /dev/null

    # 2) Play
    PLAY_BODY="<?xml version=\"1.0\" encoding=\"utf-8\"?><s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body><u:Play xmlns:u=\"urn:schemas-upnp-org:service:AVTransport:1\"><InstanceID>0</InstanceID><Speed>1</Speed></u:Play></s:Body></s:Envelope>"
    curl -s -m 8 -X POST \
        -H "Content-Type: text/xml; charset=utf-8" \
        -H "SOAPACTION: \"urn:schemas-upnp-org:service:AVTransport:1#Play\"" \
        -d "$PLAY_BODY" "$CTRL" > /dev/null

    log "OK Preset $PRESET_ID ($NAME)"
    return 0
}

monitor_presets() {
    log "Starting preset monitor..."
    
    LAST_NOW_PLAYING=""
    
    while true; do
        # Poll /now_playing to detect preset button press
        NOW_PLAYING=$(curl -s "http://$DEVICE_IP:$DEVICE_PORT/now_playing" 2>/dev/null)
        
        # Check if it changed
        if [ "$NOW_PLAYING" != "$LAST_NOW_PLAYING" ]; then
            LAST_NOW_PLAYING="$NOW_PLAYING"
            
            # Try to detect if user pressed a preset button
            # We look for STANDBY or empty source (happens when preset not configured)
            if echo "$NOW_PLAYING" | grep -q 'source="STANDBY"'; then
                log "Detected possible preset press (STANDBY)"
                # Unfortunately we can't easily detect WHICH preset was pressed
                # without WebSocket monitoring
            fi
        fi
        
        sleep 1
    done
}

# Main
case "$1" in
    start)
        if [ -f "$PID_FILE" ]; then
            OLD_PID=$(cat "$PID_FILE")
            if kill -0 "$OLD_PID" 2>/dev/null; then
                echo "Preset handler already running (PID $OLD_PID)"
                exit 0
            fi
        fi
        
        echo "Starting preset handler daemon..."
        log "=== Preset Handler Started ==="
        
        # Start proxies first
        "$PROXY_MANAGER" start
        
        # Start monitoring in background
        monitor_presets &
        echo $! > "$PID_FILE"
        
        echo "✓ Preset handler started (PID $(cat $PID_FILE))"
        echo "  Log: $LOG_FILE"
        ;;
    
    stop)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                kill "$PID"
                rm -f "$PID_FILE"
                log "=== Preset Handler Stopped ==="
                echo "✓ Preset handler stopped"
            else
                echo "Preset handler not running"
                rm -f "$PID_FILE"
            fi
        else
            echo "Preset handler not running"
        fi
        ;;
    
    play)
        # Manual trigger: play specific preset
        if [ -z "$2" ]; then
            echo "Usage: $0 play <preset_id>"
            exit 1
        fi
        play_preset "$2"
        ;;
    
    status)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "✓ Preset handler running (PID $PID)"
                echo "  Log: $LOG_FILE"
                if [ -f "$LOG_FILE" ]; then
                    echo "  Last 5 log entries:"
                    tail -5 "$LOG_FILE" | sed 's/^/    /'
                fi
            else
                echo "✗ Preset handler not running (stale PID file)"
            fi
        else
            echo "✗ Preset handler not running"
        fi
        ;;
    
    *)
        echo "Preset Handler Daemon"
        echo ""
        echo "Usage:"
        echo "  $0 start   - Start daemon"
        echo "  $0 stop    - Stop daemon"
        echo "  $0 status  - Show status"
        echo "  $0 play <N> - Manually play preset N"
        echo ""
        echo "Manual preset playback (no daemon needed):"
        echo "  $0 play 1   - Play Preset 1"
        echo "  $0 play 2   - Play Preset 2"
        echo "  etc..."
        echo ""
        exit 1
        ;;
esac
