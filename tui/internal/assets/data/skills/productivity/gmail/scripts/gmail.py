#!/usr/bin/env python3
"""
Dexter — Gmail API client with OAuth2.
Tries google-auth-oauthlib first; falls back to raw OAuth2 device/browser flow.

Usage:
  gmail.py send <to> <subject> <body>
  gmail.py list [--limit N] [--query Q]
  gmail.py read <message_id>
  gmail.py search <query>
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
import base64
import email.mime.text
import email.mime.multipart
from typing import Any, Optional

# ─── Config from env ──────────────────────────────────────────────────────────

CREDENTIALS_FILE = os.environ.get("GMAIL_CREDENTIALS_FILE", os.path.expanduser("~/.config/dexter/gmail_credentials.json"))
TOKEN_FILE        = os.environ.get("GMAIL_TOKEN_FILE",       os.path.expanduser("~/.config/dexter/gmail_token.json"))

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

_token_cache: dict = {}


def check_config():
    if not os.path.isfile(CREDENTIALS_FILE):
        print(
            f"Error: GMAIL_CREDENTIALS_FILE not found at {CREDENTIALS_FILE}\n"
            "1. Go to https://console.cloud.google.com\n"
            "2. Enable Gmail API → Create OAuth2 credentials (Desktop app)\n"
            "3. Download and save as credentials.json\n"
            f"4. Set: export GMAIL_CREDENTIALS_FILE=/path/to/credentials.json",
            file=sys.stderr,
        )
        sys.exit(1)


# ─── OAuth2 ───────────────────────────────────────────────────────────────────

def _load_credentials_json() -> dict:
    with open(CREDENTIALS_FILE) as f:
        data = json.load(f)
    # Supports "installed" and "web" credential types
    return data.get("installed") or data.get("web") or data


def _save_token(token: dict):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(token, f, indent=2)


def _load_token() -> Optional[dict]:
    if os.path.isfile(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return None


def _refresh_token(creds_json: dict, refresh_token: str) -> dict:
    data = urllib.parse.urlencode({
        "client_id": creds_json["client_id"],
        "client_secret": creds_json["client_secret"],
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _authorize_new(creds_json: dict) -> dict:
    """Attempt google-auth-oauthlib first; fall back to manual browser flow."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        credentials = flow.run_local_server(port=0)
        token = {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
        }
        return token
    except ImportError:
        pass

    # Fallback: manual browser flow
    auth_url = (
        "https://accounts.google.com/o/oauth2/auth?"
        + urllib.parse.urlencode({
            "client_id": creds_json["client_id"],
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
        })
    )
    print(f"\nOpen this URL in your browser:\n\n  {auth_url}\n")
    code = input("Paste the authorization code here: ").strip()

    data = urllib.parse.urlencode({
        "client_id": creds_json["client_id"],
        "client_secret": creds_json["client_secret"],
        "code": code,
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def get_access_token() -> str:
    global _token_cache

    if _token_cache.get("access_token"):
        return _token_cache["access_token"]

    creds_json = _load_credentials_json()
    token = _load_token()

    if token and token.get("refresh_token"):
        try:
            refreshed = _refresh_token(creds_json, token["refresh_token"])
            token.update(refreshed)
            _save_token(token)
            _token_cache = token
            return token["access_token"]
        except Exception as e:
            print(f"Token refresh failed: {e}. Re-authorizing...", file=sys.stderr)

    # Need fresh authorization
    token = _authorize_new(creds_json)
    _save_token(token)
    _token_cache = token
    return token["access_token"]


# ─── Gmail API helpers ────────────────────────────────────────────────────────

def gmail_get(endpoint: str, params: Optional[dict] = None) -> Any:
    access_token = get_access_token()
    url = f"https://gmail.googleapis.com/gmail/v1{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"{RED}Gmail API error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Gmail API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def gmail_post(endpoint: str, payload: dict) -> Any:
    access_token = get_access_token()
    url = f"https://gmail.googleapis.com/gmail/v1{endpoint}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"{RED}Gmail API error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Gmail API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_send(to: str, subject: str, body: str):
    msg = email.mime.text.MIMEText(body)
    msg["To"] = to
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    result = gmail_post("/users/me/messages/send", {"raw": raw})
    msg_id = result.get("id", "?")
    print(f"{GREEN}Email sent to {to}{RESET}")
    print(f"  Subject:    {subject}")
    print(f"  Message ID: {msg_id}")


def cmd_list(limit: int = 10, query: Optional[str] = None):
    params: dict = {"maxResults": limit, "labelIds": "INBOX"}
    if query:
        params["q"] = query

    result = gmail_get("/users/me/messages", params)
    messages = result.get("messages", [])
    if not messages:
        print("No messages found.")
        return

    print(f"\n  {'ID':<20} {'FROM':<35} SUBJECT")
    print("  " + "-" * 80)
    for m in messages:
        detail = gmail_get(f"/users/me/messages/{m['id']}", {"format": "metadata", "metadataHeaders": "From,Subject,Date"})
        headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
        from_hdr    = headers.get("From", "?")[:33]
        subject_hdr = headers.get("Subject", "(no subject)")[:40]
        print(f"  {m['id']:<20} {from_hdr:<35} {subject_hdr}")


def cmd_read(message_id: str):
    result = gmail_get(f"/users/me/messages/{message_id}", {"format": "full"})
    headers = {h["name"]: h["value"] for h in result.get("payload", {}).get("headers", [])}

    print(f"\nFrom:    {headers.get('From', '?')}")
    print(f"To:      {headers.get('To', '?')}")
    print(f"Date:    {headers.get('Date', '?')}")
    print(f"Subject: {headers.get('Subject', '?')}")
    print(f"\n{'─' * 60}")

    # Extract body
    payload = result.get("payload", {})
    body_data = _extract_body(payload)
    if body_data:
        print(body_data)
    else:
        print("[No text body found]")


def _extract_body(payload: dict) -> Optional[str]:
    """Recursively extract plain text body from Gmail message payload."""
    mime = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data", "")

    if mime == "text/plain" and data:
        return base64.urlsafe_b64decode(data + "==").decode(errors="replace")

    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result

    return None


def cmd_search(query: str):
    result = gmail_get("/users/me/messages", {"q": query, "maxResults": 20})
    messages = result.get("messages", [])
    total = result.get("resultSizeEstimate", 0)

    if not messages:
        print(f"No messages found for: {query}")
        return

    print(f"\nFound ~{total} result(s) for: {query}\n")
    print(f"  {'ID':<20} {'FROM':<35} SUBJECT")
    print("  " + "-" * 80)
    for m in messages:
        detail = gmail_get(f"/users/me/messages/{m['id']}", {"format": "metadata", "metadataHeaders": "From,Subject"})
        headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
        from_hdr    = headers.get("From", "?")[:33]
        subject_hdr = headers.get("Subject", "(no subject)")[:40]
        print(f"  {m['id']:<20} {from_hdr:<35} {subject_hdr}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    check_config()

    parser = argparse.ArgumentParser(description="Dexter Gmail CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # send
    p_send = subparsers.add_parser("send", help="Send an email")
    p_send.add_argument("to", help="Recipient email address")
    p_send.add_argument("subject", help="Email subject")
    p_send.add_argument("body", help="Email body (plain text)")

    # list
    p_list = subparsers.add_parser("list", help="List inbox messages")
    p_list.add_argument("--limit", type=int, default=10, help="Number of messages to list (default: 10)")
    p_list.add_argument("--query", help="Gmail search query (e.g. 'is:unread from:boss@company.com')")

    # read
    p_read = subparsers.add_parser("read", help="Read a specific message")
    p_read.add_argument("message_id", help="Gmail message ID (from list output)")

    # search
    p_search = subparsers.add_parser("search", help="Search messages")
    p_search.add_argument("query", help="Gmail search query")

    args = parser.parse_args()

    if args.command == "send":
        cmd_send(args.to, args.subject, args.body)
    elif args.command == "list":
        cmd_list(limit=args.limit, query=getattr(args, "query", None))
    elif args.command == "read":
        cmd_read(args.message_id)
    elif args.command == "search":
        cmd_search(args.query)


if __name__ == "__main__":
    main()
