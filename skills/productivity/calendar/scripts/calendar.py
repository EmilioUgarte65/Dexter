#!/usr/bin/env python3
"""
Dexter — Google Calendar client.
Uses google-api-python-client + OAuth2. Event content is never logged.

Dependencies:
  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

Usage:
  calendar.py list [--max-results N]
  calendar.py create <title> <date YYYY-MM-DD> <time HH:MM> [--description TEXT] [--duration MINUTES]
  calendar.py delete <event_id>
"""

import sys
import os
import argparse
import datetime
from typing import Any

# ─── Config from env ──────────────────────────────────────────────────────────

DEFAULT_CREDS_DIR  = os.path.expanduser("~/.config/dexter/calendar")
CREDENTIALS_FILE   = os.environ.get("GOOGLE_CREDENTIALS_FILE",
                                    os.path.join(DEFAULT_CREDS_DIR, "credentials.json"))
TOKEN_FILE         = os.environ.get("GOOGLE_TOKEN_FILE",
                                    os.path.join(DEFAULT_CREDS_DIR, "token.json"))
CALENDAR_ID        = os.environ.get("GOOGLE_CALENDAR_ID", "primary")

SCOPES = ["https://www.googleapis.com/auth/calendar"]

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"


# ─── Auth ─────────────────────────────────────────────────────────────────────

def get_service() -> Any:
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        print(
            f"{RED}Error: Google API client libraries not installed.\n"
            "Run: pip install google-api-python-client google-auth-httplib2 "
            f"google-auth-oauthlib{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.path.isfile(CREDENTIALS_FILE):
        print(
            f"{RED}Error: credentials.json not found at {CREDENTIALS_FILE}\n"
            "Download it from Google Cloud Console → APIs & Services → Credentials.\n"
            f"Then set: export GOOGLE_CREDENTIALS_FILE=/path/to/credentials.json{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    creds = None
    if os.path.isfile(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_list(max_results: int) -> None:
    service = get_service()
    now = datetime.datetime.utcnow().isoformat() + "Z"

    try:
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except Exception as e:
        print(f"{RED}Error fetching events: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    items = events_result.get("items", [])
    if not items:
        print("No upcoming events found.")
        return

    print(f"Next {len(items)} event(s) — {CALENDAR_ID}:\n")
    for item in items:
        event_id = item.get("id", "?")
        start    = item.get("start", {})
        start_dt = start.get("dateTime", start.get("date", "?"))
        # NOTE: title and description are intentionally not logged in detail
        print(f"  [{start_dt}]  id={event_id}")
    print()


def cmd_create(title: str, date: str, time: str, description: str, duration: int) -> None:
    try:
        start_dt = datetime.datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    except ValueError:
        print(
            f"{RED}Error: invalid date/time format.\n"
            "Use: date=YYYY-MM-DD, time=HH:MM (24h){RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    end_dt = start_dt + datetime.timedelta(minutes=duration)

    # Detect local timezone offset
    local_offset = datetime.datetime.now(datetime.timezone.utc).astimezone().utcoffset()
    tz_str = _format_offset(local_offset)

    event: dict = {
        "summary": title,
        "start":   {"dateTime": start_dt.isoformat() + tz_str, "timeZone": _local_tz_name()},
        "end":     {"dateTime": end_dt.isoformat() + tz_str,   "timeZone": _local_tz_name()},
    }
    if description:
        event["description"] = description

    service = get_service()
    try:
        created = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    except Exception as e:
        print(f"{RED}Error creating event: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    event_id = created.get("id", "?")
    # Only confirm ID and time — do not log title/description
    print(f"{GREEN}Event created: id={event_id}  start={start_dt.isoformat()}{RESET}")


def cmd_delete(event_id: str) -> None:
    service = get_service()
    try:
        service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
    except Exception as e:
        print(f"{RED}Error deleting event {event_id}: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    print(f"{GREEN}Deleted event: {event_id}{RESET}")


# ─── Timezone helpers ──────────────────────────────────────────────────────────

def _format_offset(offset: datetime.timedelta | None) -> str:
    if offset is None:
        return "+00:00"
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    hours, rem = divmod(abs(total_seconds), 3600)
    minutes = rem // 60
    return f"{sign}{hours:02d}:{minutes:02d}"


def _local_tz_name() -> str:
    try:
        import time as _time
        return _time.tzname[0]
    except Exception:
        return "UTC"


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Dexter Google Calendar CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List upcoming events")
    p_list.add_argument("--max-results", type=int, default=10,
                        help="Number of events to show (default: 10)")

    # create
    p_create = subparsers.add_parser("create", help="Create a new event")
    p_create.add_argument("title", help="Event title")
    p_create.add_argument("date", help="Date in YYYY-MM-DD format")
    p_create.add_argument("time", help="Start time in HH:MM (24h) format")
    p_create.add_argument("--description", default="", help="Optional event description")
    p_create.add_argument("--duration", type=int, default=60,
                          help="Duration in minutes (default: 60)")

    # delete
    p_delete = subparsers.add_parser("delete", help="Delete an event by ID")
    p_delete.add_argument("event_id", help="Google Calendar event ID")

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args.max_results)
    elif args.command == "create":
        cmd_create(args.title, args.date, args.time, args.description, args.duration)
    elif args.command == "delete":
        cmd_delete(args.event_id)


if __name__ == "__main__":
    main()
