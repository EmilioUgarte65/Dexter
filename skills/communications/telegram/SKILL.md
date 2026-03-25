---
name: telegram
description: >
  Send messages and files via Telegram Bot API. Get updates from your bot.
  Pure stdlib, no telethon or python-telegram-bot required.
  Trigger: "telegram", "send telegram", "mensaje telegram", "bot telegram", "tg".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Telegram

Interacts with the Telegram Bot API to send messages, files, and retrieve updates.

## Setup

1. Create a bot via [@BotFather](https://t.me/BotFather) — get the `BOT_TOKEN`
2. Get your `CHAT_ID` by messaging your bot and calling `get-updates`

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
export TELEGRAM_CHAT_ID="-1001234567890"   # optional default chat
```

## Usage

```bash
# Send a message to a specific chat
python3 skills/communications/telegram/scripts/send.py send 123456789 "Hello from Dexter!"

# Send using default TELEGRAM_CHAT_ID
python3 skills/communications/telegram/scripts/send.py send "" "Hello!"

# Send a file
python3 skills/communications/telegram/scripts/send.py send-file 123456789 /path/to/report.pdf

# Get recent updates (to find your chat_id)
python3 skills/communications/telegram/scripts/send.py get-updates
python3 skills/communications/telegram/scripts/send.py get-updates --limit 5
```

## Notes

- `TELEGRAM_BOT_TOKEN` — required. Format: `{bot_id}:{token}`
- `TELEGRAM_CHAT_ID` — optional default. Can be a user ID (positive int) or group/channel ID (negative)
- For channels, the bot must be an admin with post permissions
- Files over 50 MB cannot be sent via Bot API (Telegram limitation)
