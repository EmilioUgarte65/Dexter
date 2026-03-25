---
name: elevenlabs
description: >
  Convert text to speech using the ElevenLabs API and auto-play the audio.
  Supports voice selection, model selection, and saving to file.
  Trigger: "speak", "text to speech", "tts", "voz", "leer en voz alta", "say", "audio", "elevenlabs".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# ElevenLabs TTS

Synthesizes speech from text using ElevenLabs API and plays it with mpv/vlc/afplay/aplay.

## Setup

1. Sign up at https://elevenlabs.io and get your API key
2. Set environment variables:

```bash
export ELEVENLABS_API_KEY="your-api-key-here"
export ELEVENLABS_DEFAULT_VOICE="Rachel"   # optional, default: Rachel
```

**Optional: Install a media player for auto-play:**
```bash
# Linux
sudo apt install mpv    # recommended
sudo apt install vlc
sudo apt install alsa-utils   # for aplay

# macOS: afplay is built-in
```

## Usage

```bash
# Speak text (auto-plays with mpv/vlc/afplay/aplay)
python3 skills/productivity/elevenlabs/scripts/tts.py speak "Hello, I am Dexter!"

# Speak with a specific voice
python3 skills/productivity/elevenlabs/scripts/tts.py speak "Buenos días" --voice "Antoni"

# Save to file instead of playing
python3 skills/productivity/elevenlabs/scripts/tts.py speak "Hello world" --output /tmp/hello.mp3

# List available voices
python3 skills/productivity/elevenlabs/scripts/tts.py voices

# List available models
python3 skills/productivity/elevenlabs/scripts/tts.py models
```

## Notes

- `ELEVENLABS_API_KEY` — required
- `ELEVENLABS_DEFAULT_VOICE` — voice name or voice ID (default: `Rachel`)
- Auto-play tries: `mpv` → `vlc` → `afplay` (macOS) → `aplay` (Linux)
- Default model: `eleven_monolingual_v1` (English); use `eleven_multilingual_v2` for other languages
- Free tier: 10,000 characters/month
