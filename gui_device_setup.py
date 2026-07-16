#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI Dialog für WiFi-Setup von neuen Bose SoundTouch Geräten
"""

import sys
import os
import socket
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTextEdit, QProgressBar, QGroupBox,
    QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QFont
from soundtouch_lib import SoundTouchController, SoundTouchDiscovery
import netifaces
import time
import platform_wifi


def find_removable_drives():
    """Liefert schreibbare Wechseldatenträger-Mountpunkte, plattformübergreifend.

    Windows: erkennt Wechseldatenträger anhand von GetDriveTypeW (== DRIVE_REMOVABLE).
    Linux/macOS: übliche Mountverzeichnisse unter /media, /run/media, /mnt, /Volumes.
    """
    mounts = []
    if sys.platform.startswith("win"):
        import ctypes
        import string

        DRIVE_REMOVABLE = 2
        try:
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        except Exception:
            bitmask = 0
        for i, letter in enumerate(string.ascii_uppercase):
            if not (bitmask >> i) & 1:
                continue
            root = f"{letter}:\\"
            try:
                if ctypes.windll.kernel32.GetDriveTypeW(root) == DRIVE_REMOVABLE and os.access(root, os.W_OK):
                    mounts.append(root)
            except Exception:
                continue
    else:
        import getpass

        try:
            user = os.environ.get("USER") or getpass.getuser()
        except Exception:
            user = "user"
        bases = [f"/media/{user}", f"/run/media/{user}", "/media", "/mnt", "/Volumes"]
        for base in bases:
            if not os.path.isdir(base):
                continue
            try:
                for name in os.listdir(base):
                    path = os.path.join(base, name)
                    if os.path.isdir(path) and os.path.ismount(path) and os.access(path, os.W_OK):
                        if path not in mounts:
                            mounts.append(path)
            except (PermissionError, OSError):
                continue
    return mounts


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
        """Versuche automatisch ins Setup-WLAN zu wechseln (plattformübergreifend)."""
        self.status_message.emit(
            f"🤖 Versuche automatisch ins Setup-WLAN zu wechseln… ({platform_wifi.backend_name()})"
        )
        try:
            # Setup-SSIDs des Speakers enthalten typischerweise 'Bose'/'SoundTouch'.
            # Windows liefert gecachte Scan-Ergebnisse -> frischen Scan anstoßen
            # und einige Male wiederholen, bis der AP auftaucht.
            candidates = []
            for attempt in range(6):
                platform_wifi.request_scan()
                time.sleep(3)
                candidates = platform_wifi.scan_ssids(name_filter="Bose")
                candidates += [s for s in platform_wifi.scan_ssids(name_filter="SoundTouch")
                               if s not in candidates]
                if candidates:
                    break
                self.status_message.emit(
                    f"   Setup-WLAN noch nicht sichtbar (Versuch {attempt + 1}/6)…"
                )
            if not candidates:
                self.failed.emit(
                    "Kein Setup-WLAN gefunden (SSID mit 'Bose'/'SoundTouch'). "
                    "Bitte manuell ins Setup-WLAN wechseln – der Wizard erkennt den Wechsel automatisch."
                )
                return

            target_ssid = candidates[0]
            self.status_message.emit(f"🔁 Verbinde PC mit Setup-WLAN '{target_ssid}'…")
            # Setup-Netze sind offen -> ohne Passwort verbinden
            ok, msg = platform_wifi.connect(target_ssid, password=None, confirm_timeout=20)
            if ok:
                self.connected.emit(target_ssid)
            else:
                self.failed.emit(f"Automatischer Wechsel fehlgeschlagen: {msg}")
        except Exception as e:  # noqa: BLE001
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


class DeviceDeployWorker(QObject):
    """Worker, der das On-Device-Setup per SSH installiert."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, error_msg

    def __init__(self, device_ip: str, source_root: Path, ssh_wait_timeout: int = 180):
        super().__init__()
        self.device_ip = device_ip
        self.source_root = Path(source_root)
        self.ssh_wait_timeout = ssh_wait_timeout
        # Gemeinsame ssh/scp-Optionen. UserKnownHostsFile=os.devnull verhindert,
        # dass ein nach Factory-Reset geänderter Host-Key den Verbindungsaufbau
        # still blockiert ("REMOTE HOST IDENTIFICATION HAS CHANGED").
        self._common_opts = [
            "-o", "HostKeyAlgorithms=+ssh-rsa",
            "-o", "PubkeyAcceptedAlgorithms=+ssh-rsa",
            "-o", "StrictHostKeyChecking=no",
            "-o", f"UserKnownHostsFile={os.devnull}",
            "-o", "ConnectTimeout=8",
        ]
        self.ssh_base = ["ssh"] + self._common_opts + [f"root@{self.device_ip}"]
        # Konsolenfenster unter Windows unterdrücken
        self._no_window = 0x08000000 if sys.platform.startswith("win") else 0

    def _wait_for_ssh(self, timeout: int) -> bool:
        """Wartet, bis TCP-Port 22 auf dem Gerät erreichbar ist (SSH aktiv)."""
        deadline = time.time() + timeout
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            try:
                with socket.create_connection((self.device_ip, 22), timeout=3):
                    self.progress.emit(f"SSH-Port offen (Versuch {attempt}).")
                    return True
            except OSError:
                remaining = int(deadline - time.time())
                self.progress.emit(f"Warte auf SSH-Start… (Port 22 noch zu, ~{remaining}s verbleibend)")
                time.sleep(3)
        return False

    def _ssh(self, command: str) -> str:
        cmd = self.ssh_base + [command]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, creationflags=self._no_window)
        return out.decode(errors="ignore")

    def _copy_file(self, local: Path, remote_path: str) -> None:
        """Kopiert eine Datei per 'cat' über SSH (statt scp).

        Die Bose-Box nutzt Dropbear ohne sftp-server; moderner OpenSSH-scp
        läuft aber über SFTP und scheitert daher (Exit 255). 'cat > datei'
        über die SSH-Verbindung braucht nur eine Shell und ist robust.
        Zeilenenden werden für Text-/Skriptdateien auf LF normalisiert,
        damit die Skripte auf dem Gerät nicht an Windows-CRLF scheitern.
        """
        data = local.read_bytes()
        if local.suffix.lower() in (".sh", ".conf", ".local", ".txt", ""):
            data = data.replace(b"\r\n", b"\n")
        cmd = self.ssh_base + [f"cat > '{remote_path}'"]
        proc = subprocess.run(
            cmd,
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=self._no_window,
        )
        if proc.returncode != 0:
            out = proc.stdout.decode(errors="ignore") if proc.stdout else ""
            raise subprocess.CalledProcessError(proc.returncode, cmd, output=out.encode())

    def run(self):
        remounted_rw = False
        try:
            self.progress.emit("Warte, bis SSH auf dem Gerät aktiv ist…")
            if not self._wait_for_ssh(self.ssh_wait_timeout):
                self.finished.emit(
                    False,
                    "SSH wurde nicht rechtzeitig aktiv. Steckt der USB-Stick mit der Datei "
                    "'remote_services' im Gerät, und ist das Gerät eingeschaltet?",
                )
                return
            # Offener Port heißt noch nicht, dass der Login klappt – kurz verifizieren.
            self.progress.emit("Prüfe SSH-Login...")
            self._ssh("echo ok")

            mount_state = self._ssh("mount | grep ' on / '")
            if " ro," in mount_state or "(ro," in mount_state:
                self.progress.emit("/ ist readonly, remounte rw...")
                self._ssh("mount -o remount,rw /")
                remounted_rw = True

            self.progress.emit("Lege /mnt/nv an...")
            self._ssh("mkdir -p /mnt/nv")

            file_map = {
                "preset_handler_daemon.sh": "/mnt/nv/preset_handler_daemon.sh",
                "rhino_preset_monitor.sh": "/mnt/nv/rhino_preset_monitor.sh",
                "key_interceptor_daemon.sh": "/mnt/nv/key_interceptor_daemon.sh",
                "key_interceptor_cgi.sh": "/mnt/nv/key_interceptor_cgi.sh",
                "preset_proxy_manager.sh": "/mnt/nv/preset_proxy_manager.sh",
                "preset_system_init.sh": "/mnt/nv/preset_system_init.sh",
                "radio_proxy.sh": "/mnt/nv/radio_proxy.sh",
                "preset_proxies.conf": "/mnt/nv/preset_proxies.conf",
            }

            for local_name, remote_path in file_map.items():
                src = self.source_root / local_name
                if not src.exists():
                    self.progress.emit(f"Überspringe fehlende Datei: {local_name}")
                    continue
                # Bestehende Preset-Config NICHT überschreiben (vom Nutzer per App
                # konfigurierte Sender bleiben bei einem erneuten Setup erhalten).
                if local_name == "preset_proxies.conf":
                    try:
                        exists = self._ssh(f"[ -f '{remote_path}' ] && echo yes || echo no")
                        if exists.strip().endswith("yes"):
                            self.progress.emit("Bestehende preset_proxies.conf bleibt erhalten")
                            continue
                    except subprocess.CalledProcessError:
                        pass
                self.progress.emit(f"Kopiere {local_name}...")
                self._copy_file(src, remote_path)

            self._ssh("chmod +x /mnt/nv/*.sh")

            self.progress.emit("Erzeuge rc.local...")
            rc_local = r"""#!/bin/sh
# Auto-start custom preset system

# --- Dauerhafter Fernzugriff (SSH/Telnet) OHNE USB-Stick ---
# rc.local wird beim Boot von /etc/init.d/shelby_local ausgefuehrt.
# sshd/telnetd starten sonst nur, wenn der USB-Stick den remote_services-
# Flag setzt. Hier setzen wir den Flag persistent und starten die Dienste.
touch /tmp/remote_services
start-stop-daemon --start --exec /usr/sbin/sshd 2>/dev/null
start-stop-daemon --start --exec /usr/sbin/telnetd 2>/dev/null

# NAT redirect 8090 -> 8089 once
if ! iptables -t nat -C PREROUTING -p tcp --dport 8090 -j REDIRECT --to-ports 8089 2>/dev/null; then
    iptables -t nat -I PREROUTING -p tcp --dport 8090 -j REDIRECT --to-ports 8089
fi

# Start mock Marge server if available
if [ -x /mnt/update/mock/mock_bose_https_armv7 ]; then
    if ! pgrep -f "mock_bose_https_armv7" >/dev/null; then
        /mnt/update/mock/mock_bose_https_armv7 --blueprint /mnt/update/mock/mock_blueprint.json --http :8088 --https :443 >/tmp/mock_marge.log 2>&1 &
    fi
fi

# Start preset system
if [ -x /mnt/nv/preset_system_init.sh ]; then
    /mnt/nv/preset_system_init.sh start >/tmp/preset_system_init.log 2>&1
fi

exit 0
"""
            self._ssh(
                "cat > /mnt/nv/rc.local <<'EOF'\n" + rc_local + "\nEOF\nchmod +x /mnt/nv/rc.local"
            )

            self.progress.emit("Stelle Preset-Config-Platzhalter bereit...")
            self._ssh(
                "if [ ! -f /mnt/nv/preset_proxies.conf ]; then echo '# Presets später per GUI setzen' > /mnt/nv/preset_proxies.conf; fi"
            )

            self.progress.emit("Setze NAT-Regel und starte Dienste...")
            self._ssh(
                "iptables -t nat -C PREROUTING -p tcp --dport 8090 -j REDIRECT --to-ports 8089 2>/dev/null || iptables -t nat -I PREROUTING -p tcp --dport 8090 -j REDIRECT --to-ports 8089"
            )
            self._ssh(
                "if [ -x /mnt/update/mock/mock_bose_https_armv7 ]; then pgrep -f mock_bose_https_armv7 >/dev/null || /mnt/update/mock/mock_bose_https_armv7 --blueprint /mnt/update/mock/mock_blueprint.json --http :8088 --https :443 >/tmp/mock_marge.log 2>&1 & fi"
            )
            # Preset-System via setsid abgekoppelt starten, damit die Daemons das
            # Ende der SSH-Session überleben (preset_system_init.sh detacht nicht
            # selbst; beim Boot läuft es ohne Controlling-Terminal, hier aber schon).
            self._ssh(
                "setsid /bin/sh -c '/mnt/nv/preset_system_init.sh restart' "
                "</dev/null >/tmp/preset_system_init.log 2>&1 & sleep 3"
            )

            self.finished.emit(True, "")
        except subprocess.CalledProcessError as exc:
            err = exc.output.decode(errors="ignore") if exc.output else str(exc)
            self.finished.emit(False, err)
        except Exception as exc:  # noqa: BLE001
            self.finished.emit(False, str(exc))
        finally:
            if remounted_rw:
                try:
                    self.progress.emit("Setze root-FS zurück auf ro...")
                    self._ssh("mount -o remount,ro /")
                except subprocess.CalledProcessError:
                    pass


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
        """Aktuelle WLAN-SSID ermitteln (plattformübergreifend)."""
        return platform_wifi.current_ssid()

    def _get_wifi_info(self):
        """Ermittle aktives Interface und dessen IPv4-Adresse.

        Interface-namensunabhängig (Default-Route), damit es auch unter
        Windows funktioniert, wo WLAN-Adapter GUID-Namen tragen.
        """
        iface, ip = platform_wifi.active_ip()
        return iface or "", ip or ""
    
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
    STATUS_DEPLOYING = 9
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bose SoundTouch - Neues Gerät hinzufügen")
        self.resize(700, 600)
        
        self.status = self.STATUS_IDLE
        self.device_ip = None
        self.device_name = None
        self.setup_device_id = None
        self.setup_network_ssid = None
        self.home_network_ssid = None
        self.network_monitor = None
        self.ssid_survey_info = {}
        # Identifiers of the target device (captured in setup mode)
        self.setup_device_mac = None
        self.setup_device_serials = set()
        # Track optional threads for safe shutdown
        self.find_setup_thread = None
        self.wifi_config_thread = None
        self.wifi_scan_thread = None
        self.reconnection_thread = None
        self.connect_setup_thread = None
        self.discover_thread = None
        self.deploy_thread = None
        self.deploy_worker = None
        self.closing = False
        
        
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

        # Gerätemodell – bestimmt die Tastenkombination für den Setup-Modus
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Gerätemodell:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["SoundTouch 10", "SoundTouch 20 / 30"])
        self.model_combo.currentTextChanged.connect(
            lambda _: self.update_status(self.status) if self.status == self.STATUS_WAIT_SETUP_NETWORK else None
        )
        model_layout.addWidget(self.model_combo)
        model_layout.addStretch()
        layout.addLayout(model_layout)

        # Instruktionen
        self.instruction_label = QLabel()
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setStyleSheet("padding: 10px; background-color: #1E2129; border-radius: 8px; color: #E7E9EE;")
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
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("WLAN-Passwort")
        pw_layout.addWidget(self.password_input)
        
        # Passwort sichtbar/versteckt Toggle
        from PyQt6.QtWidgets import QCheckBox
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
        sb = self.log_text.verticalScrollBar()
        if sb is not None:
            sb.setValue(sb.maximum())
    
    def update_status(self, status):
        """Status aktualisieren und UI anpassen"""
        self.status = status
        
        if status == self.STATUS_IDLE:
            self.instruction_label.setText(
                "📱 Drücke 'Setup starten' und folge dann den Anweisungen.\n\n"
                "Der Wizard hilft dir, einen USB-Stick vorzubereiten und das Gerät einzurichten."
            )
            self.start_button.setEnabled(True)
            
        elif status == self.STATUS_WAIT_SETUP_NETWORK:
            model = self.model_combo.currentText() if hasattr(self, 'model_combo') else "SoundTouch 10"
            if "20" in model or "30" in model:
                steps = (
                    "1. USB-Stick in den Lautsprecher stecken (falls noch nicht geschehen)\n"
                    "2. Netzstecker ziehen\n"
                    "3. Taste 4 UND Taste − gedrückt halten\n"
                    "4. Bei gedrückten Tasten den Netzstecker wieder einstecken\n"
                    "5. Tasten halten, bis der Setup-Modus startet (WiFi: 'Bose xxxx')\n"
                    "6. Verbinde deinen PC mit diesem WiFi – der Wizard erkennt den Wechsel"
                )
            else:  # SoundTouch 10
                steps = (
                    "1. Halte 'Volume −' + 'Preset 1' für 10 Sekunden gedrückt\n"
                    "2. Lautsprecher startet im Setup-Modus (WiFi: 'Bose xxxx')\n"
                    "3. Verbinde deinen PC mit diesem WiFi\n"
                    "4. Der Wizard erkennt den Wechsel automatisch"
                )
            self.instruction_label.setText(
                f"⚠️ WICHTIG: {model} in den Setup-Modus bringen und zu seinem WiFi wechseln!\n\n"
                + steps
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
            # Auto-Versuch, ins Heim-WLAN zurückzukehren; der Netzwerk-Monitor
            # erkennt zusätzlich einen manuellen Wechsel (Fallback).
            self.switch_wifi_button.setEnabled(True)
            QTimer.singleShot(300, self.switch_to_home_wifi)
        elif status == self.STATUS_DISCOVERING:
            self.instruction_label.setText(
                "🔍 Suche nach neuem Lautsprecher...\n\n"
                "Scanne das Netzwerk nach dem Gerät."
            )

        elif status == self.STATUS_DEPLOYING:
            self.instruction_label.setText(
                "🔧 Installiere On-Device Setup per SSH...\n\n"
                "Stelle sicher, dass der USB-Stick mit 'remote_services' eingesteckt ist."
            )
            self.progress.setVisible(True)
            self.progress.setRange(0, 0)
            
        elif status == self.STATUS_SUCCESS:
            self.instruction_label.setText(
                "✅ Gerät erfolgreich eingerichtet!\n\n"
                f"Name: {self.device_name}\n"
                f"IP: {self.device_ip}\n\n"
                "Der Lautsprecher wird gleich automatisch neu gestartet, damit alle "
                "Dienste sauber anlaufen (dauert ~1 Minute)."
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
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
    
    def start_setup(self):
        """Setup-Prozess starten"""
        # USB-Stick automatisch vorbereiten
        self.log("💾 Suche nach USB-Sticks...")
        
        # Finde USB-Sticks (plattformübergreifend: Windows-Laufwerksbuchstaben,
        # Linux /media & /run/media, macOS /Volumes)
        try:
            usb_mounts = find_removable_drives()
        except Exception as e:
            usb_mounts = []
            self.log(f"⚠️ Fehler beim Suchen: {e}")
        
        if not usb_mounts:
            QMessageBox.warning(
                self,
                "Kein USB-Stick gefunden",
                "💾 Bitte stecke einen USB-Stick in deinen PC und versuche es erneut.\n\n"
                "Der Wizard erstellt automatisch die 'remote_services' Datei.",
                QMessageBox.StandardButton.Ok
            )
            return
        
        # USB-Stick auswählen
        selected_usb = None
        if len(usb_mounts) == 1:
            selected_usb = usb_mounts[0]
        else:
            from PyQt6.QtWidgets import QInputDialog
            item, ok = QInputDialog.getItem(
                self, "USB-Stick auswählen",
                "Mehrere USB-Sticks gefunden. Welchen möchtest du verwenden?",
                usb_mounts, 0, False
            )
            if ok and item:
                selected_usb = item
            else:
                self.log("⚠️ Setup abgebrochen - kein USB-Stick ausgewählt")
                return
        
        # remote_services Datei erstellen
        try:
            flag_file = os.path.join(selected_usb, "remote_services")
            Path(flag_file).touch()
            self.log(f"✅ Datei erstellt: {flag_file}")
            
            # Erfolg-Dialog
            _m = self.model_combo.currentText() if hasattr(self, 'model_combo') else ""
            _otg = (
                "   ⚠️ SoundTouch 10: über einen micro-USB-OTG-Adapter einstecken\n"
                "      (die Box hat keinen USB-A-Port).\n"
            ) if "10" in _m else ""
            msg = QMessageBox(self)
            msg.setWindowTitle("USB-Stick bereit")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(
                "✅ USB-Stick erfolgreich vorbereitet!\n\n"
                f"Pfad: {selected_usb}\n"
                f"Datei: remote_services\n\n"
                "NÄCHSTE SCHRITTE:\n"
                "1. Entferne den USB-Stick sicher vom PC\n"
                "2. Stecke den USB-Stick in den Lautsprecher\n"
                + _otg +
                "3. Warte 10 Sekunden (SSH startet automatisch)\n"
                "4. Klicke auf 'Ja' um fortzufahren"
            )
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.No)
            
            reply = msg.exec()
            
            if reply != QMessageBox.StandardButton.Yes:
                self.log("⚠️ Setup abgebrochen")
                return
            
            self.log("🚀 Setup gestartet")
            self.log("📀 USB-Stick sollte jetzt im Gerät stecken")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Fehler",
                f"❌ Konnte 'remote_services' nicht erstellen:\n\n{e}\n\n"
                f"Versuche manuell: touch {selected_usb}/remote_services"
            )
            return
        
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
        """Aktuelle SSID ermitteln (plattformübergreifend)."""
        return platform_wifi.current_ssid() or "unknown"

    def _get_setup_device_ip(self):
        """Ermittle wahrscheinliche Setup-IP basierend auf der aktuellen Route.

        Interface-namensunabhängig (funktioniert auch unter Windows).
        """
        # 1) Bevorzugt: echtes Default-Gateway (der Setup-AP ist im Setup-Modus
        #    das Gateway des PCs).
        try:
            gw = platform_wifi.default_gateway()
            if gw:
                self.log(f"   Gateway erkannt: {gw}")
                return gw
        except Exception as e:
            self.log(f"   Hinweis: Konnte Gateway nicht direkt ermitteln: {e}")

        # 2) Fallback: aktive IP holen und letztes Oktett durch .1 ersetzen.
        try:
            _iface, ip = platform_wifi.active_ip()
            parts = ip.split('.') if ip else []
            if len(parts) == 4:
                gateway_ip = f"{parts[0]}.{parts[1]}.{parts[2]}.1"
                self.log(f"   WLAN-IP: {ip} → Gateway (heuristisch): {gateway_ip}")
                return gateway_ip
        except Exception as e:
            self.log(f"   Fehler beim Ermitteln der Gateway-IP: {e}")
        return None
    
    def find_setup_device(self):
        """Gerät im Setup-Modus finden"""
        if self.closing:
            return
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
        self.setup_device_id = device_id
        self.log(f"✅ Gerät gefunden: {name} auf {ip}")
        # Capture MAC and serial numbers from /info for robust matching later
        try:
            info = SoundTouchController(ip, timeout=3).get_info()
            if info:
                self.setup_device_mac = info.get('mac') or self.setup_device_mac
                comps = info.get('components') or []
                for c in comps:
                    sn = c.get('serialNumber')
                    if sn:
                        self.setup_device_serials.add(sn)
                if self.setup_device_mac:
                    self.log(f"   Zielgerät MAC: {self.setup_device_mac}")
                if self.setup_device_serials:
                    self.log(f"   Seriennummer(n): {', '.join(sorted(self.setup_device_serials))}")
        except Exception:
            pass
        
        # Hinweis: Keine Proxy-Konfiguration mehr erforderlich
        
        self.update_status(self.STATUS_CONNECTED_TO_DEVICE)
    
    def _on_setup_device_not_found(self):
        """Callback wenn Setup-Gerät nicht gefunden wurde"""
        self.log("❌ Gerät nicht gefunden. Bist du im Setup-WLAN?\n"
             "   Stelle sicher, dass:\n"
             "   1. Der Lautsprecher im Setup-Modus ist\n"
             "   2. Du mit seinem WiFi verbunden bist")
    
    def send_wifi_config(self):
        """WiFi-Konfiguration an Gerät senden"""
        if self.closing:
            return
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
        
        # Safety: Stelle sicher, dass eine Geräte-IP vorhanden ist
        if not self.device_ip:
            self.log("❌ Kein Gerät verbunden – bitte erst Setup-Gerät finden")
            self.update_status(self.STATUS_ERROR)
            return

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
        if self.closing:
            return
        self.log("🔍 Scanne verfügbare Netzwerke (dies kann bis zu 1 Minute dauern)...")
        self.scan_wifi_button.setEnabled(False)
        self.send_wifi_button.setEnabled(False)
        
        if not self.device_ip:
            self.log("❌ Kein Gerät verbunden – Scan nicht möglich")
            self.scan_wifi_button.setEnabled(True)
            return

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
        if self.closing:
            return
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
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if retry == QMessageBox.StandardButton.Yes:
                self.send_wifi_config()

    def switch_to_home_wifi(self):
        """Versuche, den PC zurück ins gewählte Heim-WLAN zu verbinden (plattformübergreifend)."""
        ssid = self.ssid_combo.currentText().strip()
        password = self.password_input.text()
        if not ssid:
            self.log("❌ Keine SSID ausgewählt")
            return
        self.log(f"🔁 Verbinde PC mit '{ssid}'… ({platform_wifi.backend_name()})")
        try:
            ok, msg = platform_wifi.connect(ssid, password=password or None, confirm_timeout=20)
            if ok:
                self.log("✅ PC mit Heim-WLAN verbunden")
            else:
                self.log(f"⚠️ Automatischer Wechsel nicht bestätigt: {msg}")
                self.log("   Bitte ggf. manuell ins Heim-WLAN wechseln – der Wizard erkennt den Wechsel automatisch.")
        except Exception as e:  # noqa: BLE001
            self.log(f"❌ WLAN-Wechsel fehlgeschlagen: {e}")
    
    def connect_to_setup_wifi_auto(self):
        """Attempt to automatically connect PC to the speaker's setup WiFi (Linux, NetworkManager)."""
        if self.closing:
            return
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
        if self.closing:
            return
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
    
    def _is_target_device(self, dev: dict) -> bool:
        """Check if discovered device matches the setup target.
        Prefer deviceID; fallback to MAC, then serial numbers.
        """
        if not dev:
            return False
        did = (dev.get('deviceID') or '').strip()
        if self.setup_device_id and did and did == self.setup_device_id:
            return True
        mac = (dev.get('mac') or '').strip()
        if self.setup_device_mac and mac and mac.lower() == self.setup_device_mac.lower():
            return True
        comps = dev.get('components') or []
        if self.setup_device_serials and comps:
            for c in comps:
                sn = (c.get('serialNumber') or '').strip()
                if sn and sn in self.setup_device_serials:
                    return True
        return False

    def _on_devices_found(self, devices):
        """Callback wenn Device-Discovery abgeschlossen ist"""
        self.log(f"   {len(devices)} Gerät(e) gefunden")
        
        if devices:
            # Suche gezielt nach dem zuvor konfigurierten Gerät
            target = None
            for d in devices:
                if self._is_target_device(d):
                    target = d
                    break
            if target is None:
                self.log("⚠️  Kein exaktes Match für das eingerichtete Gerät gefunden – weiter suchen...")
                # Erneut scannen nach kurzer Wartezeit
                if not self.closing:
                    QTimer.singleShot(8000, self.discover_new_device)
                return
            
            self.device_ip = target['ip']
            self.device_name = target['name']
            self.log(f"✅ Zielgerät bestätigt: {self.device_name} ({self.device_ip})")
            
            # Beende Setup-Modus - dadurch startet das Gerät Cloud-Kommunikation
            self.log("🔧 Beende Setup-Modus (triggert Cloud-Konfiguration)...")
            try:
                controller = SoundTouchController(self.device_ip, timeout=10)
                if controller.set_setup_state("SETUP_LEAVE"):
                    self.log("✅ Setup-Modus beendet")
                    self.log("⏳ Gerät führt die Konfiguration nun eigenständig fort...")
                    
                    # Warte 5 Sekunden und prüfe dann Status
                    if not self.closing:
                        QTimer.singleShot(5000, self._check_configuration_status)
                else:
                    self.log("⚠️  Setup-Modus konnte nicht beendet werden")
                    # Versuche trotzdem Status zu prüfen
                    if not self.closing:
                        QTimer.singleShot(5000, self._check_configuration_status)
            except Exception as e:
                self.log(f"⚠️  Fehler beim Beenden des Setup-Modus: {e}")
                # Versuche trotzdem Status zu prüfen
                if not self.closing:
                    QTimer.singleShot(5000, self._check_configuration_status)
        else:
            self.log("❌ Kein Gerät gefunden. Warte noch 15 Sekunden...")
            QTimer.singleShot(15000, self.discover_new_device)
    
    def _check_configuration_status(self):
        """Prüfe Erreichbarkeit nach Setup und schließe ab."""
        try:
            if self.closing:
                return
            if not self.device_ip:
                self.log("⚠️ Keine Geräte-IP vorhanden – schließe Setup ab")
                self._finalize_setup()
                return
            controller = SoundTouchController(self.device_ip, timeout=5)
            # Einfache Prüflogik: ist das Gerät erreichbar, fahren wir fort
            info = controller.get_info()
            if info:
                self.log("✅ Gerät ist erreichbar und im Heim-WLAN online")
                self.run_on_device_setup()
            else:
                self.log("⏳ Gerät noch nicht erreichbar – prüfe erneut in 5s")
                if not self.closing:
                    QTimer.singleShot(5000, self._check_configuration_status)
        except Exception as e:
            self.log(f"⚠️  Fehler beim Status-Check: {e}")
            if not self.closing:
                QTimer.singleShot(5000, self._check_configuration_status)
    
    def run_on_device_setup(self):
        """Führt das SSH-basierte On-Device-Setup aus (Autostart, NAT, Mock, Dienste)."""
        if self.closing:
            return
        if not self.device_ip:
            self.log("❌ Keine Geräte-IP für Deployment vorhanden")
            self.update_status(self.STATUS_ERROR)
            return

        # Nochmal USB-Check vor SSH-Zugriff
        reply = QMessageBox.question(
            self,
            "USB-Stick im Gerät?",
            "📌 Für das On-Device-Setup benötigen wir SSH-Zugriff.\n\n"
            "Stelle sicher, dass der USB-Stick mit 'remote_services' noch im Gerät eingesteckt ist!\n\n"
            "USB-Stick drin?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            self.log("⚠️ Deployment abgebrochen - bitte USB-Stick einstecken und erneut versuchen")
            self.update_status(self.STATUS_ERROR)
            return

        self.update_status(self.STATUS_DEPLOYING)
        self.deploy_worker = DeviceDeployWorker(self.device_ip, Path(__file__).resolve().parent)
        self.deploy_thread = QThread()
        self.deploy_worker.moveToThread(self.deploy_thread)

        self.deploy_thread.started.connect(self.deploy_worker.run)
        self.deploy_worker.progress.connect(self.log)
        self.deploy_worker.finished.connect(self._on_deploy_finished)
        self.deploy_worker.finished.connect(self.deploy_thread.quit)
        self.deploy_thread.finished.connect(self.deploy_worker.deleteLater)
        self.deploy_thread.finished.connect(self.deploy_thread.deleteLater)

        self.deploy_thread.start()

    def _on_deploy_finished(self, success: bool, error_msg: str):
        if success:
            self.log("✅ On-Device Setup abgeschlossen.")
            self._finalize_setup()
        else:
            self.log(f"❌ On-Device Setup fehlgeschlagen: {error_msg}")
            self.update_status(self.STATUS_ERROR)

    def _finalize_setup(self):
        """Setup abschließen."""
        self.update_status(self.STATUS_SUCCESS)
        
        # Frage ob Name geändert werden soll
        QTimer.singleShot(1000, self.ask_rename_device)
    
    def ask_rename_device(self):
        """Frage ob Gerät umbenannt werden soll"""
        reply = QMessageBox.question(
            self,
            "Gerät umbenennen?",
            f"Möchtest du das Gerät '{self.device_name}' umbenennen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            from PyQt6.QtWidgets import QInputDialog
            new_name, ok = QInputDialog.getText(self, "Neuer Name",
                                               "Neuer Gerätename:",
                                               text=self.device_name)
            
            if ok and new_name.strip():
                self.rename_device(new_name.strip())
        else:
            self.log("✅ Setup abgeschlossen!")
            self.log(f"Gerät '{self.device_name}' erfolgreich hinzugefügt! IP: {self.device_ip}")

        # Zum Abschluss: Gerät per SSH neu starten (bestätigt die rc.local-Persistenz)
        self._reboot_device()

    def _reboot_device(self):
        """Startet den Lautsprecher per SSH neu (fire-and-forget)."""
        if not self.device_ip:
            return
        self.log("🔄 Starte den Lautsprecher neu (per SSH)…")
        ssh_base = [
            "ssh",
            "-o", "HostKeyAlgorithms=+ssh-rsa",
            "-o", "PubkeyAcceptedAlgorithms=+ssh-rsa",
            "-o", "StrictHostKeyChecking=no",
            "-o", f"UserKnownHostsFile={os.devnull}",
            "-o", "ConnectTimeout=8",
            f"root@{self.device_ip}",
        ]
        no_window = 0x08000000 if sys.platform.startswith("win") else 0
        try:
            # Reboot im Hintergrund -> ssh kehrt sofort zurück, Box rebootet ~1s später
            subprocess.run(
                ssh_base + ["(sleep 1; reboot) >/dev/null 2>&1 &"],
                timeout=10, creationflags=no_window,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self.log("✅ Neustart ausgelöst – in ~1 Minute ist der Lautsprecher wieder da.")
        except Exception as e:
            self.log(f"⚠️ Reboot per SSH nicht möglich: {e} – bitte den Lautsprecher manuell neu starten.")

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
    
    def _shutdown_threads(self):
        """Beendet alle Hintergrund-Threads sauber. Idempotent.

        WIRD SOWOHL von closeEvent (X-Button) ALS AUCH von done() (OK/Verlassen/
        Escape) aufgerufen – reject() löst KEIN closeEvent aus, deshalb muss die
        Aufräumung auch hier hängen, sonst 'QThread destroyed while running'.
        """
        if getattr(self, '_threads_stopped', False):
            return
        self._threads_stopped = True
        self.closing = True

        if self.network_monitor:
            try:
                self.network_monitor.stop()
                self.network_monitor.wait(3000)
            except Exception:
                pass

        def _stop_thread(t):
            try:
                if t and t.isRunning():
                    t.requestInterruption()
                    t.quit()
                    t.wait(2000)
                    if t.isRunning():
                        t.terminate()
                        t.wait(1000)
            except Exception:
                pass

        _stop_thread(getattr(self, 'find_setup_thread', None))
        _stop_thread(getattr(self, 'wifi_config_thread', None))
        _stop_thread(getattr(self, 'wifi_scan_thread', None))
        _stop_thread(getattr(self, 'reconnection_thread', None))
        _stop_thread(getattr(self, 'connect_setup_thread', None))
        _stop_thread(getattr(self, 'discover_thread', None))
        # Läuft am ENDE des Setups (SSH-Deploy)
        _stop_thread(getattr(self, 'deploy_thread', None))

    def closeEvent(self, event):
        """Dialog wird über das Fenster-X geschlossen."""
        self._shutdown_threads()
        event.accept()

    def done(self, result):
        """Fängt OK/Verlassen (reject/accept)/Escape ab – dort kein closeEvent."""
        self._shutdown_threads()
        super().done(result)


# Alias für den simplen Dialog-Namen, damit simple_soundtouch_v3 das Setup findet
DeviceSetupDialog = DeviceSetupWizard


if __name__ == "__main__":
    app = QApplication(sys.argv)
    wizard = DeviceSetupWizard()
    wizard.show()
    sys.exit(app.exec())
