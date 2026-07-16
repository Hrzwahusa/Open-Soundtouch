#!/bin/sh
# Persistent Preset Proxy Manager
# Läuft auf der Bose Box und startet Proxies automatisch beim Boot
# Gespeichert in: /mnt/update/preset_proxy_manager.sh

CONFIG_FILE="/mnt/nv/preset_proxies.conf"
PROXY_SCRIPT="/mnt/nv/radio_proxy.sh"
LOG_FILE="/tmp/preset_proxy_manager.log"

log() {
    echo "[PresetMgr] $1" | tee -a "$LOG_FILE"
}

start_proxy() {
    PORT=$1
    URL=$2
    NAME=$3
    
    # Check if already running
    if ps | grep -v grep | grep "radio_proxy.sh $PORT" > /dev/null; then
        log "Proxy on port $PORT already running"
        return 0
    fi
    
    log "Starting proxy: Port $PORT - $NAME"
    "$PROXY_SCRIPT" "$PORT" "$URL" > /tmp/radio_proxy_$PORT.log 2>&1 &
    
    sleep 1
    
    # Verify
    if netstat -tln | grep ":$PORT " > /dev/null; then
        log "✓ Proxy started on port $PORT"
        return 0
    else
        log "✗ Failed to start proxy on port $PORT"
        return 1
    fi
}

stop_all_proxies() {
    log "Stopping all proxies..."
    pkill -f "$PROXY_SCRIPT"
    sleep 1
    log "✓ All proxies stopped"
}

load_and_start_proxies() {
    if [ ! -f "$CONFIG_FILE" ]; then
        log "No config file found: $CONFIG_FILE"
        log "Create config with format: PORT|URL|NAME"
        return 1
    fi
    
    log "Loading proxies from $CONFIG_FILE"
    
    while IFS='|' read -r port url name; do
        # Skip comments and empty lines
        [ -z "$port" ] && continue
        echo "$port" | grep -q "^#" && continue
        
        start_proxy "$port" "$url" "$name"
    done < "$CONFIG_FILE"
    
    log "✓ All proxies started"
}

show_status() {
    echo "=========================================="
    echo "  Preset Proxy Manager - Status"
    echo "=========================================="
    echo ""
    
    if [ -f "$CONFIG_FILE" ]; then
        echo "Configured proxies:"
        while IFS='|' read -r port url name; do
            [ -z "$port" ] && continue
            echo "$port" | grep -q "^#" && continue
            
            if netstat -tln | grep ":$port " > /dev/null 2>&1; then
                status="✓ RUNNING"
            else
                status="✗ STOPPED"
            fi
            
            echo "  Port $port: $name [$status]"
        done < "$CONFIG_FILE"
    else
        echo "No configuration file found."
        echo "Create: $CONFIG_FILE"
        echo "Format: PORT|URL|NAME"
    fi
    
    echo ""
    echo "Active radio_proxy.sh processes:"
    ps | grep radio_proxy.sh | grep -v grep | wc -l
    echo ""
}

# Main command handler
case "$1" in
    start)
        load_and_start_proxies
        ;;
    stop)
        stop_all_proxies
        ;;
    restart)
        stop_all_proxies
        sleep 2
        load_and_start_proxies
        ;;
    status)
        show_status
        ;;
    add)
        # Add new preset proxy
        if [ -z "$2" ] || [ -z "$3" ] || [ -z "$4" ]; then
            echo "Usage: $0 add <port> <url> <name>"
            echo "Example: $0 add 9001 'http://stream.example.com/radio.mp3' 'My Radio'"
            exit 1
        fi
        
        PORT=$2
        URL=$3
        NAME=$4
        
        # Create config if not exists
        touch "$CONFIG_FILE"
        
        # Check if port already in use
        if grep -q "^$PORT|" "$CONFIG_FILE"; then
            log "Port $PORT already configured. Remove first or use 'update'."
            exit 1
        fi
        
        # Add to config
        echo "$PORT|$URL|$NAME" >> "$CONFIG_FILE"
        log "✓ Added: Port $PORT - $NAME"
        
        # Start immediately
        start_proxy "$PORT" "$URL" "$NAME"
        ;;
    remove)
        if [ -z "$2" ]; then
            echo "Usage: $0 remove <port>"
            exit 1
        fi
        
        PORT=$2
        
        # Remove from config
        if [ -f "$CONFIG_FILE" ]; then
            grep -v "^$PORT|" "$CONFIG_FILE" > "$CONFIG_FILE.tmp"
            mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
            log "✓ Removed port $PORT from config"
        fi
        
        # Stop proxy
        pkill -f "radio_proxy.sh $PORT"
        log "✓ Stopped proxy on port $PORT"
        ;;
    autostart)
        # Enable autostart
        AUTOSTART_SCRIPT="/mnt/update/autostart_proxies.sh"
        
        cat > "$AUTOSTART_SCRIPT" << 'AUTOSTART_EOF'
#!/bin/sh
# Auto-start preset proxies on boot
sleep 5
/mnt/update/preset_proxy_manager.sh start
AUTOSTART_EOF
        
        chmod +x "$AUTOSTART_SCRIPT"
        log "✓ Autostart script created: $AUTOSTART_SCRIPT"
        log "  Add to init.d or cron for automatic startup"
        ;;
    *)
        echo "Preset Proxy Manager"
        echo ""
        echo "Usage:"
        echo "  $0 start              - Start all configured proxies"
        echo "  $0 stop               - Stop all proxies"
        echo "  $0 restart            - Restart all proxies"
        echo "  $0 status             - Show status"
        echo "  $0 add <port> <url> <name> - Add new preset"
        echo "  $0 remove <port>      - Remove preset"
        echo "  $0 autostart          - Create autostart script"
        echo ""
        echo "Config file: $CONFIG_FILE"
        echo "Format: PORT|URL|NAME (one per line)"
        echo ""
        exit 1
        ;;
esac
