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
