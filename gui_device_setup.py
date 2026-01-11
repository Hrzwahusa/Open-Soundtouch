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
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QFont
from soundtouch_lib import SoundTouchController, SoundTouchDiscovery
import netifaces
import time


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
        
        # SSID
        ssid_layout = QHBoxLayout()
        ssid_layout.addWidget(QLabel("SSID:"))
        self.ssid_input = QLineEdit()
        self.ssid_input.setPlaceholderText("Name deines WLANs")
        ssid_layout.addWidget(self.ssid_input)
        wifi_layout.addLayout(ssid_layout)
        
        # Passwort
        pw_layout = QHBoxLayout()
        pw_layout.addWidget(QLabel("Passwort:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("WLAN-Passwort")
        pw_layout.addWidget(self.password_input)
        wifi_layout.addLayout(pw_layout)
        
        # Security Type
        sec_layout = QHBoxLayout()
        sec_layout.addWidget(QLabel("Sicherheit:"))
        self.security_combo = QComboBox()
        self.security_combo.addItems(["wpa_or_wpa2", "wpa2", "wpa", "wep", "open"])
        sec_layout.addWidget(self.security_combo)
        sec_layout.addStretch()
        wifi_layout.addLayout(sec_layout)
        
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
            
        elif status == self.STATUS_CONNECTED_TO_DEVICE:
            self.instruction_label.setText(
                "✅ Mit Lautsprecher verbunden!\n\n"
                "Gib jetzt die Zugangsdaten deines Heim-WLANs ein und klicke 'WiFi senden'."
            )
            self.wifi_group.setEnabled(True)
            self.send_wifi_button.setEnabled(True)
            self.progress.setVisible(False)
            
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
                "🔄 Lautsprecher startet neu...\n\n"
                "Warte ca. 30 Sekunden."
            )
            
        elif status == self.STATUS_WAIT_HOME_NETWORK:
            self.instruction_label.setText(
                "⚠️ Wechsle zurück zu deinem Heim-WLAN!\n\n"
                "Verbinde deinen PC wieder mit deinem normalen WLAN.\n"
                "Der Wizard sucht dann automatisch nach dem Lautsprecher."
            )
            
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
            
        elif status == self.STATUS_ERROR:
            self.instruction_label.setText(
                "❌ Fehler beim Setup\n\n"
                "Bitte versuche es erneut oder prüfe die Verbindung."
            )
            self.progress.setVisible(False)
    
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
            # Zurück im Heim-WLAN
            self.home_network_ssid = self.get_current_ssid()
            self.log(f"✅ Zurück im Heim-WLAN: {self.home_network_ssid}")
            self.update_status(self.STATUS_DISCOVERING)
            
            # Nach Gerät suchen
            QTimer.singleShot(3000, self.discover_new_device)
    
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
        
        for ip in setup_ips:
            try:
                self.log(f"   Versuche {ip}...")
                controller = SoundTouchController(ip, timeout=2)
                info = controller.get_info()
                if info:
                    self.device_ip = ip
                    self.log(f"✅ Gerät gefunden: {info.get('name', 'Unknown')} auf {ip}")
                    self.update_status(self.STATUS_CONNECTED_TO_DEVICE)
                    return
            except:
                pass
        
        self.log("❌ Gerät nicht gefunden. Bist du im Setup-WLAN?\n"
             "   Stelle sicher, dass:\n"
             "   1. Der Lautsprecher im Setup-Modus ist\n"
             "   2. Du mit seinem WiFi verbunden bist")
    
    def send_wifi_config(self):
        """WiFi-Konfiguration an Gerät senden"""
        ssid = self.ssid_input.text().strip()
        password = self.password_input.text()
        security = self.security_combo.currentText()
        
        if not ssid:
            self.log("❌ Fehler: Bitte SSID eingeben!")
            return
        
        if not password and security != "open":
            self.log("❌ Fehler: Bitte Passwort eingeben!")
            return
        
        self.update_status(self.STATUS_SENDING_WIFI)
        self.log(f"📤 Sende WiFi-Config: SSID='{ssid}', Security={security}")
        
        try:
            controller = SoundTouchController(self.device_ip, timeout=10)
            
            # WiFi-Profil hinzufügen
            success = controller.add_wireless_profile(ssid, password, security, timeout_secs=30)
            
            if success:
                self.log("✅ WiFi-Config gesendet!")
                self.log("🔄 Gerät startet neu und verbindet sich...")
                self.update_status(self.STATUS_DEVICE_REBOOTING)
                
                # Warte 30 Sekunden
                QTimer.singleShot(30000, lambda: self.update_status(self.STATUS_WAIT_HOME_NETWORK))
            else:
                self.log("❌ Fehler beim Senden der WiFi-Config: WiFi-Konfiguration konnte nicht gesendet werden!")
                self.update_status(self.STATUS_ERROR)
                
        except Exception as e:
            self.log(f"❌ Fehler beim Senden der WiFi-Config: {e}")
            self.update_status(self.STATUS_ERROR)
    
    def discover_new_device(self):
        """Nach neuem Gerät im Heim-WLAN suchen"""
        self.log("🔍 Scanne Netzwerk nach neuem Gerät...")
        
        try:
            discovery = SoundTouchDiscovery()
            devices = discovery.scan(max_workers=20)
            
            self.log(f"   {len(devices)} Gerät(e) gefunden")
            
            if devices:
                # Nehme erstes Gerät (oder zeige Liste wenn mehrere)
                device = devices[0]
                self.device_ip = device['ip']
                self.device_name = device['name']
                
                self.log(f"✅ Gerät gefunden: {self.device_name} ({self.device_ip})")
                self.update_status(self.STATUS_SUCCESS)
                
                # Frage ob Name geändert werden soll
                QTimer.singleShot(1000, self.ask_rename_device)
            else:
                self.log("❌ Kein Gerät gefunden. Warte noch 10 Sekunden...")
                QTimer.singleShot(10000, self.discover_new_device)
                
        except Exception as e:
            self.log(f"❌ Fehler beim Scannen: {e}")
            self.update_status(self.STATUS_ERROR)
    
    def ask_rename_device(self):
        """Frage ob Gerät umbenannt werden soll"""
        reply = QMessageBox.question(self, "Gerät umbenennen?",
                                    f"Möchtest du das Gerät '{self.device_name}' umbenennen?",
                                    QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            from PyQt5.QtWidgets import QInputDialog
            new_name, ok = QInputDialog.getText(self, "Neuer Name",
                                               "Neuer Gerätename:",
                                               text=self.device_name)
            
            if ok and new_name.strip():
                self.rename_device(new_name.strip())
        else:
            self.log("✅ Setup abgeschlossen!")
            QMessageBox.information(self, "Erfolg",
                                   f"Gerät '{self.device_name}' erfolgreich hinzugefügt!\n\n"
                                   f"IP: {self.device_ip}")
    
    def rename_device(self, new_name):
        """Gerät umbenennen"""
        self.log(f"✏️ Benenne Gerät um: '{self.device_name}' → '{new_name}'")
        
        try:
            controller = SoundTouchController(self.device_ip)
            success = controller.set_device_name(new_name)
            
            if success:
                self.device_name = new_name
                self.log(f"✅ Name geändert: {new_name}")
                QMessageBox.information(self, "Erfolg",
                                       f"Gerät wurde umbenannt zu:\n{new_name}\n\n"
                                       f"IP: {self.device_ip}")
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
