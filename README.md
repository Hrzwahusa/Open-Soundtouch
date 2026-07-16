# 🔊 Open SoundTouch

[![Latest release](https://img.shields.io/github/v/release/Hrzwahusa/Open-Soundtouch?label=download&color=F5A623)](https://github.com/Hrzwahusa/Open-Soundtouch/releases/latest)

**An open replacement for the discontinued Bose SoundTouch app – keeps SoundTouch speakers (10 / 20 / 30) alive without the Bose cloud.**

You can join the closed Beta Test for android at https://hrzwahusa.github.io/Open-Soundtouch/index.html

📥 **Windows (desktop):** download the latest portable build from the [**Releases**](https://github.com/Hrzwahusa/Open-Soundtouch/releases/latest) page — unzip and run `Open SoundTouch.exe` (keep its `_internal` folder next to it).

Bose shut down the cloud and the app for the SoundTouch line. This project brings the speakers back – locally, cloud-free – via the device's own SoundTouch Web API plus a small helper system installed permanently on the speaker.

---

## ✨ Features

- **Device control** – play/pause/stop/skip, power (standby), volume.
- **Internet radio over DLNA** – since `LOCAL_INTERNET_RADIO`/TuneIn is dead without the cloud, streams are played directly to the speaker's DLNA/UPnP renderer. Includes **TuneIn search** and **custom stream URLs**.
- **Favorites** – your own, unlimited radio favorites list (independent of presets), stored locally.
- **Presets** – the **physical preset buttons** on the device **and** the in-app presets trigger DLNA radio playback (via an on-device interceptor). Presets can be assigned from the app.
- **Multi-room groups** – create/edit/activate groups of speakers, with **group volume** (all together) **and per-speaker control**.
- **System audio streaming** – stream any PC audio (browser, Spotify, games …) to the speaker via WASAPI loopback – no "Stereo Mix", no extra install.
- **Rename devices** – directly from the app.
- **Setup wizard** – cross-platform wizard that gets a fresh/factory-reset device onto your WiFi and installs the on-device system (ST10 and ST20/30).
- **One well-crafted dark design** ("Midnight").

---

## 🚀 Installation & run

Requires **Python 3.10+**.

```bash
pip install -r requirements.txt
python simple_soundtouch.py
```

`requirements.txt` bundles everything needed – including **ffmpeg** (via `imageio-ffmpeg`) and, on Windows, **`PyAudioWPatch`** for WASAPI loopback. So **no separate ffmpeg install** is required.

**Linux (only for system audio capture):** additionally an audio server (`pulseaudio-utils` or `pipewire`).

---

## 🧭 How it works

A SoundTouch connected to your WiFi answers the local **SoundTouch Web API (port 8090)**. That makes control, discovery and grouping work out of the box. Two things need more, because the cloud is gone:

1. **Internet radio.** The native source `LOCAL_INTERNET_RADIO` is unavailable (`/sources` doesn't list it). So the app plays radio through the speaker's **DLNA/UPnP renderer** (port 8091) by setting the direct stream URL. Reliable and cloud-free.

2. **Preset buttons & autonomy.** To make the **physical buttons** start radio and survive reboots, a small system is installed on the speaker (see below). This requires enabling **SSH** once – handled by the setup wizard via a USB stick.

### What gets installed on the speaker

Over SSH, scripts are copied to `/mnt/nv/` (persistent storage) and an autostart hook (`rc.local`, run by `/etc/init.d/shelby_local`) is set up:

- **`/tmp/remote_services` flag + sshd/telnetd** – makes SSH **permanent** (works after reboot even without the USB stick).
- **NAT redirect 8090 → 8089** + **key interceptor** (`key_interceptor_cgi.sh` via `nc`): intercepts `/key` preset presses and starts radio playback; forwards all other API calls transparently to the real API (127.0.0.1:8090).
- **Rhino monitor** (`rhino_preset_monitor.sh`): detects **physical** preset presses via the system log and calls the handler.
- **Preset handler** (`preset_handler_daemon.sh`): plays the stream configured in `preset_proxies.conf` directly over DLNA.

---

## 🛠️ Setup wizard (onboard a fresh/factory-reset device)

The wizard (Settings → "📱 Setup New Device") walks you through:

1. **Pick the model** (SoundTouch 10 or 20/30) – determines the button combo.
2. **Prepare a USB stick** – the wizard writes a `remote_services` file to a (FAT32) stick. This enables SSH/Telnet on the speaker.
3. **Enter setup mode on the speaker:**
   - **SoundTouch 10:** hold `Volume −` + `Preset 1` for ~10 s.
   - **SoundTouch 20/30:** insert USB stick → **unplug power** → hold **button 4 + button −** → replug power while holding → keep holding until setup mode starts.
4. **Send WiFi** – the wizard connects your PC to the speaker's setup WiFi (automatic, with a guided-manual fallback), sends your WiFi credentials, and the speaker joins your home network.
5. **Deploy the on-device system** – scripts are installed and started over SSH.
6. **Automatic reboot** – the wizard reboots the speaker itself over SSH at the end (confirms persistence).

Afterwards SSH is permanently enabled and the preset/radio system runs autonomously – the USB stick is no longer needed.

---

## 📁 Project structure

```
simple_soundtouch.py      # Main app (PyQt6 GUI)
soundtouch_lib.py         # SoundTouch Web API, discovery, zones/groups
app_theme.py              # The single design ("Midnight")
device_ssh.py             # SSH helper (manage preset config on the device)
platform_wifi.py          # Cross-platform WiFi helpers (setup)
gui_device_setup.py       # Setup wizard (WiFi + on-device deploy)
system_audio_capture.py   # PC audio → speaker (WASAPI loopback / PCM)
tunein_helper.py          # TuneIn search / stream URL resolution
dlna_helper.py            # DLNA/UPnP SOAP (radio playback)
nowplaying_status.py      # now-playing parser

# On-device scripts (deployed by the wizard to /mnt/nv/):
key_interceptor_cgi.sh    preset_handler_daemon.sh   rhino_preset_monitor.sh
key_interceptor_daemon.sh preset_proxy_manager.sh    preset_system_init.sh
radio_proxy.sh            preset_proxies.conf

requirements.txt   README.md
ignore/            # parked legacy/unused files (not in the repo)
docs/              # SoundTouch Web API docs & notes
android/           # Native Android app (Kotlin/Compose) — see android/README.md
```

Runtime data (not in the repo): `soundtouch_devices.json`, `group_config.json`, `radio_favorites.json`.

## 📱 Android app

A native Android companion app (Kotlin + Jetpack Compose) lives in [`android/`](android/).
It has feature parity with the desktop app except for the initial device setup
(use the desktop wizard once): control, TuneIn search + favorites, multi-room
groups with group/per-speaker volume, physical preset buttons (via SSH), phone
audio streaming to the speaker, and system-wide volume-key control while
streaming. Open the `android/` folder in Android Studio to build. Details and
architecture: [`android/README.md`](android/README.md).

---

## 🔧 Troubleshooting

- **"System audio capture not available" (Windows):** `pip install PyAudioWPatch` (included in requirements) and restart the app.
- **No devices found:** speaker on the same WiFi? Port 8090 not blocked by a firewall? Hit "🔄 Refresh" in the app.
- **Radio won't start / no sound:** it must be a **direct** http stream (not https – the DLNA renderer currently only plays http). TuneIn results are resolved to their stream URL automatically.
- **No SSH/presets after a speaker reboot:** once set up via the wizard, `rc.local` starts everything automatically. A quick reboot of the device confirms it.
- **Device unreachable in standby:** briefly wake it (e.g. press a button), then the API responds again.


---

## ⚖️ Disclaimer

This project is unofficial and not affiliated with Bose. It modifies your own purchased device to keep it usable after end of support. Use at your own risk.
