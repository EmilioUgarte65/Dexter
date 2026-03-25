---
name: ollama-router
description: >
  AI router that decides whether a task should be handled by a local Ollama model
  or a cloud model (Claude/GPT). Routes lightweight tasks to Ollama to save cost.
  Trigger: ollama, modelo local, local model, router, llama, mistral, router AI
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Ollama Router Skill

## Purpose

Route AI tasks to the cheapest capable model. Local Ollama for simple tasks, cloud
models for anything requiring judgment, architecture decisions, or multi-file reasoning.

## Routing Rules

### Route to LOCAL (Ollama) when:
- Simple lookups, definitions, or factual questions with short answers
- Code formatting, linting, basic style fixes (no logic changes)
- Short text summaries (< 500 words source)
- File operations: rename suggestions, path normalization, glob patterns
- Template filling with known values
- Estimated output < 500 tokens
- **ANY task containing credentials, API keys, passwords, PII, or internal hostnames** → local-only (privacy rule — non-negotiable)

### Route to CLOUD (Claude/GPT) when:
- Architecture decisions or design reviews
- Security auditing or vulnerability analysis
- Multi-file analysis or cross-cutting refactors
- SDD phases (propose, spec, design, apply, verify)
- Tasks requiring judgment, nuance, or domain expertise
- Debugging complex runtime errors with unclear root cause
- Anything where a wrong answer causes irreversible harm
- Estimated output > 500 tokens or reasoning chains needed

## Privacy Rule (MANDATORY)

If the prompt or context contains ANY of:
- API keys, tokens, secrets, passwords
- PII (names + contact info, SSNs, financial data)
- Internal hostnames, IP ranges, or network topology
- Database connection strings

→ **Route to local Ollama ONLY. Never send to cloud.** Flag this to the user.

## How to Use the Router

### Before delegating any task, check routing:

```bash
# Get a recommendation for your task description
python3 skills/ai/ollama-router/scripts/router.py recommend "<task description>"

# Check available local models
python3 skills/ai/ollama-router/scripts/router.py models

# Check Ollama status
python3 skills/ai/ollama-router/scripts/router.py status
```

### If recommendation is "local":
Send the task to Ollama:
```bash
python3 skills/ai/ollama-router/scripts/router.py ask "<prompt>" [--model llama3.2] [--stream]
```

### If recommendation is "cloud":
Delegate normally to Claude/GPT via the orchestrator.

## Decision Flowchart

```
Contains sensitive data (keys, PII, internal hosts)?
└── YES → Ollama local-only (privacy rule)
└── NO ↓

Estimated output > 500 tokens OR needs judgment/reasoning?
└── YES → Cloud (Claude/GPT)
└── NO ↓

SDD phase, security audit, or architecture decision?
└── YES → Cloud (Claude/GPT)
└── NO → Ollama local
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_DEFAULT_MODEL` | `llama3.2` | Default model when none specified |

## Script Reference

```bash
# Full command reference
python3 skills/ai/ollama-router/scripts/router.py --help

# Commands:
#   ask <prompt>          Send prompt to Ollama, get response
#   models                List available local models
#   recommend <desc>      Print routing recommendation
#   pull <model>          Pull model from Ollama registry
#   status                Check Ollama health + loaded models
```

## When Ollama Is Unavailable

If `status` returns an error, fall back to cloud silently. Log a warning but do not
block the task. The router degrades gracefully — local unavailability is not a failure.
