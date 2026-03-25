#!/usr/bin/env python3
"""
Dexter — ElevenLabs Text-to-Speech client.
Uses stdlib only (urllib). No external dependencies.
Auto-plays with mpv, vlc, afplay, or aplay.

Usage:
  tts.py speak <text> [--voice NAME] [--output file.mp3]
  tts.py voices
  tts.py models
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import subprocess
import tempfile
from typing import Optional

# ─── Config from env ──────────────────────────────────────────────────────────

API_KEY       = os.environ.get("ELEVENLABS_API_KEY", "")
DEFAULT_VOICE = os.environ.get("ELEVENLABS_DEFAULT_VOICE", "Rachel")

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"

BASE_URL      = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL = "eleven_monolingual_v1"


def check_config():
    if not API_KEY:
        print(
            "Error: ELEVENLABS_API_KEY not set.\n"
            "Sign up at https://elevenlabs.io and get your API key, then:\n"
            "  export ELEVENLABS_API_KEY=your-key-here",
            file=sys.stderr,
        )
        sys.exit(1)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _headers(content_type: str = "application/json") -> dict:
    return {
        "xi-api-key": API_KEY,
        "Content-Type": content_type,
    }


def el_get(endpoint: str) -> dict:
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, headers=_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            print(f"{RED}ElevenLabs error {e.code}: {err.get('detail', {}).get('message', body)}{RESET}", file=sys.stderr)
        except Exception:
            print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach ElevenLabs API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def el_post_audio(endpoint: str, payload: dict) -> bytes:
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={**_headers(), "Accept": "audio/mpeg"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            print(f"{RED}ElevenLabs error {e.code}: {err.get('detail', {}).get('message', body)}{RESET}", file=sys.stderr)
        except Exception:
            print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach ElevenLabs API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Voice resolution ─────────────────────────────────────────────────────────

def resolve_voice_id(voice_name: str) -> str:
    """Resolve a voice name or ID to a voice ID."""
    # If it looks like a voice ID (alphanumeric, ~20 chars), use directly
    if len(voice_name) > 15 and voice_name.isalnum():
        return voice_name

    result = el_get("/voices")
    voices = result.get("voices", [])
    for v in voices:
        if v.get("name", "").lower() == voice_name.lower():
            return v["voice_id"]
        if v.get("voice_id") == voice_name:
            return voice_name

    available = [v.get("name", "?") for v in voices]
    print(f"{RED}Voice '{voice_name}' not found.{RESET}", file=sys.stderr)
    print(f"Available voices: {', '.join(available[:10])}", file=sys.stderr)
    sys.exit(1)


# ─── Audio playback ───────────────────────────────────────────────────────────

PLAYERS = [
    ["mpv", "--no-video", "--really-quiet"],
    ["vlc", "--intf", "dummy", "--play-and-exit", "-q"],
    ["afplay"],        # macOS
    ["aplay"],         # Linux ALSA
    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
]


def play_audio(file_path: str) -> bool:
    """Try available players. Returns True if playback succeeded."""
    for player_cmd in PLAYERS:
        try:
            result = subprocess.run(
                player_cmd + [file_path],
                capture_output=True,
                timeout=120,
            )
            if result.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return False


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_speak(text: str, voice_name: Optional[str] = None, output: Optional[str] = None):
    voice = voice_name or DEFAULT_VOICE
    voice_id = resolve_voice_id(voice)

    payload = {
        "text": text,
        "model_id": DEFAULT_MODEL,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }

    print(f"Synthesizing speech ({len(text)} chars, voice: {voice})...", end=" ", flush=True)
    audio_data = el_post_audio(f"/text-to-speech/{voice_id}", payload)
    print(f"{GREEN}done{RESET}")

    if output:
        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        with open(output, "wb") as f:
            f.write(audio_data)
        print(f"{GREEN}Saved to: {output}{RESET}  ({len(audio_data) / 1024:.1f} KB)")
        return

    # Auto-play
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name

    try:
        played = play_audio(tmp_path)
        if played:
            print(f"{GREEN}Played successfully.{RESET}")
        else:
            print(
                f"{RED}No audio player found. Install mpv, vlc, or aplay.{RESET}\n"
                f"Audio saved to: {tmp_path}",
                file=sys.stderr,
            )
    finally:
        try:
            if os.path.exists(tmp_path) and not output:
                os.unlink(tmp_path)
        except Exception:
            pass


def cmd_voices():
    result = el_get("/voices")
    voices = result.get("voices", [])

    if not voices:
        print("No voices found.")
        return

    print(f"\n  {len(voices)} voice(s) available:\n")
    print(f"  {'NAME':<25} {'VOICE ID':<25} LABELS")
    print("  " + "-" * 70)
    for v in sorted(voices, key=lambda x: x.get("name", "")):
        name     = v.get("name", "?")[:23]
        vid      = v.get("voice_id", "?")[:23]
        labels   = v.get("labels", {})
        label_str = ", ".join(f"{k}: {v}" for k, v in labels.items())[:30]
        print(f"  {GREEN}{name:<25}{RESET} {vid:<25} {label_str}")


def cmd_models():
    result = el_get("/models")
    models = result if isinstance(result, list) else result.get("models", [])

    if not models:
        print("No models found.")
        return

    print(f"\n  {len(models)} model(s) available:\n")
    for m in models:
        mid   = m.get("model_id", "?")
        name  = m.get("name", "?")
        desc  = m.get("description", "")[:60]
        langs = len(m.get("languages", []))
        print(f"  {GREEN}{mid}{RESET}")
        print(f"    Name:      {name}")
        print(f"    Languages: {langs}")
        if desc:
            print(f"    Desc:      {desc}")
        print()


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter ElevenLabs TTS CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # speak
    p_speak = subparsers.add_parser("speak", help="Synthesize and play text")
    p_speak.add_argument("text", help="Text to synthesize")
    p_speak.add_argument("--voice", help=f"Voice name or ID (default: {DEFAULT_VOICE})")
    p_speak.add_argument("--output", help="Save audio to file instead of playing (e.g. output.mp3)")

    # voices
    subparsers.add_parser("voices", help="List available voices")

    # models
    subparsers.add_parser("models", help="List available TTS models")

    args = parser.parse_args()
    check_config()

    if args.command == "speak":
        cmd_speak(args.text, voice_name=getattr(args, "voice", None), output=getattr(args, "output", None))
    elif args.command == "voices":
        cmd_voices()
    elif args.command == "models":
        cmd_models()


if __name__ == "__main__":
    main()
