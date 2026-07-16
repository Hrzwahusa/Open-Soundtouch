#!/bin/sh
# Minimal HTTP audio proxy for Bose SoundTouch
# Listens on a given port and forwards a remote stream with basic HTTP headers.

PORT="$1"
STREAM_URL="$2"

if [ -z "$PORT" ] || [ -z "$STREAM_URL" ]; then
    echo "Usage: $0 <port> <stream_url>"
    exit 1
fi

while true; do
    {
        echo -ne "HTTP/1.1 200 OK\r\n"
        echo -ne "Content-Type: audio/mpeg\r\n"
        echo -ne "Connection: close\r\n"
        echo -ne "Accept-Ranges: none\r\n"
        echo -ne "ICY-MetaInt: 0\r\n"
        echo -ne "\r\n"
        curl -s -L "$STREAM_URL"
    } | nc -l -p "$PORT"
    sleep 1
done
