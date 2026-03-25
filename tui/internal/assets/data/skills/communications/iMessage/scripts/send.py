#!/usr/bin/env python3
"""
Dexter — iMessage client via osascript (macOS only).
Sends text messages through Messages.app. No media support.

Usage:
  send.py send <recipient> <message>

recipient: E.164 phone number (+1234567890) or Apple ID email address.
"""

import sys
import os
import platform
import argparse
import subprocess
import re
from typing import Optional

# ─── Config from env ──────────────────────────────────────────────────────────

ALLOWLIST_RAW = os.environ.get("IMESSAGE_ALLOWLIST", "")
ALLOWLIST: list[str] = [r.strip() for r in ALLOWLIST_RAW.split(",") if r.strip()] if ALLOWLIST_RAW else []

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

E164_RE  = re.compile(r"^\+\d{7,15}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def check_platform() -> None:
    if platform.system() != "Darwin":
        print(
            f"{RED}Error: iMessage is macOS only.\n"
            f"Current platform: {platform.system()}\n"
            "Use a different communication skill on this OS.{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)


def validate_recipient(recipient: str) -> None:
    is_phone = bool(E164_RE.match(recipient))
    is_email = bool(EMAIL_RE.match(recipient))

    if not is_phone and not is_email:
        print(
            f"{RED}Error: '{recipient}' is not a valid recipient.\n"
            "Provide an E.164 phone number (e.g. +1234567890) "
            f"or an Apple ID email address.{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    if ALLOWLIST and recipient not in ALLOWLIST:
        print(
            f"{YELLOW}⚠  Security warning: '{recipient}' is NOT in IMESSAGE_ALLOWLIST.\n"
            f"   Allowed recipients: {', '.join(ALLOWLIST)}\n"
            f"   Message NOT sent.{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)


def build_applescript(recipient: str, message: str) -> str:
    # Escape backslashes and double quotes for AppleScript string embedding
    safe_recipient = recipient.replace("\\", "\\\\").replace('"', '\\"')
    safe_message   = message.replace("\\", "\\\\").replace('"', '\\"')
    return (
        'tell application "Messages"\n'
        f'    set targetService to 1st service whose service type = iMessage\n'
        f'    set targetBuddy to buddy "{safe_recipient}" of targetService\n'
        f'    send "{safe_message}" to targetBuddy\n'
        'end tell'
    )


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_send(recipient: str, message: str) -> None:
    check_platform()
    validate_recipient(recipient)

    script = build_applescript(recipient, message)
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        print(f"{RED}Error: osascript timed out. Is Messages.app responding?{RESET}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"{RED}Error: osascript not found. Are you on macOS?{RESET}", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        # Common failure: Automation permission not granted
        if "not allowed" in stderr.lower() or "1743" in stderr:
            print(
                f"{RED}Error: Terminal is not allowed to control Messages.app.\n"
                "Grant Automation permission:\n"
                "  System Settings → Privacy & Security → Automation\n"
                f"Details: {stderr}{RESET}",
                file=sys.stderr,
            )
        else:
            print(f"{RED}osascript error:\n{stderr}{RESET}", file=sys.stderr)
        sys.exit(1)

    preview = message[:60] + ("..." if len(message) > 60 else "")
    print(f"{GREEN}Sent to {recipient}: {preview}{RESET}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Dexter iMessage CLI (macOS only)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_send = subparsers.add_parser("send", help="Send a text message via Messages.app")
    p_send.add_argument(
        "recipient",
        help="Phone number (E.164, e.g. +1234567890) or Apple ID email",
    )
    p_send.add_argument("message", help="Text to send (no media supported)")

    args = parser.parse_args()

    if args.command == "send":
        cmd_send(args.recipient, args.message)


if __name__ == "__main__":
    main()
