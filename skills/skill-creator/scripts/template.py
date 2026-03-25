#!/usr/bin/env python3
"""
Dexter — Skill template generator.
Generates boilerplate SKILL.md and scripts/main.py for new Dexter skills.

Imported by create.py — not intended to be run directly.
"""

from typing import Optional


# ─── SKILL.md generator ───────────────────────────────────────────────────────

def generate_skill_md(
    name: str,
    category: str,
    description: str,
    triggers: list[str],
    has_script: bool,
    author: str = "dexter",
) -> str:
    """
    Generate the full content of a SKILL.md file.

    Args:
        name:        kebab-case skill name (e.g. "deploy-hetzner")
        category:    skill category (e.g. "productivity")
        description: one-paragraph description of what the skill does
        triggers:    list of trigger keyword strings
        has_script:  whether a scripts/ directory will be created
        author:      metadata.author value (default: "dexter")

    Returns:
        Complete SKILL.md content as a string.
    """
    trigger_line = ", ".join(f'"{t}"' for t in triggers)
    script_section = _script_section(name, category) if has_script else _inline_section()
    script_ref = (
        f"\n  Trigger: {trigger_line}"
    )

    return f"""---
name: {name}
description: >
  {description}
  Trigger: {", ".join(triggers)}
license: Apache-2.0
metadata:
  author: {author}
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# {_title(name)}

{description}

## Setup

```bash
# Set required environment variables
export {name.upper().replace("-", "_")}_API_TOKEN="your_token_here"
```

## Usage

{script_section}

## Agent Instructions

When the user mentions {trigger_line}:

1. **Detect intent** — what action do they want?
2. **Check config** — ensure required env vars are set
3. **Run command** — execute the appropriate subcommand
4. **Report result** — summarize the outcome in plain language

### Trigger keywords

{chr(10).join(f"- `{t}`" for t in triggers)}

## Error Handling

- Missing env var → script prints export instructions and exits with code 1
- API errors → script prints status code and response body
- Not found → suggest listing available resources
"""


def _title(name: str) -> str:
    """Convert kebab-case to Title Case."""
    return " ".join(word.capitalize() for word in name.split("-"))


def _script_section(name: str, category: str) -> str:
    script_name = name.replace("-", "_")
    base = f"skills/{category}/{name}/scripts/{script_name}.py"
    return f"""### List resources
```bash
python3 {base} list
```

### Get status
```bash
python3 {base} status <name>
```

### Create resource
```bash
python3 {base} create <name> [--option VALUE]
```

### Delete resource
```bash
python3 {base} delete <name>
```"""


def _inline_section() -> str:
    return """### Check status
```bash
# Add your commands here
echo "Replace with actual commands"
```"""


# ─── Script generator ─────────────────────────────────────────────────────────

def generate_script(name: str, commands: Optional[list[str]] = None) -> str:
    """
    Generate a boilerplate argparse script for a new skill.

    Args:
        name:     skill name (kebab-case), used for the script filename and description
        commands: list of subcommand names to scaffold (default: ["list", "create", "delete"])

    Returns:
        Complete Python script content as a string.
    """
    if commands is None:
        commands = ["list", "create", "delete"]

    env_prefix = name.upper().replace("-", "_")
    script_var  = name.replace("-", "_")
    title       = _title(name)

    # Build subparser blocks
    subparser_defs = _build_subparser_defs(commands, env_prefix)
    cmd_functions  = _build_cmd_functions(commands, env_prefix)
    dispatch_lines = "\n        ".join(
        f'"{cmd}": cmd_{cmd.replace("-", "_")},' for cmd in commands
    )

    return f"""#!/usr/bin/env python3
\"\"\"
Dexter — {title} client.
{title} integration via REST API with stdlib urllib.

Usage:
{chr(10).join(f"  {script_var}.py {cmd} [args]" for cmd in commands)}
\"\"\"

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Optional

# ─── Config from env ──────────────────────────────────────────────────────────

API_TOKEN = os.environ.get("{env_prefix}_API_TOKEN", "")
BASE_URL   = os.environ.get("{env_prefix}_BASE_URL", "https://api.example.com/v1")

GREEN  = "\\033[92m"
RED    = "\\033[91m"
YELLOW = "\\033[93m"
RESET  = "\\033[0m"


def check_config():
    \"\"\"Validate required env vars. Prints instructions and exits 1 if missing.\"\"\"
    missing = []
    if not API_TOKEN:
        missing.append("{env_prefix}_API_TOKEN")
    if missing:
        print(f"{{RED}}Error: Missing required environment variables:{{RESET}}", file=sys.stderr)
        for var in missing:
            print(f"  export {{var}}=your_value_here", file=sys.stderr)
        sys.exit(1)


# ─── API helpers ──────────────────────────────────────────────────────────────

def api_request(method: str, path: str, data: dict | None = None) -> Any:
    \"\"\"Make an authenticated API request. Exits on HTTP error.\"\"\"
    url  = f"{{BASE_URL}}{{path}}"
    body = json.dumps(data).encode() if data else None
    req  = urllib.request.Request(
        url,
        data=body,
        headers={{
            "Authorization": f"Bearer {{API_TOKEN}}",
            "Content-Type": "application/json",
        }},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"{{RED}}API error {{e.code}}: {{error_body}}{{RESET}}", file=sys.stderr)
        sys.exit(1)


# ─── Commands ─────────────────────────────────────────────────────────────────

{cmd_functions}

# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Dexter — {title} client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

{subparser_defs}

    args = parser.parse_args()

    dispatch = {{
        {dispatch_lines}
    }}
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
"""


def _build_cmd_functions(commands: list[str], env_prefix: str) -> str:
    """Generate stub function bodies for each subcommand."""
    blocks = []
    for cmd in commands:
        fn_name = cmd.replace("-", "_")
        if cmd == "list":
            body = (
                "    check_config()\n"
                "    items = api_request(\"GET\", \"/resources\")\n"
                "    for item in items.get(\"resources\", []):\n"
                "        print(f\"  {GREEN}{item['name']}{RESET} — {item.get('status', 'unknown')}\")"
            )
        elif cmd == "create":
            body = (
                "    check_config()\n"
                "    result = api_request(\"POST\", \"/resources\", {\"name\": args.name})\n"
                "    print(f\"{GREEN}Created: {result['name']} (id={result['id']}){RESET}\")"
            )
        elif cmd == "delete":
            body = (
                "    check_config()\n"
                "    api_request(\"DELETE\", f\"/resources/{args.name}\")\n"
                "    print(f\"{GREEN}Deleted: {args.name}{RESET}\")"
            )
        else:
            body = (
                "    check_config()\n"
                "    # TODO: implement\n"
                "    print(f\"{YELLOW}Command '{cmd}' not yet implemented{RESET}\")"
            )
        blocks.append(f"def cmd_{fn_name}(args):\n{body}\n")
    return "\n".join(blocks)


def _build_subparser_defs(commands: list[str], env_prefix: str) -> str:
    """Generate subparser add_parser() calls with common arguments."""
    lines = []
    for cmd in commands:
        fn_name = cmd.replace("-", "_")
        lines.append(f"    # {cmd}")
        if cmd == "create":
            lines.append(f"    p_{fn_name} = sub.add_parser(\"{cmd}\", help=\"Create a new resource\")")
            lines.append(f"    p_{fn_name}.add_argument(\"name\", help=\"Resource name\")")
        elif cmd == "delete":
            lines.append(f"    p_{fn_name} = sub.add_parser(\"{cmd}\", help=\"Delete a resource\")")
            lines.append(f"    p_{fn_name}.add_argument(\"name\", help=\"Resource name or ID\")")
        elif cmd == "list":
            lines.append(f"    sub.add_parser(\"{cmd}\", help=\"List all resources\")")
        else:
            lines.append(f"    p_{fn_name} = sub.add_parser(\"{cmd}\", help=\"{_title(cmd)}\")")
            lines.append(f"    p_{fn_name}.add_argument(\"name\", help=\"Resource name or ID\")")
        lines.append("")
    return "\n".join(lines)
