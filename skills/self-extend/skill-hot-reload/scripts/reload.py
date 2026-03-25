#!/usr/bin/env python3
"""
Dexter — Skill hot-reload via workspace injection.
True runtime reload is impossible in Claude (context is fixed at session start).
This prepares skills for the NEXT session by injecting them into CLAUDE.md.

Usage:
  reload.py reload <skill_path>
  reload.py status
  reload.py inject <skill_path>
  reload.py purge
"""

import sys
import os
import re
import argparse
from datetime import datetime
from pathlib import Path

# ─── ANSI colors ──────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

# ─── Config ───────────────────────────────────────────────────────────────────

CLAUDE_MD      = Path(os.path.expanduser("~/.claude/CLAUDE.md"))
SECTION_HEADER = "## Active Skills (Next Session)"
SECTION_END    = "## "  # Next top-level section signals end


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# ─── SKILL.md reader ──────────────────────────────────────────────────────────

def _read_skill_meta(skill_path: Path) -> dict:
    """Extract name and description from SKILL.md frontmatter."""
    if not skill_path.exists():
        return {"name": skill_path.stem, "description": "", "triggers": ""}

    content = skill_path.read_text(encoding="utf-8")

    # Extract name
    name_match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
    name       = name_match.group(1).strip() if name_match else skill_path.stem

    # Extract description (including trigger)
    desc_match = re.search(r"^description:\s*>?\s*\n(.*?)(?=^[a-z])", content, re.MULTILINE | re.DOTALL)
    description = desc_match.group(1).strip() if desc_match else ""

    # Extract trigger line
    trigger_match = re.search(r"Trigger:\s*(.+)", content, re.IGNORECASE)
    triggers = trigger_match.group(1).strip() if trigger_match else ""

    return {"name": name, "description": description, "triggers": triggers}


def _resolve_skill_md(skill_path: str) -> Path:
    p = Path(skill_path)
    if p.is_dir():
        candidate = p / "SKILL.md"
        if candidate.exists():
            return candidate
    if p.exists():
        return p
    print(f"{RED}Skill not found: {skill_path}{RESET}", file=sys.stderr)
    sys.exit(1)


# ─── CLAUDE.md management ─────────────────────────────────────────────────────

def _read_claude_md() -> str:
    if CLAUDE_MD.exists():
        return CLAUDE_MD.read_text(encoding="utf-8")
    return ""


def _write_claude_md(content: str):
    CLAUDE_MD.parent.mkdir(parents=True, exist_ok=True)
    CLAUDE_MD.write_text(content, encoding="utf-8")


def _get_active_section(content: str) -> tuple[int, int]:
    """Returns (start_idx, end_idx) of the Active Skills section."""
    start = content.find(SECTION_HEADER)
    if start == -1:
        return -1, -1

    # Find end: next top-level ## heading (but not our own)
    after = content.find("\n## ", start + len(SECTION_HEADER))
    end   = after if after != -1 else len(content)
    return start, end


def _parse_active_skills(content: str) -> list[dict]:
    """Parse registered skills from the Active Skills section."""
    start, end = _get_active_section(content)
    if start == -1:
        return []

    section = content[start:end]
    skills  = []
    for line in section.splitlines():
        # Format: | path | name | Registered: date |
        if line.startswith("| ") and "Registered:" in line:
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 3:
                skills.append({
                    "path":       parts[0],
                    "name":       parts[1],
                    "registered": parts[2].replace("Registered:", "").strip(),
                })
    return skills


def _ensure_active_section(content: str) -> str:
    """Add Active Skills section if it doesn't exist."""
    if SECTION_HEADER in content:
        return content

    # Add at end
    if not content.endswith("\n"):
        content += "\n"
    content += f"\n{SECTION_HEADER}\n\n"
    content += "<!-- Skills registered here will be available in the next Claude session -->\n\n"
    return content


def _add_skill_to_section(content: str, skill_path: str, name: str) -> str:
    """Add a skill entry to the Active Skills section."""
    content  = _ensure_active_section(content)
    start, end = _get_active_section(content)

    # Check if already registered
    section_text = content[start:end]
    if skill_path in section_text:
        return content  # Already there

    entry     = f"| {skill_path} | {name} | Registered: {_today()} |\n"
    # Insert before the section end
    insert_at = end if end == len(content) else end
    # Actually insert just before end boundary
    before_end = content[start:end].rstrip()
    new_section = before_end + "\n" + entry + "\n"
    return content[:start] + new_section + content[end:]


def _remove_active_section(content: str) -> str:
    """Remove the entire Active Skills section."""
    start, end = _get_active_section(content)
    if start == -1:
        return content
    return content[:start] + content[end:]


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_reload(skill_path: str):
    path = _resolve_skill_md(skill_path)
    meta = _read_skill_meta(path)

    content = _read_claude_md()
    updated = _add_skill_to_section(content, str(path), meta["name"])

    if updated == content:
        print(f"{YELLOW}Skill already registered: {meta['name']}{RESET}")
    else:
        _write_claude_md(updated)
        print(f"{GREEN}Skill registered for next session: {meta['name']}{RESET}")
        print(f"  Path    : {path}")
        print(f"  Triggers: {meta['triggers']}")

    print(f"\n{YELLOW}IMPORTANT: Claude cannot hot-reload mid-session.{RESET}")
    print(f"This skill will be available in the NEXT session.")
    print(f"\nTo verify: python3 reload.py status")


def cmd_status():
    content = _read_claude_md()
    skills  = _parse_active_skills(content)

    if not skills:
        print(f"{YELLOW}No skills registered for next session.{RESET}")
        print(f"\nRegister one with: python3 reload.py reload <skill_path>")
        return

    print(f"\n{BLUE}Skills registered for next session ({len(skills)}):{RESET}\n")
    for s in skills:
        print(f"  {GREEN}{s['name']:<30}{RESET}  {s['path']}")
        print(f"  {'':30}  Registered: {s['registered']}")
        print()

    print(f"{YELLOW}These skills will be active in the next Claude session.{RESET}")
    print(f"Source: {CLAUDE_MD}")


def cmd_inject(skill_path: str):
    path = _resolve_skill_md(skill_path)
    meta = _read_skill_meta(path)
    content = path.read_text(encoding="utf-8")

    # Strip frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        body  = parts[2].strip() if len(parts) >= 3 else content
    else:
        body  = content

    inject_path = Path.cwd() / "context_inject.md"
    inject_content = f"""# Injected Skill Context: {meta['name']}

> Generated by skill-hot-reload on {_today()}
> Paste this into your conversation to give Claude context about this skill.

---

{body}
"""

    inject_path.write_text(inject_content, encoding="utf-8")

    print(f"{GREEN}Context file created: {inject_path}{RESET}")
    print(f"\n{YELLOW}How to use:{RESET}")
    print(f"  1. Open {inject_path}")
    print(f"  2. Copy the content")
    print(f"  3. Paste into your Claude conversation")
    print(f"\nThis does NOT change what Claude knows in this session.")
    print(f"For permanent activation, use: python3 reload.py reload {skill_path}")


def cmd_purge():
    content = _read_claude_md()
    _, end   = _get_active_section(content)

    if _ == -1:
        print(f"{YELLOW}No Active Skills section found in {CLAUDE_MD}{RESET}")
        return

    skills  = _parse_active_skills(content)
    updated = _remove_active_section(content)
    _write_claude_md(updated)

    print(f"{GREEN}Purged Active Skills section from {CLAUDE_MD}{RESET}")
    print(f"  Removed: {len(skills)} skill(s)")
    for s in skills:
        print(f"    - {s['name']} ({s['path']})")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Dexter Skill Hot Reload — registers skills for next session"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # reload
    p_reload = sub.add_parser("reload", help="Register skill for next-session activation")
    p_reload.add_argument("skill_path", help="Path to SKILL.md or skill directory")

    # status
    sub.add_parser("status", help="List registered skills")

    # inject
    p_inject = sub.add_parser("inject", help="Create context_inject.md for manual reference")
    p_inject.add_argument("skill_path")

    # purge
    sub.add_parser("purge", help="Remove all skills from CLAUDE.md Active Skills section")

    args = parser.parse_args()

    if args.command == "reload":
        cmd_reload(args.skill_path)
    elif args.command == "status":
        cmd_status()
    elif args.command == "inject":
        cmd_inject(args.skill_path)
    elif args.command == "purge":
        cmd_purge()


if __name__ == "__main__":
    main()
