---
name: slack
description: >
  Post messages and files to Slack via the Web API (chat.postMessage).
  List channels, send rich messages, upload files — no SDK required.
  Trigger: "slack", "send slack", "mensaje slack", "post slack", "canal slack".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Slack

Posts messages and uploads files to Slack using the Web API. Requires a Bot Token with `chat:write` and `files:write` scopes.

## Setup

1. Create a Slack App at https://api.slack.com/apps
2. Add Bot Token Scopes: `chat:write`, `files:write`, `channels:read`
3. Install app to workspace → copy the **Bot User OAuth Token**

```bash
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_DEFAULT_CHANNEL="#general"   # optional
```

Invite the bot to channels it should post in: `/invite @YourBotName`

## Usage

```bash
# Send a message to a channel
python3 skills/communications/slack/scripts/send.py send "#alerts" "Deployment complete!"

# Send using default channel
python3 skills/communications/slack/scripts/send.py send "" "Hello team!"

# Upload a file
python3 skills/communications/slack/scripts/send.py send-file "#logs" /path/to/report.csv "Monthly Report"

# List all channels the bot can see
python3 skills/communications/slack/scripts/send.py list-channels
```

## Notes

- `SLACK_BOT_TOKEN` — required. Must start with `xoxb-`
- `SLACK_DEFAULT_CHANNEL` — optional fallback channel (name with `#` or channel ID)
- Channel can be specified as `#channel-name` or Slack channel ID (`C0123456789`)
- For DMs, use the user's member ID (starts with `U`)
