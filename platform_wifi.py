#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plattformübergreifende WLAN-Helfer für den Setup-Wizard.

Kapselt SSID-Erkennung, Netzwerk-Scan und das (Um-)Verbinden des PCs
auf Windows (netsh), Linux (nmcli / iwgetid) und – best effort – macOS.

Alle Funktionen sind defensiv: sie werfen keine Exceptions nach außen,
sondern liefern leere/negative Defaults, damit der aufrufende Wizard
sauber auf den geführt-manuellen Fallback umschalten kann.
"""

import sys
import time
import tempfile
import subprocess
from xml.sax.saxutils import escape

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_LINUX = not IS_WINDOWS and not IS_MACOS

# Verhindert aufblitzende Konsolenfenster unter Windows
_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0


def _run(cmd, timeout=20):
    """Führe ein Kommando aus. Gibt (returncode, stdout+stderr) zurück.

    returncode ist -1, wenn das Programm nicht gefunden wurde.
    """
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_NO_WINDOW,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return -1, ""
    except subprocess.TimeoutExpired:
        return -2, ""
    except Exception as exc:  # noqa: BLE001
        return -3, str(exc)


# ---------------------------------------------------------------------------
# Aktuelle SSID
# ---------------------------------------------------------------------------

def current_ssid():
    """Aktuell verbundene WLAN-SSID oder "" wenn nicht ermittelbar."""
    if IS_WINDOWS:
        return _win_current_ssid()
    if IS_MACOS:
        return _mac_current_ssid()
    return _linux_current_ssid()


def _win_current_ssid():
    rc, out = _run(["netsh", "wlan", "show", "interfaces"])
    if rc != 0:
        return ""
    for line in out.splitlines():
        if ":" not in line:
            continue
        label, _, value = line.partition(":")
        # "BSSID" enthält ebenfalls "SSID" -> exakt auf Label prüfen
        if label.strip().lower() == "ssid":
            return value.strip()
    return ""


def _linux_current_ssid():
    rc, out = _run(["iwgetid", "-r"])
    if rc == 0 and out.strip():
        return out.strip()
    # Fallback: NetworkManager
    rc, out = _run(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"])
    if rc == 0:
        for line in out.splitlines():
            if line.startswith("yes:"):
                return line.split(":", 1)[1].strip()
    return ""


def _mac_current_ssid():
    airport = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
    rc, out = _run([airport, "-I"])
    if rc == 0:
        for line in out.splitlines():
            if " SSID:" in line and " BSSID:" not in line:
                return line.split(":", 1)[1].strip()
    return ""


# ---------------------------------------------------------------------------
# Netzwerk-Scan (PC-seitig)
# ---------------------------------------------------------------------------

def scan_ssids(name_filter=None):
    """Liste sichtbarer SSIDs. name_filter: nur SSIDs, die diese Teilzeichenkette
    (case-insensitiv) enthalten. Ergebnis ist duplikatfrei und behält Reihenfolge.
    """
    if IS_WINDOWS:
        ssids = _win_scan_ssids()
    elif IS_MACOS:
        ssids = _mac_scan_ssids()
    else:
        ssids = _linux_scan_ssids()

    seen = []
    for s in ssids:
        if not s or s in seen:
            continue
        if name_filter and name_filter.lower() not in s.lower():
            continue
        seen.append(s)
    return seen


def request_scan():
    """Fordert einen frischen WLAN-Scan an (best effort).

    Windows liefert per netsh gecachte Scan-Ergebnisse; damit ein gerade neu
    gestarteter Setup-AP auftaucht, stößt diese Funktion über die native
    WLAN-API (WlanScan) einen echten Rescan an. Linux/nmcli scannt bei
    'dev wifi list' ohnehin frisch. Gibt True zurück, wenn ein Scan angestoßen
    wurde.
    """
    if not IS_WINDOWS:
        return True
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        class WLAN_INTERFACE_INFO(ctypes.Structure):
            _fields_ = [
                ("InterfaceGuid", GUID),
                ("strInterfaceDescription", wintypes.WCHAR * 256),
                ("isState", wintypes.DWORD),
            ]

        class WLAN_INTERFACE_INFO_LIST(ctypes.Structure):
            _fields_ = [
                ("dwNumberOfItems", wintypes.DWORD),
                ("dwIndex", wintypes.DWORD),
                ("InterfaceInfo", WLAN_INTERFACE_INFO * 1),
            ]

        wlanapi = ctypes.windll.wlanapi
        handle = wintypes.HANDLE()
        negotiated = wintypes.DWORD()
        if wlanapi.WlanOpenHandle(2, None, ctypes.byref(negotiated), ctypes.byref(handle)) != 0:
            return False
        try:
            p = ctypes.POINTER(WLAN_INTERFACE_INFO_LIST)()
            if wlanapi.WlanEnumInterfaces(handle, None, ctypes.byref(p)) != 0:
                return False
            lst = p.contents
            if lst.dwNumberOfItems < 1:
                return False
            guid = lst.InterfaceInfo[0].InterfaceGuid
            wlanapi.WlanScan(handle, ctypes.byref(guid), None, None, None)
            return True
        finally:
            wlanapi.WlanCloseHandle(handle, None)
    except Exception:
        return False


def _win_scan_ssids():
    rc, out = _run(["netsh", "wlan", "show", "networks", "mode=bssid"])
    if rc != 0:
        return []
    ssids = []
    for line in out.splitlines():
        stripped = line.strip()
        # Zeilen der Form "SSID 1 : MyNetwork"
        if stripped.lower().startswith("ssid ") and ":" in stripped:
            value = stripped.split(":", 1)[1].strip()
            ssids.append(value)
    return ssids


def _linux_scan_ssids():
    rc, out = _run(["nmcli", "-t", "-f", "SSID", "dev", "wifi", "list"], timeout=30)
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _mac_scan_ssids():
    airport = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
    rc, out = _run([airport, "-s"], timeout=30)
    if rc != 0:
        return []
    ssids = []
    for line in out.splitlines()[1:]:  # erste Zeile ist die Kopfzeile
        # SSID ist am Zeilenanfang (bis zum ersten Doppelblock)
        name = line.strip().split("  ")[0].strip()
        if name:
            ssids.append(name)
    return ssids


# ---------------------------------------------------------------------------
# Aktive IP / Gateway (interface-namensunabhängig)
# ---------------------------------------------------------------------------

def active_ip():
    """(interface, ipv4) des Interfaces mit der Default-Route.

    Namensunabhängig – funktioniert auch dort, wo WLAN-Interfaces GUIDs
    heißen (Windows). Fällt auf das erste nicht-Loopback-IPv4 zurück.
    """
    iface, ip, _gw = _default_route_info()
    if ip:
        return iface, ip
    # Fallback: erstes nicht-Loopback IPv4 irgendeines Interfaces
    try:
        import netifaces
        for name in netifaces.interfaces():
            for addr in netifaces.ifaddresses(name).get(netifaces.AF_INET, []):
                cand = addr.get("addr")
                if cand and not cand.startswith("127."):
                    return name, cand
    except Exception:
        pass
    return "", ""


def default_gateway():
    """IPv4-Default-Gateway als String oder ""."""
    _iface, _ip, gw = _default_route_info()
    return gw or ""


def _default_route_info():
    """(interface, ip, gateway) für die Default-Route."""
    try:
        import netifaces
        gws = netifaces.gateways()
        default = gws.get("default", {}).get(netifaces.AF_INET)
        if default:
            gw, iface = default[0], default[1]
            for addr in netifaces.ifaddresses(iface).get(netifaces.AF_INET, []):
                ip = addr.get("addr")
                if ip and not ip.startswith("127."):
                    return iface, ip, gw
    except Exception:
        pass
    return "", "", ""


# ---------------------------------------------------------------------------
# Verbinden
# ---------------------------------------------------------------------------

def connect(ssid, password=None, confirm_timeout=15):
    """Verbinde den PC mit einem WLAN.

    password=None/"" -> offenes Netz (typisch für den Setup-AP des Speakers).
    Gibt (success, message) zurück. success=True nur, wenn die Verbindung
    innerhalb von confirm_timeout bestätigt wurde (aktuelle SSID == ssid).
    """
    if not ssid:
        return False, "Keine SSID angegeben"

    if IS_WINDOWS:
        ok, msg = _win_connect(ssid, password)
    elif IS_MACOS:
        ok, msg = _mac_connect(ssid, password)
    else:
        ok, msg = _linux_connect(ssid, password)

    if not ok:
        return False, msg

    # Verbindungsaufbau ist asynchron -> auf Bestätigung warten
    deadline = time.time() + confirm_timeout
    while time.time() < deadline:
        if current_ssid() == ssid:
            return True, f"Verbunden mit '{ssid}'"
        time.sleep(1)
    # Kommando akzeptiert, aber (noch) nicht bestätigt
    return False, f"Verbindungsbefehl gesendet, aber '{ssid}' nicht bestätigt (Timeout)"


def _linux_connect(ssid, password):
    if password:
        cmd = ["nmcli", "dev", "wifi", "connect", ssid, "password", password]
    else:
        cmd = ["nmcli", "dev", "wifi", "connect", ssid]
    rc, out = _run(cmd, timeout=40)
    if rc == -1:
        return False, "'nmcli' nicht gefunden – bitte manuell wechseln."
    if rc != 0:
        return False, f"nmcli-Verbindung fehlgeschlagen: {out.strip()[:200]}"
    return True, "ok"


def _mac_connect(ssid, password):
    cmd = ["networksetup", "-setairportnetwork", "en0", ssid]
    if password:
        cmd.append(password)
    rc, out = _run(cmd, timeout=40)
    if rc == -1:
        return False, "'networksetup' nicht gefunden – bitte manuell wechseln."
    if rc != 0:
        return False, f"Verbindung fehlgeschlagen: {out.strip()[:200]}"
    return True, "ok"


def _win_profile_xml(ssid, password):
    ssid_x = escape(ssid)
    if password:
        security = (
            "<authEncryption>"
            "<authentication>WPA2PSK</authentication>"
            "<encryption>AES</encryption>"
            "<useOneX>false</useOneX>"
            "</authEncryption>"
            "<sharedKey>"
            "<keyType>passPhrase</keyType>"
            "<protected>false</protected>"
            f"<keyMaterial>{escape(password)}</keyMaterial>"
            "</sharedKey>"
        )
    else:
        security = (
            "<authEncryption>"
            "<authentication>open</authentication>"
            "<encryption>none</encryption>"
            "<useOneX>false</useOneX>"
            "</authEncryption>"
        )
    return (
        '<?xml version="1.0"?>\n'
        '<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">\n'
        f"  <name>{ssid_x}</name>\n"
        f"  <SSIDConfig><SSID><name>{ssid_x}</name></SSID></SSIDConfig>\n"
        "  <connectionType>ESS</connectionType>\n"
        "  <connectionMode>manual</connectionMode>\n"
        f"  <MSM><security>{security}</security></MSM>\n"
        "</WLANProfile>\n"
    )


def _win_connect(ssid, password):
    # 1) Temporäres Profil anlegen (nötig für neue/offene Netze).
    #    Für bereits bekannte Heimnetze überschreibt das nichts Kritisches.
    path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(_win_profile_xml(ssid, password))
            path = fh.name
        rc, out = _run(["netsh", "wlan", "add", "profile", f"filename={path}", "user=current"])
        if rc == -1:
            return False, "'netsh' nicht gefunden – bitte manuell wechseln."
        # rc != 0 ist nicht zwingend fatal (Profil kann schon existieren) -> weiter
    finally:
        if path:
            try:
                import os
                os.unlink(path)
            except Exception:
                pass

    rc, out = _run(["netsh", "wlan", "connect", f'name={ssid}', f'ssid={ssid}'])
    if rc == -1:
        return False, "'netsh' nicht gefunden – bitte manuell wechseln."
    if rc != 0:
        return False, f"netsh-Verbindung fehlgeschlagen: {out.strip()[:200]}"
    return True, "ok"


def backend_name():
    """Name des aktiven WLAN-Backends (für Logs)."""
    if IS_WINDOWS:
        return "Windows/netsh"
    if IS_MACOS:
        return "macOS/networksetup"
    return "Linux/nmcli"
