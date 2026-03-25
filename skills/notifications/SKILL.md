---
name: notifications
description: >
  Route agent outputs and workflow results to the user's preferred messaging channel (Telegram, WhatsApp, Slack, Discord).
  Always active — check config before each notification. No trigger needed.
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Notifications

Routes messages to the user's configured channel. Supports Telegram, WhatsApp, Slack, and Discord.

## Config

Located at `~/.dexter/notifications.json`. Template at `notifications/config.template.json`.

```json
{
  "channel": "telegram",
  "telegram": { "bot_token": "...", "chat_id": "..." },
  "events": { "session_end": true, "workflow_complete": true, "audit_block": true, "error": true }
}
```

If `channel` is `"none"` or file doesn't exist → notifications are silently skipped.

## When to Send

| Event | When |
|-------|------|
| `session_end` | Before ending session — send session summary |
| `workflow_complete` | After a ClawFlows workflow finishes |
| `audit_block` | When security-auditor blocks a skill |
| `error` | When a critical failure occurs |

**Do NOT send for**: every small step, file reads, intermediate results, routine questions. Only meaningful outcomes.

## How to Send

```bash
python3 ~/.claude/skills/notifications/scripts/notify.py \
  --event <event> \
  --message "<text>"
```

### Session end (always — if configured)

```bash
python3 ~/.claude/skills/notifications/scripts/notify.py \
  --event session_end \
  --message "$(cat <<'EOF'
✅ Done: <one-line summary of what was accomplished>

📋 Key changes:
• <file or result 1>
• <file or result 2>

▶️ Next: <what remains if anything>
EOF
)"
```

### Workflow complete

```bash
python3 ~/.claude/skills/notifications/scripts/notify.py \
  --event workflow_complete \
  --message "Morning briefing sent — 65°F, 3 meetings, 2 priority tasks"
```

### Audit block

```bash
python3 ~/.claude/skills/notifications/scripts/notify.py \
  --event audit_block \
  --message "BLOCKED: curl exfiltration detected in skills/evil-skill/"
```

## Setup — Telegram (recommended)

1. Message `@BotFather` on Telegram → `/newbot`
2. Copy the bot token
3. Message your bot once, then get your chat_id:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```
4. Edit `~/.dexter/notifications.json`:
   ```json
   { "channel": "telegram", "telegram": { "bot_token": "...", "chat_id": "..." } }
   ```

## Setup — YCloud (WhatsApp Business API)

1. Entrás a [ycloud.com](https://www.ycloud.com) → Console → **Developers > API Keys** → copiás tu API key
2. Necesitás tu número de WhatsApp Business registrado en YCloud (`from`)
3. Editás `~/.dexter/notifications.json`:
   ```json
   {
     "channel": "ycloud",
     "ycloud": {
       "api_key": "TU_API_KEY",
       "from": "+1234567890",
       "to": "+1234567890"
     }
   }
   ```

> **Nota**: el número `to` es tu propio número o el que quieras notificar. Formato E.164 (`+` + código de país).

## Setup — WhatsApp (Baileys — cualquier número, sin cuenta Meta)

Dexter incluye un servidor Baileys mínimo. Funciona con cualquier número regular de WhatsApp — solo escaneás un QR una vez.

### Primera vez (QR pairing)

```bash
bash ~/.claude/skills/communications/whatsapp/server/start.sh
```

Aparece el QR en la terminal. En tu teléfono: **WhatsApp → Configuración → Dispositivos vinculados → Vincular dispositivo**. Escaneás y listo — las credenciales quedan en `~/.dexter/whatsapp/` para siempre.

### Inicio en background (arranque normal)

```bash
bash ~/.claude/skills/communications/whatsapp/server/start.sh --background
# Logs: tail -f ~/.dexter/whatsapp-server.log
```

### Config en `~/.dexter/notifications.json`

```json
{
  "channel": "whatsapp",
  "whatsapp": {
    "api_url": "http://localhost:3000",
    "phone": "+5491112345678"
  }
}
```

> El installer (`bash install.sh`) ofrece hacer todo esto automáticamente en el **Step 3c**.

### Access Policies (WhatsApp)

Add to `~/.dexter/notifications.json` to restrict which numbers the bot can message:

```json
"whatsapp": {
  "allowFrom": ["+5491112345678"],
  "dmPolicy": "allowlist"
}
```

| dmPolicy | Behavior |
|----------|----------|
| `open` | Can message any number |
| `allowlist` | Only numbers in `allowFrom` |

## Setup — Slack / Discord

Paste your incoming webhook URL under `slack.webhook_url` or `discord.webhook_url` and set `channel` accordingly.
