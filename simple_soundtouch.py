#!/usr/bin/env python3
"""
Simple SoundTouch Controller v3
Minimalist GUI with all features

Features:
- Device Discovery for WiFi AND Ethernet networks
- Device Setup for new devices
- Theme Selector
- System Audio Capture (works with any app!)
- Volume Buttons (+/-)
- Multi-Room Groups
"""

import sys
import threading
import json
import os
from tunein_helper import TuneInHelper
import device_ssh

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QComboBox,
                             QGroupBox, QListWidget, QMessageBox, QMenuBar, QMenu,
                             QDialog, QLineEdit, QListWidgetItem, QTabWidget, QInputDialog,
                             QScrollArea, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QAction

from soundtouch_lib import SoundTouchDiscovery, SoundTouchController, SoundTouchGroupManager
from system_audio_capture import SystemAudioCapture

# Optional imports
DEVICE_SETUP_AVAILABLE = True  # lazy import inside handler

from app_theme import APP_STYLE
import i18n


class Signals(QObject):
    """Signal emitter for thread-safe GUI updates."""
    device_found = pyqtSignal(str, str)  # name, ip
    status_update = pyqtSignal(str)
    capture_status = pyqtSignal(bool)  # is_capturing
    

class SimpleSoundTouchGUI(QMainWindow):
    """Minimalist SoundTouch controller with System Audio Capture."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SoundTouch - Simple Controller v3")
        self.setMinimumSize(900, 700)
        
        # Backend
        self.device: SoundTouchController = None
        self.audio_capture = SystemAudioCapture()
        self.signals = Signals()
        self.all_devices = []
        self.group_manager = None
        self.current_volume = 30
        self.devices_file_path = os.path.join(os.path.dirname(__file__), "soundtouch_devices.json")
        self.groups_file_path = os.path.join(os.path.dirname(__file__), "group_config.json")        
        self.saved_groups = []  # Locally saved group configurations
        self.active_group = None  # Currently active group
        self.favorites = []  # Internetradio-Favoriten (unabhängig von Presets)
        self.favorites_file_path = os.path.join(os.path.dirname(__file__), "radio_favorites.json")

        # TuneIn
        self.tunein_helper = None
        self.search_results = []
        
        # Connect signals
        self.signals.device_found.connect(self._on_device_found)
        self.signals.status_update.connect(self._on_status_update)
        self.signals.capture_status.connect(self._on_capture_status)
        
        # Apply the single app design ("Midnight")
        self._apply_theme()

        # Setup UI
        self._setup_ui()

        # Gespeicherte Gruppen ZUERST laden, damit sie beim Aufbau des
        # Geräte-Dropdowns schon enthalten sind (sonst erst nach Refresh sichtbar).
        self._load_groups()

        # Radio-Favoriten laden (füllt die Liste im Favoriten-Tab)
        self._load_favorites()

        # Load cached devices; if none, start discovery
        if not self._load_saved_devices():
            self._discover_devices()

        # Check audio capture capabilities
        self._check_audio_capture()
        
    def _apply_theme(self):
        """Apply the single app design ("Midnight") app-wide."""
        # App-weit setzen, damit auch Dialoge/Menüs das Design erben
        app = QApplication.instance()
        if app:
            app.setStyleSheet(APP_STYLE)
        else:
            self.setStyleSheet(APP_STYLE)
    
    def _load_saved_devices(self) -> bool:
        """Load previously saved devices to avoid scanning each start."""
        try:
            if not os.path.exists(self.devices_file_path):
                return False
            with open(self.devices_file_path, 'r', encoding='utf-8') as f:
                devices = json.load(f)
            if not devices:
                return False

            self.all_devices = devices
            self.device_combo.clear()
            self.device_combo.addItem("-- Select Device --")
            
            # Add saved groups first
            if self.saved_groups:
                for group in self.saved_groups:
                    group_name = group.get('name', 'Unnamed Group')
                    self.device_combo.addItem(f"📻 {group_name}", userData=group)
            
            # Then add individual devices
            for device in devices:
                name = device.get('name', 'Unknown')
                ip = device.get('ip', '')
                self.device_combo.addItem(f"{name} ({ip})", userData=ip)
            self._update_devices_file()
            self.group_manager = SoundTouchGroupManager(devices)
            self.signals.status_update.emit("💾 Loaded saved devices")
            return True
        except Exception as e:
            print(f"Failed to load saved devices: {e}")
            return False

    def _save_devices(self):
        """Persist discovered devices."""
        try:
            with open(self.devices_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.all_devices, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save devices: {e}")
    
    def _load_groups(self):
        """Load saved group configurations."""
        try:
            if os.path.exists(self.groups_file_path):
                with open(self.groups_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.saved_groups = data.get('groups', [])
                    print(f"✅ Loaded {len(self.saved_groups)} saved groups")
        except Exception as e:
            print(f"Failed to load groups: {e}")
            self.saved_groups = []
    
    def _save_groups(self):
        """Persist group configurations."""
        try:
            with open(self.groups_file_path, 'w', encoding='utf-8') as f:
                json.dump({'groups': self.saved_groups}, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved {len(self.saved_groups)} groups")
        except Exception as e:
            print(f"Failed to save groups: {e}")
    
    def _activate_group(self, group_config: dict) -> bool:
        """Activate a multi-room group from saved configuration."""
        try:
            # Find master and slave devices
            master_ip = group_config.get('master_ip')
            slave_ips = group_config.get('slave_ips', [])
            
            master_device = next((d for d in self.all_devices if d['ip'] == master_ip), None)
            if not master_device:
                QMessageBox.warning(self, "Error", f"Master device not found: {master_ip}")
                return False
            
            slave_devices = [d for d in self.all_devices if d['ip'] in slave_ips]
            if len(slave_devices) != len(slave_ips):
                QMessageBox.warning(self, "Warning", "Some slave devices are not available")
            
            # Create the group using group manager
            if not self.group_manager:
                self.group_manager = SoundTouchGroupManager(self.all_devices)
            
            success = self.group_manager.create_group(
                master_device, 
                slave_devices, 
                group_config.get('name', 'Group')
            )
            
            if success:
                self.active_group = group_config
                self.device = SoundTouchController(master_ip)  # Control via master
                self.signals.status_update.emit(f"✅ Group '{group_config['name']}' activated")
                # Einzel-Lautstärke-Regler leicht verzögert aufbauen (Netzabfragen),
                # damit die UI vorher aktualisiert.
                QTimer.singleShot(150, self._refresh_volume_section)
                return True
            else:
                QMessageBox.warning(self, "Error", "Failed to create group")
                return False
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to activate group: {e}")
            return False
    
    def _deactivate_group(self) -> bool:
        """Deactivate the current active group."""
        if not self.active_group or not self.group_manager:
            return True
        
        try:
            # Find and remove all groups - work backwards to avoid index issues
            groups = self.group_manager.get_groups()
            for i in range(len(groups) - 1, -1, -1):
                group = groups[i]
                # Remove all slaves from this group
                slaves_to_remove = group['slaves'][:]
                for slave in slaves_to_remove:
                    self.group_manager.remove_from_group(i, slave)
            
            self.active_group = None
            self.signals.status_update.emit("✅ Group deactivated")
            self._refresh_volume_section()
            return True

        except Exception as e:
            print(f"Failed to deactivate group: {e}")
            return False

    def _clear_layout(self, layout):
        """Entfernt alle Widgets/Sub-Layouts aus einem Layout."""
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            else:
                sub = item.layout()
                if sub is not None:
                    self._clear_layout(sub)

    def _refresh_volume_section(self):
        """Baut die Lautstärke-Sektion im Control-Tab auf:
        - Gruppe aktiv: Gruppen-Regler (alle zusammen) + je Lautsprecher eine Zeile
        - einzelnes Gerät: eine Zeile
        - nichts gewählt: Hinweis
        """
        if not hasattr(self, 'volume_container'):
            return
        self._clear_layout(self.volume_container)
        self._volume_labels = {}

        if self.active_group:
            master_ip = self.active_group.get('master_ip')
            ips = [ip for ip in ([master_ip] + list(self.active_group.get('slave_ips', []))) if ip]

            # Gruppen-Regler: verschiebt ALLE relativ (behält die Balance untereinander)
            grow = QHBoxLayout()
            glbl = QLabel("🔊 Gruppe (alle)")
            glbl.setMinimumWidth(170)
            glbl.setStyleSheet("font-weight: 700;")
            grow.addWidget(glbl)
            gminus = QPushButton("🔉 −"); gminus.setMaximumWidth(64)
            gplus = QPushButton("🔊 ＋"); gplus.setMaximumWidth(64)
            gminus.clicked.connect(lambda: self._set_group_volume(-5))
            gplus.clicked.connect(lambda: self._set_group_volume(+5))
            grow.addWidget(gminus)
            grow.addWidget(gplus)
            grow.addStretch()
            self.volume_container.addLayout(grow)

            sep = QLabel("Einzeln:")
            sep.setStyleSheet("color: #8A909C; font-style: italic; padding-top: 4px;")
            self.volume_container.addWidget(sep)

            for ip in ips:
                self._add_volume_row(ip, master=(ip == master_ip))
            return

        if self.device is not None:
            self._add_volume_row(self.device.ip, single=True)
            return

        hint = QLabel("Kein Gerät ausgewählt.")
        hint.setStyleSheet("color: #8A909C; font-style: italic;")
        self.volume_container.addWidget(hint)

    def _add_volume_row(self, ip, master=False, single=False):
        """Eine Lautstärke-Zeile für einen Lautsprecher: [Name] [−] [Pegel] [＋]."""
        dev = next((d for d in self.all_devices if d.get('ip') == ip), None)
        name = (dev.get('name') if dev else None) or ip
        icon = "👑 " if master else ("🔊 " if single else "🔈 ")

        row = QHBoxLayout()
        lbl = QLabel(icon + name)
        lbl.setMinimumWidth(170)
        row.addWidget(lbl)

        btn_minus = QPushButton("🔉 −"); btn_minus.setMaximumWidth(64)
        level = QLabel("--"); level.setMinimumWidth(44)
        level.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_plus = QPushButton("🔊 ＋"); btn_plus.setMaximumWidth(64)

        try:
            vd = SoundTouchController(ip, timeout=3).get_volume()
            if vd:
                level.setText(str(vd.get('actualvolume', '--')))
        except Exception:
            pass

        self._volume_labels[ip] = level
        btn_minus.clicked.connect(lambda _, p=ip, l=level: self._set_member_volume(p, -5, l))
        btn_plus.clicked.connect(lambda _, p=ip, l=level: self._set_member_volume(p, +5, l))
        row.addWidget(btn_minus)
        row.addWidget(level)
        row.addWidget(btn_plus)
        row.addStretch()
        self.volume_container.addLayout(row)

    def _set_member_volume(self, ip, delta, level_label=None):
        """Ändert die Lautstärke eines einzelnen Lautsprechers direkt per IP."""
        try:
            c = SoundTouchController(ip, timeout=3)
            vd = c.get_volume()
            if not vd:
                if level_label:
                    level_label.setText("--")
                self.signals.status_update.emit(f"⚠️ {ip} nicht erreichbar (Standby?)")
                return
            current = vd.get('actualvolume', 0)
            new = max(0, min(100, current + delta))
            if c.set_volume(new):
                if level_label:
                    level_label.setText(str(new))
                self.signals.status_update.emit(f"🔊 {ip} → {new}")
            else:
                self.signals.status_update.emit(f"⚠️ Lautstärke ({ip}) fehlgeschlagen")
        except Exception as e:
            self.signals.status_update.emit(f"⚠️ Lautstärke ({ip}): {e}")

    def _set_group_volume(self, delta):
        """Ändert die Lautstärke ALLER Lautsprecher der Gruppe relativ (behält die Balance)."""
        if not self.active_group:
            return
        master_ip = self.active_group.get('master_ip')
        ips = [ip for ip in ([master_ip] + list(self.active_group.get('slave_ips', []))) if ip]
        for ip in ips:
            self._set_member_volume(ip, delta, self._volume_labels.get(ip))
        self.signals.status_update.emit(f"🔊 Gruppe {'+' if delta >= 0 else ''}{delta}")

    def _setup_ui(self):
        """Create the UI with tabs."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        # Title
        title = QLabel("🔊 Bose SoundTouch - Simple Controller")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        # Shared Device Selection (visible on all tabs)
        self.device_group = QGroupBox("📡 Device")
        self.device_layout = QVBoxLayout()

        self.device_combo = QComboBox()
        self.device_combo.currentTextChanged.connect(self._on_device_selected)
        self.device_layout.addWidget(self.device_combo)

        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.clicked.connect(self._discover_devices)
        self.device_layout.addWidget(self.btn_refresh)

        self.btn_power = QPushButton("⚡ Power Toggle")
        self.btn_power.clicked.connect(self._toggle_power)
        self.btn_power.setEnabled(False)
        self.device_layout.addWidget(self.btn_power)

        self.device_group.setLayout(self.device_layout)
        main_layout.addWidget(self.device_group)
        
        # Create tab widget
        tabs = QTabWidget()
        main_layout.addWidget(tabs)
        
        # Tabs: jede Seite als Ganzes scrollbar (nicht die einzelnen Kacheln),
        # damit bei wenig Fensterhöhe nichts gestaucht/abgeschnitten wird.
        tabs.addTab(self._scrollable(self._create_control_tab()), "🎵 Control")
        tabs.addTab(self._scrollable(self._create_presets_tab()), "⭐ Presets")
        tabs.addTab(self._scrollable(self._create_favorites_tab()), "❤️ Favoriten")
        tabs.addTab(self._scrollable(self._create_tunein_tab()), "📻 TuneIn")
        tabs.addTab(self._scrollable(self._create_groups_tab()), "🏠 Groups")
        tabs.addTab(self._scrollable(self._create_settings_tab()), "⚙️ Settings")
        
        # Status Bar
        self.status_label = QLabel("Ready")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("padding: 6px 12px; background: #1E2129; border-radius: 6px; color: #8A909C;")
        main_layout.addWidget(self.status_label)
    
    def _scrollable(self, inner: QWidget) -> QScrollArea:
        """Wickelt eine Tab-Seite in einen vertikalen Scroll-Bereich, damit die
        GANZE Seite scrollt (nicht die einzelnen Kacheln) und nichts gestaucht
        oder abgeschnitten wird, wenn der Inhalt höher als das Fenster ist."""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setWidget(inner)
        return area

    def _create_control_tab(self) -> QWidget:
        """Create the main control tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Playback / Transport controls
        playback_group = QGroupBox("⏯️ Wiedergabe")
        playback_layout = QHBoxLayout()
        self.transport_buttons = []
        for label, key in [("⏮️", "PREV_TRACK"), ("▶️ / ⏸️", "PLAY_PAUSE"),
                            ("⏹️", "STOP"), ("⏭️", "NEXT_TRACK")]:
            btn = QPushButton(label)
            btn.setMinimumHeight(46)
            btn.clicked.connect(lambda checked, k=key: self._transport(k))
            btn.setEnabled(False)
            playback_layout.addWidget(btn)
            self.transport_buttons.append(btn)
        playback_group.setLayout(playback_layout)
        layout.addWidget(playback_group)

        # System Audio Capture
        audio_group = QGroupBox("🎵 System Audio Capture")
        audio_layout = QVBoxLayout()
        
        self.audio_status_label = QLabel("Checking system audio capabilities...")
        self.audio_status_label.setWordWrap(True)
        audio_layout.addWidget(self.audio_status_label)
        
        capture_controls = QHBoxLayout()
        self.btn_start_capture = QPushButton("▶️ Start Capture")
        self.btn_start_capture.clicked.connect(self._start_capture)
        self.btn_start_capture.setEnabled(False)
        capture_controls.addWidget(self.btn_start_capture)
        
        self.btn_stop_capture = QPushButton("⏹️ Stop Capture")
        self.btn_stop_capture.clicked.connect(self._stop_capture)
        self.btn_stop_capture.setEnabled(False)
        capture_controls.addWidget(self.btn_stop_capture)
        
        audio_layout.addLayout(capture_controls)
        
        info_label = QLabel(
            "💡 Play audio from ANY app (Browser, Spotify, Games, etc.)\n"
            "and it will be streamed to your Bose device!"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #8A909C; font-style: italic;")
        audio_layout.addWidget(info_label)
        
        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)
        
        # Volume – dynamisch: einzelnes Gerät ODER Gruppe (alle + je Speaker)
        self.volume_group = QGroupBox("🔊 Volume")
        vol_outer = QVBoxLayout()
        self.volume_container = QVBoxLayout()
        self.volume_container.setSpacing(8)
        vol_outer.addLayout(self.volume_container)
        self.volume_group.setLayout(vol_outer)
        layout.addWidget(self.volume_group)
        self._refresh_volume_section()

        layout.addStretch()
        return tab
    
    def _create_presets_tab(self) -> QWidget:
        """Create the presets management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Current Presets Display
        presets_group = QGroupBox("⭐ Saved Presets")
        presets_layout = QVBoxLayout()
        
        # Presets list
        self.presets_list = QListWidget()
        self.presets_list.setMinimumHeight(150)
        presets_layout.addWidget(self.presets_list)
        
        # Preset action buttons
        preset_actions_layout = QHBoxLayout()
        
        self.btn_refresh_presets = QPushButton("🔄 Refresh Presets")
        self.btn_refresh_presets.clicked.connect(self._refresh_presets)
        self.btn_refresh_presets.setEnabled(False)
        preset_actions_layout.addWidget(self.btn_refresh_presets)
        
        self.btn_play_preset = QPushButton("▶️ Play Selected")
        self.btn_play_preset.clicked.connect(self._play_selected_preset)
        self.btn_play_preset.setEnabled(False)
        preset_actions_layout.addWidget(self.btn_play_preset)
        
        presets_layout.addLayout(preset_actions_layout)
        presets_group.setLayout(presets_layout)
        layout.addWidget(presets_group)
        
        # Quick Preset Buttons
        quick_presets_group = QGroupBox("🎯 Quick Access")
        quick_layout = QVBoxLayout()
        
        # Row 1: Presets 1-3
        row1 = QHBoxLayout()
        self.preset_buttons = []
        for i in range(1, 4):
            btn = QPushButton(f"Preset {i}")
            btn.clicked.connect(lambda checked, preset=i: self._recall_preset(preset))
            btn.setEnabled(False)
            btn.setMinimumHeight(50)
            row1.addWidget(btn)
            self.preset_buttons.append(btn)
        quick_layout.addLayout(row1)
        
        # Row 2: Presets 4-6
        row2 = QHBoxLayout()
        for i in range(4, 7):
            btn = QPushButton(f"Preset {i}")
            btn.clicked.connect(lambda checked, preset=i: self._recall_preset(preset))
            btn.setEnabled(False)
            btn.setMinimumHeight(50)
            row2.addWidget(btn)
            self.preset_buttons.append(btn)
        quick_layout.addLayout(row2)
        
        quick_presets_group.setLayout(quick_layout)
        layout.addWidget(quick_presets_group)
        
        # Store Current Content as Preset
        store_group = QGroupBox("💾 Store Current as Preset")
        store_layout = QVBoxLayout()
        
        store_label = QLabel("Store what's currently playing to a preset slot:")
        store_layout.addWidget(store_label)
        
        store_buttons_layout = QHBoxLayout()
        self.store_preset_buttons = []
        for i in range(1, 7):
            btn = QPushButton(f"→ Slot {i}")
            btn.clicked.connect(lambda checked, preset=i: self._store_current_to_preset(preset))
            btn.setEnabled(False)
            store_buttons_layout.addWidget(btn)
            self.store_preset_buttons.append(btn)
        store_layout.addLayout(store_buttons_layout)
        
        store_group.setLayout(store_layout)
        layout.addWidget(store_group)

        layout.addStretch()
        return tab

    # ---------------- Radio-Favoriten ----------------

    def _create_favorites_tab(self) -> QWidget:
        """Favoritenliste fürs Internetradio – unabhängig von Presets."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        fav_group = QGroupBox("❤️ Radio-Favoriten")
        fav_layout = QVBoxLayout()

        self.favorites_list = QListWidget()
        self.favorites_list.setMinimumHeight(180)
        self.favorites_list.itemDoubleClicked.connect(lambda _: self._play_selected_favorite())
        fav_layout.addWidget(self.favorites_list)

        actions = QHBoxLayout()
        btn_play = QPushButton("▶️ Abspielen")
        btn_play.clicked.connect(self._play_selected_favorite)
        actions.addWidget(btn_play)
        btn_preset = QPushButton("💾 Auf Preset legen…")
        btn_preset.clicked.connect(self._save_favorite_to_preset)
        actions.addWidget(btn_preset)
        btn_remove = QPushButton("🗑️ Entfernen")
        btn_remove.setProperty("danger", True)
        btn_remove.clicked.connect(self._remove_favorite)
        actions.addWidget(btn_remove)
        fav_layout.addLayout(actions)

        fav_group.setLayout(fav_layout)
        layout.addWidget(fav_group)

        add_group = QGroupBox("➕ Favorit hinzufügen")
        add_layout = QVBoxLayout()
        add_layout.addWidget(QLabel("Name und direkte Stream-URL (http):"))
        row = QHBoxLayout()
        self.fav_name_input = QLineEdit()
        self.fav_name_input.setPlaceholderText("Name, z. B. Rock Antenne")
        self.fav_url_input = QLineEdit()
        self.fav_url_input.setPlaceholderText("http://stream.…/stream.mp3")
        row.addWidget(self.fav_name_input)
        row.addWidget(self.fav_url_input, 2)
        btn_add = QPushButton("➕ Hinzufügen")
        btn_add.clicked.connect(self._add_favorite_manual)
        row.addWidget(btn_add)
        add_layout.addLayout(row)

        btn_add_current = QPushButton("➕ Gerade gespielten Sender hinzufügen")
        btn_add_current.clicked.connect(self._add_current_to_favorites)
        add_layout.addWidget(btn_add_current)

        add_group.setLayout(add_layout)
        layout.addWidget(add_group)

        layout.addStretch()
        self._refresh_favorites()
        return tab

    def _load_favorites(self):
        """Favoriten aus radio_favorites.json laden."""
        try:
            if os.path.exists(self.favorites_file_path):
                with open(self.favorites_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.favorites = data.get('favorites', []) if isinstance(data, dict) else []
        except Exception as e:
            print(f"Failed to load favorites: {e}")
            self.favorites = []
        self._refresh_favorites()

    def _save_favorites(self):
        """Favoriten persistent speichern."""
        try:
            with open(self.favorites_file_path, 'w', encoding='utf-8') as f:
                json.dump({'favorites': self.favorites}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save favorites: {e}")

    def _refresh_favorites(self):
        """Favoritenliste im UI neu aufbauen."""
        if not hasattr(self, 'favorites_list'):
            return
        self.favorites_list.clear()
        if not self.favorites:
            item = QListWidgetItem("Noch keine Favoriten – unten hinzufügen oder aus der TuneIn-Suche.")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.favorites_list.addItem(item)
            return
        for i, fav in enumerate(self.favorites):
            it = QListWidgetItem(f"❤️ {fav.get('name', 'Unbenannt')}")
            it.setData(Qt.ItemDataRole.UserRole, i)
            it.setToolTip(fav.get('url', ''))
            self.favorites_list.addItem(it)

    def _selected_favorite(self):
        """Gibt (index, fav) des ausgewählten Favoriten zurück oder (None, None)."""
        items = self.favorites_list.selectedItems()
        if not items:
            return None, None
        idx = items[0].data(Qt.ItemDataRole.UserRole)
        if idx is None or idx >= len(self.favorites):
            return None, None
        return idx, self.favorites[idx]

    def add_favorite(self, name, url):
        """Fügt einen Favoriten hinzu (Duplikate anhand URL vermeiden)."""
        name = (name or '').strip()
        url = (url or '').strip()
        if not url:
            return False
        if not name:
            name = url
        if any((f.get('url') == url) for f in self.favorites):
            self.signals.status_update.emit(f"ℹ️ '{name}' ist schon in den Favoriten")
            return False
        self.favorites.append({'name': name, 'url': url})
        self._save_favorites()
        self._refresh_favorites()
        self.signals.status_update.emit(f"❤️ '{name}' zu Favoriten hinzugefügt")
        return True

    def _add_favorite_manual(self):
        name = self.fav_name_input.text()
        url = self.fav_url_input.text().strip()
        if not url.startswith(('http://', 'https://')):
            QMessageBox.warning(self, "Ungültige URL", "Bitte eine direkte Stream-URL (http://…) angeben.")
            return
        if self.add_favorite(name, url):
            self.fav_name_input.clear()
            self.fav_url_input.clear()

    def _add_current_to_favorites(self):
        if not self.device:
            QMessageBox.warning(self, "Kein Gerät", "Bitte zuerst einen Lautsprecher auswählen.")
            return
        try:
            np = self.device.get_now_playing() or {}
        except Exception:
            np = {}
        url = (np.get('location') or '').strip()
        name = (np.get('track') or np.get('stationName') or 'Radio').strip()
        if not url.startswith('http'):
            QMessageBox.information(self, "Nichts zum Speichern",
                                    "Es läuft gerade kein Internet-Radio-Stream (keine http-URL).")
            return
        self.add_favorite(name, url)

    def _play_selected_favorite(self):
        if not self.device:
            QMessageBox.warning(self, "Kein Gerät", "Bitte zuerst einen Lautsprecher auswählen.")
            return
        idx, fav = self._selected_favorite()
        if fav is None:
            QMessageBox.warning(self, "Keine Auswahl", "Bitte einen Favoriten auswählen.")
            return
        try:
            ok = self.device.play_url_dlna(fav['url'], track=fav.get('name', 'Radio'),
                                           artist="Internet Radio", album="Favorit")
            if ok:
                self.signals.status_update.emit(f"📻 Spiele Favorit: {fav.get('name')}")
            else:
                QMessageBox.warning(self, "Fehler", "Wiedergabe fehlgeschlagen.")
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Wiedergabe fehlgeschlagen: {e}")

    def _remove_favorite(self):
        idx, fav = self._selected_favorite()
        if fav is None:
            QMessageBox.warning(self, "Keine Auswahl", "Bitte einen Favoriten auswählen.")
            return
        self.favorites.pop(idx)
        self._save_favorites()
        self._refresh_favorites()
        self.signals.status_update.emit(f"🗑️ '{fav.get('name')}' entfernt")

    def _save_favorite_to_preset(self):
        if not self.device:
            QMessageBox.warning(self, "Kein Gerät", "Bitte zuerst einen Lautsprecher auswählen.")
            return
        idx, fav = self._selected_favorite()
        if fav is None:
            QMessageBox.warning(self, "Keine Auswahl", "Bitte einen Favoriten auswählen.")
            return
        preset_id, ok = QInputDialog.getInt(
            self, "Auf Preset legen",
            f"'{fav.get('name')}' auf welchen Preset-Slot?", 1, 1, 6, 1)
        if not ok:
            return
        content_item = {
            'source': 'LOCAL_INTERNET_RADIO',
            'location': fav['url'],
            'itemName': fav.get('name', 'Radio'),
            'isPresetable': 'true',
        }
        native_ok = False
        try:
            native_ok = self.device.store_preset(preset_id, content_item)
        except Exception:
            pass
        device_ok = self._write_device_preset(preset_id, fav['url'], fav.get('name', 'Radio'))
        if native_ok or device_ok:
            QMessageBox.information(self, "Erfolg",
                                    f"'{fav.get('name')}' auf Preset {preset_id} gelegt.\n"
                                    f"Drücke die Preset-Taste {preset_id} an der Box.")
        else:
            QMessageBox.warning(self, "Fehler", f"Preset {preset_id} konnte nicht gespeichert werden.")

    def _create_tunein_tab(self) -> QWidget:
        """Create the TuneIn search and browse tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # TuneIn Search
        search_group = QGroupBox("🔍 Search TuneIn")
        search_layout = QVBoxLayout()
        
        search_label = QLabel("Search for radio stations by name, genre, or location:")
        search_label.setWordWrap(True)
        search_layout.addWidget(search_label)
        
        search_input_layout = QHBoxLayout()
        self.tunein_search_input = QLineEdit()
        self.tunein_search_input.setPlaceholderText("e.g., Bayern, Jazz, Berlin, Heavy Metal...")
        self.tunein_search_input.returnPressed.connect(self._search_tunein)
        search_input_layout.addWidget(self.tunein_search_input)
        
        self.btn_search_tunein = QPushButton("🔍 Search")
        self.btn_search_tunein.clicked.connect(self._search_tunein)
        self.btn_search_tunein.setEnabled(False)
        search_input_layout.addWidget(self.btn_search_tunein)
        
        search_layout.addLayout(search_input_layout)
        
        # Search results list
        self.search_results_list = QListWidget()
        self.search_results_list.setMaximumHeight(200)
        self.search_results = []  # Store full station data
        search_layout.addWidget(self.search_results_list)
        
        # Browse results actions
        search_actions = QHBoxLayout()
        
        self.btn_play_search_result = QPushButton("▶️ Play Selected")
        self.btn_play_search_result.clicked.connect(self._play_search_result)
        self.btn_play_search_result.setEnabled(False)
        search_actions.addWidget(self.btn_play_search_result)
        
        self.btn_save_search_result = QPushButton("💾 Save to Preset...")
        self.btn_save_search_result.clicked.connect(self._save_search_result_to_preset)
        self.btn_save_search_result.setEnabled(False)
        search_actions.addWidget(self.btn_save_search_result)

        self.btn_fav_search_result = QPushButton("❤️ Zu Favoriten")
        self.btn_fav_search_result.clicked.connect(self._save_search_to_favorites)
        self.btn_fav_search_result.setEnabled(False)
        search_actions.addWidget(self.btn_fav_search_result)

        search_layout.addLayout(search_actions)
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # Custom TuneIn URL
        custom_group = QGroupBox("🔗 Custom TuneIn Station")
        custom_layout = QVBoxLayout()
        
        custom_label = QLabel("Enter TuneIn station location (e.g., /v1/playback/station/s24939):")
        custom_label.setWordWrap(True)
        custom_layout.addWidget(custom_label)
        
        custom_input_layout = QHBoxLayout()
        self.tunein_location_input = QLineEdit()
        self.tunein_location_input.setPlaceholderText("/v1/playback/station/sXXXXX")
        custom_input_layout.addWidget(self.tunein_location_input)
        
        self.btn_play_custom = QPushButton("▶️ Play")
        self.btn_play_custom.clicked.connect(self._play_custom_tunein)
        self.btn_play_custom.setEnabled(False)
        custom_input_layout.addWidget(self.btn_play_custom)
        
        custom_layout.addLayout(custom_input_layout)
        
        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)
        
        # Info section
        info_label = QLabel(
            "<b>How to find TuneIn station IDs:</b><br>"
            "1. Play a station on your device<br>"
            "2. Check the 'Now Playing' info for the location<br>"
            "3. Use that location here or save it as a preset"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background: #1E2129; border-radius: 8px; color: #8A909C;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        return tab
    
    def _create_groups_tab(self) -> QWidget:
        """Create the groups management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Info label
        info_label = QLabel(
            "💡 Active groups are shown in the device selection dropdown above.\n"
            "Use the buttons below to create or manage saved group configurations."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background: #1E2129; border-radius: 8px; color: #8A909C;")
        layout.addWidget(info_label)
        
        # Create/manage group buttons
        manage_group = QGroupBox("🏠 Group Management")
        manage_layout = QVBoxLayout()
        
        btn_create_new = QPushButton("➕ Create New Group")
        btn_create_new.clicked.connect(self._open_create_group_dialog)
        manage_layout.addWidget(btn_create_new)
        
        btn_manage = QPushButton("✏️ Manage Saved Groups")
        btn_manage.clicked.connect(self._open_manage_groups_dialog)
        manage_layout.addWidget(btn_manage)
        
        manage_group.setLayout(manage_layout)
        layout.addWidget(manage_group)

        layout.addStretch()
        return tab
    
    def _create_settings_tab(self) -> QWidget:
        """Create the settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        settings_label = QLabel("⚙️ Application Settings")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        settings_label.setFont(font)
        layout.addWidget(settings_label)

        # Language / Sprache  (switching restarts the app)
        lang_group = QGroupBox(i18n.t("language"))
        lang_layout = QHBoxLayout()
        self._lang_codes = list(i18n.LANGS.keys())
        self.lang_combo = QComboBox()
        for code in self._lang_codes:
            self.lang_combo.addItem(i18n.LANGS[code])
        self.lang_combo.setCurrentIndex(self._lang_codes.index(i18n.current_language()))
        self.lang_combo.currentIndexChanged.connect(self._change_language)
        lang_layout.addWidget(self.lang_combo)
        lang_layout.addStretch()
        lang_group.setLayout(lang_layout)
        layout.addWidget(lang_group)

        if DEVICE_SETUP_AVAILABLE:
            btn_setup = QPushButton("📱 Setup New Device")
            btn_setup.clicked.connect(self._open_device_setup)
            layout.addWidget(btn_setup)

        # Gerät umbenennen (nur einzelner Lautsprecher, nicht bei aktiver Gruppe)
        rename_group = QGroupBox("✏️ Lautsprecher umbenennen")
        rename_layout = QVBoxLayout()
        hint = QLabel("Benennt den aktuell im Dropdown ausgewählten Lautsprecher um. "
                      "Bei einer aktiven Gruppe nicht verfügbar.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8A909C;")
        rename_layout.addWidget(hint)
        self.btn_rename_device = QPushButton("✏️ Ausgewählten Lautsprecher umbenennen…")
        self.btn_rename_device.clicked.connect(self._rename_device)
        self.btn_rename_device.setEnabled(False)
        rename_layout.addWidget(self.btn_rename_device)
        rename_group.setLayout(rename_layout)
        layout.addWidget(rename_group)

        layout.addStretch()
        return tab

    def _change_language(self, index):
        """Switch UI language (English/German) and restart the app to apply it."""
        codes = getattr(self, "_lang_codes", [])
        if index < 0 or index >= len(codes):
            return
        code = codes[index]
        if code == i18n.current_language():
            return
        reply = QMessageBox.question(
            self, i18n.t("restart_title"), i18n.t("restart_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            i18n.set_language(code)
            i18n.restart_app()
            QApplication.quit()
        else:
            self.lang_combo.blockSignals(True)
            self.lang_combo.setCurrentIndex(codes.index(i18n.current_language()))
            self.lang_combo.blockSignals(False)

    def _rename_device(self):
        """Benennt den aktuell ausgewählten einzelnen Lautsprecher um."""
        if self.active_group:
            QMessageBox.information(
                self, "Gruppe aktiv",
                "Bei einer aktiven Gruppe kann nicht umbenannt werden.\n"
                "Wähle zuerst einen einzelnen Lautsprecher im Dropdown aus."
            )
            return
        if not self.device:
            QMessageBox.warning(self, "Kein Gerät", "Bitte zuerst einen Lautsprecher auswählen.")
            return

        current = ""
        try:
            info = self.device.get_info()
            current = (info or {}).get('name', '') or ''
        except Exception:
            pass

        new_name, ok = QInputDialog.getText(
            self, "Lautsprecher umbenennen", "Neuer Name:", text=current
        )
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name:
            QMessageBox.warning(self, "Ungültig", "Der Name darf nicht leer sein.")
            return

        try:
            if self.device.set_device_name(new_name):
                self.signals.status_update.emit(f"✏️ Umbenannt in '{new_name}'")
                # Discovery neu, damit Dropdown & all_devices den neuen Namen zeigen
                QTimer.singleShot(800, self._discover_devices)
            else:
                QMessageBox.warning(self, "Fehler", "Umbenennen fehlgeschlagen.")
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Umbenennen fehlgeschlagen: {e}")
    
    def _check_audio_capture(self):
        """Check if system audio capture is available."""
        capabilities = self.audio_capture.detect_capabilities()
        
        if capabilities['available']:
            self.audio_status_label.setText(f"✅ {capabilities['message']}")
            self.audio_status_label.setStyleSheet("color: #7CE38B;")
        else:
            self.audio_status_label.setText(f"❌ {capabilities['message']}")
            self.audio_status_label.setStyleSheet("color: #FF6B70;")
    
    def _discover_devices(self):
        """Discover SoundTouch devices on ALL network interfaces."""
        self.btn_refresh.setEnabled(False)
        self.device_combo.clear()
        self.device_combo.addItem("Scanning all networks...")
        self.signals.status_update.emit("🔍 Discovering devices on all networks...")
        
        def scan():
            all_devices = []
            
            # Try to get all network interfaces
            try:
                import netifaces
                scanned_networks = set()
                
                # Virtual/Docker interfaces to skip
                skip_patterns = [
                    'docker', 'br-', 'veth', 'virbr', 'vmnet', 'vbox',
                    'lxc', 'lxd', 'tun', 'tap', 'flannel', 'cni', 'lo'
                ]
                
                for iface in netifaces.interfaces():
                    # Skip virtual/Docker interfaces
                    if any(pattern in iface.lower() for pattern in skip_patterns):
                        continue
                    
                    try:
                        addrs = netifaces.ifaddresses(iface)
                        if netifaces.AF_INET in addrs:
                            for addr in addrs[netifaces.AF_INET]:
                                ip = addr.get('addr')
                                if ip and not ip.startswith('127.'):
                                    # Skip Docker networks (172.17-31.x.x)
                                    parts = ip.split('.')
                                    if parts[0] == '172' and 17 <= int(parts[1]) <= 31:
                                        continue
                                    
                                    # Convert to /24 subnet
                                    network = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
                                    
                                    # Skip if already scanned
                                    if network in scanned_networks:
                                        continue
                                    
                                    scanned_networks.add(network)
                                    self.signals.status_update.emit(f"🔍 Scanning {network} ({iface})...")
                                    
                                    # Scan this network
                                    discovery = SoundTouchDiscovery(network=network)
                                    devices = discovery.scan(max_threads=50, timeout=30)
                                    
                                    # Add unique devices
                                    for device in devices:
                                        # Check if device already found
                                        if not any(d['ip'] == device['ip'] for d in all_devices):
                                            all_devices.append(device)
                    except:
                        continue
                
                if not scanned_networks:
                    # Fallback to default scan
                    self.signals.status_update.emit("🔍 Using default network scan...")
                    discovery = SoundTouchDiscovery()
                    all_devices = discovery.scan()
                    
            except ImportError:
                # netifaces not available, use default scan
                self.signals.status_update.emit("🔍 netifaces not available, using default scan...")
                discovery = SoundTouchDiscovery()
                all_devices = discovery.scan()
            
            # Store all devices
            self.all_devices = all_devices

            # Save cache for next start
            if all_devices:
                self._save_devices()
            
            # Clear combo
            self.device_combo.clear()
            
            if not all_devices:
                self.device_combo.addItem("No devices found")
                self.signals.status_update.emit("❌ No devices found on any network")
            else:
                self.device_combo.addItem("-- Select Device --")
                
                # Add saved groups first
                if self.saved_groups:
                    for group in self.saved_groups:
                        group_name = group.get('name', 'Unnamed Group')
                        # Use special icon for groups
                        self.device_combo.addItem(f"📻 {group_name}", userData=group)
                
                # Then add individual devices
                for device in all_devices:
                    name = device.get('name', 'Unknown')
                    ip = device.get('ip', '')
                    self.signals.device_found.emit(name, ip)
                
                self.signals.status_update.emit(f"✅ Found {len(all_devices)} device(s)")
                
                # Update devices list for groups
                self._update_devices_file()
                
                # Initialize group manager
                if len(all_devices) > 0:
                    self.group_manager = SoundTouchGroupManager(all_devices)
            
            self.btn_refresh.setEnabled(True)
        
        threading.Thread(target=scan, daemon=True).start()
    
    def _on_device_found(self, name: str, ip: str):
        """Add device to combo box."""
        self.device_combo.addItem(f"{name} ({ip})", userData=ip)
    
    def _on_device_selected(self, text: str):
        """Handle device selection (device or group)."""
        if text.startswith("--") or "Scanning" in text or "No devices" in text:
            self.device = None
            self._disable_controls()
            return
        
        # Check if we need to transfer an active stream
        was_capturing = self.audio_capture.is_capturing
        old_device = self.device
        
        # Get selection data (IP or group config)
        selection_data = self.device_combo.currentData()
        
        # Check if this is a group (dict) or device (string IP)
        if isinstance(selection_data, dict):
            # Group selection
            if was_capturing and old_device:
                self.signals.status_update.emit("⏸️ Stopping stream on previous device...")
                self.audio_capture.stop_capture()
            
            # Deactivate any existing group
            self._deactivate_group()
            
            # Activate the selected group
            if self._activate_group(selection_data):
                self._enable_controls()

                # Restart capture if it was running
                if was_capturing:
                    self.signals.status_update.emit("▶️ Restarting stream on group master...")
                    import time
                    time.sleep(0.5)
                    self.audio_capture.start_capture(selection_data['master_ip'])
                    self.btn_start_capture.setEnabled(False)
                    self.btn_stop_capture.setEnabled(True)
            else:
                self._disable_controls()
            return
        
        # Single device selection
        ip = selection_data
        if ip:
            # Stop capture on old device if running
            if was_capturing and old_device:
                self.signals.status_update.emit("⏸️ Stopping stream on previous device...")
                self.audio_capture.stop_capture()
            
            # Deactivate any existing group (dissolve group when selecting single device)
            if self.active_group:
                self.signals.status_update.emit("📻 Dissolving active group...")
                self._deactivate_group()
            
            # Switch to new device
            self.device = SoundTouchController(ip)
            self._enable_controls()
            self.signals.status_update.emit(f"✅ Connected to {text}")

            # Restart capture on new device if it was running
            if was_capturing:
                self.signals.status_update.emit("▶️ Restarting stream on new device...")
                # Small delay to let old device clean up
                import time
                time.sleep(0.5)
                self.audio_capture.start_capture(ip)
                self.btn_start_capture.setEnabled(False)
                self.btn_stop_capture.setEnabled(True)
    
    def _enable_controls(self):
        """Enable controls when device is connected."""
        self.btn_power.setEnabled(True)
        # Lautstärke-Sektion passend zu Gerät/Gruppe neu aufbauen
        self._refresh_volume_section()
        # Umbenennen nur bei einzelnem Gerät (nicht bei aktiver Gruppe)
        if hasattr(self, 'btn_rename_device'):
            self.btn_rename_device.setEnabled(self.device is not None and not self.active_group)

        # Enable transport controls
        for btn in getattr(self, 'transport_buttons', []):
            btn.setEnabled(True)

        # Enable preset buttons
        for btn in self.preset_buttons:
            btn.setEnabled(True)
        for btn in self.store_preset_buttons:
            btn.setEnabled(True)
        
        # Enable preset tab buttons
        self.btn_refresh_presets.setEnabled(True)
        self.btn_play_preset.setEnabled(True)
        
        # Enable TuneIn tab buttons
        self.btn_play_custom.setEnabled(True)
        self.btn_search_tunein.setEnabled(True)
        
        # Enable capture if available
        capabilities = self.audio_capture.detect_capabilities()
        if capabilities['available']:
            self.btn_start_capture.setEnabled(True)
        
        # Auto-refresh presets
        QTimer.singleShot(500, self._refresh_presets)
    
    def _disable_controls(self):
        """Disable controls when no device is connected."""
        self.btn_power.setEnabled(False)
        # Lautstärke-Sektion leeren/Hinweis anzeigen
        self._refresh_volume_section()
        if hasattr(self, 'btn_rename_device'):
            self.btn_rename_device.setEnabled(False)

        # Disable transport controls
        for btn in getattr(self, 'transport_buttons', []):
            btn.setEnabled(False)

        # Disable preset buttons
        for btn in self.preset_buttons:
            btn.setEnabled(False)
        for btn in self.store_preset_buttons:
            btn.setEnabled(False)
        
        # Disable preset tab buttons
        self.btn_refresh_presets.setEnabled(False)
        self.btn_play_preset.setEnabled(False)
        
        # Disable TuneIn tab buttons
        self.btn_play_custom.setEnabled(False)
        self.btn_search_tunein.setEnabled(False)
        self.btn_play_search_result.setEnabled(False)
        self.btn_save_search_result.setEnabled(False)
        self.btn_fav_search_result.setEnabled(False)

        self.btn_start_capture.setEnabled(False)
        self.btn_stop_capture.setEnabled(False)
    
    def _open_device_setup(self):
        """Open device setup dialog."""
        if not DEVICE_SETUP_AVAILABLE:
            QMessageBox.warning(self, "Not Available", "Device setup module not found")
            return

        try:
            from gui_device_setup import DeviceSetupDialog
            dialog = DeviceSetupDialog(self)
            if dialog.exec():
                QTimer.singleShot(2000, self._discover_devices)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open device setup: {e}")
    
    def _toggle_power(self):
        """Toggle device power."""
        if not self.device:
            return
        
        try:
            # power_on() existierte nicht -> POWER-Taste (Standby an/aus)
            if self.device.power_toggle():
                self.signals.status_update.emit("⚡ Power umgeschaltet")
            else:
                self.signals.status_update.emit("⚠️ Power-Befehl fehlgeschlagen")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to toggle power: {e}")
    
    def _recall_preset(self, preset_number: int):
        """Recall a preset."""
        if not self.device:
            return
        
        try:
            self.device.select_preset(preset_number)
            self.signals.status_update.emit(f"⭐ Preset {preset_number} activated")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to recall preset: {e}")
    
    def _refresh_presets(self):
        """Zeigt die konfigurierten Presets (On-Device Radio-Config + native Presets)."""
        if not self.device:
            return

        self.presets_list.clear()
        entries = {}

        # 1) On-Device Radio-Config = das, was die Tasten per DLNA spielen
        try:
            if device_ssh.is_reachable(self.device.ip):
                for n, p in device_ssh.read_presets(self.device.ip).items():
                    entries[n] = {
                        'name': p.get('name') or f'Preset {n}',
                        'url': p.get('url', ''),
                        'radio': True,
                    }
        except Exception:
            pass

        # 2) Native Presets ergänzen (falls Slot nicht schon als Radio konfiguriert)
        try:
            for pr in (self.device.get_presets() or []):
                try:
                    nid = int(pr.get('id'))
                except (TypeError, ValueError):
                    continue
                if nid not in entries:
                    entries[nid] = {
                        'name': pr.get('itemName') or f'Preset {nid}',
                        'url': '',
                        'radio': False,
                        'source': pr.get('source', ''),
                    }
        except Exception:
            pass

        if not entries:
            self.presets_list.addItem("Keine Presets konfiguriert")
            self.signals.status_update.emit("ℹ️ Keine Presets gefunden")
            return

        for n in sorted(entries):
            e = entries[n]
            if e.get('radio'):
                text = f"⭐ Preset {n}: {e['name']}  📻"
            else:
                src = e.get('source', '')
                text = f"Preset {n}: {e['name']}" + (f" ({src})" if src else "")
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, n)
            if e.get('url'):
                item.setToolTip(e['url'])
            self.presets_list.addItem(item)

        self.signals.status_update.emit(f"✅ {len(entries)} Preset(s)")
    
    def _play_selected_preset(self):
        """Play the selected preset from the list."""
        if not self.device:
            QMessageBox.warning(self, "No Device", "Please select a device first")
            return
        
        selected_items = self.presets_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a preset to play")
            return
        
        preset_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
        if preset_id:
            self._recall_preset(int(preset_id))
    
    def _transport(self, key: str):
        """Sende einen Transport-Befehl (PLAY_PAUSE, STOP, NEXT_TRACK, PREV_TRACK)."""
        if not self.device:
            QMessageBox.warning(self, "No Device", "Please select a device first")
            return
        try:
            ok = self.device.send_key(key)
            self.signals.status_update.emit(
                f"⏯️ {key}" if ok else f"⚠️ {key} fehlgeschlagen"
            )
        except Exception as e:
            self.signals.status_update.emit(f"⚠️ {key}: {e}")

    def _write_device_preset(self, preset_id: int, url: str, name: str) -> bool:
        """Schreibt einen Radio-Preset in die On-Device-Config (physische Taste → DLNA-Radio)."""
        if not self.device or not url:
            return False
        ip = self.device.ip
        try:
            if not device_ssh.is_reachable(ip):
                self.signals.status_update.emit(
                    "⚠️ Gerät per SSH nicht erreichbar – Preset nur nativ gespeichert"
                )
                return False
            ok = device_ssh.set_preset(ip, preset_id, url, name)
            if ok:
                self.signals.status_update.emit(f"✅ Preset {preset_id} auf Gerät konfiguriert: {name}")
            else:
                self.signals.status_update.emit(f"⚠️ Konnte Preset {preset_id} nicht auf Gerät schreiben")
            return ok
        except Exception as e:
            self.signals.status_update.emit(f"⚠️ SSH-Fehler beim Preset-Schreiben: {e}")
            return False

    def _store_current_to_preset(self, preset_id: int):
        """Store currently playing content to a preset slot."""
        if not self.device:
            QMessageBox.warning(self, "No Device", "Please select a device first")
            return
        
        # Confirm with user
        reply = QMessageBox.question(
            self, 
            "Store Preset",
            f"Store currently playing content to Preset {preset_id}?\n\n"
            f"This will overwrite any existing content in this slot.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                success = self.device.store_preset(preset_id)
                if success:
                    # Falls gerade ein Radio-Stream läuft (UPNP/DLNA), auch die
                    # On-Device-Config setzen, damit die Taste ohne PC funktioniert.
                    try:
                        np = self.device.get_now_playing() or {}
                        loc = np.get('location', '') or ''
                        nm = np.get('track') or np.get('stationName') or f"Preset {preset_id}"
                        if loc.startswith('http'):
                            self._write_device_preset(preset_id, loc, nm)
                    except Exception:
                        pass
                    self.signals.status_update.emit(f"💾 Stored to Preset {preset_id}")
                    QMessageBox.information(self, "Success",
                                          f"Current content saved to Preset {preset_id}!")
                    # Refresh presets list
                    self._refresh_presets()
                else:
                    QMessageBox.warning(self, "Error", "Failed to store preset")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to store preset: {e}")

    def _resolve_tunein_location(self, location: str) -> str:
        """Resolve TuneIn guide/location (/v1/playback/station/...) to a direct stream URL."""
        try:
            helper = TuneInHelper(self.device.ip)
            resolved = helper.get_stream_url(location)
            return resolved or location
        except Exception:
            return location
    
    def _play_selected_station(self):
        """Play the selected TuneIn station."""
        if not self.device:
            QMessageBox.warning(self, "No Device", "Please select a device first")
            return
        
        selected_items = self.stations_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a station to play")
            return
        
        # Get station info
        station_name = selected_items[0].text()
        station = next((s for s in self.popular_stations if s['name'] == station_name), None)
        
        if not station:
            return
        
        try:
            # Play TuneIn station
            resolved = self._resolve_tunein_location(station['location'])
            content_item = {
                'source': 'LOCAL_INTERNET_RADIO',
                'location': resolved,
                'itemName': station_name
            }
            success = self.device.select_content_item(content_item)
            
            if success:
                self.signals.status_update.emit(f"📻 Playing {station_name}")
            else:
                QMessageBox.warning(self, "Error", f"Failed to play {station_name}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to play station: {e}")
    
    def _save_station_to_preset(self):
        """Save the selected TuneIn station to a preset slot."""
        if not self.device:
            QMessageBox.warning(self, "No Device", "Please select a device first")
            return
        
        selected_items = self.stations_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a station first")
            return
        
        # Get station info
        station_name = selected_items[0].text()
        station = next((s for s in self.popular_stations if s['name'] == station_name), None)
        
        if not station:
            return
        
        # Ask which preset slot
        from PyQt6.QtWidgets import QInputDialog
        preset_id, ok = QInputDialog.getInt(
            self, 
            "Save to Preset",
            f"Save '{station_name}' to which preset slot?",
            1, 1, 6, 1
        )
        
        if ok:
            try:
                resolved = self._resolve_tunein_location(station['location'])
                content_item = {
                    'source': 'LOCAL_INTERNET_RADIO',
                    'location': resolved,
                    'itemName': station_name,
                    'isPresetable': 'true'
                }
                
                native_ok = self.device.store_preset(preset_id, content_item)
                # On-Device-Config: physische/App-Taste spielt den Stream per DLNA
                device_ok = self._write_device_preset(preset_id, resolved, station_name)

                if native_ok or device_ok:
                    self.signals.status_update.emit(f"💾 {station_name} → Preset {preset_id}")
                    QMessageBox.information(self, "Success",
                                          f"'{station_name}' auf Preset {preset_id} gespeichert!\n\n"
                                          f"Drücke die Preset-Taste {preset_id} an der Box.")
                else:
                    QMessageBox.warning(self, "Error", "Failed to store preset")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save station: {e}")
    
    def _play_custom_tunein(self):
        """Play a custom TuneIn station by location."""
        if not self.device:
            QMessageBox.warning(self, "No Device", "Please select a device first")
            return
        
        location = self.tunein_location_input.text().strip()
        if not location:
            QMessageBox.warning(self, "No Location", "Please enter a TuneIn station location")
            return
        
        try:
            resolved = self._resolve_tunein_location(location)
            content_item = {
                'source': 'LOCAL_INTERNET_RADIO',
                'location': resolved,
                'itemName': 'Custom Station'
            }
            success = self.device.select_content_item(content_item)
            
            if success:
                self.signals.status_update.emit(f"📻 Playing custom TuneIn station")
            else:
                QMessageBox.warning(self, "Error", "Failed to play station")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to play station: {e}")
    
    def _search_tunein(self):
        """Search TuneIn for radio stations using TuneIn's public API."""
        if not self.device:
            QMessageBox.warning(self, "No Device", "Please select a device first")
            return
        
        query = self.tunein_search_input.text().strip()
        if not query:
            QMessageBox.warning(self, "No Query", "Please enter a search term")
            return
        
        try:
            self.signals.status_update.emit(f"🔍 Searching TuneIn for '{query}'...")
            results = self.device.search_tunein(query, max_results=20)
            
            # Clear previous results
            self.search_results_list.clear()
            self.search_results = []
            
            if not results:
                self.signals.status_update.emit(f"No results found for '{query}'")
                QMessageBox.information(self, "No Results", f"No stations found for '{query}'")
                return
            
            # Populate results
            for station in results:
                self.search_results.append(station)
                display_name = station['name']
                if station.get('description'):
                    display_name += f" - {station['description']}"
                self.search_results_list.addItem(display_name)
            
            self.signals.status_update.emit(f"Found {len(results)} stations")
            self.btn_play_search_result.setEnabled(True)
            self.btn_save_search_result.setEnabled(True)
            self.btn_fav_search_result.setEnabled(True)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Search failed: {e}")
    
    def _play_search_result(self):
        """Play the selected search result."""
        if not self.device:
            QMessageBox.warning(self, "No Device", "Please select a device first")
            return
        
        selected_items = self.search_results_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a station to play")
            return
        
        # Get station index
        index = self.search_results_list.row(selected_items[0])
        if index < 0 or index >= len(self.search_results):
            return
        
        station = self.search_results[index]
        
        try:
            resolved = self._resolve_tunein_location(station['location'])
            content_item = {
                'source': 'LOCAL_INTERNET_RADIO',
                'location': resolved,
                'itemName': station['name']
            }
            
            # Add optional TuneIn attributes if present
            # NOTE: Do NOT add 'type' for LOCAL_INTERNET_RADIO - it causes playback to fail!
            # 'type' is only used for TUNEIN source
            if 'sourceAccount' in station:
                content_item['sourceAccount'] = station['sourceAccount']
            if 'isPresetable' in station:
                content_item['isPresetable'] = station['isPresetable']
            if 'containerArt' in station:
                content_item['containerArt'] = station['containerArt']
            
            success = self.device.select_content_item(content_item)
            
            if success:
                self.signals.status_update.emit(f"📻 Playing {station['name']}")
            else:
                QMessageBox.warning(self, "Error", f"Failed to play {station['name']}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to play station: {e}")
    
    def _save_search_result_to_preset(self):
        """Save the selected search result to a preset slot (native + On-Device-Config)."""
        if not self.device:
            QMessageBox.warning(self, "No Device", "Please select a device first")
            return

        selected_items = self.search_results_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a station first")
            return

        index = self.search_results_list.row(selected_items[0])
        if index < 0 or index >= len(self.search_results):
            return

        station = self.search_results[index]

        preset_id, ok = QInputDialog.getInt(
            self, "Save to Preset",
            f"Save '{station['name']}' to which preset slot?",
            1, 1, 6, 1
        )
        if not ok:
            return

        try:
            resolved = self._resolve_tunein_location(station['location'])
            content_item = {
                'source': 'LOCAL_INTERNET_RADIO',
                'location': resolved,
                'itemName': station['name'],
                'isPresetable': 'true',
            }
            # Nativer Preset: Name/Anzeige + macht den Preset "invalid" -> Rhino-Trigger
            native_ok = self.device.store_preset(preset_id, content_item)
            # On-Device-Config: physische/App-Taste spielt den Stream per DLNA
            device_ok = self._write_device_preset(preset_id, resolved, station['name'])

            if native_ok or device_ok:
                self.signals.status_update.emit(f"💾 {station['name']} → Preset {preset_id}")
                QMessageBox.information(
                    self, "Success",
                    f"✓ '{station['name']}' auf Preset {preset_id} gespeichert!\n\n"
                    f"Drücke die Preset-Taste {preset_id} an der Box – spielt ohne PC/Cloud."
                )
            else:
                QMessageBox.warning(self, "Error", f"Preset {preset_id} konnte nicht gespeichert werden")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save preset: {e}")

    def _save_search_to_favorites(self):
        """Ausgewähltes Suchergebnis in die Favoriten übernehmen (aufgelöste Stream-URL)."""
        selected_items = self.search_results_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a station first")
            return
        index = self.search_results_list.row(selected_items[0])
        if index < 0 or index >= len(self.search_results):
            return
        station = self.search_results[index]
        try:
            resolved = self._resolve_tunein_location(station['location'])
        except Exception:
            resolved = station.get('location', '')
        if not resolved or not resolved.startswith('http'):
            QMessageBox.warning(self, "Fehler", "Konnte keine abspielbare Stream-URL ermitteln.")
            return
        self.add_favorite(station['name'], resolved)

    def _start_capture(self):
        """Start system audio capture."""
        if not self.device:
            QMessageBox.warning(self, "No Device", "Please select a device first")
            return
        
        capabilities = self.audio_capture.detect_capabilities()
        if not capabilities['available']:
            QMessageBox.warning(self, "Not Available", capabilities['message'])
            return
        
        try:
            device_ip = self.device.ip
            self.audio_capture.start_capture(device_ip)
            
            self.btn_start_capture.setEnabled(False)
            self.btn_stop_capture.setEnabled(True)
            self.signals.status_update.emit("🎵 System audio capture started!")
            
            QMessageBox.information(
                self, 
                "Capture Started", 
                "System audio is now being captured!\n\n"
                "Play any audio from any app and it will be streamed to your Bose device."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start capture: {e}")
    
    def _stop_capture(self):
        """Stop system audio capture."""
        try:
            self.audio_capture.stop_capture()
            
            self.btn_start_capture.setEnabled(True)
            self.btn_stop_capture.setEnabled(False)
            self.signals.status_update.emit("⏹️ System audio capture stopped")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to stop capture: {e}")
    
    def _on_status_update(self, message: str):
        """Update status label."""
        self.status_label.setText(message)
    
    def _on_capture_status(self, is_capturing: bool):
        """Update capture button states."""
        self.btn_start_capture.setEnabled(not is_capturing)
        self.btn_stop_capture.setEnabled(is_capturing)
    
    def _update_devices_file(self):
        """Update the list of available devices for grouping."""
        try:
            with open(self.devices_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.all_devices, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to update devices file: {e}")
    
    def _open_create_group_dialog(self):
        """Open dialog to create a new saved group."""
        if not self.all_devices or len(self.all_devices) < 2:
            QMessageBox.warning(self, "Insufficient Devices", 
                              "You need at least 2 devices to create a group.\n"
                              "Please discover devices first.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Create New Group")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        
        # Group name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Group Name:"))
        name_input = QLineEdit()
        name_input.setPlaceholderText("e.g., Living Room + Kitchen")
        name_layout.addWidget(name_input)
        layout.addLayout(name_layout)
        
        # Master selection
        layout.addWidget(QLabel("Master Device (will control the group):"))
        master_combo = QComboBox()
        for device in self.all_devices:
            master_combo.addItem(f"{device['name']} ({device['ip']})", userData=device['ip'])
        layout.addWidget(master_combo)
        
        # Slave selection
        layout.addWidget(QLabel("Slave Devices (check all to include):"))
        slave_list = QListWidget()
        slave_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for device in self.all_devices:
            item = QListWidgetItem(f"{device['name']} ({device['ip']})")
            item.setData(Qt.ItemDataRole.UserRole, device['ip'])
            slave_list.addItem(item)
        layout.addWidget(slave_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        create_btn = QPushButton("✅ Create Group")
        cancel_btn = QPushButton("❌ Cancel")
        button_layout.addWidget(create_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        def create_group():
            group_name = name_input.text().strip()
            if not group_name:
                QMessageBox.warning(dialog, "Error", "Please enter a group name")
                return
            
            master_ip = master_combo.currentData()
            slave_ips = []
            for i in range(slave_list.count()):
                item = slave_list.item(i)
                if item.isSelected():
                    ip = item.data(Qt.ItemDataRole.UserRole)
                    if ip != master_ip:  # Exclude master
                        slave_ips.append(ip)
            
            if not slave_ips:
                QMessageBox.warning(dialog, "Error", "Please select at least one slave device")
                return
            
            # Check if group name already exists
            if any(g['name'] == group_name for g in self.saved_groups):
                QMessageBox.warning(dialog, "Error", f"Group '{group_name}' already exists")
                return
            
            # Save group configuration
            group_config = {
                'name': group_name,
                'master_ip': master_ip,
                'slave_ips': slave_ips
            }
            self.saved_groups.append(group_config)
            self._save_groups()
            
            # Refresh device dropdown to include new group
            self._discover_devices()
            
            self.signals.status_update.emit(f"✅ Group '{group_name}' created")
            dialog.accept()
        
        create_btn.clicked.connect(create_group)
        cancel_btn.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def _open_manage_groups_dialog(self):
        """Open dialog to edit or delete saved groups."""
        if not self.saved_groups:
            QMessageBox.information(self, "No Groups", 
                                  "No saved groups found.\n"
                                  "Create a group first from the Groups menu.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Manage Groups")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        
        # Groups list
        layout.addWidget(QLabel("Saved Groups:"))
        groups_list_widget = QListWidget()
        
        def refresh_groups_list():
            groups_list_widget.clear()
            for group in self.saved_groups:
                master_name = next((d['name'] for d in self.all_devices if d['ip'] == group['master_ip']), group['master_ip'])
                slave_count = len(group['slave_ips'])
                item_text = f"{group['name']} - Master: {master_name}, Slaves: {slave_count}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, group)
                groups_list_widget.addItem(item)
        
        refresh_groups_list()
        layout.addWidget(groups_list_widget)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        edit_btn = QPushButton("✏️ Edit")
        delete_btn = QPushButton("🗑️ Delete")
        close_btn = QPushButton("✅ Close")
        
        button_layout.addWidget(edit_btn)
        button_layout.addWidget(delete_btn)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        def edit_group():
            current_item = groups_list_widget.currentItem()
            if not current_item:
                QMessageBox.warning(dialog, "No Selection", "Please select a group to edit")
                return
            
            group_config = current_item.data(Qt.ItemDataRole.UserRole)
            group_index = self.saved_groups.index(group_config)
            
            # Open edit dialog
            edit_dialog = QDialog(dialog)
            edit_dialog.setWindowTitle(f"Edit Group: {group_config['name']}")
            edit_dialog.setMinimumWidth(500)
            
            edit_layout = QVBoxLayout()
            
            # Group name
            name_layout = QHBoxLayout()
            name_layout.addWidget(QLabel("Group Name:"))
            name_input = QLineEdit(group_config['name'])
            name_layout.addWidget(name_input)
            edit_layout.addLayout(name_layout)
            
            # Master selection
            edit_layout.addWidget(QLabel("Master Device:"))
            master_combo = QComboBox()
            for i, device in enumerate(self.all_devices):
                master_combo.addItem(f"{device['name']} ({device['ip']})", userData=device['ip'])
                if device['ip'] == group_config['master_ip']:
                    master_combo.setCurrentIndex(i)
            edit_layout.addWidget(master_combo)
            
            # Slave selection
            edit_layout.addWidget(QLabel("Slave Devices:"))
            slave_list = QListWidget()
            slave_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
            for device in self.all_devices:
                item = QListWidgetItem(f"{device['name']} ({device['ip']})")
                item.setData(Qt.ItemDataRole.UserRole, device['ip'])
                if device['ip'] in group_config['slave_ips']:
                    item.setSelected(True)
                slave_list.addItem(item)
            edit_layout.addWidget(slave_list)
            
            # Buttons
            edit_button_layout = QHBoxLayout()
            save_btn = QPushButton("💾 Save")
            cancel_btn = QPushButton("❌ Cancel")
            edit_button_layout.addWidget(save_btn)
            edit_button_layout.addWidget(cancel_btn)
            edit_layout.addLayout(edit_button_layout)
            
            edit_dialog.setLayout(edit_layout)
            
            def save_changes():
                new_name = name_input.text().strip()
                if not new_name:
                    QMessageBox.warning(edit_dialog, "Error", "Please enter a group name")
                    return
                
                # Check if name changed and conflicts
                if new_name != group_config['name']:
                    if any(g['name'] == new_name for g in self.saved_groups):
                        QMessageBox.warning(edit_dialog, "Error", f"Group '{new_name}' already exists")
                        return
                
                master_ip = master_combo.currentData()
                slave_ips = []
                for i in range(slave_list.count()):
                    item = slave_list.item(i)
                    if item.isSelected():
                        ip = item.data(Qt.ItemDataRole.UserRole)
                        if ip != master_ip:
                            slave_ips.append(ip)
                
                if not slave_ips:
                    QMessageBox.warning(edit_dialog, "Error", "Please select at least one slave device")
                    return
                
                # Update group
                self.saved_groups[group_index] = {
                    'name': new_name,
                    'master_ip': master_ip,
                    'slave_ips': slave_ips
                }
                self._save_groups()
                refresh_groups_list()
                
                # If this was the active group, update it
                if self.active_group and self.active_group.get('name') == group_config['name']:
                    self._deactivate_group()
                    self.signals.status_update.emit(f"⚠️ Active group '{group_config['name']}' was modified - please reactivate")
                
                # Refresh device dropdown
                self._discover_devices()
                
                self.signals.status_update.emit(f"✅ Group '{new_name}' updated")
                edit_dialog.accept()
            
            save_btn.clicked.connect(save_changes)
            cancel_btn.clicked.connect(edit_dialog.reject)
            
            edit_dialog.exec()
        
        def delete_group():
            current_item = groups_list_widget.currentItem()
            if not current_item:
                QMessageBox.warning(dialog, "No Selection", "Please select a group to delete")
                return
            
            group_config = current_item.data(Qt.ItemDataRole.UserRole)
            
            reply = QMessageBox.question(
                dialog,
                "Confirm Deletion",
                f"Delete group '{group_config['name']}'?\n\nThis cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Deactivate if this is the active group
                if self.active_group and self.active_group.get('name') == group_config['name']:
                    self._deactivate_group()
                
                self.saved_groups.remove(group_config)
                self._save_groups()
                refresh_groups_list()
                
                # Refresh device dropdown
                self._discover_devices()
                
                self.signals.status_update.emit(f"✅ Group '{group_config['name']}' deleted")
        
        edit_btn.clicked.connect(edit_group)
        delete_btn.clicked.connect(delete_group)
        close_btn.clicked.connect(dialog.accept)
        
        dialog.exec()
    
    def closeEvent(self, event):
        """Clean up on close."""
        if self.audio_capture.is_capturing:
            self.audio_capture.stop_capture()
        event.accept()


def main():
    app = QApplication(sys.argv)
    
    # Set app style
    app.setStyle('Fusion')
    
    window = SimpleSoundTouchGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
