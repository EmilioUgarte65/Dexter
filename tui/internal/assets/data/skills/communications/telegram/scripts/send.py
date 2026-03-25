#!/usr/bin/env python3
"""
Dexter — Telegram Bot API client.
Uses stdlib only (urllib). No external dependencies.

Usage:
  send.py send <chat_id> <message>
  send.py send-file <chat_id> <file>
  send.py get-updates [--limit N]
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import uuid
import mimetypes
from typing import Any, Optional

# ─── Config from env ──────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
DEFAULT_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"

BASE_URL = "https://api.telegram.org"


def check_config():
    if not BOT_TOKEN:
        print(
            "Error: TELEGRAM_BOT_TOKEN not set.\n"
            "Get one from @BotFather on Telegram, then:\n"
            "  export TELEGRAM_BOT_TOKEN=123456:ABC...",
            file=sys.stderr,
        )
        sys.exit(1)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def tg_request(method: str, payload: Optional[dict] = None) -> Any:
    url = f"{BASE_URL}/bot{BOT_TOKEN}/{method}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
            result = json.loads(body)
            if not result.get("ok"):
                print(f"{RED}Telegram error: {result.get('description', 'unknown')}{RESET}", file=sys.stderr)
                sys.exit(1)
            return result.get("result")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            print(f"{RED}Telegram error {e.code}: {err.get('description', body)}{RESET}", file=sys.stderr)
        except Exception:
            print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Telegram API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def tg_post_multipart(method: str, fields: dict, file_field: str, file_path: str) -> Any:
    """Send multipart/form-data with a file attachment (stdlib only)."""
    url = f"{BASE_URL}/bot{BOT_TOKEN}/{method}"
    boundary = uuid.uuid4().hex

    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"
    filename = os.path.basename(file_path)

    body_parts = b""
    for key, value in fields.items():
        body_parts += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
            f"{value}\r\n"
        ).encode()

    with open(file_path, "rb") as f:
        file_data = f.read()

    body_parts += (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        url,
        data=body_parts,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            result = json.loads(body)
            if not result.get("ok"):
                print(f"{RED}Telegram error: {result.get('description', 'unknown')}{RESET}", file=sys.stderr)
                sys.exit(1)
            return result.get("result")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Telegram API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def resolve_chat(chat_id: str) -> str:
    if chat_id:
        return chat_id
    if DEFAULT_CHAT_ID:
        return DEFAULT_CHAT_ID
    print(f"{RED}No chat_id provided and TELEGRAM_CHAT_ID is not set.{RESET}", file=sys.stderr)
    sys.exit(1)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_send(chat_id: str, message: str):
    cid = resolve_chat(chat_id)
    result = tg_request("sendMessage", {"chat_id": cid, "text": message, "parse_mode": "HTML"})
    msg_id = result.get("message_id", "?")
    preview = message[:60] + ("..." if len(message) > 60 else "")
    print(f"{GREEN}Sent to {cid} (message_id={msg_id}): {preview}{RESET}")


def cmd_send_file(chat_id: str, file_path: str):
    if not os.path.isfile(file_path):
        print(f"{RED}File not found: {file_path}{RESET}", file=sys.stderr)
        sys.exit(1)

    cid = resolve_chat(chat_id)
    filename = os.path.basename(file_path)
    mime, _ = mimetypes.guess_type(file_path)

    # Choose method based on mime type
    if mime and mime.startswith("image/"):
        method = "sendPhoto"
        file_field = "photo"
    elif mime and mime.startswith("audio/"):
        method = "sendAudio"
        file_field = "audio"
    elif mime and mime.startswith("video/"):
        method = "sendVideo"
        file_field = "video"
    else:
        method = "sendDocument"
        file_field = "document"

    result = tg_post_multipart(method, {"chat_id": cid}, file_field, file_path)
    msg_id = result.get("message_id", "?")
    print(f"{GREEN}Sent {filename} to {cid} (message_id={msg_id}){RESET}")


def cmd_get_updates(limit: int = 10):
    result = tg_request("getUpdates", {"limit": limit, "timeout": 0})
    if not result:
        print("No updates found. Send a message to your bot first.")
        return

    print(f"Last {len(result)} update(s):\n")
    for update in result:
        upd_id = update.get("update_id", "?")
        msg = update.get("message", {})
        chat = msg.get("chat", {})
        from_user = msg.get("from", {})
        text = msg.get("text", "[non-text]")

        chat_id = chat.get("id", "?")
        chat_type = chat.get("type", "?")
        username = from_user.get("username", from_user.get("first_name", "?"))

        print(f"  update_id: {upd_id}")
        print(f"  chat_id:   {GREEN}{chat_id}{RESET}  (type: {chat_type})")
        print(f"  from:      @{username}")
        print(f"  text:      {text[:80]}")
        print()


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    check_config()

    parser = argparse.ArgumentParser(description="Dexter Telegram CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # send
    p_send = subparsers.add_parser("send", help="Send a text message")
    p_send.add_argument("chat_id", help="Chat ID (or empty string to use TELEGRAM_CHAT_ID)")
    p_send.add_argument("message", help="Message text (HTML supported)")

    # send-file
    p_file = subparsers.add_parser("send-file", help="Send a file")
    p_file.add_argument("chat_id", help="Chat ID (or empty string to use TELEGRAM_CHAT_ID)")
    p_file.add_argument("file", help="Path to the file")

    # get-updates
    p_updates = subparsers.add_parser("get-updates", help="Get recent bot updates")
    p_updates.add_argument("--limit", type=int, default=10, help="Number of updates to fetch (default: 10)")

    args = parser.parse_args()

    if args.command == "send":
        cmd_send(args.chat_id, args.message)
    elif args.command == "send-file":
        cmd_send_file(args.chat_id, args.file)
    elif args.command == "get-updates":
        cmd_get_updates(limit=args.limit)


if __name__ == "__main__":
    main()
