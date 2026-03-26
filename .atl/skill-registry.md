# Skill Registry — Dexter

Generated: 2026-03-22
Source: `~/.claude/skills/` (user-level) + `/home/tali/proyectos/Dexter/skills/` (project-level)

## User-Level Skills (Claude Code)

### General Skills

| Skill | Trigger | Path |
|-------|---------|------|
| `go-testing` | When writing Go tests, using teatest, or adding test coverage | `~/.claude/skills/go-testing/SKILL.md` |
| `skill-creator` | When user asks to create a new skill, add agent instructions, or document patterns for AI | `~/.claude/skills/skill-creator/SKILL.md` |

### SDD Skills (Orchestrator-Managed)

| Skill | Trigger | Path |
|-------|---------|------|
| `sdd-init` | Initialize SDD in a project | `~/.claude/skills/sdd-init/SKILL.md` |
| `sdd-explore` | Explore and investigate ideas before committing to a change | `~/.claude/skills/sdd-explore/SKILL.md` |
| `sdd-propose` | Create a change proposal | `~/.claude/skills/sdd-propose/SKILL.md` |
| `sdd-spec` | Write specifications with requirements and scenarios | `~/.claude/skills/sdd-spec/SKILL.md` |
| `sdd-design` | Create technical design document | `~/.claude/skills/sdd-design/SKILL.md` |
| `sdd-tasks` | Break down a change into implementation tasks | `~/.claude/skills/sdd-tasks/SKILL.md` |
| `sdd-apply` | Implement tasks from the change | `~/.claude/skills/sdd-apply/SKILL.md` |
| `sdd-verify` | Validate implementation matches specs | `~/.claude/skills/sdd-verify/SKILL.md` |
| `sdd-archive` | Sync delta specs and archive a completed change | `~/.claude/skills/sdd-archive/SKILL.md` |

---

## Dexter Project Skills

### Core (Always Available)

| File | Purpose |
|------|---------|
| `DEXTER.md` | Core config: persona, Engram, SDD, Agent Teams, bundle loader, security, domotics |
| `SOUL.md` | OpenClaw-compatible alias of DEXTER.md |
| `CAPABILITIES.md` | Lightweight capabilities index — loaded every session |
| `skills/_shared/bundle-loader.md` | Lazy bundle activation rules and keyword trigger map |

### Bundles (Lazy-Loaded)

| Bundle | Path | Skills Inside | Trigger |
|--------|------|---------------|---------|
| `communications` | `skills/communications/` | whatsapp, telegram, slack, discord, signal, iMessage, outlook, teams | WhatsApp, Telegram, Slack, Discord, Signal, iMessage, Outlook, Teams, mensaje |
| `productivity` | `skills/productivity/` | gmail, obsidian, github, google-cloud, hetzner, cron, system-monitor, elevenlabs, calendar, todoist, travel, sentry | email, Gmail, correo, calendar, agenda, GitHub, PR, GCP, Hetzner, nube, cron, sistema, TTS, voz, ElevenLabs, tarea, vuelo, Sentry, error |
| `social` | `skills/social/` | twitter-x, instagram, linkedin | Twitter, X, Instagram, LinkedIn, publicar |
| `research` | `skills/research/` | web-browser, data-aggregator, report-generator | investigar, buscar web, reporte, transcribir |
| `knowledge` | `skills/knowledge/` | personal-kb, meeting-transcription | Obsidian, nota, vault, transcribir reunión |
| `domotics` | `skills/domotics/` | home-assistant, mqtt, philips-hue, device-discovery | hogar, Home Assistant, MQTT, Hue, IoT |
| `security` | `skills/security/` | security-auditor, virustotal, linux-security-tools, hardening-check | seguridad, auditoría, nmap, VirusTotal |
| `ai` | `skills/ai/` | ollama-router, token-optimizer, llm-router | Ollama, modelo local, optimizar tokens, fallback LLM, proveedor |
| `infrastructure` | `skills/infrastructure/` | webhooks | webhook, cron job, sistema |
| `self-extend` | `skills/self-extend/` | skill-hot-reload, skill-modifier, skill-writer | nueva skill, hot-reload, extender Dexter, skill-writer, generate skill, crear skill |
| `marketplace` | `skills/marketplace/` | marketplace | marketplace, buscar skill, instalar skill, install skill, hay una skill para, dexter install, browse skills |
| `dev` | `skills/dev/` | sentry, self-correct-loop | sentry, error, crash, exception, bug report, self-correct, fix until it works, iterate until green |

### Individual Skills by Bundle

#### communications
| Skill | Path |
|-------|------|
| `whatsapp` | `skills/communications/whatsapp/SKILL.md` |
| `telegram` | `skills/communications/telegram/SKILL.md` |
| `slack` | `skills/communications/slack/SKILL.md` |
| `discord` | `skills/communications/discord/SKILL.md` |
| `signal` | `skills/communications/signal/SKILL.md` |
| `iMessage` | `skills/communications/iMessage/SKILL.md` |
| `outlook` | `skills/communications/outlook/SKILL.md` |
| `teams` | `skills/communications/teams/SKILL.md` |

#### productivity
| Skill | Path |
|-------|------|
| `gmail` | `skills/productivity/gmail/SKILL.md` |
| `obsidian` | `skills/productivity/obsidian/SKILL.md` |
| `github` | `skills/productivity/github/SKILL.md` |
| `google-cloud` | `skills/productivity/google-cloud/SKILL.md` |
| `hetzner` | `skills/productivity/hetzner/SKILL.md` |
| `cron` | `skills/productivity/cron/SKILL.md` |
| `system-monitor` | `skills/productivity/system-monitor/SKILL.md` |
| `elevenlabs` | `skills/productivity/elevenlabs/SKILL.md` |
| `calendar` | `skills/productivity/calendar/SKILL.md` |
| `todoist` | `skills/productivity/todoist/SKILL.md` |
| `travel` | `skills/productivity/travel/SKILL.md` |
| `sentry` | `skills/productivity/sentry/SKILL.md` |

#### social
| Skill | Path |
|-------|------|
| `twitter-x` | `skills/social/twitter-x/SKILL.md` |
| `instagram` | `skills/social/instagram/SKILL.md` |
| `linkedin` | `skills/social/linkedin/SKILL.md` |

#### research
| Skill | Path |
|-------|------|
| `web-browser` | `skills/research/web-browser/SKILL.md` |
| `data-aggregator` | `skills/research/data-aggregator/SKILL.md` |
| `report-generator` | `skills/research/report-generator/SKILL.md` |

#### knowledge
| Skill | Path |
|-------|------|
| `personal-kb` | `skills/knowledge/personal-kb/SKILL.md` |
| `meeting-transcription` | `skills/knowledge/meeting-transcription/SKILL.md` |

#### domotics
| Skill | Path |
|-------|------|
| `home-assistant` | `skills/domotics/home-assistant/SKILL.md` |
| `mqtt` | `skills/domotics/mqtt/SKILL.md` |
| `philips-hue` | `skills/domotics/philips-hue/SKILL.md` |
| `device-discovery` | `skills/domotics/device-discovery/SKILL.md` |

#### security
| Skill | Path |
|-------|------|
| `security-auditor` | `skills/security/security-auditor/SKILL.md` |
| `virustotal` | `skills/security/virustotal/SKILL.md` |
| `linux-security-tools` | `skills/security/linux-security-tools/SKILL.md` |
| `hardening-check` | `skills/security/hardening-check/SKILL.md` |

#### ai
| Skill | Path |
|-------|------|
| `ollama-router` | `skills/ai/ollama-router/SKILL.md` |
| `token-optimizer` | `skills/ai/token-optimizer/SKILL.md` |
| `llm-router` | `skills/ai/llm-router/SKILL.md` |

#### infrastructure
| Skill | Path |
|-------|------|
| `webhooks` | `skills/infrastructure/webhooks/SKILL.md` |

#### self-extend
| Skill | Path |
|-------|------|
| `skill-hot-reload` | `skills/self-extend/skill-hot-reload/SKILL.md` |
| `skill-modifier` | `skills/self-extend/skill-modifier/SKILL.md` |
| `self-correct-loop` | `skills/self-extend/self-correct-loop/SKILL.md` |
| `skill-writer` | `skills/skill-writer/SKILL.md` |

#### marketplace
| Skill | Path |
|-------|------|
| `marketplace` | `skills/marketplace/SKILL.md` |

#### dev
| Skill | Path | Script |
|-------|------|--------|
| `sentry` | `skills/dev/sentry/SKILL.md` | `skills/dev/sentry/scripts/sentry_client.py` |
| `self-correct-loop` | `skills/dev/self-correct-loop/SKILL.md` | _(none)_ |

### Compatibility

| Skill | Path | Purpose |
|-------|------|---------|
| `openclaw-adapter` | `skills/openclaw-adapter/SKILL.md` | Convert ClawHub/OpenClaw skills to Dexter format |
| `clawflows-adapter` | `skills/clawflows-adapter/SKILL.md` | Import ClawFlows community workflows (WORKFLOW.md) into Dexter SKILL.md format |
| `notifications` | `skills/notifications/SKILL.md` | Route session results to Telegram, WhatsApp, Slack, or Discord |
| `sonoscli` (fixture) | `skills/sonoscli/SKILL.md` | ClawHub reverse-engineering fixture — DO NOT remove |
| `skill-creator` | `skills/skill-creator/SKILL.md` | Create new Dexter skills following project conventions |

### Agent Configs

| Agent | Config Dir | Overlay |
|-------|-----------|---------|
| `claude-code` | `agents/claude-code/` | `overlay.json` |
| `opencode` | `agents/opencode/` | `sdd-overlay-single.json` / `sdd-overlay-multi.json` |
| `codex` | `agents/codex/` | `paths.sh` |
| `cursor` | `agents/cursor/` | `paths.sh` |
| `gemini` | `agents/gemini/` | `paths.sh` |
| `vscode` | `agents/vscode/` | `paths.sh` |

---

## Skill Count

Total leaf skills with SKILL.md: **48**

| # | Bundle | Skill |
|---|--------|-------|
| 1 | communications | whatsapp |
| 2 | communications | telegram |
| 3 | communications | slack |
| 4 | communications | discord |
| 5 | communications | signal |
| 6 | communications | iMessage |
| 7 | communications | outlook |
| 8 | communications | teams |
| 9 | productivity | gmail |
| 10 | productivity | obsidian |
| 11 | productivity | github |
| 12 | productivity | google-cloud |
| 13 | productivity | hetzner |
| 14 | productivity | cron |
| 15 | productivity | system-monitor |
| 16 | productivity | elevenlabs |
| 17 | productivity | calendar |
| 18 | productivity | todoist |
| 19 | productivity | travel |
| 20 | productivity | sentry |
| 21 | social | twitter-x |
| 22 | social | instagram |
| 23 | social | linkedin |
| 24 | research | web-browser |
| 25 | research | data-aggregator |
| 26 | research | report-generator |
| 27 | knowledge | personal-kb |
| 28 | knowledge | meeting-transcription |
| 29 | domotics | home-assistant |
| 30 | domotics | mqtt |
| 31 | domotics | philips-hue |
| 32 | domotics | device-discovery |
| 33 | security | security-auditor |
| 34 | security | virustotal |
| 35 | security | linux-security-tools |
| 36 | security | hardening-check |
| 37 | ai | ollama-router |
| 38 | ai | token-optimizer |
| 45 | ai | llm-router |
| 46 | infrastructure | webhooks |
| 39 | self-extend | skill-hot-reload |
| 40 | self-extend | skill-modifier |
| 41 | self-extend | self-correct-loop |
| 42 | compatibility | skill-creator |
| 43 | dev | sentry |
| 44 | dev | self-correct-loop |
| 47 | self-extend | skill-writer |
| 48 | marketplace | marketplace |

---

## Conventions

- Dexter uses **engram** persistence by default (no openspec/ dirs created unless requested)
- All external skills must pass through `security-auditor` before execution
- Bundle loading is **lazy** — CAPABILITIES.md is always available
- Project stack: Shell/PowerShell installer + Markdown ecosystem (no Go binary yet — Phase 2)
