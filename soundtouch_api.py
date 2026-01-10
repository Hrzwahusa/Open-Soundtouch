#!/usr/bin/env python3
"""
SoundTouch REST API Server
FastAPI-based REST API for SoundTouch device discovery and control.
Perfect for integration with Android apps, web frontends, or other clients.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
from soundtouch_lib import SoundTouchDiscovery, SoundTouchController
from soundtouch_media import media_manager, SMBMediaServer, LocalMediaServer
import mimetypes

# Initialize FastAPI app
app = FastAPI(
    title="SoundTouch API",
    description="REST API for Bose SoundTouch device discovery and control",
    version="1.0.0"
)


# ============================================================================
# Pydantic Models for Request/Response
# ============================================================================

class DeviceInfo(BaseModel):
    """Device information model."""
    name: str
    type: str
    ip: str
    mac: str
    deviceID: str
    margeAccount: Optional[str] = None
    components: List[dict] = []
    url: str


class KeyCommand(BaseModel):
    """Key command model."""
    key: str
    sender: str = "Gabbo"


class NowPlayingInfo(BaseModel):
    """Now playing info model."""
    source: str
    sourceAccount: Optional[str] = None
    artist: str
    track: str
    album: str


class SetupStateRequest(BaseModel):
    """Setup state change request."""
    state: str
    timeout_ms: Optional[int] = None


class WirelessProfileRequest(BaseModel):
    """WiFi profile configuration."""
    ssid: str
    password: str
    security_type: str = "wpa_or_wpa2"
    timeout: int = 30


class MediaServerConfig(BaseModel):
    """Media server configuration."""
    name: str
    type: str  # "smb" or "local"
    host: Optional[str] = None
    share: Optional[str] = None
    path: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class PlayMediaRequest(BaseModel):
    """Play media file on speaker."""
    server: str
    file_path: str
    device_ip: str


# ============================================================================
# Discovery Endpoints
# ============================================================================

@app.get("/api/discover", response_model=List[DeviceInfo])
async def discover_devices(network: Optional[str] = None, port: int = 8090, threads: int = 50):
    """
    Discover SoundTouch devices on the network.
    
    Args:
        network: Network CIDR (e.g., "192.168.1.0/24"). Auto-detects if not specified.
        port: Port to scan (default: 8090)
        threads: Number of concurrent threads (default: 50)
    
    Returns:
        List of discovered devices
    """
    scanner = SoundTouchDiscovery(network=network, port=port)
    devices = scanner.scan(max_threads=threads)
    return devices


@app.get("/api/devices", response_model=List[DeviceInfo])
async def get_cached_devices():
    """
    Get previously discovered devices from cache.
    (In a production app, this would query a database)
    """
    # For now, just return empty list - would be stored in DB in production
    return []


# ============================================================================
# Control Endpoints
# ============================================================================

@app.post("/api/control/{device_ip}/key")
async def send_key(device_ip: str, command: KeyCommand, port: int = 8090):
    """
    Send a key press to a device.
    
    Args:
        device_ip: IP address of the device
        command: Key command with key name and optional sender
        port: Port (default: 8090)
    
    Returns:
        Success status
    """
    controller = SoundTouchController(device_ip, port=port)
    success = controller.send_key(command.key, sender=command.sender)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to send key '{command.key}' to {device_ip}"
        )
    
    return {
        "status": "success",
        "device_ip": device_ip,
        "key": command.key
    }


@app.get("/api/control/{device_ip}/nowplaying", response_model=Optional[NowPlayingInfo])
async def get_nowplaying(device_ip: str, port: int = 8090):
    """
    Get currently playing info from a device.
    
    Args:
        device_ip: IP address of the device
        port: Port (default: 8090)
    
    Returns:
        Now playing information
    """
    controller = SoundTouchController(device_ip, port=port)
    info = controller.get_nowplaying()
    
    if info is None:
        raise HTTPException(
            status_code=503,
            detail=f"Could not retrieve now playing info from {device_ip}"
        )
    
    return info


# ============================================================================
# Volume Endpoints
# ============================================================================

@app.get("/api/control/{device_ip}/volume")
async def get_volume(device_ip: str, port: int = 8090):
    """Get volume info from a device."""
    controller = SoundTouchController(device_ip, port=port)
    volume = controller.get_volume()
    
    if volume is None:
        raise HTTPException(status_code=503, detail=f"Could not get volume from {device_ip}")
    
    return volume


@app.post("/api/control/{device_ip}/volume")
async def set_volume(device_ip: str, volume: int, mute: bool = False, port: int = 8090):
    """Set volume on a device."""
    if not 0 <= volume <= 100:
        raise HTTPException(status_code=400, detail="Volume must be 0-100")
    
    controller = SoundTouchController(device_ip, port=port)
    success = controller.set_volume(volume, mute)
    
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to set volume")
    
    return {"status": "success", "device_ip": device_ip, "volume": volume, "mute": mute}


# ============================================================================
# Bass Endpoints
# ============================================================================

@app.get("/api/control/{device_ip}/bass-capabilities")
async def get_bass_capabilities(device_ip: str, port: int = 8090):
    """Get bass capabilities of a device."""
    controller = SoundTouchController(device_ip, port=port)
    capabilities = controller.get_bass_capabilities()
    
    if capabilities is None:
        raise HTTPException(status_code=503, detail=f"Could not get bass capabilities from {device_ip}")
    
    return capabilities


@app.get("/api/control/{device_ip}/bass")
async def get_bass(device_ip: str, port: int = 8090):
    """Get current bass setting."""
    controller = SoundTouchController(device_ip, port=port)
    bass = controller.get_bass()
    
    if bass is None:
        raise HTTPException(status_code=503, detail=f"Could not get bass from {device_ip}")
    
    return bass


@app.post("/api/control/{device_ip}/bass")
async def set_bass(device_ip: str, bass: int, port: int = 8090):
    """Set bass level on a device."""
    controller = SoundTouchController(device_ip, port=port)
    success = controller.set_bass(bass)
    
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to set bass")
    
    return {"status": "success", "device_ip": device_ip, "bass": bass}


# ============================================================================
# Source Endpoints
# ============================================================================

@app.get("/api/control/{device_ip}/sources")
async def get_sources(device_ip: str, port: int = 8090):
    """Get available sources for a device."""
    controller = SoundTouchController(device_ip, port=port)
    sources = controller.get_sources()
    
    if sources is None:
        raise HTTPException(status_code=503, detail=f"Could not get sources from {device_ip}")
    
    return {"sources": sources}


@app.post("/api/control/{device_ip}/source")
async def select_source(device_ip: str, source: str, source_account: str = "", port: int = 8090):
    """Select a source/input on a device."""
    controller = SoundTouchController(device_ip, port=port)
    success = controller.select_source(source, source_account)
    
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to select source")
    
    return {"status": "success", "device_ip": device_ip, "source": source, "sourceAccount": source_account}


# ============================================================================
# Presets Endpoints
# ============================================================================

@app.get("/api/control/{device_ip}/presets")
async def get_presets(device_ip: str, port: int = 8090):
    """Get presets from a device."""
    controller = SoundTouchController(device_ip, port=port)
    presets = controller.get_presets()
    
    if presets is None:
        raise HTTPException(status_code=503, detail=f"Could not get presets from {device_ip}")
    
    return {"presets": presets}


# ============================================================================
# Capabilities Endpoints
# ============================================================================

@app.get("/api/control/{device_ip}/capabilities")
async def get_capabilities(device_ip: str, port: int = 8090):
    """Get device capabilities."""
    controller = SoundTouchController(device_ip, port=port)
    capabilities = controller.get_capabilities()
    
    if capabilities is None:
        raise HTTPException(status_code=503, detail=f"Could not get capabilities from {device_ip}")
    
    return {"capabilities": capabilities}


# ============================================================================
# Audio DSP Controls Endpoints
# ============================================================================

@app.get("/api/control/{device_ip}/audio-dsp")
async def get_audio_dsp_controls(device_ip: str, port: int = 8090):
    """Get audio DSP settings."""
    controller = SoundTouchController(device_ip, port=port)
    controls = controller.get_audio_dsp_controls()
    
    if controls is None:
        raise HTTPException(status_code=503, detail=f"Could not get audio DSP controls from {device_ip}")
    
    return controls


@app.post("/api/control/{device_ip}/audio-dsp")
async def set_audio_dsp_controls(device_ip: str, audiomode: Optional[str] = None, videosyncaudiodelay: Optional[int] = None, port: int = 8090):
    """Set audio DSP controls."""
    controller = SoundTouchController(device_ip, port=port)
    success = controller.set_audio_dsp_controls(audiomode, videosyncaudiodelay)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to set audio DSP controls")
    
    return {"status": "success", "device_ip": device_ip, "audiomode": audiomode, "videosyncaudiodelay": videosyncaudiodelay}


# ============================================================================
# Tone Controls Endpoints (Bass & Treble)
# ============================================================================

@app.get("/api/control/{device_ip}/tone-controls")
async def get_tone_controls(device_ip: str, port: int = 8090):
    """Get bass and treble settings."""
    controller = SoundTouchController(device_ip, port=port)
    controls = controller.get_tone_controls()
    
    if controls is None:
        raise HTTPException(status_code=503, detail=f"Could not get tone controls from {device_ip}")
    
    return controls


@app.post("/api/control/{device_ip}/tone-controls")
async def set_tone_controls(device_ip: str, bass: Optional[int] = None, treble: Optional[int] = None, port: int = 8090):
    """Set bass and treble."""
    controller = SoundTouchController(device_ip, port=port)
    success = controller.set_tone_controls(bass, treble)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to set tone controls")
    
    return {"status": "success", "device_ip": device_ip, "bass": bass, "treble": treble}


# ============================================================================
# Level Controls Endpoints (Speaker Levels)
# ============================================================================

@app.get("/api/control/{device_ip}/level-controls")
async def get_level_controls(device_ip: str, port: int = 8090):
    """Get front and rear speaker levels."""
    controller = SoundTouchController(device_ip, port=port)
    controls = controller.get_level_controls()
    
    if controls is None:
        raise HTTPException(status_code=503, detail=f"Could not get level controls from {device_ip}")
    
    return controls


@app.post("/api/control/{device_ip}/level-controls")
async def set_level_controls(device_ip: str, front: Optional[int] = None, rear: Optional[int] = None, port: int = 8090):
    """Set front and rear speaker levels."""
    controller = SoundTouchController(device_ip, port=port)
    success = controller.set_level_controls(front, rear)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to set level controls")
    
    return {"status": "success", "device_ip": device_ip, "front": front, "rear": rear}


# ============================================================================
# Zone Management Endpoints
# ============================================================================

@app.get("/api/control/{device_ip}/zone")
async def get_zone(device_ip: str, port: int = 8090):
    """Get multi-room zone configuration."""
    controller = SoundTouchController(device_ip, port=port)
    zone = controller.get_zone()
    
    if zone is None:
        raise HTTPException(status_code=503, detail=f"Could not get zone from {device_ip}")
    
    return zone


@app.post("/api/control/{device_ip}/zone")
async def create_zone(device_ip: str, master_mac: str, members: List[dict], port: int = 8090):
    """Create a multi-room zone."""
    controller = SoundTouchController(device_ip, port=port)
    members_tuples = [(m["ip"], m["mac"]) for m in members]
    success = controller.set_zone(master_mac, members_tuples)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to create zone")
    
    return {"status": "success", "device_ip": device_ip, "master": master_mac}


@app.post("/api/control/{device_ip}/zone/slave/add")
async def add_zone_slave(device_ip: str, master_mac: str, slave_ip: str, slave_mac: str, port: int = 8090):
    """Add a slave device to a zone."""
    controller = SoundTouchController(device_ip, port=port)
    success = controller.add_zone_slave(master_mac, slave_ip, slave_mac)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add zone slave")
    
    return {"status": "success", "device_ip": device_ip, "slave_mac": slave_mac}


@app.post("/api/control/{device_ip}/zone/slave/remove")
async def remove_zone_slave(device_ip: str, master_mac: str, slave_mac: str, port: int = 8090):
    """Remove a slave device from a zone."""
    controller = SoundTouchController(device_ip, port=port)
    success = controller.remove_zone_slave(master_mac, slave_mac)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to remove zone slave")
    
    return {"status": "success", "device_ip": device_ip, "slave_mac": slave_mac}


# ============================================================================
# Device Management Endpoints
# ============================================================================

@app.post("/api/control/{device_ip}/name")
async def set_device_name(device_ip: str, name: str, port: int = 8090):
    """Set the device name."""
    controller = SoundTouchController(device_ip, port=port)
    success = controller.set_device_name(name)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to set device name")
    
    return {"status": "success", "device_ip": device_ip, "name": name}


# ============================================================================
# WiFi Setup Endpoints
# ============================================================================

@app.post("/api/control/{device_ip}/setup")
async def set_setup_state(device_ip: str, request: SetupStateRequest, port: int = 8090):
    """Set a setup state (e.g. SETUP_WIFI, SETUP_WIFI_LEAVE)."""
    controller = SoundTouchController(device_ip, port=port)
    success = controller.set_setup_state(request.state, request.timeout_ms)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to change setup state")

    return {"status": "success", "device_ip": device_ip, "state": request.state}


@app.post("/api/control/{device_ip}/wifi-profile")
async def add_wifi_profile(device_ip: str, profile: WirelessProfileRequest, port: int = 8090):
    """Add a WiFi profile so the speaker can join the network."""
    controller = SoundTouchController(device_ip, port=port)
    success = controller.add_wireless_profile(
        profile.ssid,
        profile.password,
        profile.security_type,
        profile.timeout,
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to add WiFi profile")

    return {"status": "success", "device_ip": device_ip, "ssid": profile.ssid}


@app.get("/api/control/{device_ip}/wifi-profile")
async def get_wifi_profile(device_ip: str, port: int = 8090):
    """Get the currently active WiFi profile (SSID)."""
    controller = SoundTouchController(device_ip, port=port)
    profile = controller.get_wireless_profile()

    if profile is None:
        raise HTTPException(status_code=503, detail=f"Could not get WiFi profile from {device_ip}")

    return profile


@app.get("/api/control/{device_ip}/wifi-site-survey")
async def wifi_site_survey(device_ip: str, port: int = 8090):
    """Scan for visible WiFi networks near the speaker."""
    controller = SoundTouchController(device_ip, port=port)
    results = controller.perform_wireless_site_survey()

    if results is None:
        raise HTTPException(status_code=503, detail=f"Could not perform site survey on {device_ip}")

    return results


# ============================================================================
# Utility Endpoints
# ============================================================================

@app.get("/api/keys", response_model=List[str])
async def get_available_keys():
    """
    Get list of available key commands.
    
    Returns:
        List of key names
    """
    return SoundTouchController.get_available_keys()


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {
        "status": "healthy",
        "service": "SoundTouch API"
    }


# ============================================================================
# Media Server Endpoints
# ============================================================================

@app.post("/api/media/servers")
async def add_media_server(config: MediaServerConfig):
    """Add a new media server (SMB share or local path)."""
    if config.type == "smb":
        if not config.host or not config.share:
            raise HTTPException(status_code=400, detail="SMB requires host and share")
        
        server = SMBMediaServer(
            config.name,
            config.host,
            config.share,
            config.username or "",
            config.password or ""
        )
    elif config.type == "local":
        if not config.path:
            raise HTTPException(status_code=400, detail="Local server requires path")
        
        server = LocalMediaServer(config.name, config.path)
    else:
        raise HTTPException(status_code=400, detail="Invalid server type")
    
    media_manager.add_server(server)
    
    return {"status": "success", "name": config.name, "type": config.type}


@app.get("/api/media/servers")
async def list_media_servers():
    """List all configured media servers."""
    return {"servers": media_manager.list_servers()}


@app.delete("/api/media/servers/{name}")
async def remove_media_server(name: str):
    """Remove a media server."""
    media_manager.remove_server(name)
    return {"status": "success", "name": name}


@app.get("/api/media/servers/{name}/files")
async def list_server_files(name: str, path: str = "", extensions: Optional[str] = None):
    """List media files from a server."""
    server = media_manager.get_server(name)
    if not server:
        raise HTTPException(status_code=404, detail=f"Server '{name}' not found")
    
    ext_list = extensions.split(',') if extensions else None
    
    if not server.connect():
        raise HTTPException(status_code=503, detail=f"Could not connect to server '{name}'")
    
    try:
        files = server.list_files(path, ext_list)
        server.disconnect()
        return {"server": name, "path": path, "files": files}
    except Exception as e:
        server.disconnect()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/media/files")
async def search_all_files(extensions: Optional[str] = None):
    """Search all configured servers for media files."""
    ext_list = extensions.split(',') if extensions else None
    files = media_manager.search_all(ext_list)
    return {"total": len(files), "files": files}


@app.get("/api/media/stream/{server_name}/{file_path:path}")
async def stream_media_file(server_name: str, file_path: str):
    """Stream a media file from a server."""
    server = media_manager.get_server(server_name)
    if not server:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found")
    
    from urllib.parse import unquote
    file_path = unquote(file_path)
    
    # Determine content type
    content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
    
    # For local files, use file streaming
    if isinstance(server, LocalMediaServer):
        import aiofiles
        file_full_path = server.get_file_path(file_path)
        
        if not file_full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        async def file_iterator():
            async with aiofiles.open(file_full_path, 'rb') as f:
                while chunk := await f.read(64 * 1024):
                    yield chunk
        
        return StreamingResponse(file_iterator(), media_type=content_type)
    
    # For SMB files, read and stream
    elif isinstance(server, SMBMediaServer):
        if not server.connect():
            raise HTTPException(status_code=503, detail="Could not connect to SMB server")
        
        try:
            file_content = server.read_file(file_path)
            if file_content is None:
                raise HTTPException(status_code=404, detail="File not found")
            
            from io import BytesIO
            return StreamingResponse(BytesIO(file_content), media_type=content_type)
        finally:
            server.disconnect()
    
    raise HTTPException(status_code=400, detail="Unsupported server type")


@app.post("/api/media/play")
async def play_media_on_speaker(request: PlayMediaRequest, port: int = 8090):
    """Play a media file on a SoundTouch speaker."""
    server = media_manager.get_server(request.server)
    if not server:
        raise HTTPException(status_code=404, detail=f"Server '{request.server}' not found")
    
    # Get streaming URL
    stream_url = server.get_file_url(request.file_path)
    
    # Get server's external IP (where API is hosted)
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    # Build full URL
    full_url = f"http://{local_ip}:8000{stream_url}"
    
    # Send to speaker
    controller = SoundTouchController(request.device_ip, port=port)
    success = controller.select_source("INTERNET_RADIO", full_url)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to play on speaker")
    
    return {
        "status": "success",
        "device_ip": request.device_ip,
        "file": request.file_path,
        "stream_url": full_url
    }


# ============================================================================
# Root Endpoint
# ============================================================================

@app.get("/")
async def root():
    """
    API root endpoint with usage info.
    """
    return {
        "name": "SoundTouch API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "discovery": {
                "GET /api/discover": "Scan network for SoundTouch devices",
            },
            "control": {
                "POST /api/control/{device_ip}/key": "Send key press to device",
                "GET /api/control/{device_ip}/nowplaying": "Get currently playing info",
            },
            "volume": {
                "GET /api/control/{device_ip}/volume": "Get volume info",
                "POST /api/control/{device_ip}/volume": "Set volume (0-100)",
            },
            "bass": {
                "GET /api/control/{device_ip}/bass-capabilities": "Get bass capabilities",
                "GET /api/control/{device_ip}/bass": "Get current bass",
                "POST /api/control/{device_ip}/bass": "Set bass level",
            },
            "sources": {
                "GET /api/control/{device_ip}/sources": "Get available sources",
                "POST /api/control/{device_ip}/source": "Select source/input",
            },
            "presets": {
                "GET /api/control/{device_ip}/presets": "Get presets",
            },
            "capabilities": {
                "GET /api/control/{device_ip}/capabilities": "Get device capabilities",
            },
            "audio_dsp": {
                "GET /api/control/{device_ip}/audio-dsp": "Get audio DSP settings",
                "POST /api/control/{device_ip}/audio-dsp": "Set audio DSP controls",
            },
            "tone_controls": {
                "GET /api/control/{device_ip}/tone-controls": "Get bass/treble settings",
                "POST /api/control/{device_ip}/tone-controls": "Set bass/treble",
            },
            "level_controls": {
                "GET /api/control/{device_ip}/level-controls": "Get speaker levels",
                "POST /api/control/{device_ip}/level-controls": "Set speaker levels",
            },
            "zones": {
                "GET /api/control/{device_ip}/zone": "Get zone config",
                "POST /api/control/{device_ip}/zone": "Create zone",
                "POST /api/control/{device_ip}/zone/slave/add": "Add slave to zone",
                "POST /api/control/{device_ip}/zone/slave/remove": "Remove slave from zone",
            },
            "device": {
                "POST /api/control/{device_ip}/name": "Set device name",
            },
            "wifi": {
                "POST /api/control/{device_ip}/setup": "Set setup state (e.g. SETUP_WIFI)",
                "POST /api/control/{device_ip}/wifi-profile": "Add WiFi profile",
                "GET /api/control/{device_ip}/wifi-profile": "Get active WiFi profile",
                "GET /api/control/{device_ip}/wifi-site-survey": "Scan for WiFi networks",
            },
            "utility": {
                "GET /api/keys": "Get available keys",
                "GET /api/health": "Health check",
            }
        }
    }


if __name__ == "__main__":
    print("[*] Starting SoundTouch REST API Server...")
    print("[*] API Docs available at: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
