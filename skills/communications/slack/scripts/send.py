#!/usr/bin/env python3
"""
Dexter — Slack Web API client.
Uses stdlib only (urllib). No external dependencies.

Usage:
  send.py send <channel> <message>
  send.py send-file <channel> <file> [title]
  send.py list-channels
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
import uuid
import mimetypes
from typing import Any, Optional

# ─── Config from env ──────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
DEFAULT_CHANNEL = os.environ.get("SLACK_DEFAULT_CHANNEL", "")

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"

BASE_URL = "https://slack.com/api"


def check_config():
    if not BOT_TOKEN:
        print(
            "Error: SLACK_BOT_TOKEN not set.\n"
            "Create a Slack App at https://api.slack.com/apps, add bot scopes,\n"
            "install to workspace, then:\n"
            "  export SLACK_BOT_TOKEN=xoxb-...",
            file=sys.stderr,
        )
        sys.exit(1)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def slack_post(method: str, payload: dict) -> Any:
    url = f"{BASE_URL}/{method}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {BOT_TOKEN}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
            result = json.loads(body)
            if not result.get("ok"):
                error = result.get("error", "unknown")
                print(f"{RED}Slack error: {error}{RESET}", file=sys.stderr)
                sys.exit(1)
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Slack API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def slack_get(method: str, params: Optional[dict] = None) -> Any:
    url = f"{BASE_URL}/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {BOT_TOKEN}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
            result = json.loads(body)
            if not result.get("ok"):
                error = result.get("error", "unknown")
                print(f"{RED}Slack error: {error}{RESET}", file=sys.stderr)
                sys.exit(1)
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Slack API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def slack_upload_multipart(channel: str, file_path: str, title: Optional[str] = None) -> Any:
    """Upload a file using multipart/form-data (stdlib only)."""
    url = f"{BASE_URL}/files.upload"
    boundary = uuid.uuid4().hex
    filename = os.path.basename(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"

    with open(file_path, "rb") as f:
        file_data = f.read()

    # Build multipart body
    parts = b""
    text_fields = {"channels": channel}
    if title:
        text_fields["title"] = title
    text_fields["filename"] = filename

    for key, value in text_fields.items():
        parts += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
            f"{value}\r\n"
        ).encode()

    parts += (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        url,
        data=parts,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {BOT_TOKEN}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            result = json.loads(body)
            if not result.get("ok"):
                print(f"{RED}Slack error: {result.get('error', 'unknown')}{RESET}", file=sys.stderr)
                sys.exit(1)
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Slack API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def resolve_channel(channel: str) -> str:
    if channel:
        return channel
    if DEFAULT_CHANNEL:
        return DEFAULT_CHANNEL
    print(f"{RED}No channel provided and SLACK_DEFAULT_CHANNEL is not set.{RESET}", file=sys.stderr)
    sys.exit(1)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_send(channel: str, message: str):
    ch = resolve_channel(channel)
    result = slack_post("chat.postMessage", {"channel": ch, "text": message})
    ts = result.get("ts", "?")
    preview = message[:60] + ("..." if len(message) > 60 else "")
    print(f"{GREEN}Posted to {ch} (ts={ts}): {preview}{RESET}")


def cmd_send_file(channel: str, file_path: str, title: Optional[str] = None):
    if not os.path.isfile(file_path):
        print(f"{RED}File not found: {file_path}{RESET}", file=sys.stderr)
        sys.exit(1)

    ch = resolve_channel(channel)
    result = slack_upload_multipart(ch, file_path, title)
    filename = os.path.basename(file_path)
    file_id = result.get("file", {}).get("id", "?")
    print(f"{GREEN}Uploaded {filename} to {ch} (file_id={file_id}){RESET}")
    if title:
        print(f"  Title: {title}")


def cmd_list_channels():
    result = slack_get("conversations.list", {"types": "public_channel,private_channel", "limit": 200})
    channels = result.get("channels", [])
    if not channels:
        print("No channels found.")
        return

    print(f"\n  {'CHANNEL':<40} {'ID':<15} TYPE")
    print("  " + "-" * 65)
    for ch in sorted(channels, key=lambda c: c.get("name", "")):
        name = ch.get("name", "?")
        cid = ch.get("id", "?")
        is_private = ch.get("is_private", False)
        is_member = ch.get("is_member", False)
        ch_type = "private" if is_private else "public"
        member_mark = f" {GREEN}(member){RESET}" if is_member else ""
        print(f"  #{name:<39} {cid:<15} {ch_type}{member_mark}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter Slack CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # send
    p_send = subparsers.add_parser("send", help="Send a message to a channel")
    p_send.add_argument("channel", help="Channel name (#general) or ID, or empty for default")
    p_send.add_argument("message", help="Message text (mrkdwn supported)")

    # send-file
    p_file = subparsers.add_parser("send-file", help="Upload a file to a channel")
    p_file.add_argument("channel", help="Channel name or ID, or empty for default")
    p_file.add_argument("file", help="Path to the file")
    p_file.add_argument("title", nargs="?", help="Optional file title")

    # list-channels
    subparsers.add_parser("list-channels", help="List all accessible channels")

    args = parser.parse_args()
    check_config()

    if args.command == "send":
        cmd_send(args.channel, args.message)
    elif args.command == "send-file":
        cmd_send_file(args.channel, args.file, getattr(args, "title", None))
    elif args.command == "list-channels":
        cmd_list_channels()


if __name__ == "__main__":
    main()
