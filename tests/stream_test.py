import argparse
import http.server
import os
import socket
import threading
import time
import wave
import math
import struct
import requests
import shutil
import subprocess

# Optional: MP3 generation (requires pydub + ffmpeg in PATH)
try:
    from pydub import AudioSegment
    _HAS_PYDUB = True
except Exception:
    _HAS_PYDUB = False


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


def _sine_samples(duration: float, freq: float, sr: int, volume: float):
    total = int(sr * duration)
    for n in range(total):
        v = volume * math.sin(2 * math.pi * freq * n / sr)
        yield int(v * 32767)


def create_wave(path: str, duration: float = 5.0, freq: float = 440.0, sr: int = 44100, volume: float = 0.2):
    samples = list(_sine_samples(duration, freq, sr, volume))
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples))


def create_mp3(path: str, duration: float = 5.0, freq: float = 440.0, sr: int = 44100, volume: float = 0.2):
    # Try pydub first
    if _HAS_PYDUB:
        samples = b"".join(struct.pack("<h", s) for s in _sine_samples(duration, freq, sr, volume))
        audio = AudioSegment(
            data=samples,
            sample_width=2,
            frame_rate=sr,
            channels=1,
        )
        audio.export(path, format="mp3")
        return
    # Fallback: use ffmpeg CLI if available
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("Neither pydub nor ffmpeg CLI available. Install ffmpeg or pip install pydub.")
    tmp_wav = path + ".tmp.wav"
    create_wave(tmp_wav, duration=duration, freq=freq, sr=sr, volume=volume)
    cmd = [ffmpeg, "-y", "-i", tmp_wav, path]
    subprocess.run(cmd, check=True)
    os.remove(tmp_wav)


def start_http_server(directory: str, port: int) -> http.server.ThreadingHTTPServer:
    handler = http.server.SimpleHTTPRequestHandler
    os.chdir(directory)
    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def send_stream(speaker_ip: str, stream_url: str):
    url = f"http://{speaker_ip}:8090/select"
    body = (
        f'<ContentItem source="LOCAL_INTERNET_RADIO" location="{stream_url}" isPresetable="true">'
        f"<itemName>Test Stream</itemName>"
        f"</ContentItem>"
    )
    resp = requests.post(url, data=body, timeout=5)
    return resp


def check_stream_accessible(stream_url: str):
    """Check that the stream URL is reachable from this host (basic sanity)."""
    try:
        r = requests.get(stream_url, timeout=5, stream=True)
        r.raise_for_status()
        return r.headers.get("Content-Type", ""), r.headers.get("Content-Length", "")
    except Exception as exc:
        print(f"WARNING: Could not fetch {stream_url}: {exc}")
        return None, None


def main():
    parser = argparse.ArgumentParser(description="Generate test audio, host via HTTP, and stream to Bose SoundTouch.")
    parser.add_argument("--speaker", default="192.168.50.19", help="Speaker IP (SoundTouch port 8090)")
    parser.add_argument("--port", type=int, default=8765, help="HTTP server port")
    parser.add_argument("--file", default="test.mp3", help="Output filename (.mp3 or .wav)")
    parser.add_argument("--duration", type=float, default=5.0, help="Seconds of audio")
    parser.add_argument("--freq", type=float, default=440.0, help="Frequency in Hz")
    parser.add_argument("--no-generate", action="store_true", help="Do not generate audio, serve existing file")
    parser.add_argument("--stream-url", help="Use an existing external stream URL (skip local file/server)")
    args = parser.parse_args()

    base_dir = os.path.abspath(os.path.dirname(__file__))
    out_path = os.path.join(base_dir, args.file)

    # If external stream provided, skip generation/server
    if args.stream_url:
        stream_url = args.stream_url
        print(f"Using external stream URL: {stream_url}")
        ctype, clen = check_stream_accessible(stream_url)
        if ctype:
            print(f"HEAD ok: Content-Type={ctype}, Content-Length={clen}")
        resp = send_stream(args.speaker, stream_url)
        print(f"Speaker response: {resp.status_code} {resp.text}")
        return

    if not args.no_generate:
        if args.file.lower().endswith(".mp3"):
            print(f"Creating MP3: {out_path} ({args.duration}s @ {args.freq} Hz)")
            if not _HAS_PYDUB:
                # Try ffmpeg CLI
                try:
                    create_mp3(out_path, duration=args.duration, freq=args.freq)
                except Exception as exc:
                    raise SystemExit("MP3 requested but pydub/ffmpeg not available. Install pydub+ffmpeg or use --file test.wav or --no-generate.") from exc
            else:
                create_mp3(out_path, duration=args.duration, freq=args.freq)
        else:
            print(f"Creating WAV: {out_path} ({args.duration}s @ {args.freq} Hz)")
            create_wave(out_path, duration=args.duration, freq=args.freq)
    else:
        if not os.path.exists(out_path):
            raise SystemExit(f"--no-generate set but file not found: {out_path}")

    print(f"Starting HTTP server on port {args.port} serving {base_dir}")
    server = start_http_server(base_dir, args.port)

    try:
        ip = local_ip()
        stream_url = f"http://{ip}:{args.port}/{args.file}"
        print(f"Local stream URL: {stream_url}")
        ctype, clen = check_stream_accessible(stream_url)
        if ctype:
            print(f"HEAD ok: Content-Type={ctype}, Content-Length={clen}")
        print(f"Sending to speaker {args.speaker} ...")
        resp = send_stream(args.speaker, stream_url)
        print(f"Speaker response: {resp.status_code} {resp.text}")
        print("Leave this script running while the speaker plays. Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
