#!/usr/bin/env python3
"""
SoundTouch GUI for Linux and Windows
PyQt5-based GUI for controlling Bose SoundTouch devices.
"""

import sys
import json
import netifaces
import ipaddress
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QComboBox, 
                             QGroupBox, QSlider, QTextEdit, QTabWidget,
                             QListWidget, QProgressBar, QFileDialog, QLineEdit,
                             QMessageBox, QGridLayout)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QFont
from soundtouch_lib import SoundTouchDiscovery, SoundTouchController
from soundtouch_websocket import SoundTouchWebSocket
from gui_media_player import MediaPlayerWidget
from gui_group_manager import GroupManagerWidget
from gui_device_setup import DeviceSetupWizard


def get_local_networks():
    """Ermittelt alle aktiven Netzwerk-Interfaces und deren Netzwerke."""
    networks = []
    
    try:
        for iface in netifaces.interfaces():
            # Überspringe Loopback und Docker
            if iface.startswith('lo') or iface.startswith('docker') or iface.startswith('br-'):
                continue
                
            addrs = netifaces.ifaddresses(iface)
            
            # IPv4 Adressen
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    ip = addr.get('addr')
                    netmask = addr.get('netmask')
                    
                    # Überspringe Loopback IPs
                    if ip and ip != '127.0.0.1' and netmask:
                        try:
                            network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                            
                            # Filter Docker-Netzwerke (172.17.0.0/16, 172.18.0.0/16, etc.)
                            if network.network_address.packed[0] == 172 and network.network_address.packed[1] in range(16, 32):
                                print(f"Überspringe Docker-Netzwerk: {network}")
                                continue
                            
                            # Nur Netzwerke bis /22 scannen (max 1024 IPs)
                            if network.prefixlen < 22:
                                # Konvertiere zu /24 wenn zu groß
                                network_24 = ipaddress.IPv4Network(f"{ip}/24", strict=False)
                                print(f"Netzwerk {network} zu groß, benutze {network_24}")
                                networks.append(str(network_24))
                            else:
                                networks.append(str(network))
                        except:
                            pass
    except Exception as e:
        print(f"Error detecting networks: {e}")
        # Fallback: versuche Default Route
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            parts = local_ip.split('.')
            fallback_network = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
            networks.append(fallback_network)
        except:
            pass
    
    return networks


import os


class DeviceScanner(QThread):
    """Background thread for device discovery."""
    devices_found = pyqtSignal(list)
    scan_complete = pyqtSignal()
    progress = pyqtSignal(str)  # Progress messages
    
    def __init__(self, networks=None):
        super().__init__()
        self.networks = networks if networks else [None]  # None = auto-detect
        self._stop = False
        
    def run(self):
        """Scan for devices across multiple networks."""
        all_devices = []
        try:
            total_networks = len(self.networks)
            for idx, network in enumerate(self.networks, 1):
                if self._stop:
                    break
                    
                try:
                    self.progress.emit(f"Scanne Netzwerk {idx}/{total_networks}: {network}...")
                    discovery = SoundTouchDiscovery(network=network)
                    # Reduziere Threads und setze Timeout
                    devices = discovery.scan(max_threads=20, timeout=60)
                    
                    # Deduplicate by MAC address
                    for device in devices:
                        if not any(d['mac'] == device['mac'] for d in all_devices):
                            all_devices.append(device)
                            self.progress.emit(f"Gefunden: {device['name']} ({device['ip']})")
                except Exception as e:
                    print(f"Error scanning network {network}: {e}")
            
            self.devices_found.emit(all_devices)
        except Exception as e:
            print(f"Error scanning: {e}")
        finally:
            self.scan_complete.emit()
    
    def stop(self):
        """Stop the scan."""
        self._stop = True


class SoundTouchGUI(QMainWindow):
    """Main GUI window for SoundTouch control."""
    
    def __init__(self):
        super().__init__()
        self.devices = []
        self.current_device = None
        self.controller = None
        self.scanner = None
        self.websocket = None
        self.last_source = None  # track current source to route transport keys
        
        # Auto-refresh timer (fallback if WebSocket unavailable)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.update_now_playing)
        
        self.init_ui()
        self.load_saved_devices()
        
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle('Bose SoundTouch Controller')
        self.setMinimumSize(1000, 700)
        self.setWindowIcon(QIcon())  # Set a placeholder icon
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # Device selection section
        device_group = self.create_device_selection()
        main_layout.addWidget(device_group)
        
        # Create tab widget
        tabs = QTabWidget()
        tabs.addTab(self.create_control_tab(), "Steuerung")
        tabs.addTab(self.create_info_tab(), "Info")
        
        # Media Player tab
        self.media_player = MediaPlayerWidget()
        tabs.addTab(self.media_player, "🎵 Media Player")
        
        # Group Manager tab
        self.group_manager = GroupManagerWidget()
        tabs.addTab(self.group_manager, "👥 Gruppen")
        
        main_layout.addWidget(tabs)
        
        # Status bar
        self.statusBar().showMessage('Bereit')
        
        # Apply styling
        self.apply_style()
        
    def create_device_selection(self):
        """Create device selection group."""
        group = QGroupBox("Gerät auswählen")
        main_layout = QVBoxLayout()
        
        # Network selection row
        network_layout = QHBoxLayout()
        network_layout.addWidget(QLabel("Netzwerk:"))
        
        self.network_input = QLineEdit()
        self.network_input.setPlaceholderText("Auto = Aktive Interfaces (oder z.B. 192.168.50.0/24)")
        network_layout.addWidget(self.network_input, 1)
        main_layout.addLayout(network_layout)
        
        # Device selection row
        device_layout = QHBoxLayout()
        
        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self.on_device_selected)
        device_layout.addWidget(QLabel("Gerät:"))
        device_layout.addWidget(self.device_combo, 1)
        
        scan_btn = QPushButton("Scan")
        scan_btn.clicked.connect(self.scan_devices)
        device_layout.addWidget(scan_btn)
        
        add_device_btn = QPushButton("➕ Gerät hinzufügen")
        add_device_btn.clicked.connect(self.open_device_setup)
        device_layout.addWidget(add_device_btn)
        
        self.scan_progress = QProgressBar()
        self.scan_progress.setMaximum(0)
        self.scan_progress.setVisible(False)
        device_layout.addWidget(self.scan_progress)
        
        main_layout.addLayout(device_layout)
        
        group.setLayout(main_layout)
        return group
        
    def create_control_tab(self):
        """Create main control tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Now Playing Display
        now_playing_group = QGroupBox("Aktuelle Wiedergabe")
        now_playing_layout = QVBoxLayout()
        
        self.track_label = QLabel("Track: -")
        self.track_label.setFont(QFont("Arial", 13, QFont.Bold))
        self.artist_label = QLabel("Artist: -")
        self.album_label = QLabel("Album: -")
        self.source_label = QLabel("Source: -")
        
        now_playing_layout.addWidget(self.track_label)
        now_playing_layout.addWidget(self.artist_label)
        now_playing_layout.addWidget(self.album_label)
        now_playing_layout.addWidget(self.source_label)
        now_playing_group.setLayout(now_playing_layout)
        layout.addWidget(now_playing_group)
        
        # Playback Controls
        playback_group = QGroupBox("Wiedergabe")
        playback_layout = QGridLayout()
        playback_layout.setSpacing(8)
        
        # Transport controls
        btn_prev = self.create_button("⏮ Zurück", "PREV_TRACK")
        btn_play = self.create_button("▶ Play", "PLAY")
        btn_pause = self.create_button("⏸ Pause", "PAUSE")
        btn_next = self.create_button("⏭ Weiter", "NEXT_TRACK")
        
        playback_layout.addWidget(btn_prev, 0, 0)
        playback_layout.addWidget(btn_play, 0, 1)
        playback_layout.addWidget(btn_pause, 0, 2)
        playback_layout.addWidget(btn_next, 0, 3)
        
        # Volume controls
        btn_vol_down = self.create_button("🔉 -", "VOLUME_DOWN")
        btn_vol_up = self.create_button("🔊 +", "VOLUME_UP")
        
        playback_layout.addWidget(btn_vol_down, 1, 0)
        playback_layout.addWidget(btn_vol_up, 1, 1)
        
        playback_group.setLayout(playback_layout)
        layout.addWidget(playback_group)
        
        # Preset buttons
        preset_group = QGroupBox("Presets")
        preset_layout = QGridLayout()
        
        for i in range(1, 7):
            btn = self.create_button(f"Preset {i}", f"PRESET_{i}")
            preset_layout.addWidget(btn, (i-1)//3, (i-1)%3)
        
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)
        
        # Additional controls
        extra_group = QGroupBox("Weitere Steuerung")
        extra_layout = QGridLayout()
        
        btn_power = self.create_button("Power", "POWER")
        btn_mute = self.create_button("Mute", "MUTE")
        btn_shuffle = self.create_button("Shuffle", "SHUFFLE_ON")
        btn_repeat = self.create_button("Repeat", "REPEAT_ALL")
        
        extra_layout.addWidget(btn_power, 0, 0)
        extra_layout.addWidget(btn_mute, 0, 1)
        extra_layout.addWidget(btn_shuffle, 1, 0)
        extra_layout.addWidget(btn_repeat, 1, 1)
        
        extra_group.setLayout(extra_layout)
        layout.addWidget(extra_group)
        
        layout.addStretch()
        return widget
        
    def create_info_tab(self):
        """Create info display tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Device info
        info_group = QGroupBox("Geräteinformationen")
        info_layout = QVBoxLayout()
        
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        info_layout.addWidget(self.info_text)
        
        refresh_btn = QPushButton("Aktualisieren")
        refresh_btn.clicked.connect(self.update_device_info)
        info_layout.addWidget(refresh_btn)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        return widget
        
    def create_button(self, text, key):
        """Create a button that routes transport depending on source."""
        btn = QPushButton(text)
        btn.clicked.connect(lambda: self.handle_transport(key))
        btn.setMinimumHeight(40)
        return btn
        
    def apply_style(self):
        """Apply modern light mode styling."""
        self.setStyleSheet("""
            /* Main Window */
            QMainWindow {
                background-color: #f8f9fa;
                color: #2c3e50;
            }
            
            /* Central Widget */
            QWidget {
                background-color: #f8f9fa;
                color: #2c3e50;
            }
            
            /* Group Boxes */
            QGroupBox {
                color: #2c3e50;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                padding-left: 10px;
                padding-right: 10px;
                padding-bottom: 10px;
                font-weight: 600;
                font-size: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #2563eb;
            }
            
            /* Buttons - Primary (Blue) */
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                padding: 10px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
            QPushButton:disabled {
                background-color: #e5e7eb;
                color: #9ca3af;
            }
            
            /* Buttons - Delete (Red) */
            QPushButton#deleteBtn, QPushButton[styleType="delete"] {
                background-color: #dc2626;
            }
            QPushButton#deleteBtn:hover, QPushButton[styleType="delete"]:hover {
                background-color: #b91c1c;
            }
            
            /* Buttons - Secondary (Orange) */
            QPushButton#secondaryBtn {
                background-color: #ea580c;
            }
            QPushButton#secondaryBtn:hover {
                background-color: #c2410c;
            }
            
            /* Tab Widget */
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f3f4f6;
                color: #6b7280;
                padding: 8px 20px;
                border: 1px solid #e5e7eb;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #2563eb;
                color: white;
                border: 1px solid #2563eb;
            }
            QTabBar::tab:hover {
                background-color: #e5e7eb;
            }
            
            /* Line Edit / Text Input */
            QLineEdit {
                background-color: #ffffff;
                color: #2c3e50;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 2px solid #2563eb;
            }
            
            /* Combo Box */
            QComboBox {
                background-color: #ffffff;
                color: #2c3e50;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 8px;
                font-size: 11px;
            }
            QComboBox:focus {
                border: 2px solid #2563eb;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(noimg);
            }
            
            /* Text Edit / Console */
            QTextEdit {
                background-color: #ffffff;
                color: #4b5563;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Courier New', monospace;
                font-size: 10px;
            }
            
            /* Label */
            QLabel {
                color: #2c3e50;
            }
            
            /* Progress Bar */
            QProgressBar {
                background-color: #e5e7eb;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 4px;
            }
            
            /* List Widget */
            QListWidget {
                background-color: #ffffff;
                color: #2c3e50;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                outline: none;
            }
            QListWidget::item {
                padding: 6px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #f3f4f6;
            }
            QListWidget::item:selected {
                background-color: #2563eb;
                color: white;
            }
            
            /* Tree Widget */
            QTreeWidget {
                background-color: #ffffff;
                color: #2c3e50;
                border: 1px solid #d1d5db;
                border-radius: 6px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:hover {
                background-color: #f3f4f6;
            }
            QTreeWidget::item:selected {
                background-color: #2563eb;
                color: white;
            }
            
            /* Slider */
            QSlider::groove:horizontal {
                background-color: #d1d5db;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background-color: #2563eb;
                width: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background-color: #1d4ed8;
            }
            
            /* Scroll Bar */
            QScrollBar:vertical {
                background-color: #f8f9fa;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #cbd5e1;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #94a3b8;
            }
            QScrollBar:horizontal {
                background-color: #f8f9fa;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background-color: #cbd5e1;
                border-radius: 6px;
                min-width: 20px;
            }
            
            /* Message Box */
            QMessageBox {
                background-color: #f8f9fa;
            }
            QMessageBox QLabel {
                color: #2c3e50;
            }
            
            /* Dialog */
            QDialog {
                background-color: #f8f9fa;
            }
            
            /* Checkbox */
            QCheckBox {
                color: #2c3e50;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #2563eb;
                border: 1px solid #2563eb;
                border-radius: 3px;
            }
        """)
        
    def scan_devices(self):
        """Start device scanning."""
        if self.scanner and self.scanner.isRunning():
            return
        
        # Parse network input
        networks = []
        network_text = self.network_input.text().strip()
        
        if network_text:
            # User specified network(s)
            for net in network_text.split(','):
                net = net.strip()
                if net:
                    networks.append(net)
            self.statusBar().showMessage(f'Scanne Netzwerk(e): {network_text}...')
        else:
            # Auto-detect - nur aktive Netzwerke scannen
            networks = get_local_networks()
            if not networks:
                self.statusBar().showMessage(
                    "Keine Netzwerke",
                    "Konnte keine aktiven Netzwerke erkennen.\n"
                    "Bitte manuell eingeben (z.B. 192.168.50.0/24)"
                )
                return
            
            self.statusBar().showMessage(f'Scanne aktive Netzwerke: {", ".join(networks)}...')
        
        self.scan_progress.setVisible(True)
        
        self.scanner = DeviceScanner(networks=networks)
        self.scanner.devices_found.connect(self.on_devices_found)
        self.scanner.scan_complete.connect(self.on_scan_complete)
        self.scanner.progress.connect(self.on_scan_progress)
        self.scanner.start()
    
    def on_scan_progress(self, message):
        """Handle scan progress updates."""
        self.statusBar().showMessage(message)
        
    def on_devices_found(self, devices):
        """Handle found devices."""
        self.devices = devices
        self.device_combo.clear()
        
        for device in devices:
            display_text = f"{device['name']} ({device['type']}) - {device['ip']}"
            self.device_combo.addItem(display_text, device)
            
        if devices:
            self.save_devices()
            # Update group manager with new devices
            self.group_manager.set_devices(devices)
            
    def on_scan_complete(self):
        """Handle scan completion."""
        self.scan_progress.setVisible(False)
        count = len(self.devices)
        self.statusBar().showMessage(f'{count} Gerät(e) gefunden', 3000)
        
    def on_device_selected(self, index):
        """Handle device selection."""
        if index < 0:
            return
            
        device = self.device_combo.itemData(index)
        if device:
            # Stop refresh timer before switching
            self.refresh_timer.stop()
            
            # Disconnect old WebSocket if any
            if self.websocket:
                try:
                    self.websocket.disconnect()
                except Exception as e:
                    print(f"Error disconnecting WebSocket: {e}")
                self.websocket = None
            
            self.current_device = device
            
            # Clear streaming metadata cache when switching devices
            self.media_player.currently_streaming_file = None
            self.media_player.streaming_start_time = None
            
            # Quick check if device is reachable before attempting connection
            test_controller = SoundTouchController(device['ip'], timeout=2)
            if not test_controller.is_reachable(timeout=2):
                self.statusBar().showMessage(f"Gerät {device['name']} ist nicht erreichbar", 5000)
                self.current_device = None
                self.controller = None
                return
            
            self.controller = SoundTouchController(device['ip'])
            self.statusBar().showMessage(f"Verbunden mit {device['name']}")
            
            # Update media player with current device
            self.media_player.set_controller(self.controller, device)
            
            # Try to connect WebSocket for real-time updates (with short timeout)
            try:
                self.websocket = SoundTouchWebSocket(device['ip'])
                if self.websocket.connect():
                    self.statusBar().showMessage(f"Verbunden mit {device['name']} (WebSocket aktiv)", 3000)
                    # Register callbacks for real-time updates
                    self.websocket.add_callback('nowPlayingUpdated', self._on_now_playing_updated)
                    self.websocket.add_callback('volumeUpdated', self._on_volume_updated)
                    self.websocket.add_callback('bassUpdated', self._on_bass_updated)
                    # Fallback polling every 10 seconds (in case WebSocket drops)
                    self.refresh_timer.start(10000)
                else:
                    self.statusBar().showMessage(f"Verbunden mit {device['name']} (Polling-Modus)", 3000)
                    # WebSocket failed, use polling with shorter interval
                    self.refresh_timer.start(1500)  # Update every 1.5 seconds
            except Exception as e:
                # WebSocket connection failed, use polling instead
                print(f"WebSocket connection failed: {e}")
                self.statusBar().showMessage(f"Verbunden mit {device['name']} (Polling-Modus)", 3000)
                self.refresh_timer.start(1500)  # Update every 1.5 seconds
            
            # Immediately refresh to show current state
            self.update_now_playing()
            self.update_device_info()
            # capture initial source if available
            try:
                info = self.controller.get_nowplaying()
                if info and info.get('source'):
                    self.last_source = info.get('source')
            except Exception:
                pass
    
    def open_device_setup(self):
        """Öffnet den Device Setup Wizard."""
        # Pause WebSocket während Setup um Konflikte zu vermeiden
        websocket_was_active = False
        if self.websocket:
            self.statusBar().showMessage("Pausiere WebSocket für Setup...", 2000)
            try:
                self.websocket.disconnect()
                websocket_was_active = True
            except:
                pass
            self.websocket = None
        
        # Pausiere auch den Refresh-Timer
        timer_was_active = self.refresh_timer.isActive()
        if timer_was_active:
            self.refresh_timer.stop()
        
        wizard = DeviceSetupWizard(self)
        result = wizard.exec_()
        
        # Reaktiviere WebSocket/Timer wenn Setup abgeschlossen
        if timer_was_active or websocket_was_active:
            # Wenn ein Gerät ausgewählt ist, stelle Verbindung wieder her
            if self.controller:
                device = self.device_combo.currentData()
                if device:
                    try:
                        self.websocket = SoundTouchWebSocket(device['ip'])
                        if self.websocket.connect():
                            self.statusBar().showMessage(f"WebSocket wieder verbunden mit {device['name']}", 3000)
                            self.websocket.add_callback('nowPlayingUpdated', self._on_now_playing_updated)
                            self.websocket.add_callback('volumeUpdated', self._on_volume_updated)
                            self.websocket.add_callback('bassUpdated', self._on_bass_updated)
                            self.refresh_timer.start(10000)
                        else:
                            self.refresh_timer.start(2000)
                    except:
                        self.refresh_timer.start(2000)
        
        if result == wizard.Accepted:
            # Nach erfolgreichem Setup neu scannen
            self.statusBar().showMessage("Scanne nach neuem Gerät...")
            QTimer.singleShot(1000, self.scan_devices)
            
    def send_key(self, key):
        """Send key command to device."""
        if not self.controller:
            return
            
        try:
            success = self.controller.send_key(key)
            if success:
                self.statusBar().showMessage(f"Befehl '{key}' gesendet", 2000)
                # Update display after command
                QTimer.singleShot(500, self.update_now_playing)
            else:
                self.statusBar().showMessage(f"Fehler beim Senden von '{key}'", 3000)
        except Exception as e:
            self.statusBar().showMessage(f"Fehler beim Senden von '{key}': {e}", 5000)

    def is_dlna_source(self) -> bool:
        """Heuristically detect DLNA/STORED_MUSIC/UPNP source."""
        src = self.last_source
        if not src:
            # Try reading from label as fallback
            text = self.source_label.text() if hasattr(self, 'source_label') else ''
            if ':' in text:
                src = text.split(':', 1)[1].strip()
        if not src:
            return False
        src_up = str(src).upper()
        return "DLNA" in src_up or "STORED_MUSIC" in src_up or "UPNP" in src_up

    def handle_transport(self, key: str):
        """Dispatch transport buttons based on current source."""
        # Refresh source if unknown
        if not self.last_source and self.controller:
            try:
                info = self.controller.get_nowplaying()
                if info and info.get('source'):
                    self.last_source = info.get('source')
            except Exception:
                pass

        # If we are on DLNA/STORED_MUSIC, use media player playlist logic
        if self.is_dlna_source():
            if key == "NEXT_TRACK":
                return self.media_player.play_next()
            if key == "PREV_TRACK":
                return self.media_player.play_previous()
            if key == "PLAY":
                # restart current selection via DLNA helper
                return self.media_player.stream_to_device()
            if key == "PAUSE":
                # Pause via key still works fine
                return self.send_key("PAUSE")

        # Fallback: normal key commands
        return self.send_key(key)
            
    def _on_now_playing_updated(self, data):
        """WebSocket callback for now playing updates."""
        try:
            # Only update if this is from the currently selected device
            if not self.current_device or not self.controller:
                return
            
            self.track_label.setText(f"Track: {data.get('track', 'Unknown')}")
            self.artist_label.setText(f"Artist: {data.get('artist', 'Unknown')}")
            self.album_label.setText(f"Album: {data.get('album', 'Unknown')}")
            src = data.get('source', 'Unknown')
            self.source_label.setText(f"Source: {src}")
            self.last_source = src
        except Exception as e:
            print(f"Error in now_playing callback: {e}")
    
    def _on_volume_updated(self, data):
        """WebSocket callback for volume updates."""
        try:
            # Only update if this is from the currently selected device
            if not self.current_device or not self.controller:
                return
            
            volume = data.get('actualvolume', 0)
            # Volume is now controlled via buttons, no slider to update
            pass
        except Exception as e:
            print(f"Error in volume callback: {e}")
    
    def _on_bass_updated(self, data):
        """WebSocket callback for bass updates."""
        # Could update a bass slider if you add one to the GUI
        pass
    
    def update_now_playing(self):
        """Update now playing information (fallback when WebSocket not available)."""
        if not self.controller or not self.current_device:
            return
            
        try:
            # First check if we're currently streaming a file locally
            streaming_metadata = self.media_player.get_streaming_metadata()
            
            if streaming_metadata:
                # Show metadata from locally streamed file
                self.track_label.setText(f"Track: {streaming_metadata['track']}")
                self.artist_label.setText(f"Artist: {streaming_metadata['artist']}")
                self.album_label.setText(f"Album: {streaming_metadata['album']}")
                self.source_label.setText("Source: Lokal (Streaming)")
                self.last_source = "Lokal"
            else:
                # Fall back to device info
                info = self.controller.get_nowplaying()
                if info:
                    self.track_label.setText(f"Track: {info.track}")
                    self.artist_label.setText(f"Artist: {info.artist}")
                    self.album_label.setText(f"Album: {info.album}")
                    self.source_label.setText(f"Source: {info.source}")
                    self.last_source = info.source
            
            # Volume is now controlled via buttons
        except Exception as e:
            pass

            
    def update_device_info(self):
        """Update device information display."""
        if not self.current_device:
            return
            
        info_text = f"""
<h3>{self.current_device['name']}</h3>
<p><b>Typ:</b> {self.current_device['type']}</p>
<p><b>IP:</b> {self.current_device['ip']}</p>
<p><b>MAC:</b> {self.current_device['mac']}</p>
<p><b>Device ID:</b> {self.current_device['deviceID']}</p>
<p><b>URL:</b> {self.current_device['url']}</p>
"""
        
        if 'components' in self.current_device:
            info_text += "<h4>Komponenten:</h4><ul>"
            for comp in self.current_device['components']:
                info_text += f"<li><b>{comp['category']}:</b> {comp.get('version', 'N/A')}</li>"
            info_text += "</ul>"
            
        self.info_text.setHtml(info_text)
        
    def load_saved_devices(self):
        """Load devices from saved file."""
        if os.path.exists('soundtouch_devices.json'):
            try:
                with open('soundtouch_devices.json', 'r') as f:
                    devices = json.load(f)
                    if devices:
                        self.on_devices_found(devices)
            except Exception as e:
                print(f"Error loading devices: {e}")
                
    def save_devices(self):
        """Save current devices to file."""
        try:
            with open('soundtouch_devices.json', 'w') as f:
                json.dump(self.devices, f, indent=2)
        except Exception as e:
            print(f"Error saving devices: {e}")
            
    def closeEvent(self, event):
        """Handle window close."""
        self.refresh_timer.stop()
        if self.websocket:
            try:
                self.websocket.disconnect()
            except Exception as e:
                print(f"Error disconnecting WebSocket: {e}")
            self.websocket = None
        if self.scanner and self.scanner.isRunning():
            self.scanner.quit()
            self.scanner.wait()
        event.accept()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("SoundTouch Controller")
    
    # Set application icon if available
    # app.setWindowIcon(QIcon('icon.png'))
    
    gui = SoundTouchGUI()
    gui.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
