---
name: whatsapp-persona
description: >
  Interactive setup for the WhatsApp auto-responder persona.
  Guides the user to configure how Dexter responds to unknown numbers on their behalf.
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# WhatsApp Persona Setup

Dexter can respond to WhatsApp messages on your behalf when you're not available.
Numbers in `allowFrom` get full access. Everyone else gets the **persona** — an AI
that responds as you, following your rules.

## Two access tiers

| Sender | Behavior |
|--------|----------|
| In `allowFrom` | Message logged, Dexter notifies you. Full access. |
| Unknown | Persona responder activates — replies as you using your persona config. |

## Config location

`~/.dexter/whatsapp-persona.json`

## Agent Protocol — setting up the persona

When the user asks to configure their WhatsApp persona or how the bot should respond:

1. Ask these questions one by one (don't dump them all at once):
   - "¿Cómo te llamás? (así firma los mensajes)"
   - "¿Qué hacés / a qué te dedicás? (una o dos líneas)"
   - "¿Con qué tono querés que responda? (ej: formal, casual, amigable, directo)"
   - "¿Cuál es tu disponibilidad? (ej: lunes a viernes 9-18hs)"
   - "¿Hay algo que NO querés que el bot diga o haga nunca?"

2. Once you have the answers, build the persona JSON and write it to `~/.dexter/whatsapp-persona.json`

3. Confirm: show the user the final config and ask if they want to adjust anything.

4. Optional: ask "¿Querés agregar reglas específicas para situaciones comunes?" and help
   them write rule entries (e.g. how to handle price questions, meeting requests, etc.)

## Example persona

```json
{
  "name": "Your Name",
  "about": "Freelance developer, specialized in mobile and web apps.",
  "language": "es",
  "tone": "casual y amigable",
  "availability": "Lunes a viernes de 9 a 18hs",
  "rules": [
    "No confirmar reuniones ni llamadas sin que yo lo apruebe primero",
    "Si preguntan por precios, decir que depende del proyecto y pedir detalles",
    "No hablar de otros clientes ni proyectos en curso"
  ],
  "fallback_message": "Hola! No puedo responder ahora, te escribo pronto 👋",
  "llm": {
    "provider": "anthropic",
    "model": "claude-haiku-4-5-20251001"
  }
}
```

## Updating the persona

Just ask Dexter: "actualizá mi persona de WhatsApp" and describe what cambiar.
Dexter edits `~/.dexter/whatsapp-persona.json` directamente.

## View message history

```bash
cat ~/.dexter/whatsapp-messages.jsonl | tail -20
```

Each line: `{ ts, direction (in/out), from/to, text, tier (allowed/restricted/persona/fallback) }`

## Restart server after changes

```bash
# If running in background:
bash ~/.claude/skills/communications/whatsapp/server/start.sh --stop
bash ~/.claude/skills/communications/whatsapp/server/start.sh --background
```
