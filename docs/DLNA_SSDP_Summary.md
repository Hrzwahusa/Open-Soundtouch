# DLNA/SSDP Setup Summary (Controller 192.168.50.203, Client 192.168.50.184)

Scope
- Observed SSDP and DLNA HTTP interactions during manual setup with MiniDLNA at 192.168.50.218:8200.
- Source: wireshark capture [Open-Soundtouch/wireshark_log.pcapng](../wireshark_log.pcapng) covering 17:54:42–17:57:33.

Controller 192.168.50.203 (Setup Device)
- Discovery: Sends `M-SEARCH ssdp:discover` for `MediaRenderer:1` and `MediaServer:1`.
- Responses: Receives unicast `HTTP/1.1 200 OK` from 192.168.50.218:1900 with `LOCATION: http://192.168.50.218:8200/rootDesc.xml`.
- HTTP to MiniDLNA: No direct TCP/HTTP traffic to 192.168.50.218:8200 observed in this capture.

Client 192.168.50.184 (Bose Renderer)
- Advertisements: Sends `ssdp:alive` and `ssdp:byebye` for `upnp:rootdevice`, `MediaRenderer:1`, `AVTransport:1`, `RenderingControl:1`, `ConnectionManager:1`, and `QPlay:2` with device XML at `http://192.168.50.184:8091/XD/...xml`.
- Device Description: `GET /rootDesc.xml` to 192.168.50.218:8200 → `HTTP/1.1 200 OK` including `ContentDirectory`, `ConnectionManager`, `X_MS_MediaReceiverRegistrar`.
- ContentDirectory Browse (SOAP):
  - `POST /ctl/ContentDir` `SOAPACTION: ...#Browse` `ObjectID=0` `BrowseMetadata` → returns root container.
  - `POST /ctl/ContentDir` `ObjectID=0` `BrowseDirectChildren` → returns `Musik`, `Bilder`, `Ordner durchsuchen`, `Video`.
  - `POST /ctl/ContentDir` `ObjectID=64` `BrowseMetadata` and `BrowseDirectChildren` → returns items and folders under “Ordner durchsuchen”.

Server 192.168.50.218 (MiniDLNA)
- SSDP: Replies to controller and client M-SEARCH with `200 OK`, advertises `MediaServer:1`.
- HTTP: Serves `/rootDesc.xml` and SOAP Browse responses consistent with DLNA DMS behavior.

Timeline Highlights (hh:mm:ss)
- 17:55:01: 184 M-SEARCH for `MediaServer:1`; 218 responds with LOCATION `/rootDesc.xml`.
- 17:55:53/56/53: 184 TCP to 218:8200; GET `/rootDesc.xml`; 200 OK with services.
- 17:57:01–17:57:04: 184 SOAP `Browse` sequences on `ObjectID=0` and `64`; multiple 200 OK responses.
- 17:55:12–17:55:44: 203 sends repeated M-SEARCH for `MediaRenderer:1` and `MediaServer:1`; receives replies from 218.

Notes for Programmatic Replication
- Discovery: Ensure SSDP M-SEARCH to discover DMS; use LOCATION to fetch `/rootDesc.xml`.
- Renderer Role: The Bose renderer (184) performs ContentDirectory browsing and playback; controller (203) discovers and orchestrates.
- Eventing: SUBSCRIBE/eventing is typical, but not explicitly observed for 203/184 in this pcap segment.
- Registration: No device registration calls were initiated here; behavior aligns with pure DLNA discovery and browsing.

Next Capture Recommendations
- Keep separate captures for `udp port 1900` (SSDP) and `tcp port 8200` (MiniDLNA HTTP) to correlate controller and renderer flows.
- Optional: include `tcp port 8091` to observe renderer service advertisements and potential control traffic.

Detailed Timeline (selected events)

| Time (UTC)        | Src → Dst                        | Proto | Summary |
|-------------------|----------------------------------|-------|---------|
| 17:55:01.047146   | 184 → 239.255.255.250:1900       | SSDP  | M-SEARCH `MediaRenderer:1` |
| 17:55:01.146905   | 184 → 239.255.255.250:1900       | SSDP  | M-SEARCH `MediaServer:1` |
| 17:55:01.349838   | 218:1900 → 184:44620             | SSDP  | 200 OK; LOCATION `http://192.168.50.218:8200/rootDesc.xml` |
| 17:55:12.515409   | 203 → 239.255.255.250:1900       | SSDP  | M-SEARCH `InternetGatewayDevice:1` |
| 17:55:13.333346   | 203 → 239.255.255.250:1900       | SSDP  | M-SEARCH `MediaRenderer:1` |
| 17:55:13.333677   | 203 → 239.255.255.250:1900       | SSDP  | M-SEARCH `MediaServer:1` |
| 17:55:13.350698   | 218:1900 → 203:1900              | SSDP  | 200 OK; LOCATION `/rootDesc.xml` |
| 17:55:53.409182   | 184 → 218:8200                   | HTTP  | GET `/rootDesc.xml` |
| 17:55:53.409312   | 218 → 184                        | HTTP  | 200 OK; device + services XML |
| 17:55:56.094153   | 184 → 218:8200                   | HTTP  | GET `/rootDesc.xml` |
| 17:55:56.094263   | 218 → 184                        | HTTP  | 200 OK; device + services XML |
| 17:56:53.493801   | 184 → 218:8200                   | HTTP  | GET `/rootDesc.xml` |
| 17:56:53.493873   | 218 → 184                        | HTTP  | 200 OK; device + services XML |
| 17:57:01.284735   | 184 → 218:8200                   | SOAP  | POST `/ctl/ContentDir` Browse `ObjectID=0` `BrowseMetadata` |
| 17:57:01.289149   | 218 → 184                        | SOAP  | 200 OK; root container metadata |
| 17:57:01.345500   | 184 → 218:8200                   | SOAP  | POST `/ctl/ContentDir` Browse `ObjectID=0` `BrowseDirectChildren` |
| 17:57:01.349754   | 218 → 184                        | SOAP  | 200 OK; lists `Musik`, `Bilder`, `Ordner durchsuchen`, `Video` |
| 17:57:03.968976   | 184 → 218:8200                   | SOAP  | POST `/ctl/ContentDir` Browse `ObjectID=64` `BrowseMetadata` |
| 17:57:03.972475   | 218 → 184                        | SOAP  | 200 OK; `Ordner durchsuchen` metadata |
| 17:57:04.030489   | 184 → 218:8200                   | SOAP  | POST `/ctl/ContentDir` Browse `ObjectID=64` `BrowseDirectChildren` |

Extended Earlier Events and Interpretation
- 17:55:00.85–17:55:04.38: 184 floods `ssdp:alive` announcements; 203 starts `M-SEARCH` cycles; 218 replies with LOCATION pointing to MiniDLNA.
- 17:55:53.409 / 17:55:56.094: 184 issues `GET /rootDesc.xml` twice; 218 returns device XML advertising `ContentDirectory`, `ConnectionManager`, `X_MS_MediaReceiverRegistrar`.
- 17:56:53.494: 184 repeats `GET /rootDesc.xml` (likely reconciling server details before browsing).
- 17:57:01.285: 184 sends SOAP `POST /ctl/ContentDir` with `Browse(ObjectID=0, BrowseMetadata)`; response contains the root container.
- 17:57:01.349: 184 follows with `Browse(ObjectID=0, BrowseDirectChildren)`; response lists top-level containers (Musik, Bilder, Ordner durchsuchen, Video).
- 17:57:03.969: 184 browses `ObjectID=64` (Ordner durchsuchen) metadata and children; responses contain folder entries.

What This Shows
- The app (203) discovers the DMS, then the renderer (184) actively connects and browses the server via `ContentDirectory`.
- No controller↔renderer `tcp/8091` traffic appears in this pcap, but renderer-side DLNA actions are explicit (GET `rootDesc.xml`, SOAP `Browse`).

Replication Plan (Programmatic) — **✓ TESTED AND WORKING**
See `test_dlna_e2e_playback.py` for complete working implementation.

**Steps:**
1. **Discovery**: Send SSDP `M-SEARCH` for `urn:schemas-upnp-org:device:MediaServer:1`; use `LOCATION` to fetch `/rootDesc.xml`.
2. **Browse**: Use `POST /ctl/ContentDir` with `SOAPACTION: ...ContentDirectory:1#Browse` to retrieve target `res` URLs. Key insight: MiniDLNA uses nested container IDs like `1$4` (Musik → Alle Titel).
3. **Parse DIDL-Lite**: SOAP responses have HTML-escaped DIDL-Lite; use `html.unescape()`. Use wildcard namespace matching (`.//{*}item`, `.//{*}res`) for robustness.
4. **Set URI and Play**: Call Bose AVTransport at `http://{renderer_ip}:8091/AVTransport/Control`:
   - `SetAVTransportURI` with `CurrentURI=<http://minidlna:8200/MediaItems/22.mp3>` and minimal `CurrentURIMetaData` (DIDL-Lite `item` + `res` + valid `protocolInfo` like `http-get:*:audio/mpeg:DLNA.ORG_PN=MP3;...`).
   - `Play` with `InstanceID=0`, `Speed=1`.
5. **Verify**: Query Bose `/now_playing` REST endpoint (port 8090); confirm `source="UPNP"` and `playStatus="PLAY_STATE"`.

**Critical Details:**
- MiniDLNA config must write to `/home/hans/` (no `/run/`, `/tmp` as root restricted).
- Use DLNA SOAP on 8091; avoid REST `/select` for streaming.
- Device responds HTTP 200 to both SOAP actions (SetAVTransportURI, Play).

