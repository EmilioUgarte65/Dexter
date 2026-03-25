---
name: personal-kb
description: >
  Local markdown-based personal knowledge base. Add, search, list, get, update, and export notes.
  No cloud required. Storage in ~/knowledge/ by default.
  Trigger: "base de conocimiento", "personal kb", "knowledge base", "guardar conocimiento", "buscar en mis notas".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Personal Knowledge Base

Local markdown-based knowledge base. Every note is a `.md` file. No cloud, no database, no lock-in.

## Setup

```bash
# Default storage: ~/knowledge/
# Override with:
export PERSONAL_KB_DIR="/path/to/your/notes"
```

## Usage

```bash
# Add a note
python3 skills/knowledge/personal-kb/scripts/kb.py add "Docker networking basics" "Content here..." --tags docker,networking --folder devops

# Search full-text across all notes
python3 skills/knowledge/personal-kb/scripts/kb.py search "docker networking"

# List all notes
python3 skills/knowledge/personal-kb/scripts/kb.py list
python3 skills/knowledge/personal-kb/scripts/kb.py list --folder devops
python3 skills/knowledge/personal-kb/scripts/kb.py list --tag docker

# Get a specific note
python3 skills/knowledge/personal-kb/scripts/kb.py get "Docker networking basics"
python3 skills/knowledge/personal-kb/scripts/kb.py get devops/docker-networking-basics.md

# Update a note
python3 skills/knowledge/personal-kb/scripts/kb.py update "Docker networking basics" "Updated content..."

# Delete a note
python3 skills/knowledge/personal-kb/scripts/kb.py delete "Docker networking basics"

# Export all notes
python3 skills/knowledge/personal-kb/scripts/kb.py export --format json
python3 skills/knowledge/personal-kb/scripts/kb.py export --format zip
```

## File Structure

```
~/knowledge/
├── docker-networking-basics.md
├── devops/
│   └── docker-networking-basics.md
└── recipes/
    └── pasta-carbonara.md
```

Each note file:
```markdown
---
title: Docker networking basics
tags: docker, networking
created: 2024-03-15
---

Note content here...
```

## Notes

- Full-text search scans all `.md` files recursively
- Tags are stored in YAML frontmatter
- Folders map to subdirectories
- Export to JSON or ZIP for backup/portability
