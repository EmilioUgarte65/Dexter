---
name: iMessage
description: >
  Send iMessages via macOS Messages.app using osascript. Text only, no media.
  macOS only — will warn and exit on non-Darwin platforms.
  Trigger: "imessage", "send imessage", "messages app", "apple message", "iMessage".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# iMessage

Sends text messages via the macOS Messages.app using `osascript` (AppleScript). No additional dependencies required — works on any Mac where Messages.app is signed in to an Apple ID.

## Requirements

- macOS only (Darwin). The script exits with a clear error on Linux or Windows.
- Messages.app must be open and signed in to iCloud / Apple ID.
- Terminal (or the agent's shell) must have **Automation** permission over Messages.app:
  `System Settings → Privacy & Security → Automation`

## Setup

No environment variables are strictly required. Optionally restrict recipients:

```bash
export IMESSAGE_ALLOWLIST="user@example.com,+1234567890"  # comma-separated; omit to allow any
```

## Usage

```bash
# Send a text message to a phone number
python3 skills/communications/iMessage/scripts/send.py send "+1234567890" "Hello from Dexter!"

# Send to an email address (Apple ID)
python3 skills/communications/iMessage/scripts/send.py send "user@example.com" "Meeting in 5 minutes"
```

## Notes

- `IMESSAGE_ALLOWLIST` — optional. Comma-separated phone numbers (E.164) or email addresses. If set, the script refuses to send to unlisted recipients and prints a security warning.
- Recipient validation: phone numbers must match E.164 (`+` followed by 7–15 digits); emails must contain `@`.
- **Text only** — Messages.app AppleScript does not support sending media attachments via this method.
- Messages are sent as iMessage if the recipient is on Apple devices; otherwise they fall back to SMS (if your Mac is configured for SMS relay via iPhone).
- Do not call this from a headless/CI environment — `osascript` requires an active macOS GUI session.
