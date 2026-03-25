#!/usr/bin/env python3
"""
Dexter — Signal CLI client.
Wraps signal-cli via subprocess. Requires signal-cli on PATH.

Usage:
  send.py send <recipient> <message>
  send.py send-media <recipient> <file> [--caption TEXT]
  send.py status
"""

import sys
import os
import json
import argparse
import subprocess
import shutil
import re
from typing import Optional

# ─── Config from env ──────────────────────────────────────────────────────────

SIGNAL_NUMBER   = os.environ.get("SIGNAL_NUMBER", "")
ALLOWLIST_RAW   = os.environ.get("SIGNAL_ALLOWLIST", "")
ALLOWLIST: list[str] = [n.strip() for n in ALLOWLIST_RAW.split(",") if n.strip()] if ALLOWLIST_RAW else []

GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

E164_RE = re.compile(r"^\+\d{7,15}$")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def check_config() -> str:
    if not SIGNAL_NUMBER:
        print(
            f"{RED}Error: SIGNAL_NUMBER not set.\n"
            "Set your registered Signal number:\n"
            f"  export SIGNAL_NUMBER=+1234567890{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    cli = shutil.which("signal-cli") or "/usr/local/bin/signal-cli"
    if not os.path.isfile(cli) and not shutil.which("signal-cli"):
        print(
            f"{RED}Error: signal-cli not found on PATH.\n"
            "Install from https://github.com/AsamK/signal-cli/releases{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)
    return cli


def validate_recipient(recipient: str) -> None:
    if not E164_RE.match(recipient):
        print(
            f"{RED}Error: recipient '{recipient}' is not a valid E.164 number "
            f"(e.g. +1234567890).{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    if ALLOWLIST and recipient not in ALLOWLIST:
        print(
            f"{YELLOW}⚠  Security warning: '{recipient}' is NOT in SIGNAL_ALLOWLIST.\n"
            f"   Allowed numbers: {', '.join(ALLOWLIST)}\n"
            f"   Message NOT sent.{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)


def run_signal_cli(cli: str, args: list[str]) -> dict:
    cmd = [cli, "--output=json", "-u", SIGNAL_NUMBER] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        print(f"{RED}Error: signal-cli timed out.{RESET}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"{RED}Error: signal-cli executable not found: {cli}{RESET}", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        print(f"{RED}signal-cli error (exit {result.returncode}):\n{stderr}{RESET}", file=sys.stderr)
        sys.exit(1)

    stdout = result.stdout.strip()
    if stdout:
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {"raw": stdout}
    return {}


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_send(cli: str, recipient: str, message: str) -> None:
    validate_recipient(recipient)
    run_signal_cli(cli, ["send", "-m", message, recipient])
    preview = message[:60] + ("..." if len(message) > 60 else "")
    print(f"{GREEN}Sent to {recipient}: {preview}{RESET}")


def cmd_send_media(cli: str, recipient: str, file_path: str, caption: Optional[str]) -> None:
    validate_recipient(recipient)

    if not os.path.isfile(file_path):
        print(f"{RED}Error: file not found: {file_path}{RESET}", file=sys.stderr)
        sys.exit(1)

    args = ["send", "-a", file_path]
    if caption:
        args += ["-m", caption]
    args.append(recipient)

    run_signal_cli(cli, args)
    filename = os.path.basename(file_path)
    print(f"{GREEN}Sent {filename} to {recipient}"
          + (f" (caption: {caption[:40]})" if caption else "")
          + f"{RESET}")


def cmd_status(cli: str) -> None:
    data = run_signal_cli(cli, ["listDevices"])
    raw = data.get("raw", "")
    if raw:
        print(raw)
        return

    devices = data if isinstance(data, list) else data.get("devices", [data])
    if not devices:
        print("No linked devices found.")
        return

    print(f"Linked devices for {SIGNAL_NUMBER}:\n")
    for dev in devices:
        if not isinstance(dev, dict):
            print(f"  {dev}")
            continue
        did   = dev.get("id", "?")
        name  = dev.get("name", "unnamed")
        last  = dev.get("lastSeen", "?")
        created = dev.get("created", "?")
        print(f"  Device {did}: {name}")
        print(f"    Created:   {created}")
        print(f"    Last seen: {last}")
        print()


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Dexter Signal CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # send
    p_send = subparsers.add_parser("send", help="Send a text message")
    p_send.add_argument("recipient", help="Recipient phone number (E.164, e.g. +1234567890)")
    p_send.add_argument("message", help="Text to send")

    # send-media
    p_media = subparsers.add_parser("send-media", help="Send a file attachment")
    p_media.add_argument("recipient", help="Recipient phone number (E.164)")
    p_media.add_argument("file", help="Path to the file to send")
    p_media.add_argument("--caption", default=None, help="Optional caption for the attachment")

    # status
    subparsers.add_parser("status", help="List linked devices for the registered number")

    args = parser.parse_args()
    cli = check_config()

    if args.command == "send":
        cmd_send(cli, args.recipient, args.message)
    elif args.command == "send-media":
        cmd_send_media(cli, args.recipient, args.file, args.caption)
    elif args.command == "status":
        cmd_status(cli)


if __name__ == "__main__":
    main()
