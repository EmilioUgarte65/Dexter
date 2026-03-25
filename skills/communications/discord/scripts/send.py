#!/usr/bin/env python3
"""
Dexter — Discord Webhook client.
Uses stdlib only (urllib). No external dependencies.

Usage:
  send.py send <message> [--username NAME]
  send.py send-embed <title> <description> [--color hex]
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
from typing import Optional

# ─── Config from env ──────────────────────────────────────────────────────────

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"

DEFAULT_COLOR = 0x5865F2  # Discord blurple


def check_config():
    if not WEBHOOK_URL:
        print(
            "Error: DISCORD_WEBHOOK_URL not set.\n"
            "Create a webhook in your Discord channel settings, then:\n"
            "  export DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...",
            file=sys.stderr,
        )
        sys.exit(1)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def webhook_post(payload: dict) -> None:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            # Discord returns 204 No Content on success
            resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            print(f"{RED}Discord error {e.code}: {err.get('message', body)}{RESET}", file=sys.stderr)
        except Exception:
            print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Discord webhook: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def parse_color(hex_str: str) -> int:
    """Parse a hex color string (with or without #) to integer."""
    hex_str = hex_str.lstrip("#")
    try:
        return int(hex_str, 16)
    except ValueError:
        print(f"{RED}Invalid color: {hex_str}. Use hex like FF0000 or 00FF00{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_send(message: str, username: Optional[str] = None):
    payload: dict = {"content": message}
    if username:
        payload["username"] = username

    webhook_post(payload)
    preview = message[:60] + ("..." if len(message) > 60 else "")
    name_str = f" (as {username})" if username else ""
    print(f"{GREEN}Sent to Discord{name_str}: {preview}{RESET}")


def cmd_send_embed(title: str, description: str, color_hex: Optional[str] = None):
    color = parse_color(color_hex) if color_hex else DEFAULT_COLOR
    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
            }
        ]
    }
    webhook_post(payload)
    print(f"{GREEN}Sent embed to Discord:{RESET}")
    print(f"  Title:       {title}")
    print(f"  Description: {description[:60]}{'...' if len(description) > 60 else ''}")
    print(f"  Color:       #{color:06X}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter Discord Webhook CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # send
    p_send = subparsers.add_parser("send", help="Send a plain message")
    p_send.add_argument("message", help="Message content")
    p_send.add_argument("--username", help="Override the webhook display name")

    # send-embed
    p_embed = subparsers.add_parser("send-embed", help="Send a rich embed")
    p_embed.add_argument("title", help="Embed title")
    p_embed.add_argument("description", help="Embed description/body")
    p_embed.add_argument("--color", dest="color", help="Embed color as hex (e.g. FF0000 for red)")

    args = parser.parse_args()
    check_config()

    if args.command == "send":
        cmd_send(args.message, username=getattr(args, "username", None))
    elif args.command == "send-embed":
        cmd_send_embed(args.title, args.description, color_hex=getattr(args, "color", None))


if __name__ == "__main__":
    main()
