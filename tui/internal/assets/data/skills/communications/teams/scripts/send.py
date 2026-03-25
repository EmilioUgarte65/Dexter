#!/usr/bin/env python3
"""
Dexter — Microsoft Teams / Graph API client.
Uses stdlib only (urllib). No external dependencies.
Shares OAuth2 credentials and token cache with the outlook skill.

Usage:
  send.py list-teams
  send.py send-channel --team-id <id> --channel-id <id> --message <text>
  send.py send-chat --chat-id <id> --message <text>
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

GRAPH_BASE  = "https://graph.microsoft.com/v1.0"
TOKEN_URL   = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
DEVICE_URL  = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/devicecode"
SCOPE       = (
    "https://graph.microsoft.com/Team.ReadBasic.All "
    "https://graph.microsoft.com/ChannelMessage.Send "
    "https://graph.microsoft.com/Chat.ReadWrite "
    "offline_access"
)
# Shared token cache with outlook skill
TOKEN_CACHE = Path.home() / ".dexter" / "outlook_token.json"


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


# ─── OAuth2 token management (shared with outlook skill) ──────────────────────

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
        refresh = cached.get("refresh_token")
        if refresh:
            refreshed = _refresh_token(refresh)
            if refreshed:
                _save_token_cache(refreshed)
                return refreshed["access_token"]

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


# ─── External team check ───────────────────────────────────────────────────────

def _check_no_external_team(team_id: str):
    """Refuse to post if the team belongs to a different tenant."""
    try:
        team = graph_get(f"/teams/{team_id}", {"$select": "id,displayName,visibility"})
        # The team's tenant can be inferred from the token — if the Graph call succeeds
        # with our credentials, the team is in our tenant. Visibility check:
        visibility = team.get("visibility", "").lower()
        if visibility == "public":
            print(
                f"{YELLOW}Warning: team '{team.get('displayName', team_id)}' is PUBLIC.{RESET}"
            )
            confirm = input("  Post to this public team? [y/N] ").strip().lower()
            if confirm != "y":
                print("Aborted.")
                sys.exit(0)
    except SystemExit:
        # If the team is unreachable (different tenant), the graph_get above will have
        # already printed an error and called sys.exit(1). Let it propagate.
        raise


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_list_teams():
    """List all teams the authenticated user belongs to."""
    data = graph_get("/me/joinedTeams", {"$select": "id,displayName,description,visibility"})
    teams = data.get("value", [])

    if not teams:
        print("No teams found.")
        return

    print(f"\n  TEAMS ({len(teams)})\n")
    print(f"  {'VISIBILITY':<12} {'DISPLAY NAME':<35} ID")
    print("  " + "-" * 85)
    for team in teams:
        team_id     = team.get("id", "?")
        name        = team.get("displayName", "?")[:33]
        visibility  = team.get("visibility", "?").upper()
        vis_color   = YELLOW if visibility == "PUBLIC" else GREEN
        print(f"  {vis_color}{visibility:<12}{RESET} {name:<35} {team_id}")
    print()
    print("  Use the ID above with send-channel. Get channel IDs with:")
    print("  GET /teams/{team-id}/channels")


def cmd_send_channel(team_id: str, channel_id: str, message: str):
    """Send a message to a Teams channel."""
    _check_no_external_team(team_id)

    payload = {
        "body": {"content": message, "contentType": "text"},
    }
    result = graph_post(f"/teams/{team_id}/channels/{channel_id}/messages", payload)
    msg_id = result.get("id", "?")
    print(f"{GREEN}Message sent to channel.{RESET}")
    print(f"  Team:    {team_id}")
    print(f"  Channel: {channel_id}")
    print(f"  Msg ID:  {msg_id}")


def cmd_send_chat(chat_id: str, message: str):
    """Send a message to a Teams chat (1:1 or group)."""
    payload = {
        "body": {"content": message, "contentType": "text"},
    }
    result = graph_post(f"/chats/{chat_id}/messages", payload)
    msg_id = result.get("id", "?")
    print(f"{GREEN}Message sent to chat.{RESET}")
    print(f"  Chat ID: {chat_id}")
    print(f"  Msg ID:  {msg_id}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    check_config()

    parser = argparse.ArgumentParser(description="Dexter Teams CLI (Graph API)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-teams
    subparsers.add_parser("list-teams", help="List teams the authenticated user belongs to")

    # send-channel
    p_channel = subparsers.add_parser("send-channel", help="Send a message to a Teams channel")
    p_channel.add_argument("--team-id", required=True, dest="team_id", help="Team ID (GUID)")
    p_channel.add_argument("--channel-id", required=True, dest="channel_id", help="Channel ID")
    p_channel.add_argument("--message", required=True, help="Message text to send")

    # send-chat
    p_chat = subparsers.add_parser("send-chat", help="Send a message to a Teams chat")
    p_chat.add_argument("--chat-id", required=True, dest="chat_id", help="Chat ID (thread ID)")
    p_chat.add_argument("--message", required=True, help="Message text to send")

    args = parser.parse_args()

    if args.command == "list-teams":
        cmd_list_teams()
    elif args.command == "send-channel":
        cmd_send_channel(args.team_id, args.channel_id, args.message)
    elif args.command == "send-chat":
        cmd_send_chat(args.chat_id, args.message)


if __name__ == "__main__":
    main()
