---
name: bundle-loader
description: >
  Lazy bundle activation rules for Dexter.
  Trigger: Internal — referenced by DEXTER.md bundle loader section.
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
---

# Bundle Loader — Keyword Matching Rules

## Protocol

Bundle loading is LAZY. No bundle is pre-loaded at session start.
CAPABILITIES.md is always available as a lightweight index.

## Activation Steps

When a trigger keyword is detected:

1. Identify which bundle it belongs to (see Trigger Map below)
2. Check if bundle is already loaded this session — if yes, skip
3. Announce: `[Dexter] Activating {bundle} bundle...`
4. Read all SKILL.md files in `skills/{bundle}/`
5. Apply skill instructions to current task

## Trigger Map (Canonical)

```
communications → whatsapp | telegram | signal | slack | discord | teams | imessage
                 mensaje | chat | notificación | mensajería | enviar mensaje
                 persona whatsapp | cómo responder mensajes | auto-responder | responder por mí
                 → also load: skills/communications/whatsapp/persona/SKILL.md

email          → email | gmail | outlook | correo | bandeja | inbox | mail

productivity   → calendar | agenda | tarea | todoist | recordatorio | reminder
                 viaje | check-in | scheduling | reunión agendar

social         → twitter | x.com | wordpress | publicar | post | blog | red social

research       → investigar | buscar web | web browse | reporte | transcribir
                 meeting | transcribe | datos | data-aggregator

media          → video | audio | tts | voz | elevenlabs | grabar | meditar
                 meditation | podcast | narración

knowledge      → obsidian | nota | vault | base de conocimiento | personal kb
                 docs personales | nota personal

dev            → código | code | pr | github | sentry | bug | refactor | test
                 self-correct | simplify | implementar | función

cloud          → gcp | google cloud | hetzner | nube | cloud | servidor cloud
                 infraestructura cloud | deploy

infrastructure → cron | sistema | monitoreo | terminal | salud | whoop
                 automatización | sistema | proceso | servicio

domotics       → hogar | home assistant | mqtt | philips hue | hue | luces | iot
                 dispositivo | red local | sensor | zigbee | temperatura

security       → seguridad | auditoría | vulnerability | nmap | arp-scan | virustotal
                 hardening | plugin externo | skill externa | blocklist

ai-local       → ollama | modelo local | optimizar tokens | clasificar | resumir
                 token | local model | lightweight (ALWAYS ACTIVE — zero-cost check)

self-extend    → nueva skill | escribir skill | modificar skill | hot-reload
                 extender dexter | skill writer | skill modifier
```

## Compatibility Skills (Standalone — load by file path, not bundle dir)

These are not directory bundles. When a trigger matches, load the specific SKILL.md file directly.

```
clawflows-adapter → clawflows | workflow de comunidad | community workflow
                    quiero aplicar un workflow | importar workflow | usar workflow
                    workflow de clawflows | hay un workflow que | existe un workflow
                    → READ: skills/clawflows-adapter/SKILL.md

openclaw-adapter  → clawhub | openclaw | instalar skill de clawhub
                    skill de comunidad | skill externa | convert openclaw
                    → READ: skills/openclaw-adapter/SKILL.md
```

**Key behavior — intent matching**: Load `clawflows-adapter` BEFORE building from scratch when the user asks to **automate something recurring**. Heuristic: if the request sounds like a scheduled task or personal automation, ClawFlows likely has a pre-built workflow for it.

Examples that SHOULD trigger clawflows-adapter lookup:
| User says | Likely ClawFlows workflow |
|-----------|--------------------------|
| "mandame un briefing cada mañana" | `send-morning-briefing` |
| "procesá mis emails a las 9am" | `process-email` / `check-email` |
| "generame el standup automáticamente" | `build-standup` |
| "avisame de PRs pendientes" | `review-prs` |
| "poneme en modo sleep a las 10pm" | `activate-sleep-mode` |
| "armame el plan de la semana" | `plan-week` |
| "hacé el resumen del día" | `send-daily-wrap` |
| "preparame para la próxima reunión" | `prep-next-meeting` |
| "chequeá mis gastos semanalmente" | `track-budget` |
| "rastreá mis hábitos" | `track-habits` |

Flow when intent matches:
1. Load `skills/clawflows-adapter/SKILL.md`
2. Tell the user: "ClawFlows tiene un workflow pre-construido para eso: `<name>`. ¿Lo importamos?"
3. If yes → run the import + audit flow from the SKILL.md

## False-Positive Guard

Before activating a bundle, verify the keyword is used in the INTENT of the request, not incidentally. Examples:

| User message | Bundle activated? |
|-------------|------------------|
| "send a WhatsApp to mom" | ✅ communications |
| "call the function in my code" | ❌ communications (incidental "call") |
| "check my calendar" | ✅ productivity |
| "the code has a calendar struct" | ❌ productivity (code context) |

## Override

User can manually load a bundle: "load the domotics bundle" or "activate communications"
User can prevent loading: "don't load any bundles, just answer"

## Session State

Track loaded bundles per session to avoid reloading:
```
loaded_bundles: [communications, dev]  ← example session state
```
