#!/usr/bin/env python3
"""
HTTP Audio Stream Server for SoundTouch Radio Integration.
Streams MP3 files as a continuous stream (like TuneIn Radio).
SoundTouch can then play it as a "Radio" source.
"""

import os
import sys
import threading
import time
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from soundtouch_lib import SoundTouchController


class StreamHandler(BaseHTTPRequestHandler):
    """HTTP request handler for MP3 streaming."""
    protocol_version = "HTTP/1.1"  # allow chunked responses
    
    # Class variable to hold stream state
    stream_file = None
    is_playing = True
    
    def do_HEAD(self):
        """Respond to HEAD like GET but without body."""
        if self.path == '/stream':
            if not self.stream_file or not os.path.exists(self.stream_file):
                self.send_error(404, "Stream file not found")
                return
            self.send_response(200)
            self.send_header('Content-Type', 'audio/mpeg')
            self.send_header('Transfer-Encoding', 'chunked')
            self.end_headers()
        elif self.path == '/playlist.m3u' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'audio/x-mpegurl')
            self.send_header('Content-Length', '0')
            self.end_headers()
        else:
            self.send_error(404)
    
    def do_GET(self):
        """Handle GET request for audio stream or playlist."""
        if self.path == '/stream':
            self.stream_audio()
        elif self.path == '/playlist.m3u' or self.path == '/':
            self.serve_playlist()
        else:
            self.send_error(404)
    
    def serve_playlist(self):
        """Serve M3U playlist pointing to the audio stream."""
        if not self.stream_file:
            self.send_error(404, "Stream file not found")
            return
        
        # Create M3U playlist content
        filename = os.path.basename(self.stream_file)
        m3u_content = f"""#EXTM3U
#EXT-X-VERSION:3
#EXTINF:-1, {filename}
http://0.0.0.0:8888/stream
"""
        
        self.send_response(200)
        self.send_header('Content-Type', 'audio/x-mpegurl')
        self.send_header('Content-Length', str(len(m3u_content)))
        self.end_headers()
        
        self.wfile.write(m3u_content.encode('utf-8'))
    
    def stream_audio(self):
        """Stream the audio file using chunked transfer (no Content-Length)."""
        if not self.stream_file or not os.path.exists(self.stream_file):
            self.send_error(404, "Stream file not found")
            return
        
        self.send_response(200)
        self.send_header('Content-Type', 'audio/mpeg')
        self.send_header('Transfer-Encoding', 'chunked')
        self.end_headers()
        
        try:
            with open(self.stream_file, 'rb') as f:
                while StreamHandler.is_playing:
                    chunk = f.read(8192)
                    if not chunk:
                        f.seek(0)
                        chunk = f.read(8192)
                    if not chunk:
                        time.sleep(0.05)
                        continue
                    try:
                        # Write chunk size in hex + CRLF, then data + CRLF
                        self.wfile.write(f"{len(chunk):X}\r\n".encode('ascii'))
                        self.wfile.write(chunk)
                        self.wfile.write(b"\r\n")
                    except Exception as e:
                        print(f"Stream write error: {e}")
                        break
            # Send zero-length chunk to properly terminate (if loop exits)
            try:
                self.wfile.write(b"0\r\n\r\n")
            except Exception:
                pass
        except Exception as e:
            print(f"Stream error: {e}")
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def start_stream_server(port=8888):
    """Start the HTTP stream server in a background thread."""
    server = HTTPServer(('0.0.0.0', port), StreamHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"✅ Stream server started on port {port}")
    return server, thread


def register_as_radio(device_ip: str, stream_url: str, station_name: str = "OpenSoundtouch Radio", dlna_account: str = None):
    """
    Register the stream as a playable source with the SoundTouch device.
    Register the stream as a playable source with the SoundTouch device using DLNA/SOAP.
    
    The REST /select endpoint doesn't properly handle HTTP streams, so we use DLNA AVTransport
    which is the proper UPnP method for setting and playing media URLs.
    
    Args:
        device_ip: Device IP
        stream_url: HTTP URL of the stream
        station_name: Display name
        dlna_account: Not used (kept for compatibility)
    """
    controller = SoundTouchController(device_ip)
    
    print(f"📻 Registering as radio: {station_name}")
    print(f"   URL: {stream_url}")
    
    try:
        # Use DLNA/SOAP AVTransport method (port 8091) instead of REST /select
        # This is the proper UPnP method that actually works for playing streams
        result = controller.play_url_dlna(
            url=stream_url,
            artist="OpenSoundtouch",
            album="Stream Radio",
            track=station_name
        )
        
        if result:
            print(f"✅ Stream registered and playback started via DLNA!")
            return True
        else:
            print(f"❌ DLNA playback failed")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def ensure_playback_and_volume(controller: SoundTouchController, target_volume: int = 30, retries: int = 5, delay: float = 1.0):
    """Ensure device is playing and volume is audible.

    - Unmutes if muted
    - Raises volume to target if lower
    - Sends PLAY if not in PLAYING state
    """
    try:
        # Unmute if muted
        vol = controller.get_volume() or {}
        if vol.get('muteenabled'):
            controller.send_key('mute')
            time.sleep(delay)

        # Ensure volume >= target
        actual = int(vol.get('actualvolume', 0)) if vol else 0
        if target_volume and actual < target_volume:
            controller.set_volume(target_volume, mute=False)
            time.sleep(delay)

        # Nudge play state if needed
        for _ in range(max(1, retries)):
            np = controller.get_nowplaying() or {}
            status = (np.get('playStatus') or '').upper()
            if status == 'PLAYING':
                return True
            controller.send_key('play')
            time.sleep(delay)
        return False
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="MP3 Stream Radio Server for SoundTouch")
    parser.add_argument('device_ip', help='SoundTouch device IP')
    parser.add_argument('--file', required=True, help='MP3 file to stream')
    parser.add_argument('--port', type=int, default=8888, help='Stream server port (default: 8888)')
    parser.add_argument('--server-ip', required=True, help='IP address this server is accessible from (for device)')
    parser.add_argument('--name', default='OpenSoundtouch Radio', help='Radio station name')
    parser.add_argument('--volume', type=int, default=30, help='Ensure minimum volume on device (0 to skip)')
    args = parser.parse_args()
    
    # Validate file exists
    if not os.path.exists(args.file):
        print(f"❌ File not found: {args.file}")
        sys.exit(1)
    
    # Set stream file in handler
    StreamHandler.stream_file = args.file
    StreamHandler.is_playing = True
    
    print(f"🎵 Starting Stream Radio Server")
    print(f"   File: {args.file}")
    print(f"   File size: {os.path.getsize(args.file) / 1024 / 1024:.1f} MB")
    print()
    
    # Start stream server
    server, thread = start_stream_server(args.port)
    
    # Build stream URL
    stream_url = f"http://{args.server_ip}:{args.port}/stream"
    
    # Register with device
    print()
    time.sleep(1)
    success = register_as_radio(args.device_ip, stream_url, args.name)
    
    if not success:
        print("❌ Failed to register. Exiting.")
        sys.exit(1)

    # Post-start: ensure device is audible and actually playing
    try:
        controller = SoundTouchController(args.device_ip)
        if args.volume > 0:
            ok = ensure_playback_and_volume(controller, target_volume=args.volume)
            if ok:
                print(f"🔊 Ensured playback and volume ≥ {args.volume}")
            else:
                print("⚠️ Could not confirm PLAYING state; try pressing Play/raising volume")
    except Exception as e:
        print(f"⚠️ Post-start audio check failed: {e}")
    
    print()
    print("📻 Radio Stream Active!")
    print(f"   Device can now play: {stream_url}")
    print()
    print("💡 Controls on device:")
    print("   - Play/Pause: Works (pauses stream to device)")
    print("   - Stop: Works (stops stream)")
    print("   - Volume: Works normally")
    print()
    print("Press Ctrl+C to stop server")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping stream server...")
        StreamHandler.is_playing = False
        server.shutdown()
        print("✅ Server stopped")


if __name__ == "__main__":
    main()
