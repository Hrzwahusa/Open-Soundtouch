#!/usr/bin/env python3
"""
SoundTouch Group Manager Module
Multi-room speaker group management widget.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QListWidget, QGroupBox, QLineEdit,
                             QMessageBox, QListWidgetItem, QDialog, QDialogButtonBox,
                             QCheckBox, QScrollArea, QGridLayout)
from PyQt5.QtCore import Qt, pyqtSignal
from soundtouch_lib import SoundTouchGroupManager, SoundTouchController


class CreateGroupDialog(QDialog):
    """Dialog for creating a new speaker group."""
    
    def __init__(self, devices, parent=None):
        super().__init__(parent)
        self.devices = devices
        self.selected_master = None
        self.selected_slaves = []
        
        self.setWindowTitle("Neue Gruppe erstellen")
        self.setMinimumSize(500, 400)
        self.init_ui()
        
    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        
        # Group name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Gruppen-Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("z.B. Erdgeschoss, Oben, Alle...")
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # Master selection
        master_group = QGroupBox("Master-Gerät (1 auswählen)")
        master_layout = QVBoxLayout()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        self.master_radios = []
        for device in self.devices:
            radio = QCheckBox(f"{device['name']} ({device['type']}) - {device['ip']}")
            radio.setProperty('device', device)
            radio.toggled.connect(self.on_master_selected)
            scroll_layout.addWidget(radio)
            self.master_radios.append(radio)
            
        scroll.setWidget(scroll_widget)
        master_layout.addWidget(scroll)
        master_group.setLayout(master_layout)
        layout.addWidget(master_group)
        
        # Slave selection
        slave_group = QGroupBox("Slave-Geräte (beliebig viele)")
        slave_layout = QVBoxLayout()
        
        scroll2 = QScrollArea()
        scroll2.setWidgetResizable(True)
        scroll_widget2 = QWidget()
        scroll_layout2 = QVBoxLayout(scroll_widget2)
        
        self.slave_checks = []
        for device in self.devices:
            checkbox = QCheckBox(f"{device['name']} ({device['type']}) - {device['ip']}")
            checkbox.setProperty('device', device)
            scroll_layout2.addWidget(checkbox)
            self.slave_checks.append(checkbox)
            
        scroll2.setWidget(scroll_widget2)
        slave_layout.addWidget(scroll2)
        slave_group.setLayout(slave_layout)
        layout.addWidget(slave_group)
        
        # Info label
        self.info_label = QLabel("Wähle ein Master-Gerät und mindestens ein Slave-Gerät")
        self.info_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.info_label)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def on_master_selected(self, checked):
        """Handle master selection (only one allowed)."""
        sender = self.sender()
        if checked:
            # Uncheck all others
            for radio in self.master_radios:
                if radio != sender:
                    radio.setChecked(False)
            self.selected_master = sender.property('device')
        else:
            self.selected_master = None
            
    def accept(self):
        """Validate and accept."""
        # Get selected master
        if not self.selected_master:
            QMessageBox.warning(self, "Fehler", "Bitte wähle ein Master-Gerät")
            return
            
        # Get selected slaves
        self.selected_slaves = []
        for checkbox in self.slave_checks:
            if checkbox.isChecked():
                device = checkbox.property('device')
                if device['mac'] != self.selected_master['mac']:
                    self.selected_slaves.append(device)
                    
        if not self.selected_slaves:
            QMessageBox.warning(self, "Fehler", "Bitte wähle mindestens ein Slave-Gerät")
            return
            
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Fehler", "Bitte gib einen Gruppen-Namen ein")
            return
            
        super().accept()
        
    def get_group_data(self):
        """Get the configured group data."""
        return {
            'name': self.name_input.text().strip(),
            'master': self.selected_master,
            'slaves': self.selected_slaves
        }


class GroupManagerWidget(QWidget):
    """Widget for managing multi-room speaker groups."""
    
    group_changed = pyqtSignal()
    
    def __init__(self, devices=None):
        super().__init__()
        self.devices = devices or []
        self.group_manager = None
        self.current_group_index = -1
        
        if self.devices:
            self.group_manager = SoundTouchGroupManager(self.devices)
            
        self.init_ui()
        
    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header
        header = QLabel("Multi-Room Gruppen-Verwaltung")
        header.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(header)
        
        # Group list
        groups_group = QGroupBox("Vorhandene Gruppen")
        groups_layout = QVBoxLayout()
        
        self.group_list = QListWidget()
        self.group_list.itemClicked.connect(self.on_group_selected)
        groups_layout.addWidget(self.group_list)
        
        # Group actions
        group_actions = QHBoxLayout()
        
        create_btn = QPushButton("➕ Neue Gruppe")
        create_btn.clicked.connect(self.create_group)
        create_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        group_actions.addWidget(create_btn)
        
        delete_btn = QPushButton("🗑 Gruppe löschen")
        delete_btn.clicked.connect(self.delete_group)
        delete_btn.setStyleSheet("background-color: #f44336; color: white;")
        group_actions.addWidget(delete_btn)
        
        groups_layout.addLayout(group_actions)
        groups_group.setLayout(groups_layout)
        layout.addWidget(groups_group)
        
        # Group details
        details_group = QGroupBox("Gruppen-Details")
        details_layout = QVBoxLayout()
        
        self.details_label = QLabel("Keine Gruppe ausgewählt")
        self.details_label.setWordWrap(True)
        details_layout.addWidget(self.details_label)
        
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        
        # Group controls
        controls_group = QGroupBox("Gruppen-Steuerung")
        controls_layout = QVBoxLayout()
        
        # Playback controls
        playback_layout = QGridLayout()
        
        play_btn = self.create_group_button("▶ Play", "PLAY")
        pause_btn = self.create_group_button("⏸ Pause", "PAUSE")
        prev_btn = self.create_group_button("⏮ Zurück", "PREV_TRACK")
        next_btn = self.create_group_button("⏭ Weiter", "NEXT_TRACK")
        
        playback_layout.addWidget(play_btn, 0, 0)
        playback_layout.addWidget(pause_btn, 0, 1)
        playback_layout.addWidget(prev_btn, 1, 0)
        playback_layout.addWidget(next_btn, 1, 1)
        
        controls_layout.addLayout(playback_layout)
        
        # Volume control
        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("Gruppen-Lautstärke:"))
        
        vol_down_btn = QPushButton("-")
        vol_down_btn.clicked.connect(lambda: self.adjust_group_volume(-5))
        vol_layout.addWidget(vol_down_btn)
        
        self.group_volume_label = QLabel("--")
        vol_layout.addWidget(self.group_volume_label)
        
        vol_up_btn = QPushButton("+")
        vol_up_btn.clicked.connect(lambda: self.adjust_group_volume(5))
        vol_layout.addWidget(vol_up_btn)
        
        controls_layout.addLayout(vol_layout)
        
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)
        
        layout.addStretch()
        
    def set_devices(self, devices):
        """Update the device list."""
        self.devices = devices
        self.group_manager = SoundTouchGroupManager(devices)
        self.refresh_groups()
        
    def create_group_button(self, text, key):
        """Create a button for group control."""
        btn = QPushButton(text)
        btn.clicked.connect(lambda: self.send_group_command(key))
        btn.setMinimumHeight(40)
        return btn
        
    def create_group(self):
        """Create a new group."""
        if not self.devices:
            QMessageBox.warning(self, "Fehler", "Keine Geräte verfügbar")
            return
            
        dialog = CreateGroupDialog(self.devices, self)
        if dialog.exec_() == QDialog.Accepted:
            group_data = dialog.get_group_data()
            
            if self.group_manager:
                success = self.group_manager.create_group(
                    group_data['master'],
                    group_data['slaves'],
                    group_data['name']
                )
                
                if success:
                    QMessageBox.information(self, "Erfolg", 
                        f"Gruppe '{group_data['name']}' wurde erstellt!")
                    self.refresh_groups()
                    self.group_changed.emit()
                else:
                    QMessageBox.warning(self, "Fehler", 
                        "Gruppe konnte nicht erstellt werden")
                        
    def delete_group(self):
        """Delete the selected group."""
        if self.current_group_index < 0:
            QMessageBox.warning(self, "Fehler", "Keine Gruppe ausgewählt")
            return
            
        if self.group_manager and self.current_group_index < len(self.group_manager.groups):
            group = self.group_manager.groups[self.current_group_index]
            
            reply = QMessageBox.question(self, "Bestätigung",
                f"Gruppe '{group['name']}' wirklich löschen?",
                QMessageBox.Yes | QMessageBox.No)
                
            if reply == QMessageBox.Yes:
                # Remove from manager
                self.group_manager.groups.pop(self.current_group_index)
                self.refresh_groups()
                self.group_changed.emit()
                QMessageBox.information(self, "Erfolg", "Gruppe wurde gelöscht")
                
    def refresh_groups(self):
        """Refresh the group list."""
        self.group_list.clear()
        
        if not self.group_manager:
            return
            
        for i, group in enumerate(self.group_manager.groups):
            device_count = len(group['all_devices'])
            text = f"{group['name']} ({device_count} Geräte)"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, i)
            self.group_list.addItem(item)
            
    def on_group_selected(self, item):
        """Handle group selection."""
        self.current_group_index = item.data(Qt.UserRole)
        
        if self.group_manager and self.current_group_index < len(self.group_manager.groups):
            group = self.group_manager.groups[self.current_group_index]
            
            details = f"<b>{group['name']}</b><br><br>"
            details += f"<b>Master:</b> {group['master']['name']} ({group['master']['ip']})<br><br>"
            details += f"<b>Slaves ({len(group['slaves'])}):</b><br>"
            
            for slave in group['slaves']:
                details += f"• {slave['name']} ({slave['ip']})<br>"
                
            self.details_label.setText(details)
            
    def send_group_command(self, key):
        """Send command to selected group."""
        if self.current_group_index < 0:
            QMessageBox.warning(self, "Fehler", "Keine Gruppe ausgewählt")
            return
            
        if self.group_manager:
            success = self.group_manager.send_command_to_group(self.current_group_index, key)
            if not success:
                QMessageBox.warning(self, "Fehler", "Befehl konnte nicht gesendet werden")
                
    def adjust_group_volume(self, delta):
        """Adjust volume for selected group."""
        if self.current_group_index < 0:
            QMessageBox.warning(self, "Fehler", "Keine Gruppe ausgewählt")
            return
            
        if not self.group_manager:
            return
            
        group = self.group_manager.groups[self.current_group_index]
        
        # Get current volume from master
        try:
            controller = SoundTouchController(group['master']['ip'])
            vol_data = controller.get_volume()
            
            if vol_data:
                current = vol_data['actualvolume']
                new_volume = max(0, min(100, current + delta))
                
                success = self.group_manager.set_group_volume(self.current_group_index, new_volume)
                
                if success:
                    self.group_volume_label.setText(str(new_volume))
                else:
                    QMessageBox.warning(self, "Fehler", "Lautstärke konnte nicht geändert werden")
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Fehler: {e}")
