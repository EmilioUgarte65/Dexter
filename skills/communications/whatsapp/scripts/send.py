#!/usr/bin/env python3
"""
Dexter — WhatsApp sender via Baileys-compatible HTTP API.
Uses stdlib only (urllib, mimetypes). No external dependencies.

Usage:
  send.py send <phone> <message>
  send.py send-media <phone> <file> [caption]
  send.py status
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import mimetypes
import uuid
from typing import Any, Optional

# ─── Config from env ──────────────────────────────────────────────────────────

API_URL = os.environ.get("WHATSAPP_API_URL", "http://localhost:3000").rstrip("/")
SESSION = os.environ.get("WHATSAPP_SESSION", "dexter")

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"


def check_config():
    # API_URL has a default so no strict requirement, but warn if unreachable later
    pass


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def api_post(endpoint: str, payload: dict) -> Any:
    url = f"{API_URL}{endpoint}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"{RED}API error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach WhatsApp API at {API_URL}: {e.reason}{RESET}", file=sys.stderr)
        print("Check: WHATSAPP_API_URL is correct and the Baileys server is running.", file=sys.stderr)
        sys.exit(1)


def api_get(endpoint: str) -> Any:
    url = f"{API_URL}{endpoint}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"{RED}API error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach WhatsApp API at {API_URL}: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def api_post_multipart(endpoint: str, fields: dict, file_path: str) -> Any:
    """Upload a file using multipart/form-data (stdlib only)."""
    url = f"{API_URL}{endpoint}"
    boundary = uuid.uuid4().hex

    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"
    filename = os.path.basename(file_path)

    body_parts = []
    for key, value in fields.items():
        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
            f"{value}\r\n"
        )

    with open(file_path, "rb") as f:
        file_data = f.read()

    file_part = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    body = "".join(body_parts).encode() + file_part

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = resp.read().decode()
            return json.loads(result) if result.strip() else {}
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        print(f"{RED}API error {e.code}: {body_err}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach WhatsApp API at {API_URL}: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_send(phone: str, message: str):
    # Normalize phone: strip leading +
    phone = phone.lstrip("+")
    payload = {
        "session": SESSION,
        "to": f"{phone}@c.us",
        "text": message,
    }
    result = api_post("/api/sendText", payload)
    print(f"{GREEN}Sent to {phone}: {message[:60]}{'...' if len(message) > 60 else ''}{RESET}")
    if result.get("id"):
        print(f"  Message ID: {result['id']}")


def cmd_send_media(phone: str, file_path: str, caption: Optional[str] = None):
    if not os.path.isfile(file_path):
        print(f"{RED}File not found: {file_path}{RESET}", file=sys.stderr)
        sys.exit(1)

    phone = phone.lstrip("+")
    fields = {
        "session": SESSION,
        "to": f"{phone}@c.us",
    }
    if caption:
        fields["caption"] = caption

    result = api_post_multipart("/api/sendFile", fields, file_path)
    filename = os.path.basename(file_path)
    print(f"{GREEN}Sent {filename} to {phone}{RESET}")
    if caption:
        print(f"  Caption: {caption}")
    if result.get("id"):
        print(f"  Message ID: {result['id']}")


def cmd_status():
    result = api_get(f"/api/session/{SESSION}/status")
    status = result.get("status", result.get("state", "unknown"))
    connected = status in ("CONNECTED", "connected", "open", "OPEN")
    color = GREEN if connected else RED
    print(f"Session: {SESSION}")
    print(f"Status:  {color}{status}{RESET}")
    if result.get("pushname"):
        print(f"Name:    {result['pushname']}")
    if result.get("wid"):
        print(f"Phone:   {result['wid'].get('user', 'unknown')}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter WhatsApp CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # send
    p_send = subparsers.add_parser("send", help="Send a text message")
    p_send.add_argument("phone", help="Phone in international format without + (e.g. 5491112345678)")
    p_send.add_argument("message", help="Message text")

    # send-media
    p_media = subparsers.add_parser("send-media", help="Send a media file")
    p_media.add_argument("phone", help="Phone in international format without +")
    p_media.add_argument("file", help="Path to the file to send")
    p_media.add_argument("caption", nargs="?", help="Optional caption")

    # status
    subparsers.add_parser("status", help="Check session/connection status")

    args = parser.parse_args()
    check_config()

    if args.command == "send":
        cmd_send(args.phone, args.message)
    elif args.command == "send-media":
        cmd_send_media(args.phone, args.file, getattr(args, "caption", None))
    elif args.command == "status":
        cmd_status()


if __name__ == "__main__":
    main()
