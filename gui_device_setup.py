#!/usr/bin/env python3
"""
GUI Dialog für WiFi-Setup von neuen Bose SoundTouch Geräten
"""

import sys
import socket
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTextEdit, QProgressBar, QGroupBox,
    QMessageBox, QApplication
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject
from PyQt5.QtGui import QFont
from soundtouch_lib import SoundTouchController, SoundTouchDiscovery
import netifaces
import time


class WiFiScanWorker(QObject):
    """Worker für WiFi Network Scan"""
    scan_completed = pyqtSignal(list)  # Liste von SSIDs
    scan_data_completed = pyqtSignal(list)  # Liste von Netzwerken (dict)
    scan_failed = pyqtSignal(str)  # Fehler-Nachricht
    debug_message = pyqtSignal(str)  # Debug-Nachricht
    
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
    
    def run(self):
        """Führe WiFi-Scan durch"""
        try:
            self.debug_message.emit("⏳ Starte WiFi-Scan on device...")
            result = self.controller.perform_wireless_site_survey()
            
            if result is None:
                self.scan_failed.emit("Scan hat keine Antwort erhalten - Gerät unterstützt möglicherweise kein WiFi-Survey")
                return
            
            if 'networks' in result:
                networks = result['networks']
                self.debug_message.emit(f"Raw result: {len(networks)} networks in result")
                
                if networks:
                    ssids = [network.get('ssid', '') for network in networks if network.get('ssid')]
                    unique_ssids = list(dict.fromkeys(ssids))  # Duplikate entfernen
                    self.debug_message.emit(f"Found {len(unique_ssids)} unique SSIDs: {unique_ssids}")
                    # Emit both SSID list and full network data
                    self.scan_completed.emit(unique_ssids)
                    self.scan_data_completed.emit(networks)
                else:
                    self.scan_failed.emit("Keine Netzwerke gefunden")
            else:
                self.scan_failed.emit("Ungültiges Response-Format (kein 'networks' key)")
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.debug_message.emit(f"Exception: {error_detail}")
            self.scan_failed.emit(f"Scan-Fehler: {str(e)}")


class WiFiConfigSendWorker(QObject):
    """Worker für WiFi-Config-Senden"""
    config_sent = pyqtSignal(bool)  # Erfolgreich gesendet?
    error_occurred = pyqtSignal(str)  # Fehler-Nachricht
    debug_message = pyqtSignal(str)  # Debug-Nachricht
    
    def __init__(self, controller, ssid, password, security, timeout_secs):
        super().__init__()
        self.controller = controller
        self.ssid = ssid
        self.password = password
        self.security = security
        self.timeout_secs = timeout_secs
    
    def run(self):
        """Sende WiFi-Konfiguration"""
        try:
            self.debug_message.emit(f"Sending config: SSID={self.ssid}, Security={self.security}")
            success = self.controller.add_wireless_profile(
                self.ssid, self.password, self.security, 
                timeout_secs=self.timeout_secs,
                monitor_callback=self.debug_message.emit
            )
            self.debug_message.emit(f"add_wireless_profile returned: {success}")
            self.config_sent.emit(success)
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.debug_message.emit(f"Exception in send: {error_detail}")
            self.error_occurred.emit(str(e))
            self.config_sent.emit(False)


class DeviceReconnectionWorker(QObject):
    """Worker für Device-Reconnection-Monitoring"""
    status_updated = pyqtSignal(str)  # Status-Nachricht
    reconnection_finished = pyqtSignal(bool)  # Erfolgreich reconnected?
    
    def __init__(self, controller, target_ssid):
        super().__init__()
        self.controller = controller
        self.target_ssid = target_ssid
    
    def run(self):
        """Führe das Monitoring durch"""
        def status_callback(message):
            self.status_updated.emit(message)
        
        reconnected = self.controller.wait_for_device_reconnection(
            target_ssid=self.target_ssid,
            max_wait_seconds=120,
            check_interval=5,
            status_callback=status_callback
        )
        
        self.reconnection_finished.emit(reconnected)


class ConnectSetupWiFiWorker(QObject):
    """Worker für automatische Setup-WiFi-Verbindung"""
    connected = pyqtSignal(str)  # SSID
    failed = pyqtSignal(str)  # Error message
    status_message = pyqtSignal(str)  # Status-Log
    
    def __init__(self):
        super().__init__()
    
    def run(self):
        """Versuche Setup-WLAN-Verbindung"""
        import subprocess
        self.status_message.emit("🤖 Versuche automatisch ins Setup-WLAN zu wechseln...")
        try:
            # List nearby WiFi networks with SSID and SIGNAL
            out = subprocess.check_output(["nmcli", "-t", "-f", "SSID,SIGNAL", "dev", "wifi", "list"], text=True)
            candidates = []
            for line in out.splitlines():
                if not line:
                    continue
                parts = line.split(":")
                ssid = parts[0].strip()
                # SIGNAL may be empty; default to 0
                try:
                    signal = int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else 0
                except Exception:
                    signal = 0
                if ssid and ("Bose" in ssid or "SoundTouch" in ssid):
                    candidates.append((ssid, signal))
            if not candidates:
                self.failed.emit("Kein Setup-WLAN gefunden (SSID enthält 'Bose'/'SoundTouch').")
                return
            # Pick strongest candidate
            candidates.sort(key=lambda x: x[1], reverse=True)
            target_ssid = candidates[0][0]
            self.status_message.emit(f"🔁 Verbinde PC mit Setup-WLAN '{target_ssid}'...")
            # Setup SSIDs are typically open; try without password
            subprocess.check_call(["nmcli", "dev", "wifi", "connect", target_ssid])
            self.connected.emit(target_ssid)
        except FileNotFoundError:
            self.failed.emit("'nmcli' nicht gefunden. Bitte manuell ins Setup-WLAN wechseln.")
        except subprocess.CalledProcessError as e:
            self.failed.emit(f"Setup-WLAN-Verbindung fehlgeschlagen: {e}")
        except Exception as e:
            self.failed.emit(f"Unerwarteter Fehler: {e}")


class FindSetupDeviceWorker(QObject):
    """Worker für Setup-Device-Suche"""
    device_found = pyqtSignal(str, str, str)  # (ip, name, device_id)
    device_not_found = pyqtSignal()
    status_message = pyqtSignal(str)  # Status-Log
    
    def __init__(self, setup_ips):
        super().__init__()
        self.setup_ips = setup_ips
    
    def run(self):
        """Suche nach Setup-Gerät"""
        for ip in self.setup_ips:
            try:
                self.status_message.emit(f"   Versuche {ip}...")
                controller = SoundTouchController(ip, timeout=2)
                info = controller.get_info()
                if info:
                    name = info.get('name', 'Unknown')
                    device_id = info.get('deviceID', '')
                    self.device_found.emit(ip, name, device_id)
                    return
            except:
                pass
        
        self.device_not_found.emit()


class DiscoverDeviceWorker(QObject):
    """Worker für Device-Discovery im Heim-Netzwerk"""
    devices_found = pyqtSignal(list)  # Liste von Geräten
    status_message = pyqtSignal(str)  # Status-Log
    
    def __init__(self):
        super().__init__()
    
    def run(self):
        """Führe Discovery durch"""
        try:
            # Wait briefly to ensure network transition is complete
            import time
            time.sleep(2)
            
            # Create discovery with WiFi-specific network detection
            discovery = SoundTouchDiscovery()
            # Force fresh WiFi network detection (not cached)
            discovery.network = discovery._get_wifi_network()
            self.status_message.emit(f"   Scanne WLAN-Netzwerk: {discovery.network}")
            
            # Use max_threads parameter (not max_workers)
            devices = discovery.scan(max_threads=20)
            
            self.devices_found.emit(devices)
        except Exception as e:
            self.status_message.emit(f"❌ Fehler beim Scannen: {e}")
            self.devices_found.emit([])


class NetworkMonitorThread(QThread):
    """Thread zum Überwachen des Netzwerkwechsels"""
    network_changed = pyqtSignal(str, str)  # (interface, ip)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        # Nur WLAN überwachen: SSID und WLAN-IP tracken
        self.current_ssid = self._get_current_ssid()
        self.current_iface, self.current_wifi_ip = self._get_wifi_info()
        
    def _get_current_ssid(self):
        """Aktuelle WLAN SSID ermitteln (nur WLAN)."""
        try:
            import subprocess
            ssid = subprocess.check_output(['iwgetid', '-r'], text=True).strip()
            return ssid or ""
        except Exception:
            return ""

    def _get_wifi_info(self):
        """Ermittle WLAN-Interface und dessen IPv4-Adresse.
        Bevorzugt Interfaces mit Präfixen 'wl', 'wlan', 'wlp'.
        """
        wifi_iface = None
        wifi_ip = None
        try:
            for iface in netifaces.interfaces():
                # Nur typische WLAN-Interfaces betrachten
                if not (iface.startswith('wl') or iface.startswith('wlan') or iface.startswith('wlp')):
                    continue
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr.get('addr')
                        if ip and ip != '127.0.0.1':
                            wifi_iface = iface
                            wifi_ip = ip
                            return wifi_iface, wifi_ip
        except Exception:
            pass
        return wifi_iface or "", wifi_ip or ""
    
    def run(self):
        """Überwache Netzwerkwechsel"""
        while self.running:
            # Prüfe SSID- und WLAN-IP-Änderungen
            new_ssid = self._get_current_ssid()
            new_iface, new_wifi_ip = self._get_wifi_info()

            ssid_changed = (new_ssid != self.current_ssid)
            ip_changed = (new_wifi_ip != self.current_wifi_ip)

            if ssid_changed or ip_changed:
                self.current_ssid = new_ssid
                self.current_iface, self.current_wifi_ip = new_iface, new_wifi_ip
                self.network_changed.emit(self.current_iface or "wifi", self.current_wifi_ip or "")
            
            time.sleep(2)
    
    def stop(self):
        """Thread stoppen"""
        self.running = False


class DeviceSetupWizard(QDialog):
    """Wizard zum Hinzufügen neuer SoundTouch Geräte"""
    
    # Setup-Status
    STATUS_IDLE = 0
    STATUS_WAIT_SETUP_NETWORK = 1
    STATUS_CONNECTED_TO_DEVICE = 2
    STATUS_SENDING_WIFI = 3
    STATUS_DEVICE_REBOOTING = 4
    STATUS_WAIT_HOME_NETWORK = 5
    STATUS_DISCOVERING = 6
    STATUS_SUCCESS = 7
    STATUS_ERROR = 8
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bose SoundTouch - Neues Gerät hinzufügen")
        self.resize(700, 600)
        
        self.status = self.STATUS_IDLE
        self.device_ip = None
        self.device_name = None
        self.setup_network_ssid = None
        self.home_network_ssid = None
        self.network_monitor = None
        self.ssid_survey_info = {}
        
        self.init_ui()
        
    def init_ui(self):
        """UI aufbauen"""
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("🔧 WiFi Setup-Assistent")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)
        
        # Instruktionen
        self.instruction_label = QLabel()
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setStyleSheet("padding: 10px; background-color: #e3f2fd; border-radius: 5px;")
        layout.addWidget(self.instruction_label)
        
        # Status Log
        log_group = QGroupBox("📋 Status")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # WiFi-Eingabe Gruppe
        wifi_group = QGroupBox("📶 WLAN-Zugangsdaten")
        wifi_layout = QVBoxLayout()
        
        # SSID - mit Scan-Button
        ssid_layout = QHBoxLayout()
        ssid_layout.addWidget(QLabel("SSID:"))
        self.ssid_combo = QComboBox()
        self.ssid_combo.setPlaceholderText("Netzwerk wählen...")
        self.ssid_combo.setEditable(True)
        self.ssid_combo.currentTextChanged.connect(self._on_ssid_changed)
        ssid_layout.addWidget(self.ssid_combo)
        
        self.scan_wifi_button = QPushButton("🔍 Scan")
        self.scan_wifi_button.setEnabled(False)
        self.scan_wifi_button.clicked.connect(self.scan_wifi_networks)
        self.scan_wifi_button.setMaximumWidth(80)
        ssid_layout.addWidget(self.scan_wifi_button)
        
        wifi_layout.addLayout(ssid_layout)
        
        # Passwort
        pw_layout = QHBoxLayout()
        pw_layout.addWidget(QLabel("Passwort:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("WLAN-Passwort")
        pw_layout.addWidget(self.password_input)
        
        # Passwort sichtbar/versteckt Toggle
        from PyQt5.QtWidgets import QCheckBox
        self.password_visible_checkbox = QCheckBox("Anzeigen")
        self.password_visible_checkbox.toggled.connect(self._on_password_visibility_toggle)
        pw_layout.addWidget(self.password_visible_checkbox)
        
        wifi_layout.addLayout(pw_layout)
        
        # Security Type
        sec_layout = QHBoxLayout()
        sec_layout.addWidget(QLabel("Sicherheit:"))
        self.security_combo = QComboBox()
        self.security_combo.addItems(["wpa_or_wpa2", "wpa2", "wpa", "wep", "open"])
        sec_layout.addWidget(self.security_combo)
        sec_layout.addStretch()
        wifi_layout.addLayout(sec_layout)

        # Optional: Button to connect PC back to home WiFi (Linux with NetworkManager)
        wifi_switch_layout = QHBoxLayout()
        self.switch_wifi_button = QPushButton("↺ Heim-WLAN verbinden")
        self.switch_wifi_button.setEnabled(False)
        self.switch_wifi_button.clicked.connect(self.switch_to_home_wifi)
        wifi_switch_layout.addWidget(self.switch_wifi_button)
        wifi_layout.addLayout(wifi_switch_layout)
        
        wifi_group.setLayout(wifi_layout)
        self.wifi_group = wifi_group
        self.wifi_group.setEnabled(False)
        layout.addWidget(wifi_group)
        
        # Progress Bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("🚀 Setup starten")
        self.start_button.clicked.connect(self.start_setup)
        button_layout.addWidget(self.start_button)
        
        self.send_wifi_button = QPushButton("📤 WiFi senden")
        self.send_wifi_button.setEnabled(False)
        self.send_wifi_button.clicked.connect(self.send_wifi_config)
        button_layout.addWidget(self.send_wifi_button)
        
        self.close_button = QPushButton("Abbrechen")
        self.close_button.clicked.connect(self.reject)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Initial-Status
        self.update_status(self.STATUS_IDLE)
    
    def log(self, message):
        """Nachricht im Log anzeigen"""
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def update_status(self, status):
        """Status aktualisieren und UI anpassen"""
        self.status = status
        
        if status == self.STATUS_IDLE:
            self.instruction_label.setText(
                "📱 Drücke 'Setup starten' und folge dann den Anweisungen.\n\n"
                "Der Wizard führt dich durch die Einrichtung eines neuen Bose SoundTouch Geräts."
            )
            self.start_button.setEnabled(True)
            
        elif status == self.STATUS_WAIT_SETUP_NETWORK:
            self.instruction_label.setText(
                "⚠️ WICHTIG: Wechsle jetzt zum WiFi des Lautsprechers!\n\n"
                "1. Halte 'Volume -' + 'Bluetooth' für 10 Sekunden gedrückt\n"
                "2. Lautsprecher startet im Setup-Modus (WiFi: 'Bose xxxx')\n"
                "3. Verbinde deinen PC mit diesem WiFi\n"
                "4. Der Wizard erkennt den Wechsel automatisch"
            )
            self.progress.setVisible(True)
            self.progress.setRange(0, 0)  # Indeterminate
            # Versuche automatisch ins Setup-WLAN zu wechseln (Linux)
            QTimer.singleShot(300, self.connect_to_setup_wifi_auto)
            
        elif status == self.STATUS_CONNECTED_TO_DEVICE:
            self.instruction_label.setText(
                "✅ Mit Lautsprecher verbunden!\n\n"
                "Scanne verfügbare Netzwerke automatisch ab. Du kannst auch manuell eine SSID eingeben.\n"
                "Gib dann das Passwort ein und klicke 'WiFi senden'."
            )
            self.wifi_group.setEnabled(True)
            self.send_wifi_button.setEnabled(True)
            self.scan_wifi_button.setEnabled(True)
            self.progress.setVisible(False)
            
            # Starte automatisch WiFi-Scan
            QTimer.singleShot(500, self.scan_wifi_networks)
            
        elif status == self.STATUS_SENDING_WIFI:
            self.instruction_label.setText(
                "📤 Sende WiFi-Konfiguration...\n\n"
                "Der Lautsprecher verbindet sich mit deinem WLAN und startet neu."
            )
            self.wifi_group.setEnabled(False)
            self.send_wifi_button.setEnabled(False)
            self.progress.setVisible(True)
            self.progress.setRange(0, 0)
            
        elif status == self.STATUS_DEVICE_REBOOTING:
            self.instruction_label.setText(
                "� Lautsprecher im Standby...\n\n"
                "👉 Drücke jetzt den Bluetooth-Button am Lautsprecher!\n"
                "Der Lautsprecher verbindet sich erst nach dem Aufwachen mit dem WLAN."
            )
            
        elif status == self.STATUS_WAIT_HOME_NETWORK:
            self.instruction_label.setText(
                "⚠️ Wechsle zurück zu deinem Heim-WLAN!\n\n"
                "Verbinde deinen PC wieder mit deinem normalen WLAN.\n"
                "Der Wizard sucht dann automatisch nach dem Lautsprecher."
            )
            # Allow WiFi switching helper on Linux
            self.switch_wifi_button.setEnabled(True)
        elif status == self.STATUS_DISCOVERING:
            self.instruction_label.setText(
                "🔍 Suche nach neuem Lautsprecher...\n\n"
                "Scanne das Netzwerk nach dem Gerät."
            )
            
        elif status == self.STATUS_SUCCESS:
            self.instruction_label.setText(
                "✅ Gerät erfolgreich hinzugefügt!\n\n"
                f"Name: {self.device_name}\n"
                f"IP: {self.device_ip}"
            )
            self.progress.setVisible(False)
            self.start_button.setEnabled(False)
            self.send_wifi_button.setEnabled(False)
            self.scan_wifi_button.setEnabled(False)
            # Rename close button to "Verlassen" on success
            self.close_button.setText("Verlassen")
            
        elif status == self.STATUS_ERROR:
            self.instruction_label.setText(
                "❌ Fehler beim Setup\n\n"
                "Bitte versuche es erneut oder prüfe die Verbindung."
            )
            self.progress.setVisible(False)
    
    def _on_password_visibility_toggle(self, checked):
        """Toggle Passwort Sichtbarkeit"""
        if checked:
            self.password_input.setEchoMode(QLineEdit.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.Password)
    
    def start_setup(self):
        """Setup-Prozess starten"""
        self.log("🚀 Setup gestartet")
        self.update_status(self.STATUS_WAIT_SETUP_NETWORK)
        self.start_button.setEnabled(False)
        
        # Netzwerk-Monitor starten
        self.network_monitor = NetworkMonitorThread(self)
        self.network_monitor.network_changed.connect(self.on_network_changed)
        self.network_monitor.start()
        self.log("👀 Überwache Netzwerkwechsel...")

        # Sofortige Prüfung, falls wir bereits im Setup-WLAN sind
        if self.status == self.STATUS_WAIT_SETUP_NETWORK:
            ssid = self.get_current_ssid()
            if ("Bose" in ssid or "SoundTouch" in ssid):
                self.log("✅ Setup-Netzwerk erkannt!")
                self.setup_network_ssid = ssid
                self.find_setup_device()
    
    def on_network_changed(self, interface, ip):
        """Callback wenn Netzwerk gewechselt wurde"""
        self.log(f"🔄 Netzwerkwechsel erkannt: {interface} → {ip}")
        
        if self.status == self.STATUS_WAIT_SETUP_NETWORK:
            # Prüfen ob es ein Bose Setup-Netzwerk ist
            ssid = self.get_current_ssid()
            if (
                "Bose" in ssid or "SoundTouch" in ssid or
                ip.startswith("169.254.") or
                # Wenn wir eine valide Setup-Gateway-IP ableiten können, direkt versuchen
                bool(self._get_setup_device_ip())
            ):
                self.log("✅ Setup-Netzwerk erkannt!")
                self.setup_network_ssid = ssid
                
                # Gerät suchen (im Setup-Mode ist die IP meist 169.254.x.x oder 192.168.173.1)
                self.find_setup_device()
        
        elif self.status == self.STATUS_WAIT_HOME_NETWORK:
            # Prüfe ob wir ins Heim-WLAN zurückgekehrt sind
            # (nicht mehr im Setup-Netz 192.0.2.x oder 169.254.x)
            if ip and not ip.startswith("192.0.2.") and not ip.startswith("169.254."):
                self.home_network_ssid = self.get_current_ssid()
                self.log(f"✅ Zurück im Heim-WLAN: {self.home_network_ssid} ({ip})")
                self.update_status(self.STATUS_DISCOVERING)
                
                # Warte 5 Sekunden, dann starte Discovery (gibt Speaker Zeit sich anzumelden)
                QTimer.singleShot(5000, self.discover_new_device)
    
    def get_current_ssid(self):
        """Aktuelle SSID ermitteln"""
        try:
            import subprocess
            # Linux
            result = subprocess.check_output(['iwgetid', '-r'], text=True).strip()
            return result
        except:
            return "unknown"
    
    def _get_setup_device_ip(self):
        """Ermittle wahrscheinliche Setup-IP basierend auf aktueller WLAN-IP."""
        try:
            # Hole aktuelle WLAN-IP
            for iface in netifaces.interfaces():
                if not (iface.startswith('wl') or iface.startswith('wlan') or iface.startswith('wlp')):
                    continue
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr.get('addr')
                        if ip and ip != '127.0.0.1':
                            # 1) Bevorzugt: ermittele tatsächliches Default-Gateway für dieses Interface
                            try:
                                gws = netifaces.gateways()
                                # Prüfe Standard-Gateway
                                default_gw = gws.get('default', {}).get(netifaces.AF_INET)
                                if default_gw:
                                    gw_addr, gw_iface = default_gw[0], default_gw[1]
                                    if gw_iface == iface and gw_addr:
                                        self.log(f"   WLAN-IP: {ip} → Gateway erkannt: {gw_addr}")
                                        return gw_addr

                                # Prüfe alle Gateways nach passendem Interface
                                for entry in gws.get(netifaces.AF_INET, []):
                                    try:
                                        gw_addr, gw_iface, _flags = entry
                                    except ValueError:
                                        gw_addr, gw_iface = entry  # ältere netifaces-Version
                                    if gw_iface == iface and gw_addr:
                                        self.log(f"   WLAN-IP: {ip} → Gateway erkannt: {gw_addr}")
                                        return gw_addr
                            except Exception as ge:
                                self.log(f"   Hinweis: Konnte Gateway nicht direkt ermitteln: {ge}")

                            # 2) Fallback: ersetze letztes Oktett mit .1
                            parts = ip.split('.')
                            if len(parts) == 4:
                                gateway_ip = f"{parts[0]}.{parts[1]}.{parts[2]}.1"
                                self.log(f"   WLAN-IP: {ip} → Gateway (heuristisch): {gateway_ip}")
                                return gateway_ip
        except Exception as e:
            self.log(f"   Fehler beim Ermitteln der Gateway-IP: {e}")
        return None
    
    def find_setup_device(self):
        """Gerät im Setup-Modus finden"""
        self.log("🔍 Suche Gerät im Setup-Modus...")
        
        # Versuche zuerst die wahrscheinliche IP aus dem aktuellen Netzwerk
        setup_ips = []
        detected_ip = self._get_setup_device_ip()
        if detected_ip:
            setup_ips.append(detected_ip)
        
        # Füge bekannte Standard-IPs als Fallback hinzu
        fallback_ips = [
            # Gängige Private-Netz Gateways
            "192.168.0.1", "192.168.1.1", "192.168.43.1", "192.168.50.1",
            "10.0.0.1", "10.1.1.1",
            # Link-Local (Setup ohne DHCP)
            "169.254.1.1",
            # Häufig bei Setup/Hotspot
            "192.168.173.1"
        ]
        for ip in fallback_ips:
            if ip not in setup_ips:
                setup_ips.append(ip)
        
        # Erstelle Worker
        self.find_setup_worker = FindSetupDeviceWorker(setup_ips)
        
        # Erstelle Thread
        self.find_setup_thread = QThread()
        self.find_setup_worker.moveToThread(self.find_setup_thread)
        
        # Verbinde Signals
        self.find_setup_thread.started.connect(self.find_setup_worker.run)
        self.find_setup_worker.device_found.connect(self._on_setup_device_found)
        self.find_setup_worker.device_not_found.connect(self._on_setup_device_not_found)
        self.find_setup_worker.status_message.connect(self.log)
        self.find_setup_worker.device_found.connect(self.find_setup_thread.quit)
        self.find_setup_worker.device_not_found.connect(self.find_setup_thread.quit)
        self.find_setup_thread.finished.connect(self.find_setup_worker.deleteLater)
        self.find_setup_thread.finished.connect(self.find_setup_thread.deleteLater)
        
        # Starte Thread
        self.find_setup_thread.start()
    
    def _on_setup_device_found(self, ip, name, device_id):
        """Callback wenn Setup-Gerät gefunden wurde"""
        self.device_ip = ip
        self.log(f"✅ Gerät gefunden: {name} auf {ip}")
        self.update_status(self.STATUS_CONNECTED_TO_DEVICE)
    
    def _on_setup_device_not_found(self):
        """Callback wenn Setup-Gerät nicht gefunden wurde"""
        self.log("❌ Gerät nicht gefunden. Bist du im Setup-WLAN?\n"
             "   Stelle sicher, dass:\n"
             "   1. Der Lautsprecher im Setup-Modus ist\n"
             "   2. Du mit seinem WiFi verbunden bist")
    
    def send_wifi_config(self):
        """WiFi-Konfiguration an Gerät senden"""
        ssid = self.ssid_combo.currentText().strip()
        password = self.password_input.text()
        security = self.security_combo.currentText()
        
        if not ssid:
            self.log("❌ Fehler: Bitte SSID auswählen oder eingeben!")
            return
        
        if not password and security != "open":
            self.log("❌ Fehler: Bitte Passwort eingeben!")
            return
        
        self.update_status(self.STATUS_SENDING_WIFI)
        self.log(f"📤 Sende WiFi-Config: SSID='{ssid}', Security={security}")
        self.send_wifi_button.setEnabled(False)
        self.scan_wifi_button.setEnabled(False)
        
        # Erstelle Worker
        self.wifi_config_worker = WiFiConfigSendWorker(
            SoundTouchController(self.device_ip, timeout=10),
            ssid, password, security, timeout_secs=45
        )
        
        # Erstelle Thread
        self.wifi_config_thread = QThread()
        self.wifi_config_worker.moveToThread(self.wifi_config_thread)
        
        # Verbinde Signals
        self.wifi_config_thread.started.connect(self.wifi_config_worker.run)
        self.wifi_config_worker.config_sent.connect(self._on_wifi_config_sent)
        self.wifi_config_worker.error_occurred.connect(self._on_wifi_config_error)
        self.wifi_config_worker.debug_message.connect(self.log)  # Log debug messages
        self.wifi_config_worker.config_sent.connect(self.wifi_config_thread.quit)
        self.wifi_config_thread.finished.connect(self.wifi_config_worker.deleteLater)
        self.wifi_config_thread.finished.connect(self.wifi_config_thread.deleteLater)
        
        # Starte Thread
        self.wifi_config_thread.start()
    
    def _on_wifi_config_sent(self, success):
        """Callback wenn WiFi-Config gesendet wurde"""
        self.send_wifi_button.setEnabled(True)
        
        if success:
            self.log("✅ WiFi-Config gesendet!")
            self.log("🔄 Gerät ist im Standby...")
            self.log("👉 WICHTIG: Drücke jetzt den Bluetooth-Button am Lautsprecher!")
            self.log("   Der Lautsprecher verbindet sich erst nach dem Aufwachen mit dem WLAN.")
            self.update_status(self.STATUS_DEVICE_REBOOTING)
            
            # Warte 3 Sekunden, dann starte Reconnection-Monitoring
            QTimer.singleShot(3000, lambda: self.monitor_device_reconnection(
                SoundTouchController(self.device_ip, timeout=10),
                self.ssid_combo.currentText()
            ))
        else:
            self.log("❌ Fehler beim Senden der WiFi-Config: WiFi-Konfiguration konnte nicht gesendet werden!")
            self.update_status(self.STATUS_ERROR)
    
    def _on_wifi_config_error(self, error_message):
        """Callback bei Fehler beim WiFi-Config-Senden"""
        self.send_wifi_button.setEnabled(True)
        self.scan_wifi_button.setEnabled(True)
        self.log(f"❌ Fehler beim Senden der WiFi-Config: {error_message}")
        self.update_status(self.STATUS_ERROR)
    
    def scan_wifi_networks(self):
        """Scanne verfügbare WiFi-Netzwerke"""
        self.log("🔍 Scanne verfügbare Netzwerke (dies kann bis zu 1 Minute dauern)...")
        self.scan_wifi_button.setEnabled(False)
        self.send_wifi_button.setEnabled(False)
        
        # Erstelle Worker mit erhöhtem Timeout (Scan kann lange dauern)
        self.wifi_scan_worker = WiFiScanWorker(
            SoundTouchController(self.device_ip, timeout=90)
        )
        
        # Erstelle Thread
        self.wifi_scan_thread = QThread()
        self.wifi_scan_worker.moveToThread(self.wifi_scan_thread)
        
        # Verbinde Signals
        self.wifi_scan_thread.started.connect(self.wifi_scan_worker.run)
        self.wifi_scan_worker.scan_completed.connect(self._on_wifi_scan_completed)
        self.wifi_scan_worker.scan_data_completed.connect(self._on_wifi_scan_data_completed)
        self.wifi_scan_worker.scan_failed.connect(self._on_wifi_scan_failed)
        self.wifi_scan_worker.debug_message.connect(self.log)  # Log debug messages
        self.wifi_scan_worker.scan_completed.connect(self.wifi_scan_thread.quit)
        self.wifi_scan_worker.scan_failed.connect(self.wifi_scan_thread.quit)
        self.wifi_scan_thread.finished.connect(self.wifi_scan_worker.deleteLater)
        self.wifi_scan_thread.finished.connect(self.wifi_scan_thread.deleteLater)
        
        # Starte Thread
        self.wifi_scan_thread.start()
    
    def _on_wifi_scan_completed(self, ssids):
        """Callback wenn WiFi-Scan komplett ist"""
        self.scan_wifi_button.setEnabled(True)
        self.send_wifi_button.setEnabled(True)
        
        if ssids:
            self.log(f"✅ Scan abgeschlossen: {len(ssids)} Netzwerk(e) gefunden")
            for i, ssid in enumerate(ssids, 1):
                self.log(f"   {i}. {ssid}")
        else:
            self.log("⚠️ Scan abgeschlossen, aber keine Netzwerke gefunden")
        
        # Update ComboBox
        current = self.ssid_combo.currentText()
        self.ssid_combo.clear()
        if ssids:
            self.ssid_combo.addItems(ssids)
            
            # Wiederherstellen oder auf erstes setzen
            idx = self.ssid_combo.findText(current)
            if idx >= 0:
                self.ssid_combo.setCurrentIndex(idx)
            else:
                self.ssid_combo.setCurrentIndex(0)
    
    def _on_wifi_scan_failed(self, error_message):
        """Callback bei Fehler beim WiFi-Scan"""
        self.scan_wifi_button.setEnabled(True)
        self.send_wifi_button.setEnabled(True)
        self.log(f"❌ Scan fehlgeschlagen: {error_message}")
        self.log("   Tipp: Versuche die SSID manuell einzugeben oder klicke nochmal auf 'Scan'")

    def _on_wifi_scan_data_completed(self, networks):
        """Store survey info (security types per SSID) and auto-apply."""
        self.ssid_survey_info = {}
        for n in networks:
            ssid = n.get('ssid')
            security = n.get('security')
            if ssid:
                # prefer first seen value
                if ssid not in self.ssid_survey_info:
                    self.ssid_survey_info[ssid] = security
        # Apply auto-security for current selection
        self._apply_security_for_current_ssid()

    def _on_ssid_changed(self, text):
        self._apply_security_for_current_ssid()

    def _apply_security_for_current_ssid(self):
        ssid = self.ssid_combo.currentText().strip()
        if not ssid:
            return
        sec = self.ssid_survey_info.get(ssid)
        if sec:
            idx = self.security_combo.findText(sec)
            if idx >= 0:
                self.security_combo.setCurrentIndex(idx)
    
    def monitor_device_reconnection(self, controller, target_ssid):
        """
        Monitor the device's reconnection to the home network after WiFi configuration.
        Runs in a separate thread to avoid blocking the UI.
        """
        # Erstelle Worker
        self.reconnection_worker = DeviceReconnectionWorker(controller, target_ssid)
        
        # Erstelle Thread
        self.reconnection_thread = QThread()
        self.reconnection_worker.moveToThread(self.reconnection_thread)
        
        # Verbinde Signals
        self.reconnection_thread.started.connect(self.reconnection_worker.run)
        self.reconnection_worker.status_updated.connect(self._on_reconnection_status)
        self.reconnection_worker.reconnection_finished.connect(self._on_reconnection_finished)
        self.reconnection_worker.reconnection_finished.connect(self.reconnection_thread.quit)
        self.reconnection_thread.finished.connect(self.reconnection_worker.deleteLater)
        self.reconnection_thread.finished.connect(self.reconnection_thread.deleteLater)
        
        # Starte Thread
        self.reconnection_thread.start()
    
    def _on_reconnection_status(self, message):
        """Callback für Status-Updates während Reconnection"""
        self.log(f"⏳ {message}")
    
    def _on_reconnection_finished(self, reconnected):
        """Callback wenn Reconnection-Monitoring fertig ist"""
        if reconnected:
            self.log("✅ Gerät erfolgreich mit Home-WLAN verbunden!")
            self.update_status(self.STATUS_WAIT_HOME_NETWORK)
            self.log("⏳ Warte darauf, dass PC ins Heim-WLAN zurückkehrt...")
            # Discovery wird vom Network-Monitor gestartet, wenn PC im Heim-WLAN ist
            # (siehe on_network_changed - es erkennt Rückkehr ins Heim-WLAN)
        else:
            self.log("❌ Gerät konnte sich nicht mit dem Home-WLAN verbinden.")
            self.update_status(self.STATUS_ERROR)
            
            # Retry Option
            retry = QMessageBox.question(
                self,
                "Verbindung fehlgeschlagen",
                "Gerät konnte sich nicht verbinden. Erneut versuchen?",
                QMessageBox.Yes | QMessageBox.No
            )
            if retry == QMessageBox.Yes:
                self.send_wifi_config()

    def switch_to_home_wifi(self):
        """Attempt to switch PC back to selected home WiFi using nmcli (Linux)."""
        import subprocess
        ssid = self.ssid_combo.currentText().strip()
        password = self.password_input.text()
        if not ssid:
            self.log("❌ Keine SSID ausgewählt")
            return
        self.log(f"🔁 Verbinde PC mit '{ssid}'...")
        try:
            # Try connect via NetworkManager
            if password:
                cmd = ["nmcli", "dev", "wifi", "connect", ssid, "password", password]
            else:
                cmd = ["nmcli", "dev", "wifi", "connect", ssid]
            subprocess.check_call(cmd)
            self.log("✅ PC mit Heim-WLAN verbunden")
        except FileNotFoundError:
            self.log("⚠️ 'nmcli' nicht gefunden. Bitte manuell ins Heim-WLAN wechseln.")
        except subprocess.CalledProcessError as e:
            self.log(f"❌ WLAN-Wechsel fehlgeschlagen: {e}")
    
    def connect_to_setup_wifi_auto(self):
        """Attempt to automatically connect PC to the speaker's setup WiFi (Linux, NetworkManager)."""
        # Erstelle Worker
        self.connect_setup_worker = ConnectSetupWiFiWorker()
        
        # Erstelle Thread
        self.connect_setup_thread = QThread()
        self.connect_setup_worker.moveToThread(self.connect_setup_thread)
        
        # Verbinde Signals
        self.connect_setup_thread.started.connect(self.connect_setup_worker.run)
        self.connect_setup_worker.connected.connect(self._on_setup_wifi_connected)
        self.connect_setup_worker.failed.connect(self._on_setup_wifi_failed)
        self.connect_setup_worker.status_message.connect(self.log)
        self.connect_setup_worker.connected.connect(self.connect_setup_thread.quit)
        self.connect_setup_worker.failed.connect(self.connect_setup_thread.quit)
        self.connect_setup_thread.finished.connect(self.connect_setup_worker.deleteLater)
        self.connect_setup_thread.finished.connect(self.connect_setup_thread.deleteLater)
        
        # Starte Thread
        self.connect_setup_thread.start()
    
    def _on_setup_wifi_connected(self, ssid):
        """Callback wenn Setup-WiFi-Verbindung erfolgreich war"""
        self.setup_network_ssid = ssid
        self.log(f"✅ PC mit Setup-WLAN verbunden: {ssid}")
    
    def _on_setup_wifi_failed(self, error_msg):
        """Callback wenn Setup-WiFi-Verbindung fehlgeschlagen ist"""
        self.log(f"⚠️ {error_msg}")
    
    def discover_new_device(self):
        """Nach neuem Gerät im Heim-WLAN suchen"""
        self.log("🔍 Scanne Netzwerk nach neuem Gerät (Timeout: 60 Sekunden)...")
        
        # Erstelle Worker
        self.discover_worker = DiscoverDeviceWorker()
        
        # Erstelle Thread
        self.discover_thread = QThread()
        self.discover_worker.moveToThread(self.discover_thread)
        
        # Verbinde Signals
        self.discover_thread.started.connect(self.discover_worker.run)
        self.discover_worker.devices_found.connect(self._on_devices_found)
        self.discover_worker.status_message.connect(self.log)
        self.discover_worker.devices_found.connect(self.discover_thread.quit)
        self.discover_thread.finished.connect(self.discover_worker.deleteLater)
        self.discover_thread.finished.connect(self.discover_thread.deleteLater)
        
        # Starte Thread
        self.discover_thread.start()
    
    def _on_devices_found(self, devices):
        """Callback wenn Device-Discovery abgeschlossen ist"""
        self.log(f"   {len(devices)} Gerät(e) gefunden")
        
        if devices:
            # Nehme erstes Gerät (oder zeige Liste wenn mehrere)
            device = devices[0]
            self.device_ip = device['ip']
            self.device_name = device['name']
            
            self.log(f"✅ Gerät gefunden: {self.device_name} ({self.device_ip})")
            
            # Beende Setup-Modus (schaltet Setup-WiFi-Hotspot aus)
            self.log("🔒 Beende Setup-Modus...")
            try:
                controller = SoundTouchController(self.device_ip)
                if controller.set_setup_state("SETUP_WIFI_LEAVE"):
                    self.log("✅ Setup-Modus beendet")
                else:
                    self.log("⚠️ Setup-Modus konnte nicht beendet werden (Gerät ist möglicherweise bereits im Normalbetrieb)")
            except Exception as e:
                self.log(f"⚠️ Fehler beim Beenden des Setup-Modus: {e}")
            
            self.update_status(self.STATUS_SUCCESS)
            
            # Frage ob Name geändert werden soll
            QTimer.singleShot(1000, self.ask_rename_device)
        else:
            self.log("❌ Kein Gerät gefunden. Warte noch 15 Sekunden...")
            QTimer.singleShot(15000, self.discover_new_device)
    
    def ask_rename_device(self):
        """Frage ob Gerät umbenannt werden soll"""
        reply = QMessageBox.question(
            self,
            "Gerät umbenennen?",
            f"Möchtest du das Gerät '{self.device_name}' umbenennen?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            from PyQt5.QtWidgets import QInputDialog
            new_name, ok = QInputDialog.getText(self, "Neuer Name",
                                               "Neuer Gerätename:",
                                               text=self.device_name)
            
            if ok and new_name.strip():
                self.rename_device(new_name.strip())
        else:
            self.log("✅ Setup abgeschlossen!")
            self.log(f"Gerät '{self.device_name}' erfolgreich hinzugefügt! IP: {self.device_ip}")
    
    def rename_device(self, new_name):
        """Gerät umbenennen"""
        self.log(f"✏️ Benenne Gerät um: '{self.device_name}' → '{new_name}'")
        
        try:
            controller = SoundTouchController(self.device_ip)
            success = controller.set_device_name(new_name)
            
            if success:
                self.device_name = new_name
                self.log(f"✅ Name geändert: {new_name}")
                self.log(f"Gerät wurde umbenannt zu: {new_name} (IP: {self.device_ip})")
            else:
                self.log("❌ Fehler beim Umbenennen: Gerät konnte nicht umbenannt werden.")
                
        except Exception as e:
            self.log(f"❌ Fehler beim Umbenennen: {e}")
    
    def closeEvent(self, event):
        """Dialog wird geschlossen"""
        if self.network_monitor:
            self.network_monitor.stop()
            self.network_monitor.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    wizard = DeviceSetupWizard()
    wizard.show()
    sys.exit(app.exec_())
