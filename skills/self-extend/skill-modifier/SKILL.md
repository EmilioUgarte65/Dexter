---
name: skill-modifier
description: >
  Edit existing Dexter skill metadata: triggers, description, version, name.
  Creates .bak backup before any modification. Shows diff vs backup.
  Trigger: "modificar skill", "editar skill", "actualizar triggers", "skill modifier".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Skill Modifier

Edit existing Dexter skill metadata without breaking the skill's functionality.
**Always creates a `.bak` backup before modifying.**

## Usage

```bash
# Show current metadata of a skill
python3 skills/self-extend/skill-modifier/scripts/modify.py show skills/communications/telegram/SKILL.md

# Update trigger keywords
python3 skills/self-extend/skill-modifier/scripts/modify.py triggers \
  skills/communications/telegram/SKILL.md \
  "telegram, tg, send telegram, mensaje telegram, bot telegram, notificacion telegram"

# Update description
python3 skills/self-extend/skill-modifier/scripts/modify.py description \
  skills/communications/telegram/SKILL.md \
  "Send messages, files, and media via Telegram Bot API."

# Bump version
python3 skills/self-extend/skill-modifier/scripts/modify.py version \
  skills/communications/telegram/SKILL.md 1.1

# Rename skill (updates name field + moves directory)
python3 skills/self-extend/skill-modifier/scripts/modify.py rename \
  skills/communications/telegram/ tg-messenger

# Show diff vs last backup
python3 skills/self-extend/skill-modifier/scripts/modify.py diff \
  skills/communications/telegram/SKILL.md
```

## Safety

- A `.bak` file is created automatically before each edit
- Use `diff` to review changes before applying
- Rename creates a backup of the entire directory first
- Backup files: `SKILL.md.bak` in the same directory

## Notes

- `triggers` updates the `Trigger:` line inside the `description:` block
- `description` updates the full description block (preserves trigger line if not respecified)
- `version` updates `metadata.version` field
- `rename` renames the directory and updates the `name:` field
