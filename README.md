# Dexter

AI agent ecosystem configurator. Installs into Claude Code, OpenCode, Codex, Cursor, Gemini CLI, and VS Code to give your AI agents a complete skill system: home automation, communications, productivity, security, and self-extension.

## What it does

- **30+ skills** across 7 bundles — loaded on demand by keyword, not always in context
- **Token saving** — skills are cached knowledge: solve once, reuse forever
- **Home automation** — Philips Hue, Home Assistant, MQTT, device discovery
- **Communications** — WhatsApp (Baileys), Telegram, Slack, Discord
- **Productivity** — Gmail, GitHub, Hetzner, Google Cloud, ElevenLabs TTS, Obsidian, cron
- **Security** — skill auditor, VirusTotal, hardening checks, OpenClaw adapter
- **AI routing** — route simple tasks to local Ollama, keep complex ones in the cloud
- **Self-extension** — create new skills by describing what you need

## Quick start

```bash
# Install into Claude Code
bash install.sh claude-code

# Install into OpenCode
bash install.sh opencode

# Install into all detected agents
bash install.sh
```

## Create your own skill

```bash
python3 skills/skill-creator/scripts/create.py new my-workflow --interactive
```

## Skills

| Bundle | Skills | Trigger keywords |
|--------|--------|-----------------|
| `domotics` | device-discovery, home-assistant, mqtt, philips-hue | hue, home assistant, mqtt, domótica |
| `communications` | whatsapp, telegram, slack, discord | whatsapp, telegram, enviar mensaje |
| `productivity` | gmail, github, cron, elevenlabs, obsidian, google-cloud, hetzner, system-monitor | correo, github, cron, tts, nota, GCP, hetzner |
| `security` | security-auditor, virustotal, hardening-check, linux-security-tools | audit, virustotal, seguridad |
| `ai` | ollama-router, token-optimizer | ollama, modelo local, token usage |
| `skill-creator` | skill-creator | crear skill, nueva skill |

## Environment variables

```bash
# Domotics
export HUE_BRIDGE_IP="192.168.1.x"
export HUE_API_KEY="your-key"
export HASS_URL="http://192.168.1.x:8123"
export HASS_TOKEN="your-token"
export MQTT_HOST="192.168.1.x"

# Communications
export TELEGRAM_BOT_TOKEN="..."
export SLACK_BOT_TOKEN="..."
export DISCORD_WEBHOOK_URL="..."
export WHATSAPP_API_URL="http://localhost:3000"

# Productivity
export GITHUB_TOKEN="..."
export ELEVENLABS_API_KEY="..."
export OBSIDIAN_API_KEY="..."
export HETZNER_API_TOKEN="..."
export GOOGLE_CLOUD_PROJECT="..."

# AI routing
export OLLAMA_HOST="http://localhost:11434"
```

## License

Apache-2.0
