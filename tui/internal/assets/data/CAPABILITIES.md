# Dexter Capabilities Index

> Lightweight index — always loaded, never loads bundle content.
> To use a capability, mention its trigger keywords and the bundle will activate.

## Core (Always Active)

| Capability | How to use |
|------------|-----------|
| Persistent Memory | "remember", "acordate", "qué hicimos", mem_save/mem_search |
| SDD Workflow | `/sdd-init`, `/sdd-new <change>`, `/sdd-ff`, `/sdd-apply`, `/sdd-verify` |
| Agent Teams | Automatic — orchestrator delegates to sub-agents |
| Security Auditor | Automatic — runs before any external/generated skill |
| AI Local Routing | Automatic — routes simple tasks to Ollama if available |

## Bundles (Lazy — activate by mentioning trigger keywords)

| Bundle | Trigger keywords | Skills available |
|--------|-----------------|-----------------|
| `communications` | whatsapp, telegram, slack, discord, signal, imessage, outlook, teams, mensaje, enviar mensaje, send message, wp | whatsapp, telegram, slack, discord, signal, iMessage, outlook, teams |
| `productivity` | gmail, correo, email, github, issue, PR, cron, tarea programada, schedule, sistema, cpu, memoria, disco, elevenlabs, tts, voz, obsidian, nota, vault, gcloud, GCP, hetzner, VPS, calendar, agenda, evento, todoist, tarea, task, vuelo, flight, aeropuerto, airport, sentry, error tracking | gmail, github, system-monitor, cron, elevenlabs, obsidian, google-cloud, hetzner, calendar, todoist, travel, sentry |
| `domotics` | hogar, Home Assistant, MQTT, Hue, luces, IoT, domótica, device discovery | home-assistant, mqtt, philips-hue, device-discovery |
| `security` | seguridad, auditoría, nmap, VirusTotal, hardening | security-auditor, linux-security-tools, virustotal, hardening-check |
| `ai` | ollama, modelo local, local model, llama, mistral, router, token optimizer, cuánto gasté, token usage, ahorro tokens | ollama-router, token-optimizer |
| `skill-creator` | crear skill, nueva skill, create skill, new skill, haz una skill, skill para X, documentar workflow, recipe | skill-creator |
| `social` | twitter, tweet, X, hilo twitter, linkedin, post linkedin, contenido linkedin, instagram, ig, foto instagram, story instagram | twitter-x, linkedin, instagram |
| `research` | navegar, web browser, screenshot, scrape, fetch url, buscar web, generar reporte, report, informe, documento, agregar datos, data aggregator, merge data, fetch api, consolidar datos | web-browser, report-generator, data-aggregator |
| `knowledge` | base de conocimiento, personal kb, knowledge base, guardar conocimiento, buscar en mis notas, transcribir, transcripción, meeting, reunión, audio a texto, whisper | personal-kb, meeting-transcription |
| `self-extend` | modificar skill, editar skill, actualizar triggers, skill modifier, recargar skill, hot reload, activar skill, skill reload, self-correct, autocorregir, loop correctivo | skill-modifier, skill-hot-reload, self-correct-loop |

## Plugin Compatibility

| Source | How to use |
|--------|-----------|
| ClawHub / OpenClaw skills | `openclaw-adapter` — mention "instalar skill de clawhub" |
| ClawFlows workflows (112+) | `clawflows-adapter` — when user wants a recurring automation. 112 pre-built workflows covering: morning briefing, email triage, standup generator, smart home (sleep/focus/away mode), PR review, meal planning, habit tracking, trip prep, meeting prep, expense reports, and more. **If the user asks to automate something recurring, check ClawFlows first before building from scratch.** |
| gentle-ai plugins | Auto-detected if gentle-ai is installed |

## Cross-Platform Support

Installed on: Claude Code · OpenCode · Codex · Cursor · Gemini CLI · VS Code
