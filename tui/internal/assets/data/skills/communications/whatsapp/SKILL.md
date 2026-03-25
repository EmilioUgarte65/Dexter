---
name: whatsapp
description: >
  Send WhatsApp messages and media via a Baileys-compatible HTTP API.
  Supports sending text, media files with captions, and checking session status.
  Trigger: "whatsapp", "send whatsapp", "mensaje whatsapp", "wp", "wpp", "mandar mensaje".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# WhatsApp

Sends messages via a locally-running Baileys-compatible HTTP API (e.g. whatsapp-http-api, WPPConnect, ZAP-API). No official WhatsApp API account required.

## Setup

```bash
export WHATSAPP_API_URL="http://localhost:3000"   # default
export WHATSAPP_SESSION="dexter"                  # default session name
```

Start your Baileys server and scan the QR code once. After that, use Dexter to send.

## Usage

```bash
# Send a text message
python3 skills/communications/whatsapp/scripts/send.py send 5491112345678 "Hello from Dexter!"

# Send media with optional caption
python3 skills/communications/whatsapp/scripts/send.py send-media 5491112345678 /path/to/photo.jpg "Check this out"

# Check session/connection status
python3 skills/communications/whatsapp/scripts/send.py status
```

## Phone Number Format

Use international format **without** the `+` prefix:
- Argentina: `5491112345678` (54 = country code, 9 = mobile indicator, 11 = area, 12345678 = number)
- USA: `12125551234`
- Spain: `34612345678`

## Notes

- `WHATSAPP_API_URL` — no trailing slash, default `http://localhost:3000`
- `WHATSAPP_SESSION` — session name configured in your Baileys server, default `dexter`
- Supported media: images (jpg, png, gif), video (mp4), audio (mp3, ogg), documents (pdf, docx)
- The API must be running and authenticated (QR scanned) before sending
