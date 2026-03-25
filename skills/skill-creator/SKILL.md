---
name: skill-creator
description: >
  Helps users create new Dexter skills from a description. Scaffolds SKILL.md
  and scripts/ with all boilerplate. Teaches the token-saving philosophy: document
  the recipe once, reuse forever — instead of the AI reasoning from scratch each time.
  Trigger: "crear skill", "nueva skill", "create skill", "new skill", "haz una skill",
  "skill para X", "documentar workflow", "recipe", "quiero una skill"
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Skill Creator

The most important skill in Dexter. Helps you create new skills — which are themselves
the primary mechanism for saving tokens across sessions.

## Philosophy: Skills as Cached Knowledge

> "The first time you solve a problem, the AI reasons from scratch — that costs tokens.
> You write a skill. Every future request follows the recipe. 10-20x fewer tokens."

**Without a skill**: User asks → AI reasons → AI experiments → AI responds (300-2000 tokens)
**With a skill**: User triggers → Dexter loads recipe → follows steps directly (50-200 tokens)

Skills are NOT code generators. They are **pre-documented recipes** — structured knowledge
the agent follows without needing to rediscover. Think of them like a senior engineer's
runbook: "When X happens, do Y, Z, W in this exact order."

### When to Create a Skill

- You ask Dexter the same question more than twice
- You have a multi-step workflow with specific commands
- You want consistent behavior across sessions and agents
- You want to share your workflow with others

### When NOT to Create a Skill

- One-off tasks that will never repeat
- Tasks better served by a general-purpose prompt
- When a simpler alias or shell function would suffice

---

## SKILL.md Frontmatter — Complete Template

<!-- NOTE: The yaml block below is an EXAMPLE TEMPLATE for skills you create.
     It is NOT this file's own frontmatter configuration. -->
```yaml
---
name: {name}                          # kebab-case, unique within category
description: >
  {One paragraph describing what this skill does.}
  {Include what APIs/tools it uses and any fallback strategy.}
  Trigger: {comma-separated list of trigger keywords}
license: Apache-2.0                   # always Apache-2.0 for dexter skills
metadata:
  author: dexter                      # "dexter" for official, your handle for personal
  version: "1.0"                      # bump on breaking changes
  source: dexter                      # "dexter" = trusted. "community" = review required
  audited: true                       # true only for dexter-official skills
# NOTE: example template, not this file's config
allowed-tools: Bash                   # Bash | Read | Edit | Write | Bash,Read (comma list)
---
```

### Fields Explained

| Field | Required | Notes |
|-------|----------|-------|
| `name` | yes | Must match directory name. kebab-case. |
| `description` | yes | Include trigger keywords IN the description. The AI searches this. |
| `license` | yes | Apache-2.0 for official. MIT or custom for personal. |
| `metadata.author` | yes | "dexter" for official skills. |
| `metadata.version` | yes | Semver string. Quote it: `"1.0"` not `1.0` |
| `metadata.source` | yes | `dexter` = audited/trusted. `community` = security review required. |
| `metadata.audited` | yes | `true` only after security review. |
| `allowed-tools` | yes | Comma-separated list of Claude tools this skill uses. |

---

## Trigger Keyword Design

Trigger keywords are how Dexter detects which skill to activate. Write them carefully.

### Good triggers (specific, unambiguous)

```
Trigger: "hetzner", "VPS hetzner", "servidor hetzner", "deploy hetzner"
Trigger: "gmail", "send email", "correo", "mandar mail", "leer inbox"
```

### Bad triggers (too generic — false positives)

```
Trigger: "server"           # triggers on "my server is slow" unrelated to Hetzner
Trigger: "email"            # conflicts with gmail skill
Trigger: "create"           # would fire on every request
```

### Rules for good triggers

1. **Include the tool/service name** — "hetzner", "gcloud", "obsidian"
2. **Include task variants** — "deploy", "start vm", "list servers"
3. **Include Spanish variants** if the user base speaks Spanish
4. **Avoid single common words** — "file", "run", "check" are noise
5. **Test for false positives** — would this keyword appear in unrelated sentences?

---

## Script vs Inline Instructions

### Use a `scripts/` directory when:

- The task requires >3 shell commands chained together
- You need to parse JSON responses from an API
- Error handling matters (partial failures, retries)
- You need to maintain state between calls (tokens, session IDs)
- The workflow has branches (if VM is stopped → start first, then SSH)
- You want the user to call it directly: `python3 scripts/hetzner.py list-servers`

### Use inline Bash instructions when:

- It's 1-2 simple commands with no branching
- No API parsing needed
- Example: "Run `git pull && docker compose up -d`"

### The `scripts/` directory structure

```
skills/{category}/{name}/
├── SKILL.md           ← always present
└── scripts/
    ├── main.py        ← entry point (or named after the skill: hetzner.py)
    └── template.py    ← optional: shared templates/helpers
```

---

## Script Anatomy — Required Patterns

Every Dexter script MUST follow this pattern:

```python
#!/usr/bin/env python3
"""
Dexter — {skill name} client.
Describe what it does and fallback strategy.

Usage:
  {name}.py command1 [args]
  {name}.py command2 <required> [--optional VALUE]
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Optional

# ─── Config from env ──────────────────────────────────────────────────────────

API_TOKEN = os.environ.get("SERVICE_API_TOKEN", "")
BASE_URL   = "https://api.service.example.com/v1"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"


def check_config():
    """Validate required env vars before any API call."""
    missing = []
    if not API_TOKEN:
        missing.append("SERVICE_API_TOKEN")
    if missing:
        print(
            f"{RED}Error: Missing required environment variables:{RESET}",
            file=sys.stderr,
        )
        for var in missing:
            print(f"  export {var}=your_value_here", file=sys.stderr)
        sys.exit(1)


# ─── API helpers ──────────────────────────────────────────────────────────────

def api_request(method: str, path: str, data: dict | None = None) -> dict:
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode() if data else None
    req  = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"{RED}API error {e.code}: {error_body}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_list(args):
    check_config()
    items = api_request("GET", "/items")
    for item in items.get("items", []):
        status_color = GREEN if item["status"] == "running" else YELLOW
        print(f"  {status_color}{item['name']}{RESET} — {item['status']}")


def cmd_create(args):
    check_config()
    result = api_request("POST", "/items", {"name": args.name})
    print(f"{GREEN}Created: {result['name']} (id={result['id']}){RESET}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Dexter — {skill} client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list
    sub.add_parser("list", help="List all items")

    # create
    p_create = sub.add_parser("create", help="Create a new item")
    p_create.add_argument("name", help="Item name")

    args = parser.parse_args()

    dispatch = {
        "list":   cmd_list,
        "create": cmd_create,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
```

### Required elements (checklist)

- [ ] `#!/usr/bin/env python3` shebang
- [ ] Module docstring with Usage section
- [ ] `check_config()` validates env vars and prints export instructions
- [ ] `GREEN`, `RED`, `YELLOW`, `RESET` color constants
- [ ] Section comments: `# ─── Section ────────────────────`
- [ ] `argparse` with subparsers
- [ ] `if __name__ == "__main__": main()`
- [ ] stdlib only unless a fallback imports optional deps (try/except ImportError)

---

## SKILL.md Body Structure

After the frontmatter, write the skill body in Markdown:

```markdown
# {Skill Name}

One-sentence description of what this skill does.

## Setup

Environment variables required:
```bash
export SERVICE_API_TOKEN="your_token_here"
export SERVICE_DEFAULT_ZONE="us-central1-a"   # optional with default
```

How to get credentials (links, steps).

## Usage

### List items
```bash
python3 skills/{category}/{name}/scripts/{name}.py list
```

### Create item
```bash
python3 skills/{category}/{name}/scripts/{name}.py create my-item
```

## Agent Instructions

When the user mentions {trigger keywords}:

1. **Detect intent** — what action do they want? (list / create / delete)
2. **Check config** — `check_config()` will print clear error if env vars missing
3. **Run command** — call the script with the right subcommand and args
4. **Report result** — summarize what was done in plain language

### Common patterns

| User says | Command to run |
|-----------|---------------|
| "list my items" | `python3 scripts/{name}.py list` |
| "create item foo" | `python3 scripts/{name}.py create foo` |

## Error Handling

- Missing env var → `check_config()` prints export instructions and exits 1
- API 401 → token expired or wrong; print token setup instructions
- API 404 → item not found; suggest `list` to see available names
```

---

## Complete Example: A Working Skill

> **Note**: The "Ping Monitor" below is a fictional example skill used to illustrate
> the structure. `ping.py` and `collect.py` are example script names for
> user-created skills — they do not exist in the skill-creator itself.

Here's a minimal but complete skill for a fictional "Ping Monitor" that monitors URLs:

**Directory**: `skills/productivity/ping-monitor/`

**SKILL.md**:
```yaml
---
name: ping-monitor
description: >
  Monitors URLs and reports HTTP status. Checks if a website is up or down.
  Uses stdlib urllib — no external dependencies.
  Trigger: "ping", "check url", "is site up", "monitor url", "website down"
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Ping Monitor

Checks if URLs are responding with HTTP 200. No setup required.

## Usage

```bash
python3 skills/productivity/ping-monitor/scripts/ping.py check https://example.com
python3 skills/productivity/ping-monitor/scripts/ping.py check-many urls.txt
```

## Agent Instructions

When the user asks to check if a site is up:
1. Extract the URL from their message
2. Run `ping.py check <url>`
3. Report: UP (green) or DOWN (red) with status code
```

**scripts/ping.py**:
```python
#!/usr/bin/env python3
"""
Dexter — URL ping monitor.
Checks if URLs respond with HTTP 200.

Usage:
  ping.py check <url>
  ping.py check-many <file_with_urls>
"""
import sys
import argparse
import urllib.request

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"

def cmd_check(args):
    try:
        with urllib.request.urlopen(args.url, timeout=10) as r:
            print(f"{GREEN}UP{RESET}  {args.url} — HTTP {r.status}")
    except Exception as e:
        print(f"{RED}DOWN{RESET} {args.url} — {e}")

def main():
    parser = argparse.ArgumentParser(description="Dexter — URL ping monitor")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("check")
    p.add_argument("url")
    args = parser.parse_args()
    {"check": cmd_check}[args.command](args)

if __name__ == "__main__":
    main()
```

---

## Using the Scaffold Script

```bash
# Interactive (recommended for first-time skill authors)
python3 skills/skill-creator/scripts/create.py new my-workflow --interactive

# Quick scaffold with flags
python3 skills/skill-creator/scripts/create.py new deploy-hetzner \
  --category productivity \
  --description "Deploy app to Hetzner VPS"

# Validate an existing skill before using it
python3 skills/skill-creator/scripts/create.py validate skills/productivity/my-workflow/

# List all installed skills
python3 skills/skill-creator/scripts/create.py list
python3 skills/skill-creator/scripts/create.py list --category productivity
```

## Security Checklist Before Publishing

- [ ] `source: dexter` only if contributed to official Dexter repo
- [ ] `audited: true` only after security review (no exfiltration, no eval)
- [ ] No hardcoded API keys or passwords anywhere in SKILL.md or scripts/
- [ ] API calls go only to the documented service (not third-party proxies)
- [ ] `check_config()` never logs the value of secrets, only their presence
