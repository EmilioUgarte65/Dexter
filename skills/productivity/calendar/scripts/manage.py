#!/usr/bin/env python3
"""Manage Google Calendar events via the Calendar API v3."""
import argparse
import os
import sys

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

CREDENTIALS_FILE = os.environ.get(
    "GOOGLE_CREDENTIALS_JSON",
    os.path.expanduser("~/.config/dexter/google_credentials.json"),
)
TOKEN_FILE = os.path.expanduser("~/.config/dexter/google_calendar_token.json")
CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary")

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def check_config():
    missing = []
    if not os.path.isfile(CREDENTIALS_FILE):
        missing.append(f"GOOGLE_CREDENTIALS_JSON (expected at {CREDENTIALS_FILE})")
    if missing:
        print(f"{RED}Missing configuration:{RESET}", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        print(
            "\nSetup:\n"
            "  1. Go to https://console.cloud.google.com\n"
            "  2. Enable Google Calendar API\n"
            "  3. Create OAuth2 credentials (Desktop app) and download as credentials.json\n"
            f"  4. export GOOGLE_CREDENTIALS_JSON=/path/to/credentials.json\n"
            f"  5. export GOOGLE_CALENDAR_ID=primary",
            file=sys.stderr,
        )
        sys.exit(1)


def get_service():
    """Build and return a Google Calendar service object."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        print(
            f"{RED}Missing dependencies. Install with:{RESET}\n"
            "  pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client",
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
        with open(TOKEN_FILE, "w") as token_f:
            token_f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def cmd_list(limit: int = 10):
    """List upcoming events from the calendar."""
    from datetime import datetime, timezone

    service = get_service()
    now = datetime.now(timezone.utc).isoformat()

    result = (
        service.events()
        .list(
            calendarId=CALENDAR_ID,
            timeMin=now,
            maxResults=limit,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = result.get("items", [])
    if not events:
        print("No upcoming events found.")
        return

    print(f"\n  {'ID':<30} {'START':<25} SUMMARY")
    print("  " + "-" * 80)
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date", "?"))
        summary = event.get("summary", "(no title)")[:40]
        event_id = event.get("id", "?")[:28]
        print(f"  {event_id:<30} {start:<25} {summary}")


def cmd_create(title: str, start: str, end: str, attendees: str = ""):
    """Create a new calendar event."""
    service = get_service()

    event_body: dict = {
        "summary": title,
        "start": {"dateTime": start, "timeZone": "UTC"},
        "end": {"dateTime": end, "timeZone": "UTC"},
    }

    if attendees:
        email_list = [e.strip() for e in attendees.split(",") if e.strip()]
        event_body["attendees"] = [{"email": e} for e in email_list]

    created = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
    event_id = created.get("id", "?")
    link = created.get("htmlLink", "")
    print(f"{GREEN}Event created:{RESET} {title}")
    print(f"  ID:    {event_id}")
    print(f"  Start: {start}")
    print(f"  End:   {end}")
    if link:
        print(f"  Link:  {link}")


def cmd_delete(event_id: str):
    """Delete a calendar event by ID."""
    service = get_service()
    service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
    print(f"{GREEN}Event deleted:{RESET} {event_id}")


def main():
    parser = argparse.ArgumentParser(description="Dexter — Google Calendar manager")
    parser.add_argument(
        "--action",
        choices=["list", "create", "delete"],
        required=True,
        help="Action to perform",
    )
    parser.add_argument("--limit", type=int, default=10, help="Max events to list (default: 10)")
    parser.add_argument("--title", help="Event title (required for create)")
    parser.add_argument("--start", help="Start datetime ISO 8601, e.g. 2026-03-25T10:00:00")
    parser.add_argument("--end", help="End datetime ISO 8601, e.g. 2026-03-25T11:00:00")
    parser.add_argument("--attendees", default="", help="Comma-separated attendee emails")
    parser.add_argument("--event-id", dest="event_id", help="Event ID (required for delete)")

    args = parser.parse_args()
    check_config()

    if args.action == "list":
        cmd_list(limit=args.limit)

    elif args.action == "create":
        if not args.title or not args.start or not args.end:
            print(
                f"{RED}Error:{RESET} --title, --start, and --end are required for create.",
                file=sys.stderr,
            )
            sys.exit(1)
        cmd_create(args.title, args.start, args.end, args.attendees)

    elif args.action == "delete":
        if not args.event_id:
            print(f"{RED}Error:{RESET} --event-id is required for delete.", file=sys.stderr)
            sys.exit(1)
        cmd_delete(args.event_id)


if __name__ == "__main__":
    main()
