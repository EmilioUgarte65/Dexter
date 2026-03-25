---
name: meeting-transcription
description: >
  Transcribe audio files locally via Whisper CLI or OpenAI Whisper API fallback.
  Generates bullet-point summaries and basic speaker detection.
  Trigger: "transcribir", "transcripción", "meeting", "reunión", "audio a texto", "whisper".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Meeting Transcription

Transcribes audio files using local Whisper CLI. Falls back to OpenAI Whisper API if the CLI is missing and `OPENAI_API_KEY` is set.

## Setup

### Option A: Local Whisper (preferred, free, private)

```bash
pip install openai-whisper

# Optional: set model (default: base)
export WHISPER_MODEL=base    # tiny|base|small|medium|large
```

### Option B: OpenAI Whisper API (fallback)

```bash
export OPENAI_API_KEY="sk-..."
```

## Usage

```bash
# Transcribe an audio file
python3 skills/knowledge/meeting-transcription/scripts/transcribe.py transcribe recording.mp3
python3 skills/knowledge/meeting-transcription/scripts/transcribe.py transcribe meeting.wav --language es
python3 skills/knowledge/meeting-transcription/scripts/transcribe.py transcribe call.m4a --output transcript.txt

# Generate bullet-point summary from transcript
python3 skills/knowledge/meeting-transcription/scripts/transcribe.py summary transcript.txt

# Basic speaker detection (energy-based, heuristic)
python3 skills/knowledge/meeting-transcription/scripts/transcribe.py speakers recording.wav
```

## Supported Formats

`mp3`, `mp4`, `wav`, `m4a`, `ogg`, `flac`, `webm`

## Whisper Models

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| `tiny` | 39M | Very fast | Low |
| `base` | 74M | Fast | Moderate |
| `small` | 244M | Moderate | Good |
| `medium` | 769M | Slow | Very good |
| `large` | 1.5G | Very slow | Best |

## Notes

- First run downloads the model (may take a while)
- Language auto-detection works well for most languages
- Speaker detection is heuristic (energy-based) — not diarization
- For accurate speaker diarization, use `pyannote.audio` (separate tool)
- Transcripts are saved as plain text — easy to process with other tools
