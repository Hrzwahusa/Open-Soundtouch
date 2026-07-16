#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plattformübergreifender SSH-Helfer für die Bose-Box.

Kapselt das Ausführen von Kommandos und das Schreiben von Dateien per SSH
(cat-über-SSH statt scp, da die Box Dropbear/kein sftp-server nutzt) sowie
die Verwaltung der On-Device Preset-Konfiguration /mnt/nv/preset_proxies.conf.

Format der Config (vom On-Device-Handler gelesen):  N|URL|NAME   (N = 1..6)
"""

import os
import sys
import socket
import subprocess

CONF_PATH = "/mnt/nv/preset_proxies.conf"

_SSH_OPTS = [
    "-o", "HostKeyAlgorithms=+ssh-rsa",
    "-o", "PubkeyAcceptedAlgorithms=+ssh-rsa",
    "-o", "StrictHostKeyChecking=no",
    "-o", f"UserKnownHostsFile={os.devnull}",
    "-o", "ConnectTimeout=8",
]

_NO_WINDOW = 0x08000000 if sys.platform.startswith("win") else 0


def _ssh_base(ip, user="root"):
    return ["ssh"] + _SSH_OPTS + [f"{user}@{ip}"]


def is_reachable(ip, port=22, timeout=3):
    """Schneller TCP-Check, ob SSH auf dem Gerät erreichbar ist."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def run(ip, command, timeout=15):
    """Führt ein Kommando per SSH aus. Gibt (returncode, stdout+stderr) zurück."""
    cmd = _ssh_base(ip) + [command]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=_NO_WINDOW,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return -1, str(exc)


def read_file(ip, path):
    """Liest eine Datei vom Gerät. Gibt Inhalt (str) oder None zurück."""
    rc, out = run(ip, f"cat '{path}' 2>/dev/null")
    return out if rc == 0 else None


def write_file(ip, path, content):
    """Schreibt Inhalt per cat-über-SSH auf das Gerät (kein scp).

    Zeilenenden werden auf LF normalisiert. Gibt True bei Erfolg zurück.
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    content = content.replace(b"\r\n", b"\n")
    cmd = _ssh_base(ip) + [f"cat > '{path}'"]
    try:
        proc = subprocess.run(
            cmd, input=content, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=15, creationflags=_NO_WINDOW,
        )
        return proc.returncode == 0
    except Exception:  # noqa: BLE001
        return False


# --- Preset-Konfiguration -------------------------------------------------

def read_presets(ip):
    """Liest die On-Device Preset-Config. Gibt {N: {'url','name'}} zurück."""
    txt = read_file(ip, CONF_PATH) or ""
    presets = {}
    for line in txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) >= 2:
            try:
                n = int(parts[0])
            except ValueError:
                continue
            presets[n] = {
                "url": parts[1],
                "name": parts[2] if len(parts) > 2 else f"Preset {n}",
            }
    return presets


def _write_presets(ip, presets):
    lines = [
        "# Preset-Konfiguration (von der App verwaltet)",
        "# Format: N|URL|NAME   (N = Preset 1..6)",
        "",
    ]
    for n in sorted(presets):
        p = presets[n]
        url = (p.get("url") or "").replace("|", "%7C").replace("\n", "").strip()
        name = (p.get("name") or "").replace("|", " ").replace("\n", " ").strip()
        if url:
            lines.append(f"{n}|{url}|{name}")
    return write_file(ip, CONF_PATH, "\n".join(lines) + "\n")


def set_preset(ip, n, url, name):
    """Legt/aktualisiert Preset N (Read-Modify-Write der Config auf dem Gerät)."""
    if not url:
        return False
    presets = read_presets(ip)
    presets[int(n)] = {"url": url, "name": name or f"Preset {n}"}
    return _write_presets(ip, presets)


def clear_preset(ip, n):
    """Entfernt Preset N aus der Config."""
    presets = read_presets(ip)
    presets.pop(int(n), None)
    return _write_presets(ip, presets)


if __name__ == "__main__":
    # Kleiner Selbsttest: python device_ssh.py <ip>
    ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.0.178"
    print("erreichbar:", is_reachable(ip))
    print("presets:", read_presets(ip))
