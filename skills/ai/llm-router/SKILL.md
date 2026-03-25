---
name: llm-router
description: >
  Route requests to the best available LLM provider with automatic fallback.
  Checks provider health and picks the fastest/cheapest available one.
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# LLM Router

Routes AI requests to the best available provider with automatic fallback.

## Config

Located at `~/.dexter/llm-router.json`. Template at `notifications/llm-router.template.json`.

## Check available providers

```bash
python3 ~/.claude/skills/ai/llm-router/scripts/check_providers.py --check-all
python3 ~/.claude/skills/ai/llm-router/scripts/check_providers.py --best
```

## When to use

Trigger keywords: modelo, proveedor, fallback LLM, cambiar modelo, si falla usa, backup model, router, qué modelo usar

## Agent Protocol

1. Run `--best` to find the fastest available provider
2. Use that provider for the current task
3. If it fails mid-task, run `--best` again and switch
4. Log usage is automatic (if log_usage: true in config)

## Provider priority

Configured in `~/.dexter/llm-router.json`. Lower priority number = preferred.
