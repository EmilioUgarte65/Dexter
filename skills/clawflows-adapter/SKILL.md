---
name: clawflows-adapter
description: >
  Import ClawFlows community workflows (WORKFLOW.md format) into Dexter as native SKILL.md files, with optional cron scheduling via the cron-tasks skill.
  Trigger: "importar workflow de clawflows", "import clawflows workflow", "usar workflow de comunidad", "clawflows install".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Read, Write, Bash
---

# ClawFlows Adapter

Converts a [ClawFlows](https://github.com/nikilster/clawflows) `WORKFLOW.md` into a native Dexter `SKILL.md`, maps OpenClaw skill references to Dexter equivalents, and optionally registers the schedule with the **cron-tasks** skill.

## What is ClawFlows?

ClawFlows is a community workflow library for OpenClaw — 112+ pre-built automation workflows (morning briefings, email triage, smart home, dev tools, etc.) defined in a simple `WORKFLOW.md` format.

Dexter can import and run these workflows natively. The body of each workflow is already plain Markdown agent instructions — no scripting conversion needed.

## Importing a Workflow

### Option A — from a local WORKFLOW.md

```bash
# Preview the conversion (stdout, nothing written)
python3 skills/clawflows-adapter/scripts/import_workflow.py path/to/WORKFLOW.md

# Write to a Dexter skill directory
python3 skills/clawflows-adapter/scripts/import_workflow.py path/to/WORKFLOW.md \
  --output skills/workflows/check-email/
```

### Option B — from the clawflows GitHub repo

```bash
# Clone the full library (112+ workflows)
git clone https://github.com/nikilster/clawflows /tmp/clawflows

# Import one workflow
python3 skills/clawflows-adapter/scripts/import_workflow.py \
  /tmp/clawflows/workflows/available/community/build-standup/WORKFLOW.md \
  --output skills/workflows/build-standup/
```

## Full Import + Audit Flow

```bash
# 1. Convert
python3 skills/clawflows-adapter/scripts/import_workflow.py \
  /tmp/clawflows/workflows/available/community/<name>/WORKFLOW.md \
  --output skills/workflows/<name>/

# 2. Audit (mandatory — clawflows workflows are external/community content)
python3 skills/security/security-auditor/scripts/audit.py skills/workflows/<name>/

# 3. If PASS → register schedule (if the workflow has one)
#    Check skills/workflows/<name>/SKILL.md for metadata.cron
#    Then use cron-tasks skill to register

# 4. Enable — skill is now available
```

## ClawFlows Format → Dexter Format

| ClawFlows field | Dexter field |
|----------------|--------------|
| `name` | `name` |
| `emoji` | prepended to description |
| `description` | `description` (with trigger keywords) |
| `author` | `metadata.clawflows_author` |
| `schedule` | `metadata.schedule` (preserved as-is) + `metadata.cron` (converted) |
| Body (Markdown steps) | Body (agent instructions, unchanged) |

## Schedule Conversion

ClawFlows uses plain English. The adapter converts to cron:

| ClawFlows | Cron |
|-----------|------|
| `"9am"` | `0 9 * * *` |
| `"9am, 1pm, 5pm"` | `0 9 * * *` + `0 13 * * *` + `0 17 * * *` |
| `"Monday 9am"` | `0 9 * * 1` |
| `"1st 9am"` | `0 9 1 * *` |
| `"every 2 hours"` | `0 */2 * * *` |
| `"On-demand"` | _(no cron — manual only)_ |

## OpenClaw → Dexter Skill Reference Mapping

ClawFlows workflows say "your **email skill**", "your **calendar skill**", etc. These map to Dexter:

| ClawFlows reference | Dexter skill |
|--------------------|--------------|
| `email skill` | `skills/productivity/gmail/` |
| `calendar skill` | `skills/productivity/calendar/` |
| `task manager skill` | `skills/productivity/todoist/` |
| `github skill` | `skills/productivity/github/` |
| `slack skill` | `skills/communications/slack/` |
| `discord skill` | `skills/communications/discord/` |
| `telegram skill` | `skills/communications/telegram/` |
| `whatsapp skill` | `skills/communications/whatsapp/` |
| `obsidian skill` | `skills/knowledge/personal-kb/` |
| `home assistant skill` | `skills/domotics/home-assistant/` |
| `tts skill` | `skills/productivity/elevenlabs/` |

The converted SKILL.md includes a **Dexter Skill Mapping** section when these references are detected.

## Notes

- ClawFlows was designed for OpenClaw. The `clawflows run <name>` CLI invokes the `openclaw` binary — this is NOT used in Dexter. Dexter runs workflows as agent instructions directly.
- The scheduler (`scheduler.md`) and dashboard (`system/dashboard/`) are OpenClaw-specific and are not imported.
- Custom workflows (`workflows/custom/`) follow the same WORKFLOW.md format — they import identically.
- Always run `security-auditor` before executing an imported workflow — community content is external.
