#!/usr/bin/env python3
"""
Dexter — Microsoft Outlook / Graph API client.
Uses stdlib only (urllib). No external dependencies.
Authenticates via OAuth2 device flow; caches token at ~/.dexter/outlook_token.json.

Usage:
  send.py send --to <email> --subject <subject> --body <body>
  send.py list-inbox [--limit N]
  send.py read <message_id>
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
import time
from pathlib import Path
from typing import Any, Optional

# ─── Config from env ──────────────────────────────────────────────────────────

CLIENT_ID     = os.environ.get("OUTLOOK_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("OUTLOOK_CLIENT_SECRET", "")
TENANT_ID     = os.environ.get("OUTLOOK_TENANT_ID", "")

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

GRAPH_BASE   = "https://graph.microsoft.com/v1.0"
TOKEN_URL    = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
DEVICE_URL   = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/devicecode"
SCOPE        = "https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/Mail.Send offline_access"
TOKEN_CACHE  = Path.home() / ".dexter" / "outlook_token.json"


def _mask(value: str) -> str:
    """Mask a credential string for safe logging."""
    if not value:
        return "(not set)"
    return value[:4] + "****"


def check_config():
    missing = []
    if not CLIENT_ID:
        missing.append("OUTLOOK_CLIENT_ID")
    if not CLIENT_SECRET:
        missing.append("OUTLOOK_CLIENT_SECRET")
    if not TENANT_ID:
        missing.append("OUTLOOK_TENANT_ID")
    if missing:
        for m in missing:
            print(f"{RED}Error: {m} is not set.{RESET}", file=sys.stderr)
        print(
            "\nRegister an app in Azure Portal and export:\n"
            "  export OUTLOOK_CLIENT_ID=...\n"
            "  export OUTLOOK_CLIENT_SECRET=...\n"
            "  export OUTLOOK_TENANT_ID=...",
            file=sys.stderr,
        )
        sys.exit(1)


# ─── OAuth2 token management ───────────────────────────────────────────────────

def _load_token_cache() -> Optional[dict]:
    if TOKEN_CACHE.exists():
        try:
            return json.loads(TOKEN_CACHE.read_text())
        except Exception:
            return None
    return None


def _save_token_cache(token_data: dict):
    TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_CACHE.write_text(json.dumps(token_data, indent=2))
    TOKEN_CACHE.chmod(0o600)


def _post_form(url: str, data: dict) -> dict:
    encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            print(f"{RED}Auth error {e.code}: {err.get('error_description', err.get('error', body))}{RESET}", file=sys.stderr)
        except Exception:
            print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)


def _refresh_token(refresh_token: str) -> Optional[dict]:
    result = _post_form(TOKEN_URL, {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": SCOPE,
    })
    if "access_token" in result:
        result["cached_at"] = int(time.time())
        return result
    return None


def _device_flow_auth() -> dict:
    """Run OAuth2 device flow and return token data."""
    device_resp = _post_form(DEVICE_URL, {
        "client_id": CLIENT_ID,
        "scope": SCOPE,
    })

    verification_uri = device_resp.get("verification_uri", "https://microsoft.com/devicelogin")
    user_code        = device_resp.get("user_code", "?")
    device_code      = device_resp.get("device_code", "")
    interval         = int(device_resp.get("interval", 5))
    expires_in       = int(device_resp.get("expires_in", 900))

    print(f"\n{YELLOW}Authentication required.{RESET}")
    print(f"  1. Open: {verification_uri}")
    print(f"  2. Enter code: {GREEN}{user_code}{RESET}")
    print(f"  Waiting for authorization (expires in {expires_in}s)...\n")

    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        result = _post_form(TOKEN_URL, {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        })
        if "access_token" in result:
            result["cached_at"] = int(time.time())
            return result
        error = result.get("error", "")
        if error == "authorization_pending":
            continue
        elif error == "slow_down":
            interval += 5
        else:
            print(f"{RED}Auth failed: {result.get('error_description', error)}{RESET}", file=sys.stderr)
            sys.exit(1)

    print(f"{RED}Device flow timed out.{RESET}", file=sys.stderr)
    sys.exit(1)


def get_access_token() -> str:
    """Return a valid access token, refreshing or re-authenticating as needed."""
    cached = _load_token_cache()
    if cached:
        cached_at  = cached.get("cached_at", 0)
        expires_in = int(cached.get("expires_in", 3600))
        if time.time() < cached_at + expires_in - 60:
            return cached["access_token"]
        # Try refresh
        refresh = cached.get("refresh_token")
        if refresh:
            refreshed = _refresh_token(refresh)
            if refreshed:
                _save_token_cache(refreshed)
                return refreshed["access_token"]

    # Full device flow
    token_data = _device_flow_auth()
    _save_token_cache(token_data)
    print(f"{GREEN}Authenticated and token cached.{RESET}")
    return token_data["access_token"]


# ─── Graph API helpers ─────────────────────────────────────────────────────────

def graph_get(endpoint: str, params: Optional[dict] = None) -> Any:
    token = get_access_token()
    url   = f"{GRAPH_BASE}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            msg = err.get("error", {}).get("message", body)
            print(f"{RED}Graph error {e.code}: {msg}{RESET}", file=sys.stderr)
        except Exception:
            print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Graph API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def graph_post(endpoint: str, payload: dict) -> Any:
    token = get_access_token()
    url   = f"{GRAPH_BASE}{endpoint}"
    data  = json.dumps(payload).encode()
    req   = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            msg = err.get("error", {}).get("message", body)
            print(f"{RED}Graph error {e.code}: {msg}{RESET}", file=sys.stderr)
        except Exception:
            print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Graph API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── External recipient check ──────────────────────────────────────────────────

def _warn_external_recipient(to_address: str):
    """Warn if the recipient appears to be outside the tenant domain."""
    # Retrieve the authenticated user's email to extract tenant domain
    me = graph_get("/me", {"$select": "mail,userPrincipalName"})
    my_email  = me.get("mail") or me.get("userPrincipalName") or ""
    my_domain = my_email.split("@")[-1].lower() if "@" in my_email else ""
    to_domain = to_address.split("@")[-1].lower() if "@" in to_address else ""

    if my_domain and to_domain and my_domain != to_domain:
        print(
            f"{YELLOW}Warning: recipient '{to_address}' appears to be external "
            f"(your domain: {my_domain}).{RESET}"
        )
        confirm = input("  Send anyway? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            sys.exit(0)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_send(to: str, subject: str, body: str):
    """Send an email via Graph API."""
    _warn_external_recipient(to)

    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": to}}],
        },
        "saveToSentItems": True,
    }
    graph_post("/me/sendMail", payload)
    print(f"{GREEN}Email sent to {to}.{RESET}")
    print(f"  Subject: {subject}")


def cmd_list_inbox(limit: int = 10):
    """List inbox messages."""
    data = graph_get(
        "/me/mailFolders/inbox/messages",
        {
            "$top": limit,
            "$select": "id,subject,from,receivedDateTime,isRead,bodyPreview",
            "$orderby": "receivedDateTime desc",
        },
    )
    messages = data.get("value", [])

    if not messages:
        print("Inbox is empty.")
        return

    print(f"\n  INBOX ({len(messages)} messages)\n")
    print(f"  {'READ':<6} {'FROM':<30} {'DATE':<12} SUBJECT")
    print("  " + "-" * 85)
    for msg in messages:
        is_read  = msg.get("isRead", True)
        sender   = msg.get("from", {}).get("emailAddress", {}).get("address", "?")[:28]
        received = msg.get("receivedDateTime", "?")[:10]
        subject  = msg.get("subject", "(no subject)")[:45]
        read_tag = " " if is_read else f"{GREEN}NEW{RESET}"
        print(f"  {read_tag:<6} {sender:<30} {received:<12} {subject}")
        msg_id = msg.get("id", "")
        print(f"  {'':6} ID: {msg_id[:60]}")
    print()


def cmd_read(message_id: str):
    """Read a specific message."""
    msg = graph_get(f"/me/messages/{message_id}", {
        "$select": "id,subject,from,toRecipients,receivedDateTime,body,isRead",
    })

    sender   = msg.get("from", {}).get("emailAddress", {}).get("address", "?")
    subject  = msg.get("subject", "(no subject)")
    received = msg.get("receivedDateTime", "?")[:19]
    body     = msg.get("body", {}).get("content", "").strip()
    to_list  = [r.get("emailAddress", {}).get("address", "?") for r in msg.get("toRecipients", [])]

    print(f"\n  MESSAGE\n")
    print(f"  From:    {sender}")
    print(f"  To:      {', '.join(to_list)}")
    print(f"  Subject: {subject}")
    print(f"  Date:    {received}")
    print(f"\n  {'─' * 70}\n")
    # Strip HTML tags for plain display
    import re
    plain = re.sub(r"<[^>]+>", "", body).strip()
    # Collapse excess blank lines
    plain = re.sub(r"\n{3,}", "\n\n", plain)
    for line in plain.splitlines()[:80]:
        print(f"  {line}")
    print()


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter Outlook CLI (Graph API)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # send
    p_send = subparsers.add_parser("send", help="Send an email")
    p_send.add_argument("--to", required=True, help="Recipient email address")
    p_send.add_argument("--subject", required=True, help="Email subject")
    p_send.add_argument("--body", required=True, help="Email body (plain text)")

    # list-inbox
    p_inbox = subparsers.add_parser("list-inbox", help="List inbox messages")
    p_inbox.add_argument("--limit", type=int, default=10, help="Number of messages to list (default: 10)")

    # read
    p_read = subparsers.add_parser("read", help="Read a specific message by ID")
    p_read.add_argument("message_id", help="Message ID (from list-inbox output)")

    args = parser.parse_args()
    check_config()

    if args.command == "send":
        cmd_send(args.to, args.subject, args.body)
    elif args.command == "list-inbox":
        cmd_list_inbox(limit=args.limit)
    elif args.command == "read":
        cmd_read(args.message_id)


if __name__ == "__main__":
    main()
