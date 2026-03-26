---
name: whatsapp
description: >
  Personal WhatsApp assistant powered by Baileys. Phone number pairing (no QR),
  AI responses via Claude CLI subprocess, stranger protection, group management.
  Trigger: "whatsapp", "send whatsapp", "mensaje whatsapp", "wp", "wpp", "mandar mensaje".
license: Apache-2.0
metadata:
  author: dexter
  version: "2.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# WhatsApp

Personal WhatsApp assistant that connects to your own number via Baileys (multi-device). Responds to your messages using the full Claude CLI — no separate API key needed. Protects your number from strangers and manages group participation via commands.

## Setup

### 1. Install dependencies

```bash
cd skills/communications/whatsapp/server
npm install
```

### 2. Configure persona

Create `~/.dexter/whatsapp-persona.json`:

```json
{
  "name": "Dexter",
  "allowFrom": ["+521XXXXXXXXXX"],
  "stranger_reply": "Hola, soy Dexter. No puedo hablar con extraños.",
  "language": "es"
}
```

| Field | Description |
|-------|-------------|
| `allowFrom` | Your phone number(s). These get full AI responses. Use international format with `+`. |
| `stranger_reply` | Fixed reply for unknown numbers. If omitted, strangers get an LLM response. |
| `wake_word` | Word strangers must say to get a response (default: `"dexter"`). Set to `null` to disable. |
| `allowedGroups` | List of group JIDs where Dexter responds. Managed via commands — see below. |

### 3. Start the server

```bash
# From Dexter project root
WA_PHONE=+521XXXXXXXXXX node skills/communications/whatsapp/server/server.js
```

First run only: a pairing code is shown. In WhatsApp → ⋮ → Linked devices → Link with phone number → enter the code. Press Enter in the terminal to continue.

Credentials are saved in `~/.dexter/whatsapp/` — subsequent starts connect automatically.

---

## How it works

### Access tiers

| Sender | Behavior |
|--------|----------|
| Numbers in `allowFrom` | Full Dexter AI response via `claude -p` subprocess |
| Self-chat (own number) | Same as above — write to yourself and Dexter responds |
| Unknown numbers | Ignored unless they say `"dexter"` — then gets `stranger_reply` |
| Groups (not enabled) | Fully ignored |
| Groups (enabled) | Responds when someone says `"dexter"` |

### Phone number matching

Numbers are matched by the **last 10 digits**, so country code variants are handled automatically. For example, Mexico uses `+5283...` but WhatsApp internally reports `+52183...` — both match correctly. You don't need to worry about this; just use the format printed on your SIM.

### Self-chat

Writing to your own number is the primary way to interact with Dexter. Messages you send to yourself (`fromMe: true`) are processed normally — Dexter responds in that same conversation.

### AI responses (owner)

When you message your own number, Dexter spawns `claude -p "your message"` from the Dexter project root. Claude has full access to `DEXTER.md`, `CLAUDE.md`, Engram memory, and all skills. No extra API key needed.

To use a different CLI: `DEXTER_AGENT=opencode node server.js`

---

## Group management

Enable or disable Dexter in any group by sending a command from your phone:

| Command | Action |
|---------|--------|
| `dexter join` | Enables Dexter in this group. Saves to config automatically. |
| `dexter leave` | Disables Dexter in this group. |

Once a group is enabled, anyone in it can interact with Dexter by mentioning `"dexter"` in their message.

---

## HTTP API

The server also exposes a local API for programmatic sending:

```bash
# Send a text message
curl -X POST http://localhost:3000/api/sendText \
  -H "Content-Type: application/json" \
  -d '{"to": "+521XXXXXXXXXX", "text": "Hello from Dexter!"}'

# Check connection status
curl http://localhost:3000/status
```

Default port: `3000`. Override with `WA_PORT=3001`.

---

## Files

| Path | Description |
|------|-------------|
| `~/.dexter/whatsapp/` | Baileys credentials (auto-generated) |
| `~/.dexter/whatsapp-persona.json` | Persona config (allowFrom, groups, wake word) |
| `~/.dexter/whatsapp-messages.jsonl` | Message log (all in/out) |
| `~/.dexter/notifications.json` | Fallback allowFrom config |
