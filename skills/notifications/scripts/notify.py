#!/usr/bin/env python3
"""
Dexter Notification Dispatcher — routes messages to the configured channel.
Uses stdlib only (urllib). No external dependencies.

Config: ~/.dexter/notifications.json
Supported channels: telegram, whatsapp, slack, discord, none

Usage:
  notify.py --event session_end --message "Session summary..."
  notify.py --event workflow_complete --message "Morning briefing sent ✅"
  notify.py --event audit_block --message "BLOCKED: curl exfiltration in evil-skill"
  notify.py --event error --message "Error in cron job"
  notify.py --list-events
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# ─── Config ───────────────────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / ".dexter" / "notifications.json"

VALID_EVENTS = {"session_end", "workflow_complete", "audit_block", "error"}


def load_config() -> Optional[dict]:
    """Load notifications config. Returns None if not found or channel is none."""
    if not CONFIG_PATH.exists():
        return None
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if cfg.get("channel", "none") == "none":
        return None
    return cfg


def is_event_enabled(cfg: dict, event: str) -> bool:
    return cfg.get("events", {}).get(event, True)


def format_message(cfg: dict, event: str, message: str) -> str:
    prefix = cfg.get("format", {}).get("prefix", "🤖 Dexter")
    max_len = cfg.get("format", {}).get("max_length", 4000)

    event_emoji = {
        "session_end": "📋",
        "workflow_complete": "✅",
        "audit_block": "🚨",
        "error": "❌",
    }.get(event, "ℹ️")

    full = f"{prefix} {event_emoji}\n\n{message}"
    if len(full) > max_len:
        full = full[: max_len - 3] + "..."
    return full


# ─── Channel senders ──────────────────────────────────────────────────────────

def _http_post(url: str, payload: dict, headers: Optional[dict] = None) -> bool:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception:
        return False


def send_telegram(cfg: dict, message: str) -> bool:
    tg = cfg.get("telegram", {})
    token = tg.get("bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = tg.get("chat_id") or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("notify: telegram missing bot_token or chat_id", file=sys.stderr)
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    return _http_post(url, {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    })


def send_whatsapp(cfg: dict, message: str) -> bool:
    wa = cfg.get("whatsapp", {})
    api_url = wa.get("api_url", "http://localhost:3000").rstrip("/")
    session = wa.get("session", "dexter")
    phone = wa.get("phone", "")
    if not phone:
        print("notify: whatsapp missing phone", file=sys.stderr)
        return False
    url = f"{api_url}/api/sendText"
    return _http_post(url, {
        "session": session,
        "to": phone,
        "text": message,
    })


def send_slack(cfg: dict, message: str) -> bool:
    webhook = cfg.get("slack", {}).get("webhook_url", "")
    if not webhook or webhook.startswith("https://hooks.slack.com/services/YOUR"):
        print("notify: slack webhook_url not configured", file=sys.stderr)
        return False
    return _http_post(webhook, {"text": message})


def send_discord(cfg: dict, message: str) -> bool:
    webhook = cfg.get("discord", {}).get("webhook_url", "")
    if not webhook or webhook.startswith("https://discord.com/api/webhooks/YOUR"):
        print("notify: discord webhook_url not configured", file=sys.stderr)
        return False
    return _http_post(webhook, {"content": message})


SENDERS = {
    "telegram": send_telegram,
    "whatsapp": send_whatsapp,
    "slack": send_slack,
    "discord": send_discord,
}


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Dexter notification dispatcher — routes messages to your configured channel"
    )
    parser.add_argument("--event", choices=list(VALID_EVENTS),
                        help="Event type triggering this notification")
    parser.add_argument("--message", "-m",
                        help="Message body to send")
    parser.add_argument("--list-events", action="store_true",
                        help="List supported event types")
    parser.add_argument("--channel",
                        help="Override channel from config (telegram|whatsapp|slack|discord)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be sent without sending")
    args = parser.parse_args()

    if args.list_events:
        print("Supported events:")
        for e in sorted(VALID_EVENTS):
            print(f"  {e}")
        sys.exit(0)

    if not args.event or not args.message:
        parser.print_help()
        sys.exit(1)

    cfg = load_config()
    if cfg is None:
        # No config or channel=none — silent exit, not an error
        sys.exit(0)

    if not is_event_enabled(cfg, args.event):
        sys.exit(0)

    channel = args.channel or cfg.get("channel", "none")
    if channel == "none":
        sys.exit(0)

    formatted = format_message(cfg, args.event, args.message)

    if args.dry_run:
        print(f"[dry-run] Would send via {channel}:")
        print(formatted)
        sys.exit(0)

    sender = SENDERS.get(channel)
    if not sender:
        print(f"notify: unknown channel '{channel}'", file=sys.stderr)
        sys.exit(1)

    ok = sender(cfg, formatted)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
