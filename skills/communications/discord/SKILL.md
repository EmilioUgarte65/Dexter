---
name: discord
description: >
  Send messages and embeds to Discord via webhook. No bot token or Discord SDK required.
  Supports custom usernames, avatar overrides, and rich embeds.
  Trigger: "discord", "send discord", "mensaje discord", "webhook discord", "embed discord".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Discord

Sends messages and rich embeds to a Discord channel via webhook URL. No bot setup needed — just create a webhook in your channel settings.

## Setup

1. Discord Channel → Edit → Integrations → Webhooks → New Webhook
2. Copy the webhook URL

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/123456789/xxxx..."
```

## Usage

```bash
# Send a plain message
python3 skills/communications/discord/scripts/send.py send "Deployment complete!"

# Send with custom username
python3 skills/communications/discord/scripts/send.py send "Alert!" --username "Dexter Bot"

# Send a rich embed
python3 skills/communications/discord/scripts/send.py send-embed "Build Status" "All tests passed!" --color 00FF00

# Send embed with red color (error)
python3 skills/communications/discord/scripts/send.py send-embed "Error" "Deploy failed on prod" --color FF0000
```

## Notes

- `DISCORD_WEBHOOK_URL` — required. Full webhook URL from channel settings
- `--color` — hex color without `#` (e.g. `00FF00` for green, `FF0000` for red, `0099FF` for blue)
- Default embed color is `5865F2` (Discord blurple)
- Webhooks have a rate limit of 30 requests per minute per webhook
