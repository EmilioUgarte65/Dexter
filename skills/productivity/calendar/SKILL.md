---
name: calendar
description: >
  Create, list, and delete Google Calendar events via the Calendar API with OAuth2.
  Trigger: "calendar", "agenda", "evento", "reunión", "agendar".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
allowed-tools: Read, Bash
---

# Google Calendar

Manages Google Calendar events: list upcoming events, create new ones, and delete by ID.

## Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable Google Calendar API
3. Create OAuth2 credentials → Desktop app → Download as `credentials.json`
4. First run will open browser for authorization

```bash
export GOOGLE_CREDENTIALS_JSON="$HOME/.config/dexter/google_credentials.json"
export GOOGLE_CALENDAR_ID="primary"   # or a specific calendar ID
```

**Install dependencies:**
```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

## Usage

```bash
# List next 10 upcoming events
python3 skills/productivity/calendar/scripts/manage.py --action list

# List next 20 upcoming events
python3 skills/productivity/calendar/scripts/manage.py --action list --limit 20

# Create a new event
python3 skills/productivity/calendar/scripts/manage.py --action create \
  --title "Team sync" \
  --start "2026-03-25T10:00:00" \
  --end "2026-03-25T11:00:00" \
  --attendees "alice@example.com,bob@example.com"

# Delete an event by ID
python3 skills/productivity/calendar/scripts/manage.py --action delete --event-id "abc123xyz"
```

## Requirements

- `GOOGLE_CREDENTIALS_JSON` — path to OAuth2 credentials JSON from Google Cloud Console
- `GOOGLE_CALENDAR_ID` — calendar ID to operate on (use `primary` for default calendar)
- pip: `google-auth`, `google-auth-oauthlib`, `google-auth-httplib2`, `google-api-python-client`

## How to use

"Agendá una reunión con el equipo el jueves a las 10am"
"Mostrá mis próximos eventos del calendario"
"Borrá el evento con ID abc123 del calendario"

## Script

Run `scripts/manage.py --action {list,create,delete} [options]`

| Action   | Required args                     | Optional args          |
|----------|-----------------------------------|------------------------|
| `list`   | —                                 | `--limit` (default 10) |
| `create` | `--title`, `--start`, `--end`     | `--attendees`          |
| `delete` | `--event-id`                      | —                      |
