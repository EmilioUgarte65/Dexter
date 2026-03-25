---
name: skill-hot-reload
description: >
  Registers skills for next-session activation by injecting them into CLAUDE.md.
  Claude cannot hot-reload mid-session — this prepares skills for the NEXT session.
  Trigger: "recargar skill", "hot reload", "activar skill", "skill reload".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Skill Hot Reload

Manages skill activation across Claude sessions.

## IMPORTANT: Why "hot reload" is not actually hot

Claude's capabilities are determined at session start when CLAUDE.md is loaded. There is **no way to inject new skills mid-session** — the model's instruction context is fixed once the conversation begins.

What this tool does instead:
1. **`reload`** — registers a skill in `~/.claude/CLAUDE.md` under an "Active Skills" section. The skill becomes available in the **next session**.
2. **`inject`** — writes a `context_inject.md` file that you can reference manually. It doesn't change what Claude knows, but gives you a prompt to paste.
3. **`status`** — lists all skills registered for next-session load.
4. **`purge`** — removes injected skills from CLAUDE.md.

## Usage

```bash
# Register a skill for next-session activation
python3 skills/self-extend/skill-hot-reload/scripts/reload.py reload skills/social/twitter-x/SKILL.md

# List registered skills
python3 skills/self-extend/skill-hot-reload/scripts/reload.py status

# Inject skill description into a context file (for manual reference)
python3 skills/self-extend/skill-hot-reload/scripts/reload.py inject skills/social/twitter-x/SKILL.md

# Remove all injected skills from CLAUDE.md
python3 skills/self-extend/skill-hot-reload/scripts/reload.py purge
```

## How Registration Works

`reload` adds an entry to `~/.claude/CLAUDE.md` under this section:

```markdown
## Active Skills (Next Session)
| skills/social/twitter-x/SKILL.md | twitter-x | Registered: 2024-03-15 |
```

On next session start, Claude reads CLAUDE.md and sees these entries — the skills are then available as context.

## Limitation

Claude Code no soporta recarga de instrucciones en-sesión. Los skills registrados con este skill estarán disponibles en la **próxima sesión**.

The session context is fixed when the conversation starts — there is no API or mechanism to inject new instructions mid-session. Any skill registered via `reload` takes effect only after starting a new Claude Code session.

## Notes

- This does NOT affect the current session
- Multiple skills can be registered at once
- `purge` removes ALL entries from the Active Skills section
- The `inject` command creates `context_inject.md` in the current directory
