---
name: webhooks
description: >
  Receive incoming HTTP webhooks and trigger actions. Register handlers in ~/.dexter/webhooks.json.
  Start the listener with the start.sh script.
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Webhooks

Listens on port 4242 for incoming POST requests and runs configured actions.

## Config

Located at `~/.dexter/webhooks.json`. Template at `notifications/webhooks.template.json`.

```json
[
  {
    "id": "github-push",
    "source": "github",
    "path": "/webhook/github",
    "secret": "optional_hmac_secret",
    "action": "echo 'New push received'"
  }
]
```

## When to use

When the user says things like:
- "cuando llegue un webhook de GitHub, avisame"
- "al recibir un pago de Stripe, mandame un WhatsApp"
- "trigger an action when this URL is called"

## Agent Protocol

1. Ask user: what service sends the webhook, what path, what action to run
2. Write handler to `~/.dexter/webhooks.json` (append, don't overwrite)
3. Start or restart the listener: `bash ~/.claude/skills/infrastructure/webhooks/scripts/start.sh --background`
4. Confirm: `curl http://localhost:4242/status`

## Start listener

```bash
bash ~/.claude/skills/infrastructure/webhooks/scripts/start.sh
# Background:
bash ~/.claude/skills/infrastructure/webhooks/scripts/start.sh --background
```

## Test a handler

```bash
curl -X POST http://localhost:4242/webhook/github \
  -H "Content-Type: application/json" \
  -d '{"ref": "refs/heads/main"}'
```

## Status

```bash
curl http://localhost:4242/status
```
