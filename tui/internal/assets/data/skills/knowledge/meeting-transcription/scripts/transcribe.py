#!/usr/bin/env python3
"""
Dexter — Meeting transcription via local Whisper CLI or OpenAI API fallback.
Generates transcripts, summaries, and basic speaker detection.

Usage:
  transcribe.py transcribe <audio_file> [--language es|en|auto] [--output file.txt]
  transcribe.py summary <transcript_file>
  transcribe.py speakers <audio_file>
"""

import sys
import os
import re
import json
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

# ─── ANSI colors ──────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

# ─── Config ───────────────────────────────────────────────────────────────────

OPENAI_API_KEY  = os.environ.get("OPENAI_API_KEY", "")
WHISPER_MODEL   = os.environ.get("WHISPER_MODEL", "base")

SUPPORTED_FORMATS = {".mp3", ".mp4", ".wav", ".m4a", ".ogg", ".flac", ".webm"}


def _check_audio_file(path: str) -> Path:
    p = Path(path)
    if not p.exists():
        print(f"{RED}File not found: {path}{RESET}", file=sys.stderr)
        sys.exit(1)
    if p.suffix.lower() not in SUPPORTED_FORMATS:
        print(f"{RED}Unsupported format: {p.suffix}. Supported: {', '.join(SUPPORTED_FORMATS)}{RESET}", file=sys.stderr)
        sys.exit(1)
    return p


def _check_whisper_cli() -> bool:
    """Check if whisper CLI is available."""
    try:
        result = subprocess.run(
            ["whisper", "--help"],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _check_whisper_module() -> bool:
    """Check if openai-whisper Python module is available."""
    try:
        import whisper  # noqa: F401
        return True
    except ImportError:
        return False


# ─── Transcription backends ───────────────────────────────────────────────────

def _transcribe_whisper_cli(audio_path: Path, language: str, output: Optional[str]) -> str:
    """Transcribe using whisper CLI."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "whisper", str(audio_path),
            "--model", WHISPER_MODEL,
            "--output_dir", tmpdir,
            "--output_format", "txt",
        ]
        if language and language != "auto":
            cmd += ["--language", language]

        print(f"{BLUE}Transcribing with Whisper CLI (model: {WHISPER_MODEL})...{RESET}")
        print(f"  File: {audio_path.name} ({audio_path.stat().st_size / 1024 / 1024:.1f} MB)")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600
            )
        except subprocess.TimeoutExpired:
            print(f"{RED}Transcription timed out (10min). Try a smaller model.{RESET}", file=sys.stderr)
            sys.exit(1)

        if result.returncode != 0:
            print(f"{RED}Whisper error:{RESET}", file=sys.stderr)
            print(result.stderr[-500:], file=sys.stderr)
            sys.exit(1)

        # Find output file
        txt_files = list(Path(tmpdir).glob("*.txt"))
        if not txt_files:
            print(f"{RED}No transcript file generated.{RESET}", file=sys.stderr)
            sys.exit(1)

        transcript = txt_files[0].read_text(encoding="utf-8").strip()
        return transcript


def _transcribe_whisper_module(audio_path: Path, language: str, output: Optional[str]) -> str:
    """Transcribe using openai-whisper Python module."""
    import whisper

    print(f"{BLUE}Loading Whisper model: {WHISPER_MODEL}{RESET}")
    print(f"{YELLOW}(First run downloads the model — may take a while){RESET}")

    model = whisper.load_model(WHISPER_MODEL)

    opts = {}
    if language and language != "auto":
        opts["language"] = language

    print(f"{BLUE}Transcribing: {audio_path.name}{RESET}")
    result = model.transcribe(str(audio_path), **opts)
    return result["text"].strip()


def _transcribe_openai_api(audio_path: Path, language: str, output: Optional[str]) -> str:
    """Transcribe via OpenAI Whisper API."""
    import urllib.request
    import urllib.parse

    print(f"{BLUE}Transcribing via OpenAI Whisper API...{RESET}")
    print(f"{YELLOW}Note: File will be sent to OpenAI servers.{RESET}")

    # Multipart form upload
    boundary = "----DexterBoundary" + os.urandom(8).hex()
    audio_data = audio_path.read_bytes()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="model"\r\n\r\n'
        f"whisper-1\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{audio_path.name}"\r\n'
        f"Content-Type: audio/mpeg\r\n\r\n"
    ).encode() + audio_data + (
        f"\r\n--{boundary}--\r\n"
    ).encode()

    if language and language != "auto":
        lang_part = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="language"\r\n\r\n'
            f"{language}\r\n"
        ).encode()
        # Insert before final boundary
        body = body[:-len(f"\r\n--{boundary}--\r\n".encode())] + lang_part + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            return result.get("text", "").strip()
    except Exception as e:
        print(f"{RED}API error: {e}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_transcribe(audio_file: str, language: str = "auto", output: Optional[str] = None):
    audio_path = _check_audio_file(audio_file)

    # Choose backend
    if _check_whisper_cli():
        transcript = _transcribe_whisper_cli(audio_path, language, output)
        backend    = "Whisper CLI"
    elif _check_whisper_module():
        transcript = _transcribe_whisper_module(audio_path, language, output)
        backend    = "openai-whisper module"
    elif OPENAI_API_KEY:
        transcript = _transcribe_openai_api(audio_path, language, output)
        backend    = "OpenAI Whisper API"
    else:
        print(f"{RED}No transcription backend available.{RESET}", file=sys.stderr)
        print(f"\nInstall local Whisper (free, private):", file=sys.stderr)
        print(f"  pip install openai-whisper", file=sys.stderr)
        print(f"\nOr set OPENAI_API_KEY for API fallback.", file=sys.stderr)
        sys.exit(1)

    if output:
        Path(output).write_text(transcript, encoding="utf-8")
        print(f"\n{GREEN}Transcript saved: {output}{RESET}")
        print(f"  Backend  : {backend}")
        print(f"  Words    : {len(transcript.split()):,}")
        print(f"  Chars    : {len(transcript):,}")
    else:
        print(f"\n{BLUE}{'─' * 60}{RESET}")
        print(transcript)
        print(f"{BLUE}{'─' * 60}{RESET}")
        print(f"\n{GREEN}Backend: {backend} | Words: {len(transcript.split()):,}{RESET}")


def cmd_summary(transcript_file: str):
    path = Path(transcript_file)
    if not path.exists():
        print(f"{RED}File not found: {transcript_file}{RESET}", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        print(f"{RED}Transcript file is empty.{RESET}", file=sys.stderr)
        sys.exit(1)

    print(f"\n{BLUE}Generating summary...{RESET}\n")

    # Try OpenAI if available
    if OPENAI_API_KEY:
        try:
            import urllib.request
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{
                    "role": "user",
                    "content": (
                        f"Create a concise bullet-point summary of this meeting transcript.\n"
                        f"Include: key decisions, action items, and main topics.\n\n"
                        f"TRANSCRIPT:\n{text[:8000]}"
                    )
                }],
                "max_tokens": 500,
            }
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data    = json.loads(resp.read().decode())
                summary = data["choices"][0]["message"]["content"].strip()
                print(summary)
                print(f"\n{GREEN}(AI-enhanced summary via OpenAI){RESET}")
                return
        except Exception:
            pass  # Fall through to heuristic summary

    # Heuristic summary: extract sentences with key signals
    sentences = re.split(r"[.!?]+", text)
    key_signals = [
        r"\bwill\b", r"\bshould\b", r"\bagree\b", r"\bdecid", r"\baction\b",
        r"\btask\b", r"\bresponsib", r"\bdeadline\b", r"\bnext step",
        r"\bfollow.?up\b", r"\bimportant\b", r"\bcritical\b", r"\bpriority\b",
    ]

    key_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 20:
            continue
        if any(re.search(sig, sentence, re.IGNORECASE) for sig in key_signals):
            key_sentences.append(sentence)

    print(f"{BLUE}Summary — {path.name}{RESET}\n")
    print(f"  Total words : {len(text.split()):,}")
    print(f"  Est. minutes: ~{len(text.split()) // 130}")
    print()

    if key_sentences:
        print("Key points:\n")
        for s in key_sentences[:10]:
            print(f"  • {s.strip()}")
    else:
        # Fallback: first N sentences
        print("First sentences (no key signals detected):\n")
        for s in sentences[:5]:
            if s.strip():
                print(f"  • {s.strip()}")

    print(f"\n{YELLOW}Tip: Set OPENAI_API_KEY for AI-enhanced summaries.{RESET}")


def cmd_speakers(audio_file: str):
    audio_path = _check_audio_file(audio_file)

    print(f"\n{BLUE}Basic speaker detection: {audio_path.name}{RESET}")
    print(f"{YELLOW}Note: This is energy-based heuristic detection, not true diarization.{RESET}")
    print(f"For accurate speaker diarization, use pyannote.audio.\n")

    # Check for wave module (stdlib) — only works on .wav
    if audio_path.suffix.lower() != ".wav":
        print(f"{YELLOW}Speaker detection only supports WAV files.{RESET}")
        print(f"Convert first: ffmpeg -i {audio_path} output.wav")
        sys.exit(1)

    import wave
    import struct
    import math

    try:
        with wave.open(str(audio_path), "rb") as wf:
            channels    = wf.getnchannels()
            sample_rate = wf.getframerate()
            n_frames    = wf.getnframes()
            raw_data    = wf.readframes(n_frames)
            sampwidth   = wf.getsampwidth()
    except Exception as e:
        print(f"{RED}Cannot read WAV file: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    # Parse samples
    fmt = {1: "b", 2: "h", 4: "i"}.get(sampwidth, "h")
    samples = struct.unpack(f"<{len(raw_data) // sampwidth}{fmt}", raw_data)

    # Compute RMS energy per 500ms window
    window_size = sample_rate // 2 * channels
    windows     = []
    for i in range(0, len(samples) - window_size, window_size):
        chunk = samples[i:i + window_size]
        rms   = math.sqrt(sum(s * s for s in chunk) / len(chunk))
        windows.append(rms)

    if not windows:
        print(f"{RED}No audio data found.{RESET}")
        sys.exit(1)

    # Detect silence vs speech
    mean_rms   = sum(windows) / len(windows)
    threshold  = mean_rms * 0.3

    # Group into segments
    segments = []
    in_speech = False
    start_sec = 0
    for i, rms in enumerate(windows):
        t = i * 0.5
        if rms > threshold and not in_speech:
            in_speech = True
            start_sec = t
        elif rms <= threshold and in_speech:
            in_speech = False
            segments.append((start_sec, t, "speech"))

    if in_speech:
        segments.append((start_sec, len(windows) * 0.5, "speech"))

    total_secs = len(windows) * 0.5
    print(f"Audio duration : {total_secs:.1f}s ({total_secs/60:.1f} min)")
    print(f"Speech segments: {len(segments)}")
    print()

    # Heuristically assign "speakers" based on gap size
    prev_end    = 0
    speaker_num = 1
    last_change = 0

    for i, (start, end, _) in enumerate(segments[:20]):
        gap = start - prev_end
        if gap > 2.0 and i > 0:
            speaker_num = 2 if speaker_num == 1 else 1
        duration = end - start
        print(f"  [{start:5.1f}s - {end:5.1f}s]  Speaker {speaker_num}  ({duration:.1f}s)")
        prev_end = end

    if len(segments) > 20:
        print(f"  ... ({len(segments) - 20} more segments)")

    print(f"\n{YELLOW}This is a heuristic estimate based on energy levels.{RESET}")
    print(f"For accurate results: pip install pyannote.audio")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter Meeting Transcription")
    sub    = parser.add_subparsers(dest="command", required=True)

    # transcribe
    p_tr = sub.add_parser("transcribe", help="Transcribe an audio file")
    p_tr.add_argument("audio_file")
    p_tr.add_argument("--language", default="auto", help="Language code (e.g. es, en) or 'auto'")
    p_tr.add_argument("--output",   help="Save transcript to file")

    # summary
    p_sum = sub.add_parser("summary", help="Generate bullet-point summary from transcript")
    p_sum.add_argument("transcript_file")

    # speakers
    p_spk = sub.add_parser("speakers", help="Basic speaker detection (WAV only)")
    p_spk.add_argument("audio_file")

    args = parser.parse_args()

    if args.command == "transcribe":
        cmd_transcribe(args.audio_file, args.language, args.output)
    elif args.command == "summary":
        cmd_summary(args.transcript_file)
    elif args.command == "speakers":
        cmd_speakers(args.audio_file)


if __name__ == "__main__":
    main()
