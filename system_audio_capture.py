#!/usr/bin/env python3
"""
System Audio Capture for Bose SoundTouch
Captures all system audio and streams it to Bose via DLNA.

Supports:
- Linux: PulseAudio/PipeWire
- Windows: WASAPI Loopback
- Android: TODO (Step 2)
"""

import platform
import subprocess
import threading
import time
import socket
import os
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn


class SystemAudioCapture:
    """Capture system audio and stream to Bose via DLNA."""
    
    def __init__(self):
        self.system = platform.system()
        self.is_capturing = False
        self.capture_process = None
        self.http_server = None
        self.server_thread = None
        self.port = 8766
        self.ffmpeg_pipe = None
        self.ffmpeg_bin = None  # aufgelöster Pfad zur ffmpeg-Binary
        self.sample_rate = 44100
        self.channels = 2
        self.stream_format = 'wav'   # 'wav' (roh-PCM, Linux) oder 'mp3' (WASAPI-Loopback)
        self._pa = None              # PyAudio-Instanz (WASAPI-Loopback)
        self._loopback_stream = None
        self._pcm_thread = None
        self._pcm_stop = False
        self._pipe_w = None          # Schreib-Ende der OS-Pipe (roh-PCM)

    def _find_ffmpeg(self):
        """Findet die ffmpeg-Binary: PATH, imageio-ffmpeg, gängige Installationspfade."""
        import shutil
        import os
        p = shutil.which("ffmpeg")
        if p:
            return p
        # pip-Paket imageio-ffmpeg bringt eine Binary mit
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and os.path.isfile(exe):
                return exe
        except Exception:
            pass
        # winget (Gyan.FFmpeg) installiert ohne PATH-Shim in einen versionierten
        # Unterordner unter WinGet\Packages -> rekursiv suchen.
        try:
            import glob
            localappdata = os.environ.get("LOCALAPPDATA", "")
            if localappdata:
                pkgs = os.path.join(localappdata, "Microsoft", "WinGet", "Packages")
                for pat in ("*Gyan.FFmpeg*", "*[Ff][Ff]mpeg*"):
                    hits = glob.glob(os.path.join(pkgs, pat, "**", "ffmpeg.exe"), recursive=True)
                    if hits:
                        return hits[0]
        except Exception:
            pass
        candidates = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe"),
            os.path.expandvars(r"%ProgramFiles%\ffmpeg\bin\ffmpeg.exe"),
            os.path.expandvars(r"%USERPROFILE%\scoop\shims\ffmpeg.exe"),
            r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
            "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg",
        ]
        for c in candidates:
            if c and os.path.isfile(c):
                return c
        return None

    _FFMPEG_INSTALL_MSG = (
        "FFmpeg nicht gefunden. Bitte installieren und die App neu starten:\n"
        "  • Windows:  winget install Gyan.FFmpeg   (danach App neu starten)\n"
        "  • oder von https://ffmpeg.org/download.html laden und bin-Ordner zum PATH hinzufügen\n"
        "  • oder:  pip install imageio-ffmpeg"
    )

    def detect_capabilities(self) -> dict:
        """
        Detect what audio capture methods are available on this system.
        
        Returns:
            dict with 'available', 'method', 'message'
        """
        if self.system == "Linux":
            return self._detect_linux()
        elif self.system == "Windows":
            return self._detect_windows()
        else:
            return {
                'available': False,
                'method': None,
                'message': f'System audio capture not yet supported on {self.system}'
            }
    
    def _detect_linux(self) -> dict:
        """Detect Linux audio system."""
        self.ffmpeg_bin = self._find_ffmpeg()
        if not self.ffmpeg_bin:
            return {'available': False, 'method': None, 'message': self._FFMPEG_INSTALL_MSG}
        # Check for PipeWire
        try:
            result = subprocess.run(['pw-cli', 'info'], capture_output=True, timeout=2)
            if result.returncode == 0:
                return {
                    'available': True,
                    'method': 'pipewire',
                    'message': 'PipeWire detected - ready for system audio capture'
                }
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Check for PulseAudio
        try:
            result = subprocess.run(['pactl', 'info'], capture_output=True, timeout=2)
            if result.returncode == 0:
                return {
                    'available': True,
                    'method': 'pulseaudio',
                    'message': 'PulseAudio detected - ready for system audio capture'
                }
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        return {
            'available': False,
            'method': None,
            'message': 'Neither PulseAudio nor PipeWire found. Please install pulseaudio-utils or pipewire.'
        }
    
    def _detect_windows(self) -> dict:
        """Detect Windows audio capabilities."""
        self.ffmpeg_bin = self._find_ffmpeg()

        # Bevorzugt: WASAPI-Loopback (System-Ausgang ohne 'Stereo Mix') via
        # PyAudioWPatch. Braucht ffmpeg nur zum Kodieren (PCM -> MP3).
        has_loopback = False
        try:
            import pyaudiowpatch as pa
            p = pa.PyAudio()
            try:
                has_loopback = next(p.get_loopback_device_info_generator(), None) is not None
            finally:
                p.terminate()
        except Exception:
            has_loopback = False

        # Primär: WASAPI-Loopback streamt rohes PCM -> braucht KEIN ffmpeg.
        if has_loopback:
            return {
                'available': True,
                'method': 'wasapi_loopback',
                'message': 'Bereit',
            }
        # Fallback: alter dshow/'Stereo Mix'-Weg (braucht ffmpeg)
        if self.ffmpeg_bin:
            return {
                'available': True,
                'method': 'wasapi',
                'message': ("Bereit über dshow/'Stereo Mix' (WASAPI-Loopback nicht verfügbar – "
                            "für den zuverlässigen Weg: pip install PyAudioWPatch)"),
            }
        return {
            'available': False,
            'method': None,
            'message': "System-Audio-Capture nicht verfügbar. Bitte: pip install PyAudioWPatch",
        }
    
    def start_capture(self, device_ip: str) -> bool:
        """
        Start capturing system audio and streaming to Bose.
        
        Args:
            device_ip: IP address of Bose device
            
        Returns:
            True if capture started successfully
        """
        if self.is_capturing:
            print("⚠️ Already capturing")
            return False
        
        capabilities = self.detect_capabilities()
        if not capabilities['available']:
            print(f"❌ {capabilities['message']}")
            return False
        
        print(f"🎤 Starting system audio capture using {capabilities['method']}")
        
        # Start HTTP server for streaming
        if not self._start_http_server():
            return False
        
        # Get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Diagnose audio sources (Linux/PulseAudio; auf Windows harmlos)
        try:
            result = subprocess.run(['pactl', 'list', 'short', 'sources'],
                                   capture_output=True, text=True, timeout=2)
            monitor_found = any('.monitor' in l and 'null' not in l for l in result.stdout.splitlines())
            if not monitor_found:
                print("⚠️ No monitor source found - may capture mic instead of output")
        except Exception:
            pass

        # Capture-Backend starten (WASAPI-Loopback bevorzugt, sonst ffmpeg/dshow/pulse)
        if not self._start_capture_backend(capabilities['method']):
            self._stop_http_server()
            return False

        # Stream-URL passend zum tatsächlich erzeugten Format
        ext = 'mp3' if self.stream_format == 'mp3' else 'wav'
        stream_url = f"http://{local_ip}:{self.port}/stream.{ext}"
        
        # Allow streaming immediately
        self.is_capturing = True
        
        # Start playback immediately (no delay)
        # FFmpeg will produce data within ~100ms
        
        # Tell Bose to play the stream via DLNA
        from soundtouch_lib import SoundTouchController
        device = SoundTouchController(device_ip)
        
        success = device.play_url_dlna(
            stream_url,
            track="System Audio",
            artist="Computer",
            album="Live Capture (RAW PCM)"
        )
        
        if success:
            print(f"✅ System audio streaming to Bose at {stream_url}")
            return True
        else:
            print("❌ Failed to start playback on Bose")
            self.stop_capture()
            return False
    
    def stop_capture(self):
        """Stop capturing system audio."""
        if not self.is_capturing:
            return
        
        print("🛑 Stopping system audio capture")

        # Zuerst signalisieren, dass der HTTP-Handler-Loop aufhören soll
        self.is_capturing = False

        # HTTP-Server stoppen (Accept-Loop runter)
        self._stop_http_server()

        # WASAPI-Loopback (Stream + Pump-Thread + Pipe) sauber abbauen (hängt nicht)
        self._teardown_wasapi()

        # ffmpeg-Subprozess (nur beim Nicht-Loopback-Weg vorhanden)
        if self.capture_process:
            try:
                self.capture_process.terminate()
                self.capture_process.wait(timeout=5)
            except Exception:
                try:
                    self.capture_process.kill()
                except Exception:
                    pass
            self.capture_process = None

        # Clean up virtual sink if we created one (Linux)
        self._cleanup_virtual_monitor()

        print("✅ System audio capture stopped")
    
    def _cleanup_virtual_monitor(self):
        """Remove virtual sink if it exists."""
        try:
            # Check if our virtual sink exists
            result = subprocess.run(
                ['pactl', 'list', 'short', 'sinks'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            for line in result.stdout.splitlines():
                if 'bose_capture_sink' in line:
                    # Find module ID and unload it
                    modules = subprocess.run(
                        ['pactl', 'list', 'short', 'modules'],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    
                    for mod_line in modules.stdout.splitlines():
                        if 'bose_capture_sink' in mod_line:
                            parts = mod_line.split()
                            if parts:
                                module_id = parts[0]
                                subprocess.run(['pactl', 'unload-module', module_id], timeout=2)
                                print("🧹 Cleaned up virtual audio sink")
                                break
                    break
        except:
            pass
    
    def _start_capture_backend(self, method: str) -> bool:
        """Startet das passende Capture-Backend."""
        if method == 'wasapi_loopback':
            return self._start_wasapi_loopback_capture()
        return self._start_ffmpeg_capture(method)

    def _start_wasapi_loopback_capture(self) -> bool:
        """Windows: System-Ausgang per WASAPI-Loopback aufnehmen (PyAudioWPatch)
        und als rohes PCM (WAV) streamen – minimale Latenz, kein Encoding.
        """
        try:
            import pyaudiowpatch as pa

            self._pa = pa.PyAudio()

            # Loopback des Standard-Ausgabegeräts bevorzugen
            loopback = None
            try:
                wasapi = self._pa.get_host_api_info_by_type(pa.paWASAPI)
                default_out = self._pa.get_device_info_by_index(wasapi['defaultOutputDevice'])
                for lb in self._pa.get_loopback_device_info_generator():
                    if default_out['name'] in lb['name']:
                        loopback = lb
                        break
            except Exception:
                pass
            if loopback is None:
                loopback = next(self._pa.get_loopback_device_info_generator(), None)
            if loopback is None:
                print("❌ Kein WASAPI-Loopback-Gerät gefunden")
                self._pa.terminate(); self._pa = None
                return False

            self.sample_rate = int(loopback['defaultSampleRate'])
            self.channels = min(2, int(loopback['maxInputChannels'])) or 2
            chunk = 1024
            print(f"🎧 Loopback: {loopback['name']} ({self.sample_rate} Hz, {self.channels}ch) -> roh-PCM")

            self._loopback_stream = self._pa.open(
                format=pa.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                frames_per_buffer=chunk,
                input=True,
                input_device_index=loopback['index'],
            )

            # OS-Pipe: Pump-Thread schreibt PCM hinein, HTTP-Handler liest heraus.
            # Kein ffmpeg -> keine Encoding-Latenz.
            read_fd, self._pipe_w = os.pipe()
            self.ffmpeg_pipe = os.fdopen(read_fd, 'rb', buffering=0)
            self.capture_process = None
            self.stream_format = 'wav'
            self._pcm_stop = False

            def _pump():
                try:
                    while not self._pcm_stop:
                        data = self._loopback_stream.read(chunk, exception_on_overflow=False)
                        os.write(self._pipe_w, data)
                except Exception:
                    pass
                finally:
                    try:
                        os.close(self._pipe_w)
                    except Exception:
                        pass
                    self._pipe_w = None

            self._pcm_thread = threading.Thread(target=_pump, daemon=True)
            self._pcm_thread.start()

            print(f"✅ WASAPI-Loopback läuft -> roh-PCM/WAV ({self.sample_rate} Hz)")
            return True

        except Exception as e:
            print(f"❌ WASAPI-Loopback fehlgeschlagen: {e}")
            self._teardown_wasapi()
            return False

    def _teardown_wasapi(self):
        """Räumt WASAPI-Loopback-Ressourcen ab – hängt garantiert nicht.

        Reihenfolge ist entscheidend:
        1) Stop-Flag setzen.
        2) Read-Ende der Pipe schließen. Falls der Pump-Thread im os.write auf eine
           volle Pipe blockiert (Netzwerk-Gegendruck von der Box), bekommt er so
           EPIPE und bricht ab – sonst würde er das Stop-Flag nie sehen.
        3) Pump-Thread joinen (endet jetzt zügig).
        4) ERST DANACH den PortAudio-Stream anfassen (nicht thread-safe: schließen
           während ein anderer Thread read() macht -> Deadlock/Absturz).
        """
        self._pcm_stop = True

        # (2) Read-Ende schließen -> blockiertes os.write im Pump-Thread wirft Fehler
        pipe = self.ffmpeg_pipe
        self.ffmpeg_pipe = None
        if pipe is not None:
            try:
                pipe.close()
            except Exception:
                pass

        # (3) Pump-Thread beenden (kann jetzt nicht mehr blockieren)
        t = self._pcm_thread
        if t is not None and t.is_alive():
            t.join(timeout=3)
        self._pcm_thread = None

        # (4) Jetzt ist kein Thread mehr am Stream -> sicher schließen
        if self._loopback_stream is not None:
            try:
                self._loopback_stream.stop_stream()
                self._loopback_stream.close()
            except Exception:
                pass
            self._loopback_stream = None
        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None
        # Write-End schließen (falls der Pump-Thread es nicht schon tat)
        if self._pipe_w is not None:
            try:
                os.close(self._pipe_w)
            except Exception:
                pass
            self._pipe_w = None

    def _start_ffmpeg_capture(self, method: str) -> bool:
        """Start FFmpeg process to capture and encode audio."""
        try:
            monitor_source = None
            if method in {'pulseaudio', 'pipewire'}:
                monitor_source = self._get_monitor_source()
                if monitor_source:
                    print(f"🎚️ Using monitor: {monitor_source}")
                else:
                    print("❌ No monitor source found - aborting to avoid streaming microphone")
                    return False
            
            if method == 'pulseaudio' or method == 'pipewire':
                # PulseAudio/PipeWire on Linux
                # EXTREME LOW LATENCY: Absolute minimum buffering
                cmd = [
                    self.ffmpeg_bin or 'ffmpeg',
                    '-loglevel', 'error',
                    # Zero probing/analysis
                    '-probesize', '32',
                    '-analyzeduration', '0',
                    # Ultra-low-latency input with real-time priority
                    '-f', 'pulse',
                    '-fragment_size', '64',  # Absolute minimum (32ms @ 44.1kHz)
                    '-i', monitor_source,
                    # RAW PCM output (zero encoding latency)
                    '-acodec', 'pcm_s16le',
                    '-ar', '44100',
                    '-ac', '2',
                    # Zero buffering everywhere
                    '-fflags', 'nobuffer+flush_packets',
                    '-flags', 'low_delay',
                    '-strict', 'experimental',
                    '-f', 's16le',
                    '-'
                ]
            elif method == 'wasapi':
                # Windows WASAPI Loopback
                # This captures the default audio output
                cmd = [
                    self.ffmpeg_bin or 'ffmpeg',
                    '-f', 'dshow',
                    '-i', 'audio=Stereo Mix',  # Common name, might need adjustment
                    '-acodec', 'libmp3lame',
                    '-b:a', '192k',
                    '-ar', '44100',
                    '-ac', '2',
                    '-f', 'mp3',
                    '-'
                ]
            else:
                print(f"❌ Unknown capture method: {method}")
                return False
            
            self.capture_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0  # Unbuffered
            )
            
            # Try to set real-time priority (best effort, requires privileges)
            try:
                import os
                # Set nice value to highest priority
                os.setpriority(os.PRIO_PROCESS, self.capture_process.pid, -20)
            except:
                pass  # Ignore if we don't have permissions
            
            # Store the pipe for the HTTP handler
            self.ffmpeg_pipe = self.capture_process.stdout
            
            print(f"✅ FFmpeg capture process started (PID: {self.capture_process.pid})")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start FFmpeg: {e}")
            return False
    
    def _start_http_server(self) -> bool:
        """Start HTTP server to stream captured audio."""
        try:
            # Create handler with reference to this capture instance
            handler = type('StreamHandler', (AudioStreamHandler,), {
                'capture_instance': self
            })
            
            self.http_server = ThreadingHTTPServer(('0.0.0.0', self.port), handler)
            self.server_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
            self.server_thread.start()
            
            print(f"✅ HTTP server started on port {self.port}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start HTTP server: {e}")
            return False

    def _get_monitor_source(self) -> Optional[str]:
        """Return PulseAudio/PipeWire monitor source (system output, NOT microphone monitor)."""
        try:
            # Env override for power users
            env_override = os.environ.get('PULSE_MONITOR_SOURCE')
            if env_override:
                return env_override

            # List all sources and filter for real system output monitors
            sources = subprocess.run(
                ['pactl', 'list', 'short', 'sources'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            # Collect monitors and filter out microphones/USB audio interfaces
            system_monitors = []
            mic_monitors = []
            
            for line in sources.stdout.splitlines():
                parts = line.split('\t')
                if len(parts) >= 2:
                    name = parts[1]
                    # only take monitor endpoints (playback)
                    if name.endswith('.monitor') and 'null' not in name:
                        # Skip USB microphones and audio interfaces
                        if any(x in name.lower() for x in ['microphone', 'mic', 'usb_mini', 'nt-usb']):
                            mic_monitors.append(name)
                            continue
                        system_monitors.append(name)
            
            # Prefer analog-stereo (usually main system output) over HDMI
            for monitor in system_monitors:
                if 'analog-stereo' in monitor and 'pci' in monitor:
                    return monitor
            
            # Then try any analog-stereo
            for monitor in system_monitors:
                if 'analog-stereo' in monitor:
                    return monitor
            
            # Then HDMI
            for monitor in system_monitors:
                if 'hdmi' in monitor:
                    return monitor
            
            # If we have any system monitor, use it
            if system_monitors:
                return system_monitors[0]
            
            # No system monitor found - create a virtual loopback sink
            print("⚠️ No system output monitor found, creating virtual audio sink...")
            return self._create_virtual_monitor()
                
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        except Exception:
            return None
        return None
    
    def _create_virtual_monitor(self) -> Optional[str]:
        """Create a virtual null sink for audio capture when no real output exists."""
        try:
            # Create a null sink that acts as virtual audio output
            result = subprocess.run(
                ['pactl', 'load-module', 'module-null-sink', 
                 'sink_name=bose_capture_sink',
                 'sink_properties=device.description="Bose_System_Audio_Capture"'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0:
                monitor_name = 'bose_capture_sink.monitor'
                print(f"✅ Created virtual sink: {monitor_name}")
                print("💡 Set this as your default output to capture all system audio")
                
                # Optionally set it as default (commented out - user might not want this)
                # subprocess.run(['pactl', 'set-default-sink', 'bose_capture_sink'], timeout=2)
                
                return monitor_name
            else:
                print(f"❌ Failed to create virtual sink: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating virtual sink: {e}")
            return None
    
    def _stop_http_server(self):
        """Stop HTTP server."""
        if self.http_server:
            self.http_server.shutdown()
            self.http_server = None
            self.server_thread = None


class AudioStreamHandler(BaseHTTPRequestHandler):
    """HTTP handler that streams captured audio."""
    
    def log_message(self, format, *args):
        # Suppress HTTP logs
        pass
    
    def do_GET(self):
        """Stream the captured audio (MP3 oder roh-PCM/WAV)."""
        if self.path not in ('/stream.wav', '/stream.mp3'):
            self.send_error(404)
            return

        capture = self.capture_instance
        if not capture.ffmpeg_pipe:
            self.send_error(503, "Audio capture not running")
            return

        is_mp3 = getattr(capture, 'stream_format', 'wav') == 'mp3'
        try:
            # Enable TCP_NODELAY for minimal network latency
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            self.send_response(200)
            self.send_header('Content-Type', 'audio/mpeg' if is_mp3 else 'audio/wav')
            self.send_header('Connection', 'close')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()

            # Bei roh-PCM einen WAV-Header voranstellen; MP3 ist selbstbeschreibend.
            if not is_mp3:
                self.wfile.write(self._create_wav_header(
                    getattr(capture, 'sample_rate', 44100),
                    getattr(capture, 'channels', 2),
                ))

            # Für MP3 in größeren Blöcken lesen (Frames), für PCM sehr klein (Latenz).
            read_size = 4096 if is_mp3 else 256
            while capture.is_capturing:
                chunk = capture.ffmpeg_pipe.read(read_size)
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
        except Exception as e:
            print(f"⚠️ Streaming error: {e}")

    def _create_wav_header(self, sample_rate=44100, channels=2, bits=16):
        """Create a minimal WAV header for streaming raw PCM."""
        import struct
        byte_rate = sample_rate * channels * (bits // 8)
        block_align = channels * (bits // 8)
        return struct.pack('<4sI4s4sIHHIIHH4sI',
            b'RIFF',
            0xFFFFFFFF,   # Indefinite file size for streaming
            b'WAVE',
            b'fmt ',
            16,           # Format chunk size
            1,            # PCM
            channels,
            sample_rate,
            byte_rate,
            block_align,
            bits,
            b'data',
            0xFFFFFFFF    # Indefinite data size
        )
                    
        


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP Server with threading support."""
    daemon_threads = True
    allow_reuse_address = True


# CLI interface for testing
if __name__ == "__main__":
    import sys
    
    capture = SystemAudioCapture()
    
    print("=" * 60)
    print("System Audio Capture for Bose SoundTouch")
    print("=" * 60)
    
    # Detect capabilities
    caps = capture.detect_capabilities()
    print(f"\n{caps['message']}")
    
    if not caps['available']:
        sys.exit(1)
    
    # Get Bose IP
    if len(sys.argv) < 2:
        print("\nUsage: python system_audio_capture.py <bose_ip>")
        print("Example: python system_audio_capture.py 192.168.1.100")
        sys.exit(1)
    
    device_ip = sys.argv[1]
    
    print(f"\nStarting capture to Bose at {device_ip}")
    print("Press Ctrl+C to stop\n")
    
    if capture.start_capture(device_ip):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nStopping...")
            capture.stop_capture()
    else:
        print("❌ Failed to start capture")
        sys.exit(1)
