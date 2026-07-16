#!/bin/sh
# Key Interceptor Daemon (BusyBox nc -e based)
# Listens on 8089 and executes CGI script per connection,
# then forwards to real Bose HTTP server (127.0.0.1:8090).

LISTEN_PORT=8089
BACKEND_PORT=8090
CGI_SCRIPT="/mnt/nv/key_interceptor_cgi.sh"
PID_FILE="/tmp/key_interceptor.pid"
LOG_FILE="/tmp/key_interceptor.log"

log(){ echo "[$(date '+%H:%M:%S')] $*" >> "$LOG_FILE"; }

start_server(){
    log "=== Key Interceptor Started ==="
    log "Listening on 0.0.0.0:$LISTEN_PORT (nc loop)"
    # Loop single-shot nc to avoid bind races/hangs
    while true; do
        nc -l -p "$LISTEN_PORT" -e "$CGI_SCRIPT"
        sleep 0.1
    done
}

case "$1" in
    start)
        if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "✗ Interceptor already running (PID $(cat "$PID_FILE"))"
            exit 0
        fi
        echo "Starting key interceptor..."
        start_server &
        echo $! > "$PID_FILE"
        sleep 1
        if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "✓ Key interceptor started (PID $(cat "$PID_FILE"))"
            echo "  Listening: 0.0.0.0:$LISTEN_PORT"
            echo "  Log: $LOG_FILE"
        else
            echo "✗ Failed to start interceptor"
            rm -f "$PID_FILE"
            exit 1
        fi
        ;;
    stop)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                kill "$PID"
                pkill -P "$PID" 2>/dev/null
                log "=== Key Interceptor Stopped ==="
                echo "✓ Interceptor stopped"
            fi
            rm -f "$PID_FILE"
        else
            echo "Interceptor not running"
        fi
        ;;
    status)
        if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "✓ Interceptor running (PID $(cat "$PID_FILE"))"
            if [ -f "$LOG_FILE" ]; then
                echo "  Last 5 events:"; tail -5 "$LOG_FILE" | sed 's/^/    /'
            fi
        else
            echo "✗ Interceptor not running"
        fi
        ;;
    restart)
        $0 stop; sleep 1; $0 start;;
    *)
        echo "Key Interceptor Daemon"
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1;;
esac
