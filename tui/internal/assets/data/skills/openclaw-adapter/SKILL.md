---
name: openclaw-adapter
description: >
  Convert and install ClawHub/OpenClaw community skills into native Dexter format. Handles the 3-file ClawHub format (SKILL.md + _meta.json + .clawhub/origin.json) and runs security-auditor before activating.
  Trigger: "instalar skill de clawhub", "install clawhub skill", "convert openclaw skill", "usar skill de comunidad", "npx clawhub install".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
allowed-tools: Read, Write, Bash
---

# OpenClaw / ClawHub Adapter

Converts community skills from ClawHub/OpenClaw format to native Dexter format, verifies required binaries are installed, and runs security-auditor before activation.

## Install a ClawHub Skill

```bash
# 1. Install via npx (creates 3-file structure)
npx clawhub@latest install <skill-slug>

# 2. Convert to Dexter format + audit
python3 skills/openclaw-adapter/scripts/convert.py skills/<skill-slug>/

# 3. If PASS, skill is ready to use
```

## What the Converter Does

1. **Reads** `SKILL.md`, `_meta.json`, `origin.json` from the installed skill dir
2. **Parses** the inline JSON `metadata` field (ClawHub format)
3. **Converts** frontmatter to Dexter format — adds `license`, `source: clawhub`, proper `description` with trigger, `allowed-tools`
4. **Checks** required bins (`metadata.clawdbot.requires.bins`) are installed
5. **Runs** `security-auditor` — BLOCK means the skill is rejected
6. **Writes** converted `SKILL.md` back (original preserved as `SKILL.md.clawhub-original`)
7. **Reports** result and any install instructions for missing bins

## ClawHub Format (Input)

```yaml
---
name: {slug}
description: {one-liner}
homepage: https://...
metadata: {"clawdbot":{"emoji":"...","requires":{"bins":["binary"]},"install":[{"id":"go","kind":"go","module":"...","bins":["binary"],"label":"..."}]}}
---
```

## Dexter Format (Output)

```yaml
---
name: {slug}
description: >
  {original description}
  Trigger: {slug}, {derived keywords from description}
license: Apache-2.0
metadata:
  author: dexter
  version: "{version from _meta.json}"
  source: clawhub
  clawhub:
    registry: https://clawhub.ai
    slug: {slug}
    installedVersion: {version}
  clawdbot:
    requires:
      bins: ["{binary}"]
    install:
      - id: {id}
        kind: go|npm|brew|pip
        module: {package}
        bins: ["{binary}"]
allowed-tools: Bash, Read
---
```

## Manual Conversion

If auto-conversion fails:
```bash
# Inspect the skill
cat skills/<slug>/SKILL.md
cat skills/<slug>/_meta.json
cat skills/<slug>/.clawhub/origin.json

# Check required bins
which <binary>

# Run audit manually
python3 skills/security/security-auditor/scripts/audit.py skills/<slug>/
```

## Notes

- Skills with `BLOCK` severity from security-auditor are rejected — original files are preserved but skill is not activated
- gentle-ai plugins (if installed) are auto-detected — no conversion needed
- OpenClaw server-side features (WebSocket gateway, Pi agent) are not supported — Dexter runs agent-native
