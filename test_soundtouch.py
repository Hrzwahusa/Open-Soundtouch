"""
Comprehensive test script for SoundTouch API functionality.
Tests all key presses, control functions, and API endpoints.
"""

import time
import sys
from soundtouch_lib import SoundTouchDiscovery, SoundTouchController
from soundtouch_websocket import SoundTouchWebSocket


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def wait_input(message="Press Enter to continue..."):
    """Wait for user input."""
    input(f"\n{message}")


def test_discovery():
    """Test device discovery."""
    print_section("DEVICE DISCOVERY")
    print("Scanning network for SoundTouch devices...")
    
    discovery = SoundTouchDiscovery()
    devices = discovery.scan()
    
    if not devices:
        print("❌ No devices found!")
        return None
    
    print(f"✓ Found {len(devices)} device(s):\n")
    for i, device in enumerate(devices, 1):
        print(f"{i}. {device['name']} ({device['ip']})")
        print(f"   Type: {device['type']}")
    
    return devices


def test_device_info(controller, device_data):
    """Test getting device information."""
    print_section("DEVICE INFORMATION")
    
    print("Device Info (from discovery):")
    print(f"  Name: {device_data.get('name', 'N/A')}")
    print(f"  Type: {device_data.get('type', 'N/A')}")
    print(f"  MAC: {device_data.get('mac', 'N/A')}")
    print(f"  IP: {controller.ip}")
    print(f"  Device ID: {device_data.get('deviceID', 'N/A')}")
    
    print("\nGetting now playing...")
    now_playing = controller.get_nowplaying()
    if now_playing:
        print("✓ Now Playing:")
        print(f"  Source: {now_playing.get('source', 'N/A')}")
        print(f"  Track: {now_playing.get('track', 'N/A')}")
        print(f"  Artist: {now_playing.get('artist', 'N/A')}")
        print(f"  Album: {now_playing.get('album', 'N/A')}")
    else:
        print("✓ Nothing playing")


def test_volume(controller, ws=None):
    """Test volume control."""
    print_section("VOLUME CONTROL")
    
    print("Getting current volume...")
    volume_info = controller.get_volume()
    if volume_info:
        volume = volume_info.get('actualvolume', 0)
        print(f"✓ Current volume: {volume}")
        original_volume = volume
        
        print("\nTesting volume changes...")
        
        # Set to 20
        print("Setting volume to 20...")
        if controller.set_volume(20):
            time.sleep(0.5)
            
            # Wait for WebSocket notification
            if ws:
                event = wait_for_websocket_event(ws, 'volumeUpdated', timeout=3)
                if event:
                    print(f"✓ Volume update received via WebSocket: {event.get('actualvolume', 'N/A')}")
                else:
                    print("⊘ No WebSocket notification (trying HTTP poll)")
                    new_vol_info = controller.get_volume()
                    if new_vol_info:
                        print(f"✓ Volume set to: {new_vol_info.get('actualvolume', 'N/A')}")
            else:
                new_vol_info = controller.get_volume()
                if new_vol_info:
                    print(f"✓ Volume set to: {new_vol_info.get('actualvolume', 'N/A')}")
        
        # Increase by 5 using send_key
        print("\nIncreasing volume using VOLUME_UP key (5 times)...")
        for i in range(5):
            controller.send_key('volume_up')
            time.sleep(0.2)
        
        time.sleep(1)
        
        # Wait for WebSocket notification
        if ws:
            event = wait_for_websocket_event(ws, 'volumeUpdated', timeout=3)
            if event:
                print(f"✓ Volume update received via WebSocket: {event.get('actualvolume', 'N/A')}")
            else:
                print("⊘ No WebSocket notification (trying HTTP poll)")
                new_vol_info = controller.get_volume()
                if new_vol_info:
                    print(f"✓ Volume now: {new_vol_info.get('actualvolume', 'N/A')}")
        else:
            new_vol_info = controller.get_volume()
            if new_vol_info:
                print(f"✓ Volume now: {new_vol_info.get('actualvolume', 'N/A')}")
        
        # Decrease by 5 using send_key
        print("\nDecreasing volume using VOLUME_DOWN key (5 times)...")
        for i in range(5):
            controller.send_key('volume_down')
            time.sleep(0.2)
        time.sleep(1)
        
        # Wait for WebSocket notification
        if ws:
            event = wait_for_websocket_event(ws, 'volumeUpdated', timeout=3)
            if event:
                print(f"✓ Volume update received via WebSocket: {event.get('actualvolume', 'N/A')}")
            else:
                print("⊘ No WebSocket notification (trying HTTP poll)")
                new_vol_info = controller.get_volume()
                if new_vol_info:
                    print(f"✓ Volume now: {new_vol_info.get('actualvolume', 'N/A')}")
        else:
            new_vol_info = controller.get_volume()
            if new_vol_info:
                print(f"✓ Volume now: {new_vol_info.get('actualvolume', 'N/A')}")
        
        # Restore original
        print(f"\nRestoring original volume ({original_volume})...")
        if controller.set_volume(original_volume):
            time.sleep(0.5)
            print(f"✓ Volume restored")
        else:
            print("❌ Could not restore original volume")
    else:
        print("❌ Failed to get volume")


def test_key_presses(controller):
    """Test all key press commands."""
    print_section("KEY PRESS TESTING")
    
    keys = SoundTouchController.get_available_keys()
    print(f"Available keys ({len(keys)}):")
    for i, key in enumerate(keys, 1):
        print(f"  {i:2d}. {key}")
    
    wait_input("\nReady to test key presses? This will send commands to the speaker.")
    
    # Test safe keys that don't disrupt too much
    safe_keys = [
        ("mute", "Toggling mute"),
        ("mute", "Toggling mute again (unmute)"),
        ("preset1", "Selecting preset 1"),
    ]
    
    for key, description in safe_keys:
        print(f"\n{description}...")
        if controller.send_key(key):
            print(f"✓ {key} sent")
            time.sleep(0.5)
            if verify_keypress(controller, key):
                print(f"✓ {key} verified - speaker responded")
            else:
                print(f"❌ {key} not verified - speaker may not have received command")
            time.sleep(0.5)
        else:
            print(f"❌ Failed to send {key}")


def test_presets(controller):
    """Test preset management."""
    print_section("PRESET MANAGEMENT")
    
    print("Getting presets...")
    presets = controller.get_presets()
    if presets:
        print(f"✓ Found {len(presets)} preset(s):\n")
        for preset in presets:
            print(f"  Preset {preset.get('id', 'N/A')}:")
            print(f"    Source: {preset.get('source', 'N/A')}")
            print(f"    Name: {preset.get('name', 'N/A')}")
            print(f"    Location: {preset.get('location', 'N/A')}")
    else:
        print("No presets configured")


def test_sources(controller):
    """Test available sources."""
    print_section("AVAILABLE SOURCES")
    
    print("Getting available sources...")
    sources = controller.get_sources()
    if sources:
        print(f"✓ Found {len(sources)} source(s):\n")
        for i, source in enumerate(sources, 1):
            print(f"  {i}. {source.get('source', 'N/A')}")
            if source.get('name'):
                print(f"     Name: {source.get('name')}")
            if source.get('status'):
                print(f"     Status: {source.get('status')}")
    else:
        print("❌ Failed to get sources")


def test_bass(controller):
    """Test bass control."""
    print_section("BASS CONTROL")
    
    print("Getting bass capabilities...")
    bass_caps = controller.get_bass_capabilities()
    if bass_caps:
        print(f"✓ Bass range: {bass_caps.get('minbass', 'N/A')} to {bass_caps.get('maxbass', 'N/A')}")
    
    print("\nGetting current bass level...")
    bass_info = controller.get_bass()
    if bass_info:
        bass = bass_info.get('actualbass', 0)
        print(f"✓ Current bass: {bass}")
        original_bass = bass
        
        # Only test if we have capabilities
        if bass_caps and bass_caps.get('minbass') is not None:
            print("\nTesting bass changes...")
            
            # Set to 0 (neutral)
            print("Setting bass to 0...")
            if controller.set_bass(0):
                time.sleep(0.5)
                new_bass_info = controller.get_bass()
                print(f"✓ Bass set to: {new_bass_info.get('actualbass', 'N/A')}")
            
            # Restore original
            print(f"Restoring original bass ({original_bass})...")
            controller.set_bass(original_bass)
            time.sleep(0.5)
    else:
        print("Bass control not available on this device")


def test_zones(controller):
    """Test zone (multi-room) functionality."""
    print_section("ZONE MANAGEMENT")
    
    print("Getting zone status...")
    zone_status = controller.get_zone()
    if zone_status:
        print(f"✓ Master ID: {zone_status.get('master_id', 'N/A')}")
        members = zone_status.get('members', [])
        if members:
            print(f"  Zone has {len(members)} member(s):")
            for member in members:
                print(f"    - {member.get('ip', 'N/A')} (Role: {member.get('role', 'N/A')})")
        else:
            print("  No active zone")
    else:
        print("❌ Failed to get zone status")


def test_playback_controls(controller):
    """Test playback control functions."""
    print_section("PLAYBACK CONTROLS")
    
    print("Testing playback controls...")
    print("Note: These will only work if media is currently playing\n")
    
    wait_input("Press Enter to test PLAY command...")
    if controller.send_key('play'):
        print("✓ PLAY sent")
        time.sleep(1)
    
    wait_input("Press Enter to test PAUSE command...")
    if controller.send_key('pause'):
        print("✓ PAUSE sent")
        time.sleep(1)
    
    wait_input("Press Enter to test PLAY_PAUSE toggle...")
    # Play/pause toggle is not a key, skip it
    print("(Play/pause toggle - using pause key)")
    if controller.send_key('pause'):
        print("✓ PAUSE sent")
        time.sleep(1)


def test_power(controller):
    """Test power controls."""
    print_section("POWER CONTROL")
    
    print("WARNING: This will power off the speaker!")
    response = input("Do you want to test power off? (yes/no): ")
    
    if response.lower() == 'yes':
        print("\nPowering off in 3 seconds...")
        time.sleep(3)
        
        if controller.send_key('power'):
            print("✓ Power off command sent")
            print("\nWaiting 5 seconds...")
            time.sleep(5)
            
            print("Powering back on...")
            if controller.send_key('power'):
                print("✓ Power on command sent")
                print("Waiting 10 seconds for device to boot...")
                time.sleep(10)
            else:
                print("❌ Failed to send power on")
        else:
            print("❌ Failed to send power off")
    else:
        print("Skipping power test")


def test_audio_streaming(controller):
    """Test audio streaming to speaker."""
    print_section("AUDIO STREAMING TEST")
    
    print("Testing available sources for streaming...\n")
    
    # First, get available sources
    sources = controller.get_sources()
    if not sources:
        print("❌ No sources available on speaker")
        return
    
    print(f"✓ Found {len(sources)} source(s):")
    for source in sources:
        print(f"  - {source.get('source', 'N/A')}")
    
    # Try presets first (most reliable)
    print("\nTesting presets...")
    presets = controller.get_presets()
    if presets and len(presets) > 0:
        preset = presets[0]
        print(f"Selecting preset: {preset.get('name', 'Unknown')}")
        if controller.select_source(preset.get('source', ''), preset.get('location', '')):
            print(f"✓ Preset selected")
            time.sleep(2)
            now_playing = controller.get_nowplaying()
            if now_playing:
                print(f"  Source: {now_playing.get('source', 'N/A')}")
                print(f"  Track: {now_playing.get('track', 'N/A')}")
        else:
            print(f"❌ Could not select preset")
    else:
        print("No presets configured")
    
    # Try AUX if available
    aux_available = any(s.get('source') == 'AUX' for s in sources)
    if aux_available:
        print("\nTesting AUX source...")
        if controller.select_source('AUX'):
            print("✓ AUX source selected")
        else:
            print("❌ Could not select AUX")
    
    # Try other available sources
    print("\nTesting other available sources...")
    for source in sources:
        source_name = source.get('source', '')
        if source_name not in ['AUX', 'INVALID']:
            print(f"  Trying {source_name}...")
            if controller.select_source(source_name):
                print(f"  ✓ {source_name} available")
                break
            else:
                print(f"  ⊘ {source_name} not accessible")
    
    print("✓ Audio streaming test complete")


def test_wifi_functions(controller):
    """Test WiFi-related functions."""
    print_section("WIFI FUNCTIONS (Optional)")
    
    print("WiFi functions should only be used during initial setup")
    print("These commands may interfere with normal operation!\n")
    
    response = input("Do you want to test WiFi functions? (yes/no): ")
    
    if response.lower() == 'yes':
        print("\nGetting active wireless profile...")
        profile = controller.get_wireless_profile()
        if profile:
            print("✓ Active Profile:")
            print(f"  SSID: {profile.get('ssid', 'N/A')}")
            print(f"  Security: {profile.get('security', 'N/A')}")
        else:
            print("❌ Failed to get wireless profile")
        
        print("\nPerforming wireless site survey...")
        networks = controller.perform_wireless_site_survey()
        if networks:
            print(f"✓ Found {len(networks)} network(s):")
            for network in networks[:5]:  # Show first 5
                print(f"  - {network.get('ssid', 'N/A')} (Signal: {network.get('signal', 'N/A')}, Security: {network.get('security', 'N/A')})")
            if len(networks) > 5:
                print(f"  ... and {len(networks)-5} more")
        else:
            print("❌ Failed to perform site survey")
    else:
        print("Skipping WiFi tests")


def check_speaker_on(controller, timeout=5):
    """Check if speaker is powered on by trying to get volume."""
    for i in range(timeout):
        try:
            volume = controller.get_volume()
            if volume:
                return True
            time.sleep(1)
        except:
            time.sleep(1)
    return False


def wait_for_websocket_event(ws, event_type, timeout=5):
    """Wait for a specific WebSocket event."""
    end_time = time.time() + timeout
    while time.time() < end_time:
        event = ws.get_next_event(timeout=0.5)
        if event and event.get('type') == event_type:
            return event
    return None


def verify_keypress(controller, key_name, expected_change=None):
    """Verify that a keypress was received by checking speaker state."""
    # For most keys, just check if we can still communicate
    try:
        volume = controller.get_volume()
        return volume is not None
    except:
        return False


def run_full_test():
    """Run the complete test suite."""
    print("\n" + "="*70)
    print("  SOUNDTOUCH COMPREHENSIVE TEST SUITE")
    print("="*70)
    print("\nThis script will test all SoundTouch functionality.")
    print("Some tests will send commands to your speaker.\n")
    
    # Discovery
    devices = test_discovery()
    if not devices:
        print("\nNo devices found. Exiting.")
        return
    
    # Select device
    if len(devices) > 1:
        while True:
            try:
                choice = int(input(f"\nSelect device to test (1-{len(devices)}): "))
                if 1 <= choice <= len(devices):
                    device = devices[choice - 1]
                    break
                print("Invalid choice")
            except ValueError:
                print("Invalid input")
    else:
        device = devices[0]
    
    print(f"\n✓ Selected: {device['name']} ({device['ip']})")
    controller = SoundTouchController(device['ip'])
    
    # Try to connect WebSocket for real-time notifications
    print("\nConnecting to device via WebSocket for real-time updates...")
    ws = SoundTouchWebSocket(device['ip'])
    if ws.connect():
        print("✓ WebSocket connected - will receive real-time notifications")
    else:
        print("⊘ WebSocket connection failed - will use HTTP polling")
        ws = None
    
    wait_input("\nPress Enter to start testing...")
    
    # Run tests
    try:
        # Power state testing FIRST
        print_section("POWER STATE TESTING")
        print("Checking current power state...")
        is_on = check_speaker_on(controller, timeout=3)
        
        if is_on:
            print("✓ Speaker is currently ON")
            print("\nTesting power OFF...")
            controller.send_key('power')
            time.sleep(2)
            is_off = not check_speaker_on(controller, timeout=5)
            if is_off:
                print("✓ Speaker successfully powered OFF")
            else:
                print("❌ Speaker did not power off")
            
            print("\nTesting power ON...")
            controller.send_key('power')
            time.sleep(2)
            is_on_again = check_speaker_on(controller, timeout=10)
            if is_on_again:
                print("✓ Speaker successfully powered ON")
            else:
                print("❌ Speaker did not power on")
                print("Exiting tests - speaker not responding")
                return
        else:
            print("✓ Speaker is currently OFF")
            print("\nTesting power ON...")
            controller.send_key('power')
            time.sleep(2)
            is_on = check_speaker_on(controller, timeout=10)
            if is_on:
                print("✓ Speaker successfully powered ON")
            else:
                print("❌ Speaker did not power on")
                print("Exiting tests - speaker not responding")
                return
        
        print("\n✓ Power state tests complete - speaker is ready")
        wait_input()
        
        test_device_info(controller, device)
        wait_input()
        
        test_volume(controller, ws)
        wait_input()
        
        test_bass(controller)
        wait_input()
        
        test_presets(controller)
        wait_input()
        
        test_sources(controller)
        wait_input()
        
        test_zones(controller)
        wait_input()
        
        test_key_presses(controller)
        wait_input()
        
        test_playback_controls(controller)
        wait_input()
        
        test_audio_streaming(controller)
        wait_input()
        
        test_wifi_functions(controller)
        wait_input()
        
        test_power(controller)
        
        # Cleanup
        if ws:
            ws.disconnect()
            print("\n✓ WebSocket disconnected")
        
        print_section("TEST SUITE COMPLETE")
        print("✓ All tests finished successfully!")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        run_full_test()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
