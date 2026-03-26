---
name: skill-writer
description: >
  Auto-generates a new Dexter skill when no existing skill matches the user's request.
  Analyzes the request against the skill registry, builds a complete SKILL.md + Python
  script using the LLM runtime, runs the security gate, and registers the result.
  Trigger: crear skill, write skill, no skill for, necesito una skill, generate skill, inventar skill, programar skill
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Skill Writer

Auto-generates a new Dexter skill from a plain-language description when no existing skill
covers the requested capability. Runs a full 4-phase pipeline: intent analysis, LLM-based
generation, security gate, and registry registration.

## When to Use

Use this skill when:
- A user needs a capability that no existing skill in `.atl/skill-registry.md` covers
- The user explicitly asks to create/generate/write a new skill
- You've checked the registry and found no match for the requested task

Do NOT use this skill when an existing skill already covers the request — load that skill
instead.

## Pipeline

### Phase 1 — Intent Analysis
- Check `.atl/skill-registry.md` for any skill whose name or description matches the request
- If a match is found: inform the user and ask if they want to proceed anyway
- If no match: proceed to Phase 2

### Phase 2 — Skill Generation
- Detect available LLM runtime (`DEXTER_AGENT` env var, then `claude`, then `opencode`)
- Build a detailed prompt using Dexter's SKILL.md template and the user's request
- Call the LLM and parse output: SKILL.md block + script block (separated by `---SCRIPT---`)
- Scaffold the directory using `skill-creator/scripts/create.py`
- Write the generated SKILL.md and script into the scaffolded directory

### Phase 3 — Security Gate (MANDATORY)
- Run `security-auditor/scripts/audit.py <skill-dir> --json`
- Parse JSON result
- BLOCK/CRITICAL/HIGH findings → print report, ask user if they want to fix and retry
- WARN/PASS → proceed to registration
- Save audit result to Engram under `security-audit/<skill-name>`

### Phase 4 — Registration
- Copy approved skill to `~/.dexter/community/<category>/<name>/`
- Append entry to `.atl/skill-registry.md` with `provenance: generated` tag
- Print confirmation with trigger keywords

## LLM Runtime

The skill auto-detects the available agent CLI in this order:

1. `DEXTER_AGENT` environment variable (explicit override)
2. `claude` — Claude Code CLI
3. `opencode` — OpenCode CLI

If none are found, the script exits with a clear error and install instructions.

## Agent Instructions

When the user says "crear skill", "necesito una skill para X", "generate skill", or similar:

1. **Check registry first** — search `.atl/skill-registry.md` for any existing skill matching
   the request. If found, suggest it and ask user to confirm before generating.

2. **Run generation**:
   ```bash
   python3 skills/skill-writer/scripts/skill_writer.py generate "<user request>" \
     [--category <cat>] [--name <name>]
   ```

3. **Dry-run option** — if user wants to preview without writing files:
   ```bash
   python3 skills/skill-writer/scripts/skill_writer.py generate "<request>" --dry-run
   ```

4. **List generated skills**:
   ```bash
   python3 skills/skill-writer/scripts/skill_writer.py list-generated
   ```

5. **Report result** — if generation succeeded, tell the user the skill name, location, and
   trigger keywords they can use immediately.

### Common Patterns

| User says | Action |
|-----------|--------|
| "necesito una skill para Notion" | Run `generate "Notion page and database manager"` |
| "write a skill for Linear issues" | Run `generate "Linear issue tracker"` |
| "inventar skill para controlar Spotify" | Run `generate "Spotify playback controller"` |
| "dry run skill para AWS S3" | Run `generate "AWS S3 file manager" --dry-run` |

## Error Handling

- No LLM CLI found → script exits 1 with install instructions for `claude` or `opencode`
- Security gate BLOCK → findings printed, tmp dir deleted, user asked to fix or abort
- Registry keyword collision → user warned, asked whether to continue or rename
- `create.py` scaffold fails → check `DEXTER_SKILLS_DIR` is set or cwd is project root
