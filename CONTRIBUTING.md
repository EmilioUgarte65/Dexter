# Contributing to Dexter

Thanks for your interest in contributing. Dexter is an ecosystem of markdown skills + shell scripts + a Go TUI installer — contributions don't require deep coding knowledge.

---

## Ways to contribute

- **New skill** — add a capability Dexter doesn't have yet
- **Improve an existing skill** — better instructions, more edge cases, cleaner commands
- **Bug fix** — installer, scripts, TUI binary
- **Documentation** — clearer setup, better examples
- **New agent support** — add a `paths.sh` for an agent not yet supported

---

## Adding a skill

A skill is a markdown file that teaches Dexter a workflow. No code required.

```
skills/
└── your-bundle/
    └── your-skill/
        ├── SKILL.md          ← required
        └── scripts/          ← optional Python/bash scripts
            └── your_script.py
```

### SKILL.md format

```markdown
---
name: your-skill
description: One-line description of what this skill does.
license: Apache-2.0
metadata:
  author: your-github-username
  version: "1.0"
  source: community
  audited: false
allowed-tools: Bash
---

# Your Skill

Brief explanation of the skill.

## When to use

Trigger keywords: ...

## Agent Protocol

Step-by-step instructions for the agent...

## Setup

Any credentials or config needed...
```

### Register the skill

1. Add it to `skills/_shared/bundle-loader.md` — pick the right bundle or create a new one
2. Add it to `CAPABILITIES.md` — one line in the bundle table
3. Add it to `.atl/skill-registry.md`

### Security requirement

All skills that make external HTTP calls, run shell commands with user input, or access sensitive files **must** pass `security-auditor` review. Set `audited: true` in the frontmatter only after the audit passes.

---

## Development setup

```bash
git clone https://github.com/EmilioUgarte65/Dexter.git
cd Dexter
```

No dependencies required for skill development. For the Go TUI:

```bash
cd tui
go build ./...
go test ./...
```

---

## Running tests

```bash
make test-scripts    # Python syntax + smoke tests (requires pytest)
make test-installer  # Installer flow tests (requires bats-core)
```

Tests run automatically on all Python scripts in `skills/`. Adding a script automatically adds a syntax test — no extra work needed.

---

## Commit conventions

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(bundle): add new-skill skill
fix(installer): handle missing Node.js gracefully
docs: update WhatsApp setup instructions
refactor(tui): simplify pipeline step runner
```

**Do not** add `Co-Authored-By` or AI attribution lines to commits.

---

## Pull request checklist

- [ ] Skill has valid SKILL.md frontmatter (name, description, license, metadata)
- [ ] Skill registered in `bundle-loader.md`, `CAPABILITIES.md`, and `skill-registry.md`
- [ ] Scripts are Python stdlib-only or pure bash (no heavy dependencies)
- [ ] `make test-scripts` passes
- [ ] No hardcoded secrets, API keys, or personal data
- [ ] Security-sensitive scripts note `audited: false` until reviewed

---

## Questions

Open an [issue](https://github.com/EmilioUgarte65/Dexter/issues) or start a [discussion](https://github.com/EmilioUgarte65/Dexter/discussions).
