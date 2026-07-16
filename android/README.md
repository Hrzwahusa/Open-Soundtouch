# Open SoundTouch – Android

Native Android app (Kotlin + Jetpack Compose) for controlling Bose SoundTouch speakers without the Bose cloud. Companion to the desktop app; aims for **feature parity** with it.

> 🚧 **Phase 1 – foundation.** This builds and gives you: device discovery, control (transport, power, volume) and playing a radio stream URL via DLNA. The remaining features arrive in phases (see below). Not yet on the Play Store; build it yourself in Android Studio.

## Build

1. Open the `android/` folder of this repo in **Android Studio** (Giraffe/Koala or newer).
2. Let it sync Gradle (it will download the Gradle wrapper / dependencies).
3. Run on a device or emulator **on the same WiFi** as your speakers.

Requirements: Android 8.0 (API 26)+. Kotlin 2.0, AGP 8.5, Compose BOM 2024.09.

> **Emulator note:** the Android emulator sits behind a NAT (its WiFi is `10.0.2.x`), so the subnet scan can't discover speakers on your real LAN. Use the **"IP direkt"** field on the start screen to connect straight to a speaker's IP (e.g. `192.168.0.178`) — the emulator routes that connection through the host. A **real device on the same WiFi** discovers speakers normally.

> The Gradle wrapper JAR is not committed. Android Studio generates it on first sync; or run `gradle wrapper` once if you have a local Gradle.

## Architecture

The networking layer mirrors the proven Python logic from the desktop app:

- `data/SoundTouchClient.kt` – SoundTouch Web API (port 8090): discovery `/info`, `/key`, `/volume` (set = `<volume>N</volume>`), `/now_playing`, `/sources`, zones (`setZone` puts the master first), `/name`.
- `data/DlnaClient.kt` – DLNA/UPnP AVTransport (port 8091): `SetAVTransportURI` + `Play` – how internet radio is played (native `LOCAL_INTERNET_RADIO` is dead without the cloud).
- `data/Discovery.kt` – concurrent /24 scan for speakers.
- `MainViewModel.kt` – UI state; `ui/` + `MainActivity.kt` – Compose UI (Midnight dark theme).

## Roadmap (feature parity with desktop)

- [x] **Phase 1** – project scaffold, networking core, discovery, control, DLNA radio URL, dark theme.
- [x] **Phase 2** – TuneIn search, favorites (local storage, `FavoritesStore`), play via DLNA. Presets that survive a reboot need the SSH path (they can't be stored through the dead cloud source), so preset assignment moves to Phase 4.
- [x] **Phase 3** – multi-room groups: create/activate/dissolve (`setZone` with master first, persisted in `GroupStore`), group volume (relative, keeps the balance) and per-speaker volume.
- [x] **Phase 4** – SSH (maintained JSch fork) for on-device preset config: `SshClient` reads/writes `/mnt/nv/preset_proxies.conf` (`N|URL|NAME`) over Dropbear (root, ssh-rsa, cat-over-SSH), so favorites can be bound to the physical buttons. Only works against a real, SSH-enabled speaker.
- [x] **Phase 5** – system audio capture: `AudioCaptureService` (foreground, `mediaProjection`) captures the phone's playback via MediaProjection + AudioPlaybackCapture (API 29+), serves it as a streaming WAV over an embedded HTTP server, and the speaker plays it via DLNA. Needs a real device; DRM-protected apps may block capture.

## Notes

- Speakers use plaintext HTTP on the LAN, so `usesCleartextTraffic` is enabled.
- Some desktop features are harder on Android and land last: system audio capture (native MediaProjection), and any WiFi-provisioning / USB-based setup (restricted on Android). The initial assumption is that a speaker was already onboarded/SSH-enabled via the desktop wizard.