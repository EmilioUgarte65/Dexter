---
name: whatsapp
description: >
  Personal WhatsApp assistant powered by Baileys. QR or phone-number pairing,
  AI responses via Claude CLI subprocess, stranger persona protection, persistent
  per-group config, Engram memory integration. Cross-platform: Windows, Linux, macOS.
  Trigger: "whatsapp", "send whatsapp", "mensaje whatsapp", "wp", "wpp", "mandar mensaje".
license: Apache-2.0
metadata:
  author: dexter
  version: "3.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# WhatsApp

Personal WhatsApp assistant that connects to your own number via Baileys (multi-device). Responds to messages using the full Claude CLI — no separate API key needed. Protects your number from strangers, manages groups via commands, and remembers context across restarts via Engram.

---

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
  "name": "Your Name",
  "about": "Freelance developer, React and Node.js specialist.",
  "tone": "casual and friendly",
  "language": "es",
  "allowFrom": ["+521XXXXXXXXXX"],
  "stranger_reply": "Hey, I can't chat right now. I'll get back to you soon 👋",
  "llm": { "provider": "anthropic", "model": "claude-haiku-4-5-20251001" }
}
```

| Field | Description |
|-------|-------------|
| `allowFrom` | Your phone number(s) — get full AI responses. International format with `+`. |
| `stranger_reply` | Fixed reply for unknown numbers. If omitted, strangers get an LLM response via `callLLM`. |
| `wake_word` | Word required to trigger Dexter (default: `"dexter"`). Set to `null` to disable. |
| `allowedGroups` | Group JIDs where Dexter responds. Managed via `dexter join` / `dexter leave` commands. |
| `groups` | Per-group config: personality, standing instructions, allowed members. Managed via commands. |
| `llm.provider` | LLM for stranger responses: `"anthropic"`, `"openai"`, or `"ollama"`. |

### 3. Start the server

#### QR pairing (simplest)

```bash
node skills/communications/whatsapp/server/server.js --qr
```

A QR code is printed in the terminal. Scan with WhatsApp → ⋮ → Linked devices → Link a device.

#### Phone number pairing (headless)

```bash
WA_PHONE=+521XXXXXXXXXX node skills/communications/whatsapp/server/server.js
```

A pairing code is shown. In WhatsApp → ⋮ → Linked devices → Link with phone number → enter the code.

Credentials are saved in `~/.dexter/whatsapp/` — subsequent starts reconnect automatically without scanning.

#### Keep it alive with pm2 (recommended)

```bash
npm install -g pm2
WA_PHONE=+521XXXXXXXXXX pm2 start skills/communications/whatsapp/server/server.js --name dexter-wa
pm2 save       # persist across reboots
pm2 startup    # auto-start on system boot
```

```bash
pm2 status            # check if running
pm2 logs dexter-wa    # tail logs
pm2 restart dexter-wa
pm2 stop dexter-wa
```

---

## How it works

### Access tiers

| Sender | Behavior |
|--------|----------|
| Numbers in `allowFrom` | Full Dexter AI response — spawns `claude -p` with complete tool access |
| Self-chat (own number) | Same as above — write to yourself, Dexter responds |
| Unknown numbers | Ignored unless they say the wake word — then `stranger_reply` or LLM persona |
| Groups (not enabled) | Fully ignored |
| Groups (enabled) — owner | Full unrestricted Dexter response, complete tool access, owner instructions applied |
| Groups (enabled) — allowed member | Same as owner in that group (granted via `dexter allow`) |
| Groups (enabled) — non-owner | Restricted: general knowledge only, no machine/filesystem/code access |

### Phone number matching

Numbers are matched by **last 10 digits** — country code variants are handled automatically. Mexico's `+5283...` and WhatsApp's internal `+52183...` both match the same entry. Use whatever format is printed on your SIM.

### Self-chat

Writing to your own number is the primary interaction mode. Messages sent to yourself (`fromMe: true`) are processed normally — Dexter responds in that same conversation.

### AI responses (owner)

When the owner messages, Dexter spawns `claude -p "message"` from the Dexter project root. Claude has full access to `DEXTER.md`, `CLAUDE.md`, Engram memory, and all skills.

To use a different CLI:
```bash
DEXTER_AGENT=opencode node server.js
```

---

## Memory — Engram integration

If `engram` is installed and available in PATH, Dexter uses it for persistent cross-session memory. If not, it falls back to in-process RAM history (lost on restart).

### How it works

Instead of manually tracking conversation history, Claude receives a system prompt that instructs it to use Engram tools directly:

```
1. Try to answer from what you already know
2. If you need context: mem_search query "{contactId}" project "dexter-whatsapp"
3. Only if you need detailed recent history: read the message log
4. Save important facts with mem_save
```

Claude decides when to search and what to save — Dexter delegates memory management entirely.

### What gets stored

| Data | Project | Topic key |
|------|---------|-----------|
| Contact communication profile | `dexter-whatsapp` | `wa/{phone}/perfil` |
| Group interaction profile | `dexter-whatsapp` | `wa/{groupJid}/perfil` |

Claude learns each contact's communication style, preferred topics, and interaction patterns over time. It adapts tone and responses accordingly without needing to be told.

### Tool access per context

| Context | Engram available | Tools granted |
|---------|-----------------|---------------|
| Owner DM | Yes | All tools (mem_* + machine) |
| Owner in group | Yes | All tools |
| Non-owner in group | Yes | None — `--allowedTools ''` |

Non-owners in Engram mode still get the memory-aware system prompt, but Claude cannot call tools — responses are based on injected context only.

### Fallback (no Engram)

```
chatHistory Map — per-sender, max 20 turns
Prompt format: "Conversation so far:\nUser: ...\nAssistant: ...\n\nUser: {new}"
Lost on server restart.
```

---

## Group management

All group commands are sent from your phone in the group chat. They are processed by `server.js` before reaching Claude — no LLM invocation needed.

### Lifecycle commands

| Command | Action | Persists |
|---------|--------|----------|
| `dexter join` | Enables Dexter in this group | ✅ |
| `dexter leave` | Disables Dexter in this group | ✅ |

### Access control (owner only)

Grant or revoke owner-level access to specific group members. Granted members get full Dexter capabilities in that group only — access is scoped per group.

| Command | Action | Persists |
|---------|--------|----------|
| `dexter allow +521234567890` | Grants owner-level access in this group | ✅ |
| `dexter deny +521234567890` | Revokes access in this group | ✅ |

Access is group-scoped: a member can have full access in one group and be a regular member in another.

### Persistent instructions (owner only)

Standing instructions are injected into Claude's system prompt on every message in the group — they survive server restarts.

| Command | Action | Persists |
|---------|--------|----------|
| `dexter eres [personality]` | Sets group personality | ✅ |
| `dexter set [instruction]` | Adds a standing instruction | ✅ |
| `dexter reset` | Clears all group config (personality, instructions, allowed members) | ✅ |

**Examples:**

```
dexter set always respond in Mexican Spanish, no filters
dexter set address everyone informally
dexter eres a sarcastic and witty assistant
dexter allow +521234567890
dexter reset
```

Multiple `dexter set` calls accumulate — instructions are appended to the list. Use `dexter reset` to clear all.

### Owner authority

The owner has absolute authority in groups. Their instructions are followed without pushback — personality changes, tone, language, or any behavioral directive are applied immediately and maintained. Claude never refuses an owner instruction with "that's not in my capabilities."

### Stored config structure

All group config is saved in `~/.dexter/whatsapp-persona.json` under `groups`:

```json
{
  "allowFrom": ["+521XXXXXXXXXX"],
  "allowedGroups": ["120363XXXXXX@g.us"],
  "groups": {
    "120363XXXXXX@g.us": {
      "personality": "sarcastic and witty assistant",
      "instructions": [
        "always respond in Mexican Spanish",
        "address everyone informally"
      ],
      "allowedMembers": ["+521234567890"]
    }
  }
}
```

---

## HTTP API

Local API for programmatic sending from other scripts or skills:

```bash
# Send a text message
curl -X POST http://localhost:3000/api/sendText \
  -H "Content-Type: application/json" \
  -d '{"to": "+521XXXXXXXXXX", "text": "Hello from Dexter!"}'

# Check connection status
curl http://localhost:3000/status
# → {"ok":true,"ready":true,"persona":"Your Name"}
```

Default port: `3000`. Override with `WA_PORT=3001`.

### Python client

```bash
python3 skills/communications/whatsapp/scripts/send.py send +521XXXXXXXXXX "Hello"
python3 skills/communications/whatsapp/scripts/send.py status
```

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WA_PHONE` | — | Phone number for pairing (e.g. `+521XXXXXXXXXX`) |
| `WA_PORT` | `3000` | HTTP API port |
| `WA_QR` | `0` | Set to `1` to enable QR mode without `--qr` flag |
| `DEXTER_AGENT` | auto-detect | Path or name of the LLM CLI to use |
| `DEXTER_ROOT` | 4 levels up from `server.js` | Dexter project root — override if install layout differs |

---

## Platform support

The server runs identically on Windows, Linux, and macOS. Platform differences are handled internally:

| Feature | Windows | Linux / macOS |
|---------|---------|---------------|
| Claude spawn | PowerShell + temp file (avoids cmd.exe multiline corruption) | Direct `spawn(cli, ['-p', prompt])` |
| Binary detection | `where claude` | `which claude` |
| IDE extension path | `AppData\Local\...`, `.vscode\extensions\` | `~/.config/Code/extensions/`, `~/.cursor/extensions/` |
| Engram detection | `where engram` | `which engram` |

All group commands, Engram integration, and persistent config work identically across platforms.

---

## Files

| Path | Description |
|------|-------------|
| `~/.dexter/whatsapp/` | Baileys credentials (auto-generated on first connect) |
| `~/.dexter/whatsapp-persona.json` | Persona + group config (allowFrom, groups, wake word) |
| `~/.dexter/whatsapp-messages.jsonl` | Full message log (all in/out with timestamps) |
| `~/.dexter/notifications.json` | Fallback allowFrom config |
