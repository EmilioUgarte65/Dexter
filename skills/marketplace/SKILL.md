---
name: marketplace
description: >
  Dexter Marketplace — unified skill discovery, installation, and browsing from all sources.
  Trigger: marketplace, buscar skill, instalar skill, install skill, hay una skill para, dexter install, browse skills, update skills, list installed
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Dexter Marketplace

Unified skill discovery, installation, and browsing from all sources: dexter-marketplace GitHub repo, ClawHub, community GitHub (topic: dexter-skill), and ClawFlows.

## When to Use

Use this skill when the user wants to:
- Find a skill for a specific task ("is there a skill for X?")
- Browse available skills by category
- Install a skill from the community
- Update the local skill index
- List what marketplace skills are currently installed

## Sources

| Source | Description | Backend |
|--------|-------------|---------|
| `dexter-marketplace` | Official curated skills — `github.com/EmilioUgarte65/dexter-marketplace` | GitHub API tree |
| `clawhub` | ClawHub community registry | `npx clawhub` CLI |
| `github` | Community repos tagged `topic:dexter-skill` | GitHub Search API |
| `clawflows` | ClawFlows automation workflows — `github.com/nikilster/clawflows` | GitHub API tree |

## Commands

### Search for a skill
```bash
python3 skills/marketplace/scripts/marketplace.py search "<query>"
```
Example: `python3 skills/marketplace/scripts/marketplace.py search "calendar reminder"`

### Browse by category
```bash
python3 skills/marketplace/scripts/marketplace.py browse
python3 skills/marketplace/scripts/marketplace.py browse productivity
```

### Install a skill
```bash
python3 skills/marketplace/scripts/marketplace.py install <category/name>
python3 skills/marketplace/scripts/marketplace.py install productivity/reminder --source dexter-marketplace
```

### Refresh the local index
```bash
python3 skills/marketplace/scripts/marketplace.py update-index
```

### List installed marketplace skills
```bash
python3 skills/marketplace/scripts/marketplace.py list-installed
```

## Security

All installs go through the security-auditor automatically. The flow is:
1. Download skill files to a temp directory
2. Run `audit.py <tmp_dir> --json`
3. If result is `BLOCK` — install is aborted, temp files are deleted, findings are reported
4. If result is `PASS` or `WARN` — skill is copied to `~/.dexter/community/<category>/<name>/` and registered

No skill from any external source bypasses this gate.

## Agent Instructions

When the user asks about finding, installing, or browsing skills, follow these steps:

1. **Detect intent** — is the user searching, browsing, installing, or listing?
2. **Check the local index first** — run `search` or `browse` to avoid unnecessary network calls
3. **If index is stale** — the script auto-refreshes; you can also run `update-index` explicitly
4. **For install requests** — confirm the skill name/slug with the user before proceeding
5. **Report the result** — show what was installed, any warnings from the audit, and the registry path
6. **On BLOCK** — explain which findings caused the block; suggest `--source` flag to try an alternative source

### ClawHub note

ClawHub requires `npx`. If it is not installed, the adapter prints a warning with an install hint and returns empty results — it does NOT silently skip. If the user wants ClawHub results, help them install `npx` first.

### GitHub rate limits

Unauthenticated GitHub API calls are limited to 60 requests/hour. If the user hits rate limits, suggest setting `GITHUB_TOKEN`:
```bash
export GITHUB_TOKEN=<your-token>
python3 skills/marketplace/scripts/marketplace.py update-index
```
