#!/usr/bin/env python3
"""
SoundTouch Media Player Module
Integrated media player with streaming capabilities.
"""

import os
import threading
import json
from typing import Optional, List
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QListWidget, QSlider, QFileDialog,
                             QGroupBox, QLineEdit, QComboBox, QProgressBar,
                             QMessageBox, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QTextEdit)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl
import mimetypes
import requests
import xml.etree.ElementTree as ET
import subprocess
from soundtouch_lib import SoundTouchController
from soundtouch_websocket import SoundTouchWebSocket
import sqlite3

# Config file for storing last used folder
CONFIG_FILE = os.path.expanduser("~/.opensoundtouch_config.json")







class MediaScanner(QThread):
    """Background thread for scanning media folders."""
    files_found = pyqtSignal(list)
    scan_complete = pyqtSignal()
    
    def __init__(self, folder: str):
        super().__init__()
        self.folder = folder
        self.audio_extensions = {'.mp3', '.m4a', '.flac', '.wav', '.ogg', '.wma', '.aac'}
        
    def run(self):
        """Scan folder for media files."""
        try:
            files = []
            for root, dirs, filenames in os.walk(self.folder):
                for filename in filenames:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in self.audio_extensions:
                        full_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(full_path, self.folder)
                        files.append({
                            'name': filename,
                            'path': full_path,
                            'rel_path': rel_path,
                            'size': os.path.getsize(full_path)
                        })
            self.files_found.emit(files)
        except Exception as e:
            print(f"Scan error: {e}")
        finally:
            self.scan_complete.emit()


class DLNAServerStarter(QThread):
    """Background thread for starting DLNA server."""
    server_started = pyqtSignal(object, str, str, str)  # (process, config_file, uuid, db_dir)
    server_failed = pyqtSignal(str)  # error message
    status_message = pyqtSignal(str)  # status updates
    
    def __init__(self, media_folder: str):
        super().__init__()
        self.media_folder = media_folder
        
    def run(self):
        """Start minidlna in background."""
        import subprocess
        import time
        import os
        import uuid
        
        try:
            # Kill any existing minidlna processes
            try:
                subprocess.run(['pkill', '-u', os.getenv('USER'), 'minidlnad'], timeout=2, stderr=subprocess.DEVNULL)
                time.sleep(1)
            except:
                pass
            
            # Create directories in application root instead of media folder
            minidlna_dir = os.path.join(os.getcwd(), 'minidlna_opensoundtouch')
            os.makedirs(minidlna_dir, exist_ok=True)
            db_dir = os.path.join(minidlna_dir, 'minidlna_db')
            log_dir = os.path.join(minidlna_dir, 'minidlna_logs')
            pid_dir = os.path.join(minidlna_dir, 'minidlna_pid')
            os.makedirs(pid_dir, exist_ok=True)
            os.makedirs(db_dir, exist_ok=True)
            os.makedirs(log_dir, exist_ok=True)

            uuid_file = os.path.join(minidlna_dir, 'server_uuid.txt')
        
            # Load or generate UUID
            if os.path.exists(uuid_file):
                with open(uuid_file, 'r') as f:
                    server_uuid = f.read().strip()
                self.status_message.emit(f"[DLNA] Bestehende UUID geladen: {server_uuid}")
            else:
                server_uuid = str(uuid.uuid4())
                with open(uuid_file, 'w') as f:
                    f.write(server_uuid)
                self.status_message.emit(f"[DLNA] Neue UUID generiert: {server_uuid}")
                
            # Create minidlna config
            config_content = f"""# OpenSoundtouch auto-generated minidlna config
port=8201
media_dir=A,{self.media_folder}
friendly_name=OpenSoundtouch-DLNA
db_dir={db_dir}
log_dir={log_dir}
log_level=warn
root_container=.
enable_subtitles=no
strict_dlna=no
notify_interval=30
inotify=yes
uuid={server_uuid}
"""
        
            # Write config
            config_file = os.path.join(minidlna_dir, "minidlna_opensoundtouch.conf")
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            self.status_message.emit(f"[DLNA] Config erstellt: {config_file}")
            self.status_message.emit(f"[DLNA] Starte minidlna mit Ordner: {self.media_folder}")
            
            # Start minidlna
            dlna_process = subprocess.Popen(
                ['minidlnad', '-f', config_file, '-P', os.path.join(pid_dir, 'minidlna_opensoundtouch.pid')],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.media_folder,
            )
            
            pid_file = os.path.join(pid_dir, 'minidlna_opensoundtouch.pid')
            # Wait for minidlna to start
            time.sleep(2)
            
            # Check if PID file was created
            if os.path.exists(pid_file):
                with open(pid_file, 'r') as f:
                    pid = f.read().strip()
                self.status_message.emit(f"[DLNA] minidlna gestartet mit PID: {pid}")
            else:
                self.status_message.emit("[DLNA] minidlna läuft (kein PID file gefunden, aber auch kein Fehler)")
            
            self.status_message.emit("[DLNA] Warte auf Indexing...")
            
            # Wait until DB is created
            db_path = os.path.join(db_dir, 'files.db')
            for i in range(15):  # Max 15 seconds
                if os.path.exists(db_path):
                    time.sleep(2)  # Wait a bit more for UUID
                    break
                time.sleep(1)
            
            if not os.path.exists(db_path):
                self.status_message.emit("[DLNA] Warnung: Datenbank wurde noch nicht erstellt")
            
            self.server_started.emit(dlna_process, config_file, server_uuid, db_dir)
            
        except Exception as e:
            self.status_message.emit(f"[DLNA] Fehler beim Start: {e}")
            import traceback
            traceback.print_exc()
            self.server_failed.emit(str(e))
            self.scan_complete.emit()


class StreamServer(QThread):
    """Simple HTTP server for streaming media files with CORS support."""
    server_ready = pyqtSignal(int)  # Emits port number
    
    def __init__(self, media_folder: str, port: int = 8888):
        super().__init__()
        self.media_folder = media_folder
        self.port = port
        self.running = False
        self.httpd = None
        
    def run(self):
        """Start HTTP server."""
        try:
            from http.server import SimpleHTTPRequestHandler
            from socketserver import ThreadingMixIn
            from http.server import HTTPServer
            import socket
            
            class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
                daemon_threads = True
                allow_reuse_address = True
            
            root_dir = self.media_folder

            class CORSHTTPRequestHandler(SimpleHTTPRequestHandler):
                """HTTP Handler mit CORS, Logging, Range-Support für Audio."""

                def __init__(self, *args, **kwargs):
                    # Verwende festes Root (root_dir) statt self.server
                    super().__init__(*args, directory=root_dir, **kwargs)

                def guess_type(self, path):
                    """Force proper audio MIME types for common extensions."""
                    base, ext = os.path.splitext(path)
                    ext = ext.lower()
                    audio_map = {
                        '.mp3': 'audio/mpeg',
                        '.m4a': 'audio/mp4',
                        '.aac': 'audio/aac',
                        '.flac': 'audio/flac',
                        '.wav': 'audio/wav',
                        '.ogg': 'audio/ogg'
                    }
                    return audio_map.get(ext, super().guess_type(path))

                def end_headers(self):
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers', '*')
                    self.send_header('Cache-Control', 'no-cache')
                    self.send_header('Accept-Ranges', 'bytes')  # Range-Request Support
                    SimpleHTTPRequestHandler.end_headers(self)

                def do_OPTIONS(self):
                    self.send_response(200)
                    self.end_headers()

                def do_GET(self):
                    """Handle GET with Range support."""
                    try:
                        # Delegate to parent, which handles Range automatically
                        SimpleHTTPRequestHandler.do_GET(self)
                    except (ConnectionResetError, BrokenPipeError):
                        # Client disconnected (e.g., pause pressed) - this is normal
                        pass
                    except Exception as e:
                        # Log other errors
                        print(f"[Media Server] GET error: {e}")

                def log_message(self, format, *args):
                    # Suppress "Connection reset" errors (normal when client disconnects)
                    msg = format % args
                    if "Connection reset" not in msg and "Broken pipe" not in msg:
                        print(f"[Media Server] {msg}")
            
            # Bind server
            self.httpd = ThreadingHTTPServer(('0.0.0.0', self.port), CORSHTTPRequestHandler)
            self.httpd.media_folder = self.media_folder
            
            # Confirm binding
            self.running = True
            self.server_ready.emit(self.port)
            print(f"[Media Server] Started on 0.0.0.0:{self.port}")
            print(f"[Media Server] Serving: {self.media_folder}")
            
            # Serve loop
            self.httpd.serve_forever()
        except Exception as e:
            self.running = False
            print(f"[Media Server] ERROR: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.httpd:
                try:
                    self.httpd.server_close()
                except Exception:
                    pass
            self.running = False
            print("[Media Server] Stopped")
            
    def stop(self):
        """Stop the server."""
        self.running = False
        if self.httpd:
            print("[Media Server] Stopping...")
            try:
                self.httpd.shutdown()
            except Exception:
                pass


class MediaPlayerWidget(QWidget):
    """Media player widget with streaming capabilities."""
    
    # Signals for thread-safe operations
    start_monitor_signal = pyqtSignal()
    stop_monitor_signal = pyqtSignal()
    update_progress_signal = pyqtSignal(int, int)  # (position_ms, duration_ms)
    log_notification_signal = pyqtSignal(str)  # For thread-safe logging
    fetch_status_signal = pyqtSignal()
    
    def __init__(self, controller=None, device=None):
        super().__init__()
        self.controller = controller
        self.device = device
        self.media_files = []
        self.current_file = None
        self.media_folder = None
        self.scanner = None
        self.stream_server = None
        self.server_port = 8200
        self.dlna_process = None  # minidlna subprocess
        
        # Playlist cache for continuous playback
        self.playlist_cache = []  # List of files in current folder
        self.playlist_index = 0   # Current position in playlist
        
        # Track currently streamed file for metadata
        self.currently_streaming_file = None  # File currently being streamed to device
        self.streaming_start_time = None  # When the stream started
        self.minidlna_db_path = None  # Path to minidlna files.db for duration lookups
        
        # WebSocket für asynchrone Benachrichtigungen
        self.ws = None
        self.notification_log = []
        
        # Local player for preview
        self.player = QMediaPlayer()
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        
        # Periodischer Rescan Timer (alle 5 Sekunden)
        self.rescan_timer = QTimer()
        self.rescan_timer.timeout.connect(self.auto_rescan)
        self.rescan_timer.setInterval(5000)  # 5 seconds
        
        # Track end detection timer
        self.track_monitor_timer = QTimer()
        self.track_monitor_timer.timeout.connect(self.check_track_end)
        self.track_monitor_timer.setInterval(2000)  # Check every 2 seconds
        
        # Progress interpolation timer for smooth slider updates
        self.progress_interpolation_timer = QTimer()
        self.progress_interpolation_timer.timeout.connect(self._interpolate_progress)
        self.progress_interpolation_timer.setInterval(500)  # Update every 500ms
        
        # Fast polling timer for immediate updates after stream start
        self.fast_polling_timer = QTimer()
        self.fast_polling_timer.timeout.connect(self._poll_status_fast)
        self.fast_polling_timer.setInterval(300)  # Poll every 300ms
        self.polling_attempts = 0
        self.max_polling_attempts = 30  # 30 * 300ms = 9 seconds max
        
        # Track state tracking
        self.last_position_ms = 0
        self.last_duration_ms = 0
        self.current_play_status = None
        self.cached_file_duration_ms = 0  # Duration from file metadata (fallback)
        self.last_update_time = 0  # Timestamp of last WebSocket update
        
        # Connect signals for thread-safe operations
        self.start_monitor_signal.connect(self._start_monitor)
        self.stop_monitor_signal.connect(self._stop_monitor)
        self.update_progress_signal.connect(self._update_progress_ui)
        self.log_notification_signal.connect(self._update_notification_console)
        self.fetch_status_signal.connect(self._fetch_current_status)
        
        self.init_ui()
        
        # Load last used folder on startup
        self._load_last_folder()
        
    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Folder selection
        folder_group = QGroupBox("Media Ordner")
        folder_layout = QHBoxLayout()
        
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Wähle einen Ordner mit Musikdateien...")
        folder_layout.addWidget(self.folder_input)
        
        browse_btn = QPushButton("Durchsuchen")
        browse_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(browse_btn)
        
        # Status label
        self.folder_status = QLabel("")
        folder_layout.addWidget(self.folder_status)
        
        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)
        
        # File list
        files_group = QGroupBox("Mediathek")
        files_layout = QVBoxLayout()
        
        self.file_list = QTreeWidget()
        self.file_list.setHeaderLabels(["Datei", "Größe"])
        self.file_list.setColumnWidth(0, 400)
        self.file_list.itemClicked.connect(self.on_file_selected)
        files_layout.addWidget(self.file_list)
        
        self.scan_progress = QProgressBar()
        self.scan_progress.setMaximum(0)
        self.scan_progress.setVisible(False)
        files_layout.addWidget(self.scan_progress)
        
        files_group.setLayout(files_layout)
        layout.addWidget(files_group)
        
        # Playback controls
        playback_group = QGroupBox("Wiedergabe")
        playback_layout = QVBoxLayout()
        
        # Current file info
        self.current_label = QLabel("Keine Datei ausgewählt / abgespielt")
        self.current_label.setWordWrap(True)
        playback_layout.addWidget(self.current_label)
        
        # Progress slider
        progress_layout = QHBoxLayout()
        self.time_label_start = QLabel("0:00")
        progress_layout.addWidget(self.time_label_start)
        
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.sliderMoved.connect(self.seek_position)
        progress_layout.addWidget(self.progress_slider)
        
        self.time_label_end = QLabel("0:00")
        progress_layout.addWidget(self.time_label_end)
        playback_layout.addLayout(progress_layout)
        
        # Control buttons
        btn_layout = QHBoxLayout()
        
        self.stream_btn = QPushButton("▶ Play")
        self.stream_btn.clicked.connect(self.stream_to_device)
        btn_layout.addWidget(self.stream_btn)
        
        # Playlist navigation buttons
        self.prev_btn = QPushButton("⏮ Zurück")
        self.prev_btn.clicked.connect(self.play_previous)
        btn_layout.addWidget(self.prev_btn)
        
        self.next_btn = QPushButton("Weiter ⏭")
        self.next_btn.clicked.connect(self.play_next)
        btn_layout.addWidget(self.next_btn)
        
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.clicked.connect(self.send_stop_key)
        btn_layout.addWidget(self.stop_btn)
        
        playback_layout.addLayout(btn_layout)
        
        # Volume controls
        vol_layout = QHBoxLayout()
        
        self.vol_down_btn = QPushButton("Volume 🔉 -")
        self.vol_down_btn.clicked.connect(self.send_volume_down)
        vol_layout.addWidget(self.vol_down_btn)
        
        self.vol_up_btn = QPushButton("Volume 🔊 +")
        self.vol_up_btn.clicked.connect(self.send_volume_up)
        vol_layout.addWidget(self.vol_up_btn)
        
        playback_layout.addLayout(vol_layout)
        
        playback_group.setLayout(playback_layout)
        layout.addWidget(playback_group)
        
        # Notification console for WebSocket debug
        console_group = QGroupBox("Gerätestatus-Log (WebSocket)")
        console_layout = QVBoxLayout()
        
        self.notification_console = QTextEdit()
        self.notification_console.setReadOnly(True)
        self.notification_console.setMaximumHeight(150)
        self.notification_console.setFontFamily("Monospace")
        self.notification_console.setFontPointSize(8)
        console_layout.addWidget(self.notification_console)
        
        clear_btn = QPushButton("Log löschen")
        clear_btn.clicked.connect(self.notification_console.clear)
        console_layout.addWidget(clear_btn)
        
        console_group.setLayout(console_layout)
        layout.addWidget(console_group)

    



    def set_controller(self, controller, device):
        """Set the controller and device for streaming."""
        self.controller = controller
        self.device = device
        
        # Clear streaming metadata and progress when switching devices
        # Note: keep cached_file_duration_ms for fallback
        self.currently_streaming_file = None
        self.streaming_start_time = None
        self.last_position_ms = 0
        self.last_duration_ms = 0
        self.progress_slider.setValue(0)
        self.progress_slider.setMaximum(0)
        self.time_label_start.setText("0:00")
        self.time_label_end.setText("0:00")
        
        # Connect WebSocket for async notifications
        if device and device.get('ip'):
            try:
                # Quick reachability check first
                test_ctrl = SoundTouchController(device['ip'], timeout=2)
                if not test_ctrl.is_reachable(timeout=2):
                    self._log_notification(f"[WS] Gerät {device.get('name', device['ip'])} ist nicht erreichbar")
                    return
                
                # Close old connection if exists
                if self.ws and hasattr(self.ws, 'close'):
                    try:
                        self.ws.close()
                    except:
                        pass
                
                # Create new WebSocket connection
                self.ws = SoundTouchWebSocket(device['ip'])
                
                # Register callbacks for different event types
                self.ws.add_callback('nowPlayingUpdated', self._on_now_playing_updated)
                self.ws.add_callback('volumeUpdated', self._on_volume_updated)
                self.ws.add_callback('presetsUpdated', self._on_presets_updated)
                self.ws.add_callback('bassUpdated', self._on_bass_updated)
                self.ws.add_callback('zoneUpdated', self._on_zone_updated)
                
                # Start WebSocket in background thread
                import threading
                ws_thread = threading.Thread(target=self._connect_websocket, daemon=True)
                ws_thread.start()
                
                # Fetch current status immediately via HTTP while WebSocket spins up
                QTimer.singleShot(0, self._fetch_current_status)
                
                self._log_notification("[WS] Verbinde zu WebSocket...")
            except Exception as e:
                self._log_notification(f"[WS] Fehler beim Verbinden: {e}")

        
    def browse_folder(self):
        """Browse for media folder."""
        folder = QFileDialog.getExistingDirectory(self, "Wähle Media Ordner")
        if folder:
            self.folder_input.setText(folder)
            self.media_folder = folder
            # Save folder for next startup
            self._save_last_folder(folder)
            self._log_notification("[DLNA] Starte DLNA Server...")
            # Starte minidlna für diesen Ordner (im Hintergrund)
            self.start_dlna_server()
            # Automatisch scannen
            self.scan_folder()
            # Starte periodisches Rescanning
            self.rescan_timer.start()
            
    def scan_folder(self, silent=False):
        """Scan folder for media files."""
        folder = self.folder_input.text()
        if not folder or not os.path.isdir(folder):
            if not silent:
                self._log_notification("❌ Bitte wähle einen gültigen Ordner")
            return
            
        self.media_folder = folder
        self.scan_progress.setVisible(True)
        if not silent:
            self.file_list.clear()
        
        self.folder_status.setText("Scanne...")
        
        self.scanner = MediaScanner(folder)
        self.scanner.files_found.connect(self.on_files_found)
        self.scanner.scan_complete.connect(self.on_scan_complete)
        self.scanner.start()
        
    def on_files_found(self, files):
        """Handle found media files."""
        self.media_files = files
        self.file_list.clear()
        
        # Organize by folder
        folders = {}
        for file in files:
            folder = os.path.dirname(file['rel_path'])
            if not folder:
                folder = "/"
            if folder not in folders:
                folders[folder] = []
            folders[folder].append(file)
        
        # Add to tree
        for folder, files in sorted(folders.items()):
            folder_item = QTreeWidgetItem([folder, ""])
            self.file_list.addTopLevelItem(folder_item)
            
            for file in files:
                size_mb = file['size'] / (1024 * 1024)
                file_item = QTreeWidgetItem([file['name'], f"{size_mb:.1f} MB"])
                file_item.setData(0, Qt.UserRole, file)
                folder_item.addChild(file_item)
                
        self.file_list.expandAll()
        
    def on_scan_complete(self):
        """Handle scan completion."""
        self.scan_progress.setVisible(False)
        if self.media_folder:
            import time
            self.folder_status.setText(f"{len(self.media_files)} Dateien (zuletzt: {time.strftime('%H:%M:%S')})")
    
    def auto_rescan(self):
        """Periodisch den Ordner neu scannen (falls neue Dateien hinzugefügt wurden)."""
        if self.media_folder and os.path.isdir(self.media_folder):
            # Speichere aktuelle Auswahl
            current_file = self.current_file
            self.scan_folder(silent=True)
            # Stelle Auswahl wieder her
            if current_file:
                self.current_file = current_file
        
    def on_file_selected(self, item, column):
        """Handle file selection."""
        file_data = item.data(0, Qt.UserRole)
        if file_data:
            self.current_file = file_data
            # Don't show selected file - wait until it plays
            # (will show in current_label when nowPlayingUpdated event arrives)
            
            # Build playlist cache from all files in the same folder
            current_folder = os.path.dirname(file_data['rel_path'])
            self.playlist_cache = []
            
            for f in self.media_files:
                file_folder = os.path.dirname(f['rel_path'])
                if file_folder == current_folder:
                    self.playlist_cache.append(f)
            
            # Sort by name for consistent ordering
            self.playlist_cache.sort(key=lambda x: x['name'].lower())
            
            # Find current file index in playlist
            try:
                self.playlist_index = next(
                    i for i, f in enumerate(self.playlist_cache) 
                    if f['path'] == file_data['path']
                )
                print(f"[Playlist] Loaded {len(self.playlist_cache)} files, current index: {self.playlist_index}")
            except StopIteration:
                self.playlist_index = 0
            
    def preview_local(self):
        """Play file locally for preview."""
        if not self.current_file:
            self._log_notification("❌ Bitte wähle zuerst eine Datei")
            return
            
        url = QUrl.fromLocalFile(self.current_file['path'])
        self.player.setMedia(QMediaContent(url))
        self.player.play()
        
    def stream_to_device(self):
        """Stream selected file to SoundTouch device."""
        if not self.current_file:
            self._log_notification("❌ Bitte wähle zuerst eine Datei")
            return
            
        if not self.controller:
            self._log_notification("❌ Kein Gerät verbunden")
            return
            
        # Ensure minidlna is running
        if not self.dlna_process:
            self._log_notification("minidlna nicht aktiv, minidlna wird gerade gestartet...\nDies kann 10-30 Sekunden dauern während minidlna\ndie Musikdateien indexiert.\nBitte warte und versuche dann erneut.")
            
            self.start_dlna_server()
            # Warte länger für Indexing
            QTimer.singleShot(5000, self.stream_to_device)
            return
        
        # Ensure server is running
        if not self.stream_server or not self.stream_server.running:
            self.start_stream_server()
            QTimer.singleShot(2000, self._do_stream)
        else:
            self._do_stream()

    

    def _do_stream(self):
        """Actually perform the streaming via minidlna with UPnP ContentDirectory Browse."""
        import socket
        from xml.sax.saxutils import escape
        import time
        
        # Clear notification console and log start
        self.notification_console.clear()
        self._log_notification("[Stream] 🎵 Streaming wird gestartet...")
        from soundtouch_lib import SoundTouchController
        
        # Bestimme lokale IP passend zum Zielgerät
        self._log_notification(f"[Stream] Ermittle lokale IP für {self.device['ip']}...")
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect((self.device['ip'], 80))
            local_ip = s.getsockname()[0]
        except Exception:
            try:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
            except:
                local_ip = "127.0.0.1"
        finally:
            s.close()
        
        self._log_notification(f"[Stream] Lokale IP: {local_ip}")
        
        # Test minidlna connectivity via simple HTTP check
        test_url = f"http://{local_ip}:8200/"
        try:
            import urllib.request
            with urllib.request.urlopen(test_url, timeout=2) as response:
                status = response.status
            self._log_notification(f"[DLNA] ✓ Server erreichbar (HTTP {status})")
            print(f"[DLNA] Server erreichbar: {status}")
        except Exception as e:
            self._log_notification(f"[DLNA] ✗ Server nicht erreichbar: {e}")
            self._log_notification(f"DLNA Server nicht erreichbar, minidlna läuft nicht oder ist nicht erreichbar:\n{e}\nTest-URL: {test_url}\nStelle sicher, dass minidlna installiert ist:\nsudo apt install minidlna")
            return
        
        # Verwende direkten HTTP-Server-Pfad (eigener Server)
        # statt minidlna Browse, da minidlna nur für UPnP-Registrierung verwendet wird
        rel_path = self.current_file['rel_path']
        # URL-encode den Pfad für Sonderzeichen
        from urllib.parse import quote
        encoded_path = quote(rel_path)
        stream_url = f"http://{local_ip}:{self.server_port}/{encoded_path}"
        
        file_name = os.path.basename(rel_path)
        self._log_notification(f"[Stream] 📁 Datei: {file_name}")
        self._log_notification(f"[Stream] 🔗 URL: {stream_url}")
        print(f"[Stream] Datei: {file_name}")
        print(f"[Stream] URL: {stream_url}")
        
        print(f"[Stream] URL: {stream_url}")
        
        # Test if file is accessible
        try:
            import urllib.request
            req = urllib.request.Request(stream_url, method='HEAD')
            with urllib.request.urlopen(req, timeout=2) as response:
                status = response.status
            if status != 200:
                self._log_notification(f"Datei nicht gefunden\nDatei ist über Server nicht erreichbar:\nHTTP {status}\n\n{stream_url}")
                return
            print(f"[Stream] Datei erreichbar: {status}")
        except Exception as e:
            self._log_notification(f"Datei-Test fehlgeschlagen\nKonnte Datei nicht testen:\n{e}\n\n{stream_url}")
            return
        
        # Send to device via DLNA
        try:
            from soundtouch_lib import SoundTouchController
            
            controller = SoundTouchController(self.device['ip'])
            
            # Hole Dateinamen
            track_name = os.path.basename(self.current_file['rel_path'])
            
            # Extrahiere Duration aus Datei als Fallback
            self._extract_file_duration(self.current_file['path'])
            
            # Set currently streaming file BEFORE sending to device (avoid race condition)
            # This ensures WebSocket notifications will find this file in the cache
            self.currently_streaming_file = self.current_file
            import time
            self.streaming_start_time = time.time()
            self._log_notification(f"[Stream] [Pre] Set currently_streaming_file: {self.current_file['name']}")
            
            self._log_notification(f"[Stream] 📡 Sende über DLNA: {track_name}")
            print(f"[Stream] URL: {stream_url}")
            print(f"[Stream] Track: {track_name}")
            
            # Verwende neue play_url_dlna Methode
            success = controller.play_url_dlna(
                url=stream_url,
                track=track_name,
                artist="Lokal",
                album="Lokal"
            )
            
            if success:
                # Log cache state when starting stream
                self._log_notification(f"[Stream] ✓ DLNA-Playback gestartet: {track_name}")
                print(f"[Stream] ✓ DLNA erfolgreich")
                
                # Start fast polling to get immediate updates
                self.polling_attempts = 0
                self.fast_polling_timer.start()
                self._log_notification("[Poll] ⚡ Schnelles Polling gestartet (300ms)")
            else:
                self._log_notification(f"[Stream] ✗ DLNA-Playback fehlgeschlagen")
                print(f"[Stream] ✗ DLNA fehlgeschlagen")
                self.currently_streaming_file = None
                self.streaming_start_time = None
            
        except Exception as e:
            import traceback
            self._log_notification(f"[Stream] ✗ Fehler: {e}")
            print(f"[Stream] Exception: {e}")
            traceback.print_exc()
            return
            
    def stop_playback(self):
        """Stop local playback."""
        self.player.stop()
        self.currently_streaming_file = None
        self.streaming_start_time = None
    
    def get_streaming_metadata(self) -> dict:
        """Get metadata of currently streaming file.
        
        Returns dict with track, artist, album info if streaming, else None.
        """
        if not self.currently_streaming_file:
            return None
        
        file_info = self.currently_streaming_file
        return {
            'track': os.path.basename(file_info['rel_path']),
            'artist': 'Lokal',
            'album': 'Lokal',
            'path': file_info['path'],
            'rel_path': file_info['rel_path']
        }
    
    
    def send_stop_key(self):
        """Send STOP key to device."""
        if not self.controller:
            self._log_notification("❌ Keine Geräteverbindung aktiv")
            return
        
        try:
            self._log_notification("[Control] ⏹ Sende STOP-Befehl")
            success = self.controller.send_key("STOP")
            if success:
                self._log_notification("[Control] ✓ STOP gesendet")
                # Reset UI
                self.current_label.setText("Keine Datei abgespielt")
                self.currently_streaming_file = None
            else:
                self._log_notification("[Control] ✗ STOP-Befehl fehlgeschlagen")
        except Exception as e:
            self._log_notification(f"[Control] ✗ Fehler: {e}")
    
    def send_volume_down(self):
        """Send VOLUME_DOWN key to device."""
        if not self.controller:
            self._log_notification("❌ Keine Geräteverbindung aktiv")
            return
        
        try:
            self.controller.send_key("VOLUME_DOWN")
            self._log_notification("[Volume] 🔉 Leiser")
        except Exception as e:
            self._log_notification(f"[Volume] ✗ Fehler: {e}")
    
    def send_volume_up(self):
        """Send VOLUME_UP key to device."""
        if not self.controller:
            self._log_notification("❌ Keine Geräteverbindung aktiv")
            return
        
        try:
            self.controller.send_key("VOLUME_UP")
            self._log_notification("[Volume] 🔊 Lauter")
        except Exception as e:
            self._log_notification(f"[Volume] ✗ Fehler: {e}")
    
    def check_track_end(self):
        """Check if current track has ended and auto-play next."""
        if not self.playlist_cache or not self.controller:
            return
        
        # Only check if we have valid duration
        if self.last_duration_ms <= 0:
            return
        
        # Check if we're near the end (within last 3 seconds)
        time_remaining_ms = self.last_duration_ms - self.last_position_ms
        
        # If less than 3 seconds remaining and playing, prepare for next track
        if time_remaining_ms < 3000 and time_remaining_ms > 0:
            if self.current_play_status == "PLAY_STATE":
                self._log_notification(f"[Monitor] ⏭ Track endet in {time_remaining_ms//1000}s - bereite nächsten Track vor")
        
        # If track ended (position very close to duration or beyond)
        if self.last_position_ms >= self.last_duration_ms - 500 and self.last_duration_ms > 0:
            if self.current_play_status == "PLAY_STATE":
                self._log_notification("[Monitor] ✓ Track beendet - spiele nächsten Track")
                self.track_monitor_timer.stop()
                # Wait a moment before playing next
                QTimer.singleShot(1500, self.play_next)
    
    def play_next(self):
        """Play next file in playlist."""
        if not self.playlist_cache or not self.controller:
            self._log_notification("❌ Keine Playlist oder Gerät verbunden")
            return
        
        if len(self.playlist_cache) <= 1:
            self._log_notification("[Playlist] Nur ein Track - stoppe")
            return
        
        # Move to next
        self.playlist_index = (self.playlist_index + 1) % len(self.playlist_cache)
        next_file = self.playlist_cache[self.playlist_index]
        
        # Update selection
        self.current_file = next_file
        self.current_label.setText(f"Ausgewählt: {next_file['name']}")
        
        print(f"[Playlist] Playing next: {next_file['name']} ({self.playlist_index + 1}/{len(self.playlist_cache)})")
        self._log_notification(f"[Playlist] ▶ Nächster Track: {next_file['name']} ({self.playlist_index + 1}/{len(self.playlist_cache)})")
        
        # Stream it
        self.stream_to_device()
    
    def play_previous(self):
        """Play previous file in playlist."""
        if not self.playlist_cache:
            return
        
        # Move to previous
        self.playlist_index = (self.playlist_index - 1) % len(self.playlist_cache)
        prev_file = self.playlist_cache[self.playlist_index]
        
        # Update selection
        self.current_file = prev_file
        self.current_label.setText(f"Ausgewählt: {prev_file['name']}")
        
        print(f"[Playlist] Playing previous: {prev_file['name']} ({self.playlist_index + 1}/{len(self.playlist_cache)})")
        
        # Stream it
        self.stream_to_device()
        
    def start_stream_server(self):
        """Start the streaming server."""
        if not self.media_folder:
            return
            
        if self.stream_server and self.stream_server.running:
            return
            
        self.stream_server = StreamServer(self.media_folder, self.server_port)
        self.stream_server.server_ready.connect(self.on_server_ready)
        self.stream_server.start()
        
    def on_server_ready(self, port):
        """Handle server ready."""
        # Server UI-Elemente wurden entfernt
        pass
        
    def stop_stream_server(self):
        """Stop the streaming server."""
        # Server UI-Elemente wurden entfernt
        if self.stream_server:
            self.stream_server.stop()
            self.stream_server.wait()
    
    def _connect_websocket(self):
        """Connect WebSocket in background thread."""
        try:
            if self.ws:
                self.ws.connect()
                self._log_notification("[WS] ✓ Verbunden")
                
                # Fetch current playback status immediately once the WebSocket is up
                self.fetch_status_signal.emit()
        except Exception as e:
            self._log_notification(f"[WS] ✗ Fehler: {e}")
    
    def _fetch_current_status(self):
        """Fetch current playback status from device immediately after WebSocket connect."""
        try:
            if not self.controller:
                return
            
            status = self.controller.get_nowplaying()
            if status:
                self._log_notification("[Status] 📊 Aktueller Status vom Gerät geladen")
                # Trigger the same update handler as WebSocket would
                self._on_now_playing_updated(status)
        except Exception as e:
            self._log_notification(f"[Status] Fehler beim Abrufen: {e}")
    
    def _log_notification(self, message: str):
        """Log a notification message to the console (thread-safe)."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {message}"
        self.notification_log.append(full_msg)
        
        # Emit signal to update UI (thread-safe)
        self.log_notification_signal.emit(full_msg)
    
    def _update_notification_console(self, message: str):
        """Update the notification console from signal (guaranteed to be in GUI thread)."""
        if hasattr(self, 'notification_console'):
            self.notification_console.append(message)
            # Auto-scroll to bottom
            scrollbar = self.notification_console.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def _save_last_folder(self, folder: str):
        """Save the last used folder to config file."""
        try:
            config = {"last_folder": folder}
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f)
            print(f"[Config] Ordner gespeichert: {folder}")
        except Exception as e:
            print(f"[Config] Fehler beim Speichern: {e}")
    
    def _load_last_folder(self):
        """Load the last used folder from config file and open it."""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    last_folder = config.get("last_folder")
                    if last_folder and os.path.isdir(last_folder):
                        self.folder_input.setText(last_folder)
                        self.media_folder = last_folder
                        print(f"[Config] Ordner geladen: {last_folder}")
                        # Auto-start scanning
                        QTimer.singleShot(500, self._auto_load_folder)
        except Exception as e:
            print(f"[Config] Fehler beim Laden: {e}")
    
    def _auto_load_folder(self):
        """Auto-load the last folder after UI is ready."""
        if self.media_folder and os.path.isdir(self.media_folder):
            self._log_notification("[DLNA] Starte DLNA Server...")
            self.start_dlna_server()
            self.scan_folder(silent=True)
            self.rescan_timer.start()
    
    def _on_now_playing_updated(self, notification: dict):
        """Handle nowPlayingUpdated event from device."""
        try:
            # notification kann entweder ein dict sein (alt) oder NowPlayingStatus (neu)
            if hasattr(notification, 'artist'):
                # NowPlayingStatus object
                artist = notification.artist
                album = notification.album
                track = notification.track
                play_status = notification.play_status
                position_ms = notification.position
                
                # Set fallback duration from file metadata if device omits it
                if self.cached_file_duration_ms > 0:
                    notification.set_duration_fallback(self.cached_file_duration_ms)
                
                duration_ms = notification.duration
            else:
                # dict (old format)
                artist = notification.get('artist', '?')
                album = notification.get('album', '?')
                track = notification.get('track', '?')
                play_status = notification.get('playStatus', '?')
                position_ms = notification.get('position', 0)
                duration_ms = notification.get('duration', 0)
                location = notification.get('location')
            
            # Store play status for track end detection
            self.current_play_status = play_status
            
            # Store timestamp for interpolation
            import time
            self.last_update_time = time.time()
            
            # Store for track end detection
            self.last_position_ms = position_ms
            
            # Resolve duration: prefer device, then DLNA DB, then file metadata
            if duration_ms <= 0:
                # Try DLNA DB lookup using track title
                db_duration_ms = self._lookup_duration_from_dlna_db(track) if track else 0
                if db_duration_ms > 0:
                    duration_ms = db_duration_ms
                elif self.cached_file_duration_ms > 0:
                    duration_ms = self.cached_file_duration_ms
            
            self.last_duration_ms = duration_ms if duration_ms else 0
            
            # Update current_label to show now playing track
            # Use currently_streaming_file name if available, otherwise use track from notification
            if play_status == "PLAY_STATE":
                if self.currently_streaming_file:
                    display_name = self.currently_streaming_file['name']
                else:
                    # Use track name from notification (for device switch scenario)
                    display_name = track if track and track != '?' else "Unbekannt"
                self.current_label.setText(f"🎵 Wird abgespielt: {display_name}")
            elif play_status == "PAUSE_STATE":
                if self.currently_streaming_file:
                    display_name = self.currently_streaming_file['name']
                else:
                    display_name = track if track and track != '?' else "Unbekannt"
                self.current_label.setText(f"⏸ Pausiert: {display_name}")
            else:
                self.current_label.setText("Keine Datei abgespielt")
            
            # Update UI via signal (thread-safe)
            if position_ms or duration_ms:
                self.update_progress_signal.emit(position_ms, duration_ms)
            
            # Control monitoring via signal (thread-safe)
            if play_status == "PLAY_STATE":
                self.start_monitor_signal.emit()
            else:
                self.stop_monitor_signal.emit()
            
            self._log_notification(f"[NowPlaying] {artist} - {track} ({play_status}) [{position_ms//1000}s/{duration_ms//1000}s]")
        except Exception as e:
            self._log_notification(f"[NowPlaying] Error: {e}")
    
    def _on_status_updated(self, notification: dict):
        """Handle statusUpdated event from device."""
        try:
            status = notification.get('status', '?')
            self._log_notification(f"[Status] {status}")
        except Exception as e:
            self._log_notification(f"[Status] Error: {e}")
    
    def _on_volume_updated(self, notification: dict):
        """Handle volumeUpdated event from device."""
        try:
            volume = notification.get('actualvolume', notification.get('volume', '?'))
            self._log_notification(f"[Volume] {volume}")
            # Volume is now controlled via buttons, no slider to update
        except Exception as e:
            self._log_notification(f"[Volume] Error: {e}")
    
    def _on_presets_updated(self, notification: dict):
        """Handle presetsUpdated event from device."""
        try:
            self._log_notification("[Presets] Aktualisiert")
        except Exception as e:
            self._log_notification(f"[Presets] Error: {e}")
    
    def _on_bass_updated(self, notification: dict):
        """Handle bassUpdated event from device."""
        try:
            actualbass = notification.get('actualbass', '?')
            self._log_notification(f"[Bass] {actualbass}")
        except Exception as e:
            self._log_notification(f"[Bass] Error: {e}")

    def _lookup_duration_from_dlna_db(self, track_title: str) -> int:
        """Look up duration (ms) from minidlna files.db using the track title."""
        if not track_title:
            self._log_notification("[DLNA DB] Kein Track-Titel für Lookup")
            return 0
        db_path = self._ensure_db_path()
        if not db_path:
            self._log_notification(f"[DLNA DB] Kein DB-Pfad verfügbar")
            return 0
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            try:
                # Clean up track title (remove .mp3 extension if present)
                clean_title = track_title.replace('.mp3', '').replace('.m4a', '').replace('.flac', '')
                self._log_notification(f"[DLNA DB] Suche '{clean_title}' in {db_path}")
                cur = conn.cursor()
                cur.execute(
                    "SELECT DURATION FROM DETAILS WHERE TITLE = ? LIMIT 1",
                    (clean_title,)
                )
                row = cur.fetchone()
                if not row or row[0] is None:
                    self._log_notification(f"[DLNA DB] ✗ Kein Eintrag für '{clean_title}'")
                    return 0
                raw_val = row[0]
                try:
                    # Parse duration - can be time format "0:02:39.984" or numeric
                    if isinstance(raw_val, str) and ':' in raw_val:
                        # Parse HH:MM:SS.mmm or MM:SS.mmm format
                        parts = raw_val.split(':')
                        if len(parts) == 3:  # HH:MM:SS.mmm
                            hours = int(parts[0])
                            minutes = int(parts[1])
                            seconds = float(parts[2])
                            duration_ms = int((hours * 3600 + minutes * 60 + seconds) * 1000)
                        elif len(parts) == 2:  # MM:SS.mmm
                            minutes = int(parts[0])
                            seconds = float(parts[1])
                            duration_ms = int((minutes * 60 + seconds) * 1000)
                        else:
                            self._log_notification(f"[DLNA DB] ✗ Ungültiges Format: {raw_val}")
                            return 0
                    else:
                        # Numeric value (milliseconds)
                        val = float(raw_val)
                        duration_ms = int(val)
                    
                    self._log_notification(f"[DLNA DB] ✓ Gefunden: {duration_ms}ms ({duration_ms//1000}s) aus '{raw_val}'")
                    return duration_ms
                except (ValueError, TypeError) as e:
                    self._log_notification(f"[DLNA DB] ✗ Parse-Fehler für '{raw_val}': {e}")
                    return 0
            finally:
                conn.close()
        except Exception as e:
            self._log_notification(f"[DLNA DB] ✗ Fehler: {e}")
            return 0

    def _ensure_db_path(self) -> Optional[str]:
        """Ensure we have a valid minidlna DB path, with fallbacks."""
        if self.minidlna_db_path and os.path.exists(self.minidlna_db_path):
            return self.minidlna_db_path
        # Try to detect from current config
        detected = self._detect_db_path_from_config(getattr(self, 'config_file', None))
        if detected and os.path.exists(detected):
            self.minidlna_db_path = detected
            return detected
        # Last resort: existing value even if missing
        return self.minidlna_db_path

    def _detect_db_path_from_config(self, config_file: Optional[str]) -> Optional[str]:
        """Parse db_dir from minidlna config and provide sensible fallbacks."""
        candidates = []
        try:
            if config_file and os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    for line in f:
                        if line.strip().startswith('db_dir'):
                            _, val = line.split('=', 1)
                            db_dir = val.strip()
                            if db_dir:
                                candidates.append(os.path.abspath(db_dir))
                                break
                base_dir = os.path.dirname(config_file)
                candidates.append(os.path.join(base_dir, 'minidlna_db', 'files.db'))
                candidates.append(os.path.join(base_dir, '.db', 'files.db'))
            # Repo-level fallback
            candidates.append(os.path.join(os.getcwd(), 'minidlna_opensoundtouch', 'minidlna_db', 'files.db'))
            candidates.append(os.path.join(os.getcwd(), 'minidlna', '.db', 'files.db'))
            candidates.append(os.path.join(os.getcwd(), 'test_music', 'minidlna_opensoundtouch', 'minidlna_db', 'files.db'))
            # Media-folder fallback (old location)
            if self.media_folder:
                candidates.append(os.path.join(self.media_folder, 'minidlna_opensoundtouch', 'minidlna_db', 'files.db'))
                candidates.append(os.path.join(self.media_folder, 'minidlna', '.db', 'files.db'))
        except Exception:
            pass
        # Pick first existing
        for p in candidates:
            if p and os.path.exists(p):
                return p
        # Otherwise return first candidate if any
        return candidates[0] if candidates else None

    def _resolve_path_from_location(self, location: str) -> Optional[str]:
        """Resolve absolute file path from ContentItem location URL."""
        if not location or not self.media_folder:
            return None
        try:
            from urllib.parse import urlparse, unquote
            parsed = urlparse(location)
            rel_path = unquote(parsed.path.lstrip('/'))
            abs_path = os.path.join(self.media_folder, rel_path)
            return abs_path
        except Exception:
            return None

    def _find_path_by_track(self, track: str) -> Optional[str]:
        """Find a media file by track name in scanned files."""
        if not track:
            return None
        for f in self.media_files:
            if f['name'].lower() == track.lower() or f['name'].lower() == (track + '.mp3').lower():
                return f['path']
        return None
    
    # Thread-safe slot methods
    def _start_monitor(self):
        """Start track monitor timer (called from main thread)."""
        if not self.track_monitor_timer.isActive():
            self.track_monitor_timer.start()
            self._log_notification("[Monitor] ▶ Track-Monitoring gestartet")
        if not self.progress_interpolation_timer.isActive():
            self.progress_interpolation_timer.start()
    
    def _stop_monitor(self):
        """Stop track monitor timer (called from main thread)."""
        if self.track_monitor_timer.isActive():
            self.track_monitor_timer.stop()
            self._log_notification("[Monitor] ⏸ Track-Monitoring pausiert")
        if self.progress_interpolation_timer.isActive():
            self.progress_interpolation_timer.stop()
    
    def _extract_file_duration(self, file_path: str):
        """Extract duration from audio file using mutagen."""
        try:
            from mutagen import File
            audio = File(file_path)
            if audio and hasattr(audio.info, 'length'):
                duration_sec = audio.info.length
                self.cached_file_duration_ms = int(duration_sec * 1000)
                self._log_notification(f"[File] Duration: {int(duration_sec)}s aus Datei extrahiert")
            else:
                self.cached_file_duration_ms = 0
        except ImportError:
            self._log_notification("[File] mutagen nicht installiert - Duration-Fallback nicht verfügbar")
            self.cached_file_duration_ms = 0
        except Exception as e:
            self._log_notification(f"[File] Fehler beim Lesen der Duration: {e}")
            self.cached_file_duration_ms = 0
    
    def _interpolate_progress(self):
        """Interpolate progress between WebSocket updates for smooth slider movement."""
        if not self.current_play_status == "PLAY_STATE":
            return
        
        if self.last_duration_ms <= 0:
            return
        
        # Calculate elapsed time since last WebSocket update
        import time
        current_time = time.time()
        elapsed_ms = int((current_time - self.last_update_time) * 1000)
        
        # Interpolate position
        interpolated_position = self.last_position_ms + elapsed_ms
        
        # Don't exceed duration
        if interpolated_position > self.last_duration_ms:
            interpolated_position = self.last_duration_ms
        
        # Update UI
        self.progress_slider.blockSignals(True)
        self.progress_slider.setValue(interpolated_position)
        self.progress_slider.blockSignals(False)
        
        mins = interpolated_position // 60000
        secs = (interpolated_position % 60000) // 1000
        self.time_label_start.setText(f"{mins}:{secs:02d}")
    
    def _update_progress_ui(self, position_ms: int, duration_ms: int):
        """Update progress slider and time labels (called from main thread)."""
        if position_ms:
            self.progress_slider.blockSignals(True)
            self.progress_slider.setValue(position_ms)
            self.progress_slider.blockSignals(False)
            
            mins = position_ms // 60000
            secs = (position_ms % 60000) // 1000
            self.time_label_start.setText(f"{mins}:{secs:02d}")
        
        if duration_ms:
            self.progress_slider.setMaximum(duration_ms)
            mins = duration_ms // 60000
            secs = (duration_ms % 60000) // 1000
            self.time_label_end.setText(f"{mins}:{secs:02d}")
    
    def _on_zone_updated(self, notification: dict):
        """Handle zoneUpdated event from device."""
        try:
            master = notification.get('master', '?')
            members = notification.get('members', 0)
            self._log_notification(f"[Zone] Master: {master}, Members: {members}")
        except Exception as e:
            self._log_notification(f"[Zone] Error: {e}")
    
    def start_dlna_server(self):
        """Start minidlna for the current media folder."""
        if not self.media_folder:
            return
        
        # Stop existing minidlna first
        self.stop_dlna_server()
        
        # Start DLNA server in background thread
        self.dlna_starter = DLNAServerStarter(self.media_folder)
        self.dlna_starter.server_started.connect(self._on_dlna_server_started)
        self.dlna_starter.server_failed.connect(self._on_dlna_server_failed)
        self.dlna_starter.status_message.connect(self._log_notification)
        self.dlna_starter.start()
    
    def _on_dlna_server_started(self, process, config_file, server_uuid, db_dir):
        """Handle DLNA server started successfully."""
        self.dlna_process = process
        self.config_file = config_file
        self.dlna_uuid = server_uuid
        self.minidlna_db_path = os.path.join(db_dir, 'files.db')
        self._log_notification("[DLNA] ✓ Server erfolgreich gestartet")
    
    def _on_dlna_server_failed(self, error_msg):
        """Handle DLNA server start failure."""
        self._log_notification(f"[DLNA] ✗ Start fehlgeschlagen: {error_msg}")

    def stop_dlna_server(self):
        """Stop minidlna."""
        if self.dlna_process:
            try:
                self.dlna_process.terminate()
                self.dlna_process.wait(timeout=3)
                print("[DLNA] minidlna gestoppt (terminate)")
            except subprocess.TimeoutExpired:
                try:
                    self.dlna_process.kill()
                    self.dlna_process.wait(timeout=1)
                    print("[DLNA] minidlna gestoppt (kill)")
                except:
                    pass
            except:
                pass
            finally:
                self.dlna_process = None
    
        # Cleanup: Kill alle übrigen Prozesse
        try:
            subprocess.run(['pkill', '-u', os.getenv('USER'), 'minidlnad'], timeout=2, stderr=subprocess.DEVNULL)
                
        except:
            pass
        
    def _get_dlna_file_url(self, local_ip, file_name):
        """
        Query minidlna via UPnP ContentDirectory Browse to get the correct file URL.
        Returns: URL like http://ip:8200/MediaItems/22.mp3 or None if not found.
        """
        import requests
        
        dlna_control_url = f"http://{local_ip}:8200/ctl/ContentDir"
        
        print(f"[DLNA] Searching for: {file_name}")
        print(f"[DLNA] Control URL: {dlna_control_url}")
        
        # Zuerst: Alle verfügbaren Dateien auflisten
        all_files = self._list_dlna_files(dlna_control_url)
        if all_files:
            print(f"[DLNA] Checking {len(all_files)} files...")
            
            # base_name = Dateiname OHNE Extension (wie minidlna es speichert)
            base_name = os.path.splitext(file_name)[0]
            
            for fname, furl in all_files:
                # Vergleiche mit verschiedenen Varianten
                if (fname == file_name or 
                    fname.lower() == file_name.lower() or
                    fname == base_name or  # WICHTIG: ohne Extension!
                    fname.lower() == base_name.lower()):
                    
                    print(f"[DLNA] ✓ FOUND: {fname} → {furl}")
                    return furl
        
        print(f"[DLNA] No match found for '{file_name}' (searching for '{os.path.splitext(file_name)[0]}')")
        return None
    
    def _search_dlna_file(self, dlna_control_url, file_name):
        """
        Search for a file in minidlna using UPnP Search action.
        """
        import requests
        import xml.etree.ElementTree as ET
        
        print(f"[DLNA] Searching for: {file_name}")
        
        # Versuche verschiedene Suchvarianten
        search_variants = [
            f'upnp:title = "{file_name}"',
            f'upnp:title contains "{file_name}"',
            f'upnp:title contains "{os.path.splitext(file_name)[0]}"',
        ]
        
        for search_criteria in search_variants:
            print(f"[DLNA] Search attempt: {search_criteria}")
            
            search_request = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
 <s:Body>
  <u:Search xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
   <ContainerID>0</ContainerID>
   <SearchCriteria>{search_criteria}</SearchCriteria>
   <Filter>*</Filter>
   <StartingIndex>0</StartingIndex>
   <RequestedCount>100</RequestedCount>
   <SortCriteria></SortCriteria>
  </u:Search>
 </s:Body>
</s:Envelope>"""
            
            try:
                headers = {
                    'Content-Type': 'text/xml; charset="utf-8"',
                    'SOAPACTION': '"urn:schemas-upnp-org:service:ContentDirectory:1#Search"',
                    'Content-Length': str(len(search_request))
                }
                
                response = requests.post(dlna_control_url, data=search_request, headers=headers, timeout=5)
                
                if response.status_code != 200:
                    print(f"[DLNA] Search HTTP {response.status_code} - minidlna Search nicht unterstützt")
                    continue
                
                try:
                    root = ET.fromstring(response.text)
                    namespaces = {
                        's': 'http://schemas.xmlsoap.org/soap/envelope/',
                        'u': 'urn:schemas-upnp-org:service:ContentDirectory:1'
                    }
                    
                    result_elem = root.find('.//u:SearchResponse/Result', namespaces)
                    if result_elem is None or not result_elem.text:
                        continue
                    
                    didl_root = ET.fromstring(result_elem.text)
                    didl_ns = {'didl': 'urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/'}
                    
                    for item in didl_root.findall('.//didl:item', didl_ns):
                        title_elem = item.find('didl:title', didl_ns)
                        if title_elem is None or not title_elem.text:
                            continue
                        
                        title = title_elem.text
                        if (title == file_name or 
                            title.lower() == file_name.lower()):
                            
                            res_elem = item.find('didl:res', didl_ns)
                            if res_elem is not None and res_elem.text:
                                url = res_elem.text
                                print(f"[DLNA] ✓ Found via Search: {url}")
                                return url
                
                except Exception as parse_err:
                    print(f"[DLNA] Parse error: {parse_err}")
                    continue
            
            except Exception as e:
                print(f"[DLNA] Search error: {e}")
                continue
        
        return None
    
    def _list_dlna_files(self, dlna_control_url):
        """
        List all files available in minidlna (for debugging).
        Returns: List of (filename, url) tuples or empty list on error.
        """
        import requests
        import xml.etree.ElementTree as ET
        
        browse_request = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
 <s:Body>
  <u:Browse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
   <ObjectID>0</ObjectID>
   <BrowseFlag>BrowseDirectChildren</BrowseFlag>
   <Filter>*</Filter>
   <StartingIndex>0</StartingIndex>
   <RequestedCount>0</RequestedCount>
   <SortCriteria></SortCriteria>
  </u:Browse>
 </s:Body>
</s:Envelope>"""
        
        try:
            headers = {
                'Content-Type': 'text/xml; charset="utf-8"',
                'SOAPACTION': '"urn:schemas-upnp-org:service:ContentDirectory:1#Browse"',
                'Content-Length': str(len(browse_request))
            }
            
            print(f"[DLNA] POST to {dlna_control_url}")
            response = requests.post(dlna_control_url, data=browse_request, headers=headers, timeout=5)
            
            if response.status_code != 200:
                print(f"[DLNA] Browse failed: HTTP {response.status_code}")
                print(f"[DLNA] Response: {response.text[:500]}")
                return []
            
            root = ET.fromstring(response.text)
            namespaces = {
                's': 'http://schemas.xmlsoap.org/soap/envelope/',
                'u': 'urn:schemas-upnp-org:service:ContentDirectory:1'
            }
            
            result_elem = root.find('.//u:BrowseResponse/Result', namespaces)
            if result_elem is None:
                print(f"[DLNA] ERROR: No BrowseResponse/Result in SOAP")
                print(f"[DLNA] Full response: {response.text[:1000]}")
                return []
            
            if not result_elem.text:
                print(f"[DLNA] BrowseResponse/Result is empty - minidlna still indexing?")
                return []
            
            # HTML-encoded DIDL, muss decoded werden
            didl_text = result_elem.text
            print(f"[DLNA] DIDL Length: {len(didl_text)} chars")
            print(f"[DLNA] DIDL Content (first 800 chars):\n{didl_text[:800]}")
            
            try:
                didl_root = ET.fromstring(didl_text)
            except Exception as parse_err:
                print(f"[DLNA] Failed to parse DIDL: {parse_err}")
                print(f"[DLNA] First 300 chars: {didl_text[:300]}")
                return []
            
            # Namespaces - WICHTIG: minidlna nutzt dc:title nicht didl:title
            ns = {
                'didl': 'urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/',
                'dc': 'http://purl.org/dc/elements/1.1/',
                'upnp': 'urn:schemas-upnp-org:metadata-1-0/upnp/'
            }
            
            # Debug: Zähle alle Elemente
            containers = didl_root.findall('.//didl:container', ns)
            items = didl_root.findall('.//didl:item', ns)
            print(f"[DLNA] Found {len(containers)} containers, {len(items)} items")
            
            files = []
            
            # Wenn nur containers: browse recursive
            if len(containers) > 0 and len(items) == 0:
                print(f"[DLNA] Only containers found, trying recursive browse...")
                for container in containers[:5]:  # Erste 5
                    id_attr = container.get('id')
                    # WICHTIG: minidlna nutzt dc:title nicht didl:title!
                    title_elem = container.find('dc:title', ns)
                    title = title_elem.text if title_elem is not None else "Unknown"
                    print(f"[DLNA]   - Container: {title} (ID: {id_attr})")
                    if id_attr:
                        sub_files = self._browse_dlna_container(dlna_control_url, id_attr)
                        files.extend(sub_files)
            
            # Normale Items
            for item in items:
                title_elem = item.find('dc:title', ns)
                res_elem = item.find('didl:res', ns)
                if title_elem is not None and title_elem.text and res_elem is not None and res_elem.text:
                    files.append((title_elem.text, res_elem.text))
            
            return files
            
        except Exception as e:
            print(f"[DLNA] Error listing files: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _browse_dlna_container(self, dlna_control_url, container_id):
        """
        Browse a specific DLNA container (folder) recursively.
        """
        import requests
        import xml.etree.ElementTree as ET
        
        browse_request = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
 <s:Body>
  <u:Browse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
   <ObjectID>{container_id}</ObjectID>
   <BrowseFlag>BrowseDirectChildren</BrowseFlag>
   <Filter>*</Filter>
   <StartingIndex>0</StartingIndex>
   <RequestedCount>0</RequestedCount>
   <SortCriteria></SortCriteria>
  </u:Browse>
 </s:Body>
</s:Envelope>"""
        
        try:
            headers = {
                'Content-Type': 'text/xml; charset="utf-8"',
                'SOAPACTION': '"urn:schemas-upnp-org:service:ContentDirectory:1#Browse"',
                'Content-Length': str(len(browse_request))
            }
            
            response = requests.post(dlna_control_url, data=browse_request, headers=headers, timeout=5)
            
            if response.status_code != 200:
                return []
            
            root = ET.fromstring(response.text)
            namespaces = {
                's': 'http://schemas.xmlsoap.org/soap/envelope/',
                'u': 'urn:schemas-upnp-org:service:ContentDirectory:1'
            }
            
            result_elem = root.find('.//u:BrowseResponse/Result', namespaces)
            if result_elem is None or not result_elem.text:
                return []
            
            didl_root = ET.fromstring(result_elem.text)
            didl_ns = {'didl': 'urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/'}
            dc_ns = {'dc': 'http://purl.org/dc/elements/1.1/'}
            
            files = []
            
            # Finde Items in diesem Container
            for item in didl_root.findall('.//didl:item', didl_ns):
                title_elem = item.find('dc:title', dc_ns)  # minidlna nutzt dc:title!
                res_elem = item.find('didl:res', didl_ns)
                if title_elem is not None and title_elem.text and res_elem is not None and res_elem.text:
                    files.append((title_elem.text, res_elem.text))
            
            # Finde weitere Sub-Container
            for container in didl_root.findall('.//didl:container', didl_ns):
                sub_id = container.get('id')
                if sub_id:
                    sub_files = self._browse_dlna_container(dlna_control_url, sub_id)
                    files.extend(sub_files)
            
            return files
            
        except Exception as e:
            print(f"[DLNA] Error browsing container {container_id}: {e}")
            return []
            
    def on_position_changed(self, position):
        """Handle playback position change."""
        self.progress_slider.setValue(position)
        mins = position // 60000
        secs = (position % 60000) // 1000
        self.time_label_start.setText(f"{mins}:{secs:02d}")
        
    def on_duration_changed(self, duration):
        """Handle duration change."""
        self.progress_slider.setMaximum(duration)
        mins = duration // 60000
        secs = (duration % 60000) // 1000
        self.time_label_end.setText(f"{mins}:{secs:02d}")
        
    def seek_position(self, position):
        """Seek to position."""
        self.player.setPosition(position)
        
    def _poll_status_fast(self):
        """Fast polling for immediate status updates after stream start."""
        self.polling_attempts += 1
        
        # Stop after max attempts
        if self.polling_attempts >= self.max_polling_attempts:
            self.fast_polling_timer.stop()
            self._log_notification("[Poll] ⏹ Schnelles Polling beendet (Timeout)")
            return
        
        try:
            if not self.controller:
                self.fast_polling_timer.stop()
                return
            
            status = self.controller.get_nowplaying()
            if status:
                # Extract status for logging and stop condition
                if hasattr(status, 'play_status'):
                    play_status = status.play_status
                    position_ms = status.position
                else:
                    play_status = status.get('playStatus', '')
                    position_ms = status.get('position', 0)
                
                # Log what we got (only on significant changes)
                if self.polling_attempts <= 3 or play_status == "PLAY_STATE":
                    self._log_notification(f"[Poll] #{self.polling_attempts}: {play_status} pos={position_ms}ms")
                
                # Trigger update handler
                self._on_now_playing_updated(status)
                
                # Stop fast polling once we see PLAY_STATE with position > 0
                # Also accept BUFFERING_STATE as it means track is loading
                if (play_status == "PLAY_STATE" and position_ms > 0) or \
                   (play_status == "PLAY_STATE" and self.polling_attempts >= 10):
                    self.fast_polling_timer.stop()
                    self._log_notification(f"[Poll] ✓ Schnelles Polling beendet (Track läuft, {self.polling_attempts} Versuche)")
        except Exception as e:
            # Log error for debugging
            self._log_notification(f"[Poll] Fehler bei Versuch {self.polling_attempts}: {e}")
    
    def closeEvent(self, event):
        """Handle widget close."""
        self.player.stop()
        if self.stream_server:
            self.stop_stream_server()
        # Stoppe minidlna
        self.stop_dlna_server()
        # Stop polling timers
        if hasattr(self, 'fast_polling_timer'):
            self.fast_polling_timer.stop()
        event.accept()
