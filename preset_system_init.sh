#!/bin/sh
### BEGIN INIT INFO
# Provides:          preset_system
# Required-Start:    $network $local_fs
# Required-Stop:
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Start on-device radio preset system
### END INIT INFO

case "$1" in
    start)
        echo "Starting preset system..."

        # HINWEIS: Der lokale Proxy-Manager (radio_proxy.sh) wird NICHT mehr
        # gestartet – der Handler spielt Streams direkt per DLNA. Die Skripte
        # bleiben für einen späteren HTTPS-Proxy liegen, laufen aber nicht idle mit.

        # Start Rhino preset monitor (for physical buttons)
        if [ -x /mnt/nv/rhino_preset_monitor.sh ]; then
            /mnt/nv/rhino_preset_monitor.sh > /tmp/rhino_monitor.log 2>&1 &
            echo "  ✓ Rhino preset monitor started"
        fi
        
        # Start key interceptor (for REST API /key calls)
        if [ -x /mnt/nv/key_interceptor_daemon.sh ]; then
            /mnt/nv/key_interceptor_daemon.sh start >/dev/null 2>&1
            echo "  ✓ Key interceptor started"
        fi
        
        echo "Preset system ready"
        ;;
        
    stop)
        echo "Stopping preset system..."
        pkill -f preset_proxy_manager.sh
        pkill -f rhino_preset_monitor.sh
        pkill -f key_interceptor_daemon.sh
        pkill -f key_interceptor_cgi.sh
        pkill -f preset_handler_daemon.sh
        # Kill nc listeners and socat proxies
        pkill -f "nc -l.*8089"
        pkill socat
        echo "Preset system stopped"
        ;;
        
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
        
    status)
        echo "=== Preset System Status ==="
        echo "Proxy Manager:"
        ps aux | grep preset_proxy_manager | grep -v grep || echo "  Not running"
        echo ""
        echo "Rhino Monitor (physical buttons):"
        ps aux | grep rhino_preset_monitor | grep -v grep || echo "  Not running"
        echo ""
        echo "Key Interceptor (REST API):"
        ps aux | grep "key_interceptor\|nc.*8089" | grep -v grep || echo "  Not running"
        echo ""
        echo "Active Proxies:"
        ps aux | grep "socat.*9001\|9002\|9003\|9004\|9005\|9006" | grep -v grep || echo "  None"
        ;;
        
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac

exit 0
