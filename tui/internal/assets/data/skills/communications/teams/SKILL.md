---
name: teams
description: >
  Send messages to Microsoft Teams channels and chats via Graph API.
  List teams, post to channels, and send direct chat messages.
  Trigger: "teams", "microsoft teams", "send to teams", "teams channel", "teams chat", "team message".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Microsoft Teams

Posts messages to Microsoft Teams channels and chats via the Microsoft Graph API.
Shares authentication credentials with the `outlook` skill (same Azure app registration).
Pure Python, no external dependencies.

## Setup

Uses the same Azure app registration as the `outlook` skill. Ensure these additional
API permissions are granted: `Team.ReadBasic.All`, `ChannelMessage.Send`, `Chat.ReadWrite` (Delegated).

```bash
export OUTLOOK_CLIENT_ID="your-client-id"
export OUTLOOK_CLIENT_SECRET="your-client-secret"
export OUTLOOK_TENANT_ID="your-tenant-id"
```

Token cache is shared with the `outlook` skill at `~/.dexter/outlook_token.json`.

## Usage

```bash
# List all teams the authenticated user belongs to
python3 skills/communications/teams/scripts/send.py list-teams

# Send a message to a team channel
python3 skills/communications/teams/scripts/send.py send-channel \
  --team-id "19:abc123..." \
  --channel-id "19:xyz456..." \
  --message "Deployment complete."

# Send a message to a 1:1 or group chat
python3 skills/communications/teams/scripts/send.py send-chat \
  --chat-id "19:abc@thread.v2" \
  --message "Hey, quick update."
```

## Notes

- Team and channel IDs are GUIDs or thread IDs — use `list-teams` to discover them.
- **No file attachments to external teams**: the script refuses to send messages with file
  attachment payloads if the team's `visibility` is `public` or if the tenant ID differs from `OUTLOOK_TENANT_ID`.
- Credentials are masked in all log output.
- Graph API base: `https://graph.microsoft.com/v1.0/`
- On first run, OAuth2 device flow is triggered (same as the `outlook` skill).
