---
name: calendar
description: >
  Manage Google Calendar events: list upcoming events, create new ones, delete by ID.
  Uses google-api-python-client with OAuth2. Event content is never logged.
  Trigger: "calendar", "google calendar", "schedule", "create event", "list events", "delete event".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Google Calendar

Manages events in Google Calendar via the Google Calendar API v3. Supports listing upcoming events, creating events with title/date/time/description, and deleting events by ID.

## Setup

1. Create a Google Cloud project and enable the **Google Calendar API**.
2. Create OAuth 2.0 credentials (Desktop app) and download as `credentials.json`.
3. Place `credentials.json` in a known path and export it:

```bash
export GOOGLE_CREDENTIALS_FILE="/path/to/credentials.json"   # defaults to ~/.config/dexter/calendar/credentials.json
export GOOGLE_TOKEN_FILE="/path/to/token.json"                # defaults to ~/.config/dexter/calendar/token.json
export GOOGLE_CALENDAR_ID="primary"                           # optional; defaults to "primary"
```

4. Install dependencies:

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

5. On first run, a browser window opens for OAuth consent. The token is saved to `token.json` for subsequent runs.

## Usage

```bash
# List next 10 upcoming events
python3 skills/productivity/calendar/scripts/calendar.py list

# List next 25 upcoming events
python3 skills/productivity/calendar/scripts/calendar.py list --max-results 25

# Create an event (date: YYYY-MM-DD, time: HH:MM, 24h)
python3 skills/productivity/calendar/scripts/calendar.py create "Team Sync" 2026-04-01 14:00

# Create with optional description and duration (minutes, default 60)
python3 skills/productivity/calendar/scripts/calendar.py create "Team Sync" 2026-04-01 14:00 --description "Weekly sync" --duration 30

# Delete an event by ID
python3 skills/productivity/calendar/scripts/calendar.py delete "abc123eventid"
```

## Notes

- **Event content is never logged** — titles, descriptions, and attendee data are not printed to stdout beyond confirmation messages.
- `GOOGLE_CREDENTIALS_FILE` — path to the OAuth2 `credentials.json` downloaded from Google Cloud Console.
- `GOOGLE_TOKEN_FILE` — path where the access/refresh token is persisted after first auth. Keep this file private.
- `GOOGLE_CALENDAR_ID` — target calendar. Use `"primary"` for the main calendar or a full calendar ID (e.g. `abc@group.calendar.google.com`).
- All times are treated as local timezone of the calendar unless the system timezone is configured.
