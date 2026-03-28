
<img width="2720" height="1381" alt="DEXTER" src="https://github.com/user-attachments/assets/ba260806-6f6f-4571-9d1c-ed0c7cc8a3df" />

# Dexter

**AI agent ecosystem configurator** — installs a complete skill system into Claude Code, OpenCode, Codex, Cursor, Gemini CLI, and VS Code.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Skills](https://img.shields.io/badge/skills-47-brightgreen.svg)](#skills)
[![Platforms](https://img.shields.io/badge/platforms-6-orange.svg)](#supported-agents)
[![Tests](https://img.shields.io/badge/tests-99%20passing-brightgreen.svg)](#testing)
[![Status](https://img.shields.io/badge/status-beta%20%E2%80%94%20active%20development-yellow.svg)](#)

> **🚧 En desarrollo activo — beta pública**
> Dexter está siendo depurado y mejorado continuamente. Si encontrás algún bug o comportamiento inesperado, abrí un [issue](https://github.com/EmilioUgarte65/Dexter/issues) — cualquier reporte es bienvenido y muy apreciado. 🙏

---

## What is Dexter?

Dexter is a **mega-fusion of [gentle-ai](https://github.com/gentleman-programming/gentle-ai) and [OpenClaw](https://openclaw.dev)** — injected directly into your AI agent's runtime. It gives your agent a persistent memory system, 46 lazy-loaded skills, home automation, communications, security auditing, self-extension, and a structured development workflow.

You install it once. Your agent becomes dramatically more capable.

```
WhatsApp messages? → Dexter handles them with your persona.
Telegram notifications? → Session summaries sent automatically.
Home automation? → Control Philips Hue, Home Assistant, MQTT.
Recurring automations? → 112+ ClawFlows community workflows ready to import.
New skills? → Describe what you need, Dexter creates and hot-reloads them.
```

---

## Quick Start

```bash
git clone https://github.com/EmilioUgarte65/Dexter.git
cd Dexter
bash install.sh
```

The installer auto-detects your agent and walks you through:

| Step | What happens |
|------|-------------|
| **Backup** | Saves existing config to `~/.dexter-backup/` |
| **System Prompt** | Injects Dexter into your agent's context |
| **Skills** | Copies all 46 skills to `~/.claude/skills/` |
| **Notifications** | Creates `~/.dexter/notifications.json` |
| **WhatsApp** | Optional — pairing code + persona setup |
| **Webhooks & LLM Router** | Optional — incoming webhooks + provider fallback |
| **MCPs** | Configures Engram memory + Context7 |
| **Overlay** | Applies hooks, permissions, and settings |

**Target a specific agent:**
```bash
bash install.sh --agent claude-code
bash install.sh --agent opencode
bash install.sh --agent cursor
bash install.sh --dry-run     # preview without writing
```

**Uninstall:**
```bash
bash uninstall.sh
```

---

## Key Features

### 🧠 Persistent Memory (Engram)

> Powered by [Engram](https://github.com/Gentleman-Programming/engram) — persistent memory for AI agents.

Cross-session memory powered by SQLite + FTS5. Dexter saves decisions, bugs, discoveries, and conventions automatically — no manual prompting required.

```
mem_save    → save a decision or discovery
mem_search  → find anything from past sessions
mem_context → load recent session history on startup
```

### 🔒 Your Memory is Yours — 100% Private

Every Dexter installation builds its own memory from YOUR conversations. Nothing is shared.

| What | Where | Shared? |
|------|-------|---------|
| Skills, DEXTER.md, capabilities | GitHub repo | ✅ Same for everyone — the base brain |
| Your conversations & decisions | `~/.claude/` (Engram SQLite) | ❌ Never leaves your machine |
| Generated skills | `~/.dexter/community/` | ❌ Local only |
| Notifications config & tokens | `~/.dexter/` | ❌ Local only |

The GitHub repo is the **onboarding manual** — identical for all users. Your Dexter grows uniquely through your sessions: the more you use it, the more it learns your preferences, your stack, your workflow.

Two users installing Dexter get the same base agent. After a week of conversations, they have two completely different agents.

### 💬 WhatsApp Auto-Responder
Works with any regular WhatsApp number — no Meta Business account needed. Enter a pairing code once, paired forever.

**Two access tiers:**
- Numbers in `allowFrom` → full Dexter access
- Unknown numbers → your **persona** responds on your behalf (powered by LLM + your rules)

```bash
bash ~/.claude/skills/communications/whatsapp/server/start.sh
# First run shows a pairing code → enter it in WhatsApp → done
```

Configure your persona interactively:
> *"configurá mi persona de WhatsApp"*

### 📣 Notifications
Send session results to Telegram, WhatsApp, Slack, Discord, or YCloud. Configured in `~/.dexter/notifications.json`.

```bash
python3 ~/.claude/skills/notifications/scripts/notify.py \
  --event session_end \
  --message "✅ Feature X implemented — 3 files changed"
```

### 🔗 Incoming Webhooks
Receive HTTP triggers from GitHub, Stripe, or any service — run actions, send notifications.

```bash
bash ~/.claude/skills/infrastructure/webhooks/scripts/start.sh --background
# Listens on localhost:4242
```

### 🤖 LLM Router with Fallback
Checks provider health (Anthropic, OpenAI, Google, Ollama) and picks the fastest available one. Automatic fallback on error.

```bash
python3 ~/.claude/skills/ai/llm-router/scripts/check_providers.py --best
# → anthropic (38ms)
```

### 🏠 Home Automation
Control your smart home directly from your AI agent.

```
Philips Hue  → turn lights on/off, change color, brightness
Home Assistant → control any entity, get states, trigger automations
MQTT         → publish/subscribe to any broker
Device Discovery → nmap/arp-scan your local network
```

### 🔒 Security Auditor
Every external skill passes through the security auditor before execution. Checks for exfiltration patterns, eval/exec, obfuscation, and prompt injection.

```
PASS  → proceed normally
WARN  → proceed with caution, alert logged
BLOCK → do not execute, report findings
```

### 📋 SDD Workflow
Spec-Driven Development — a structured planning layer for substantial changes.

```
/sdd-new <change>   → explore + propose
/sdd-ff <change>    → fast-forward: spec + design + tasks
/sdd-apply          → implement in batches
/sdd-verify         → validate vs specs
```

### 🛒 Marketplace — Universal Skill Hub

Discover and install skills from any source with one command:

```bash
# Search across all sources
dexter marketplace search "linkedin poster"

# Install a community skill (goes through security audit automatically)
dexter marketplace install marketing/linkedin-poster

# No skill exists? Dexter writes it
dexter marketplace generate "I need a skill to post to LinkedIn"
```

**Sources:**
- [dexter-marketplace](https://github.com/EmilioUgarte65/dexter-marketplace) — official community repo (segmented by category)
- **ClawHub** — 100+ pre-built agent skills
- **ClawFlows** — 112+ community workflows
- **GitHub** — any public repo tagged `dexter-skill`

Every install goes through `security-auditor` automatically. No unsafe code runs.

### 🖱️ GUI Control — Computer Use

Automate any desktop task by describing it in plain language. Dexter takes screenshots, visually reasons about the screen, and executes clicks, keystrokes, and scrolls until the task is done. Completed task sequences are saved as replayable macros.

```bash
# Run a GUI task
gui run "open Firefox and go to gmail.com"
gui run "click the send button in Outlook"

# Replay a saved macro (zero screenshots — instant)
gui macro replay open-firefox-and-go-to-gmailcom

# Verify the screen after a task
gui verify "did the email send?"

# Check platform capabilities
gui status
```

Supports Linux X11 and macOS. Wayland not supported (requires X11).

---

### 🔄 ClawFlows Integration
112+ community workflows ready to import. When you ask for a recurring automation, Dexter checks ClawFlows before building from scratch.

```
"mandame un briefing cada mañana" → sends-morning-briefing workflow
"procesá mis emails a las 9am"   → process-email workflow
"avisame de PRs pendientes"      → review-prs workflow
```

---

## Skills

Skills are **lazy-loaded** — only activated when their trigger keywords appear in conversation. CAPABILITIES.md stays in context as a lightweight index.

| Bundle | Skills | Trigger keywords |
|--------|--------|-----------------|
| `communications` | whatsapp, telegram, slack, discord, signal, iMessage, outlook, teams | WhatsApp, Telegram, mensaje, enviar mensaje |
| `productivity` | gmail, github, cron, elevenlabs, obsidian, google-cloud, hetzner, calendar, todoist, travel, sentry, system-monitor | correo, PR, cron, TTS, nota, GCP, vuelo |
| `domotics` | home-assistant, mqtt, philips-hue, device-discovery | hogar, luces, MQTT, IoT, Home Assistant |
| `security` | security-auditor, virustotal, linux-security-tools, hardening-check | seguridad, auditoría, VirusTotal, hardening |
| `social` | twitter-x, instagram, linkedin | Twitter, X, Instagram, LinkedIn, publicar |
| `research` | web-browser, data-aggregator, report-generator | investigar, buscar web, reporte |
| `knowledge` | personal-kb, meeting-transcription | nota, vault, transcribir reunión |
| `ai` | ollama-router, token-optimizer, llm-router | Ollama, modelo local, fallback LLM, proveedor |
| `infrastructure` | webhooks | webhook, disparar acción |
| `dev` | sentry, self-correct-loop | Sentry, self-correct, fix until green |
| `self-extend` | skill-hot-reload, skill-modifier, self-correct-loop | nueva skill, hot-reload, extender Dexter |
| `notifications` | notify | notificar, session end, Telegram, WhatsApp |
| `skill-creator` | skill-creator | crear skill, recipe |
| `gui-control` | gui | click, computer use, automatizar pantalla, desktop automation, macro |

**Total: 47 skills** — [full registry](.atl/skill-registry.md)

### Create your own skill

```bash
python3 skills/skill-creator/scripts/create.py new my-workflow --interactive
```

Skills are markdown files — no code required. Describe the protocol once, reuse it forever at zero token cost.

---

## Supported Agents

| Agent | Config location | Notes |
|-------|----------------|-------|
| **Claude Code** | `~/.claude/` | Full support — hooks, MCP, overlay |
| **OpenCode** | `~/.config/opencode/` | JSONMerge strategy |
| **Codex** | `~/.codex/` | FileReplace strategy |
| **Cursor** | `~/.cursor/` | MCPConfigFile strategy |
| **Gemini CLI** | `~/.gemini/` | TOMLFile strategy |
| **VS Code** | `~/.github/` | AppendToFile strategy |

---

## Configuration

All config lives in `~/.dexter/`. Created automatically on install.

| File | Purpose |
|------|---------|
| `notifications.json` | Channel config (Telegram/WhatsApp/Slack/Discord/YCloud) |
| `whatsapp-persona.json` | Auto-responder persona — how Dexter responds as you |
| `webhooks.json` | Incoming webhook handlers |
| `llm-router.json` | Provider priority + fallback settings |
| `whatsapp/` | Baileys session credentials |
| `whatsapp-messages.jsonl` | Incoming/outgoing WhatsApp log |
| `webhook-log.jsonl` | Incoming webhook log |
| `audit-log.jsonl` | Security auditor results |

### Notifications setup

Edit `~/.dexter/notifications.json`:

```json
{
  "channel": "telegram",
  "telegram": {
    "bot_token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
  }
}
```

Supported channels: `telegram` · `whatsapp` · `ycloud` · `slack` · `discord`

### WhatsApp Persona

```json
{
  "name": "Your Name",
  "about": "Freelance developer, React and Node.js specialist.",
  "tone": "casual and friendly",
  "availability": "Monday to Friday 9am–6pm",
  "rules": [
    "Don't confirm meetings without my approval",
    "For pricing questions, ask for project details first"
  ],
  "llm": { "provider": "anthropic", "model": "claude-haiku-4-5-20251001" }
}
```

---

## Plugin Compatibility

| Source | How to use |
|--------|-----------|
| **ClawFlows** (112+ workflows) | *"quiero aplicar un workflow de clawflows"* |
| **ClawHub / OpenClaw skills** | *"instalar skill de clawhub"* |

---

## Testing

```bash
make test-scripts    # 91 pytest tests (syntax + smoke)
make test-installer  # 22 bats tests (installer flow)
```

---

## Repository Structure

```
Dexter/
├── agents/          # Agent-specific configs (claude-code, opencode, cursor…)
├── skills/          # 46 skills across 13 bundles
├── notifications/   # Config templates
├── hooks/           # Lifecycle hooks
├── mcp/             # MCP server configs
├── tui/             # Go TUI installer binary (Bubbletea)
├── tests/           # Test suite (pytest + bats)
├── install.sh       # Unix installer
├── install.ps1      # Windows installer
├── DEXTER.md        # Core agent configuration
├── CAPABILITIES.md  # Lightweight skills index
└── SOUL.md          # OpenClaw-compatible alias
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

[Apache 2.0](LICENSE) — Copyright 2024 Dexter Contributors

---

## Acknowledgements

Dexter is built on the shoulders of these projects:

| Project | What it contributes |
|---------|-------------------|
| [Engram](https://github.com/Gentleman-Programming/engram) | Persistent cross-session memory — SQLite + FTS5 MCP server |
| [gentle-ai](https://github.com/gentleman-programming/gentle-ai) | Ecosystem configurator, SDD workflow, Agent Teams Lite |
| [OpenClaw](https://openclaw.dev) | 14 action bundles, WhatsApp integration, domotics |
| [ClawFlows](https://github.com/nikilster/clawflows) | 112+ community workflows |
