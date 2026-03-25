---
name: ai
description: >
  AI routing and token optimization tools for Dexter.
  Routes tasks to local (Ollama) or cloud (Claude) models based on complexity.
  Tracks token usage and suggests skill creation for repeated patterns.
  Trigger: ollama, modelo local, local model, token optimizer, token usage, llama, mistral, router AI
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# AI Bundle

## Skills in this bundle

| Skill | Purpose |
|-------|---------|
| `ollama-router` | Route requests to local Ollama models, save cost on simple tasks |
| `token-optimizer` | Track token usage, suggest skill creation for repeated patterns |

## Routing Decision Tree

```
Is this task complex or needs judgment?
├── YES → Cloud (Claude/GPT)
│   └── architecture, security, SDD phases, multi-file analysis
└── NO → Local (Ollama)
    └── formatting, summaries, simple lookups, file ops

Does the prompt contain sensitive data (keys, PII, internal hosts)?
└── ALWAYS local → privacy first
```

## Quick start

```bash
# Check what models are available
python3 skills/ai/ollama-router/scripts/router.py models

# Get routing recommendation for a task
python3 skills/ai/ollama-router/scripts/router.py recommend "summarize this README"

# Check your token spending this week
python3 skills/ai/token-optimizer/scripts/optimizer.py report --days 7

# See skill creation suggestions
python3 skills/ai/token-optimizer/scripts/optimizer.py suggest
```
