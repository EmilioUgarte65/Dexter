---
name: obsidian
description: >
  Interact with your Obsidian vault via the Local REST API plugin.
  Create notes, append content, read, search, and list notes.
  Trigger: "obsidian", "nota", "vault", "nota obsidian", "crear nota", "apuntes", "knowledge base".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Obsidian

Manages your Obsidian vault via the [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) community plugin.

## Setup

1. Install **Local REST API** plugin in Obsidian: Community Plugins → Browse → "Local REST API"
2. Enable the plugin and copy the API key from plugin settings
3. Note the port (default: 27123)

```bash
export OBSIDIAN_API_URL="http://localhost:27123"   # default
export OBSIDIAN_API_KEY="your-api-key-from-plugin-settings"
```

## Usage

```bash
# Create a new note
python3 skills/productivity/obsidian/scripts/obsidian.py new "Meeting Notes" "# Team Sync\n\n- Action item 1\n- Action item 2"

# Create in a specific folder
python3 skills/productivity/obsidian/scripts/obsidian.py new "Daily Note" "Today was productive." --folder "Daily Notes"

# Append content to a note
python3 skills/productivity/obsidian/scripts/obsidian.py append "Projects/Dexter.md" "\n## Phase 4 complete!"

# Read a note
python3 skills/productivity/obsidian/scripts/obsidian.py read "Projects/Dexter.md"

# Search notes
python3 skills/productivity/obsidian/scripts/obsidian.py search "phase 4"

# List notes in vault or folder
python3 skills/productivity/obsidian/scripts/obsidian.py list
python3 skills/productivity/obsidian/scripts/obsidian.py list --folder "Projects"
```

## Notes

- `OBSIDIAN_API_URL` — default `http://localhost:27123`; change if you configured a different port
- `OBSIDIAN_API_KEY` — required. Found in Obsidian → Settings → Local REST API
- Note paths are relative to vault root (e.g. `Projects/Dexter.md`)
- `new` creates `.md` extension automatically if not included
- Obsidian must be running for the plugin API to respond
