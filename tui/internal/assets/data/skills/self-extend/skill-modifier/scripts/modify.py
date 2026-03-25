#!/usr/bin/env python3
"""
Dexter — Skill modifier. Edit SKILL.md metadata without breaking skills.
Always creates .bak backup before modifying.

Usage:
  modify.py show <skill_path>
  modify.py triggers <skill_path> <new_triggers>
  modify.py description <skill_path> <new_description>
  modify.py version <skill_path> <new_version>
  modify.py rename <skill_path> <new_name>
  modify.py diff <skill_path>
"""

import sys
import os
import re
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

# ─── ANSI colors ──────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"


# ─── Path resolution ──────────────────────────────────────────────────────────

def _resolve_skill_md(skill_path: str) -> Path:
    """Accept either a SKILL.md path or directory path."""
    p = Path(skill_path)

    if p.is_dir():
        candidate = p / "SKILL.md"
        if candidate.exists():
            return candidate
        print(f"{RED}No SKILL.md found in: {p}{RESET}", file=sys.stderr)
        sys.exit(1)

    if p.name == "SKILL.md" and p.exists():
        return p

    # Try appending SKILL.md
    candidate = p / "SKILL.md"
    if candidate.exists():
        return candidate

    if p.exists():
        return p

    print(f"{RED}Skill not found: {skill_path}{RESET}", file=sys.stderr)
    sys.exit(1)


# ─── Frontmatter parsing ──────────────────────────────────────────────────────

def _read_skill(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _split_frontmatter(content: str) -> tuple[str, str, str]:
    """Returns (before_yaml, yaml_block, after_yaml)."""
    if not content.startswith("---"):
        return "", "", content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return "", parts[1] if len(parts) > 1 else "", ""

    return "---", parts[1], "---" + parts[2]


def _parse_yaml_block(yaml_text: str) -> dict:
    """Parse simple YAML fields (no nesting beyond one level)."""
    result = {}
    lines  = yaml_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            # Multiline value (>) — collect continuation lines
            if val in (">", "|", ">-", "|-"):
                block_lines = []
                i += 1
                while i < len(lines) and (lines[i].startswith("  ") or lines[i].strip() == ""):
                    block_lines.append(lines[i].strip())
                    i += 1
                result[key] = " ".join(block_lines)
                continue
            else:
                result[key] = val
        elif line.startswith("  ") and result:
            # Continuation of previous key
            last_key = list(result)[-1]
            result[last_key] = (result[last_key] + " " + line.strip()).strip()
        i += 1
    return result


def _show_metadata(path: Path):
    content = _read_skill(path)
    _, yaml_block, _ = _split_frontmatter(content)
    meta = _parse_yaml_block(yaml_block)

    print(f"\n{BLUE}Skill: {path}{RESET}\n")
    for key, val in meta.items():
        print(f"  {key:<15} {val}")


# ─── Backup ───────────────────────────────────────────────────────────────────

def _backup(path: Path) -> Path:
    bak = path.with_suffix(".md.bak")
    shutil.copy2(path, bak)
    print(f"{YELLOW}Backup: {bak}{RESET}")
    return bak


# ─── Field updaters ───────────────────────────────────────────────────────────

def _update_field(content: str, field: str, new_value: str) -> str:
    """Update a simple top-level YAML field."""
    pattern = re.compile(rf"^({re.escape(field)}\s*:)(.*)$", re.MULTILINE)
    match   = pattern.search(content)
    if match:
        return content[:match.start()] + f'{field}: {new_value}' + content[match.end():]
    return content


def _update_description_block(content: str, new_description: str, trigger: Optional[str] = None) -> str:
    """Replace the description: > block, preserving or adding Trigger line."""
    # Extract current trigger if not provided
    if trigger is None:
        m = re.search(r"Trigger:\s*(.+?)(?=\n[a-z]|\nlicense)", content, re.DOTALL)
        if m:
            trigger = m.group(1).strip()

    new_desc = new_description.strip()
    if trigger and "Trigger:" not in new_desc:
        new_desc += f"\n  Trigger: {trigger}"

    # Build new description block
    indented = "\n".join("  " + line if line.strip() else "" for line in new_desc.splitlines())
    new_block = f"description: >\n{indented}"

    # Replace old description block
    pattern = re.compile(r"^description:\s*>.*?(?=^[a-z])", re.MULTILINE | re.DOTALL)
    match   = pattern.search(content)
    if match:
        return content[:match.start()] + new_block + "\n" + content[match.end():]

    # Fallback: simple replace
    return re.sub(r"^description:.*$", new_block, content, flags=re.MULTILINE)


def _update_trigger_in_description(content: str, new_triggers: str) -> str:
    """Update only the Trigger: line inside the description block."""
    # Find and replace the Trigger: line
    pattern = re.compile(r"(Trigger:\s*)(.+)", re.IGNORECASE)
    new_trigger_line = f"Trigger: {new_triggers}"
    if pattern.search(content):
        return pattern.sub(new_trigger_line, content)

    # If no Trigger line exists, add it at end of description block
    desc_end = re.search(r"(description:.*?\n)(license:)", content, re.DOTALL)
    if desc_end:
        insert_at = desc_end.start(2)
        return content[:insert_at] + f"  Trigger: {new_triggers}\n" + content[insert_at:]

    return content


def _update_version(content: str, new_version: str) -> str:
    """Update metadata.version field."""
    pattern = re.compile(r'(version:\s*)["\']?[\d.]+["\']?')
    if pattern.search(content):
        return pattern.sub(f'version: "{new_version}"', content)
    return content


# ─── Diff ─────────────────────────────────────────────────────────────────────

def _show_diff(path: Path):
    bak = path.with_suffix(".md.bak")
    if not bak.exists():
        print(f"{YELLOW}No backup found: {bak}{RESET}")
        return

    current = path.read_text(encoding="utf-8").splitlines()
    backup  = bak.read_text(encoding="utf-8").splitlines()

    print(f"\n{BLUE}Diff: {path} vs {bak}{RESET}\n")

    import difflib
    diff = list(difflib.unified_diff(backup, current, fromfile="backup", tofile="current", lineterm=""))

    if not diff:
        print(f"{GREEN}No changes.{RESET}")
        return

    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            print(f"{GREEN}{line}{RESET}")
        elif line.startswith("-") and not line.startswith("---"):
            print(f"{RED}{line}{RESET}")
        else:
            print(line)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_show(skill_path: str):
    path = _resolve_skill_md(skill_path)
    _show_metadata(path)


def cmd_triggers(skill_path: str, new_triggers: str):
    path    = _resolve_skill_md(skill_path)
    _backup(path)
    content = _read_skill(path)
    updated = _update_trigger_in_description(content, new_triggers)
    path.write_text(updated, encoding="utf-8")
    print(f"{GREEN}Triggers updated in: {path}{RESET}")
    print(f"  New triggers: {new_triggers}")


def cmd_description(skill_path: str, new_description: str):
    path    = _resolve_skill_md(skill_path)
    _backup(path)
    content = _read_skill(path)
    updated = _update_description_block(content, new_description)
    path.write_text(updated, encoding="utf-8")
    print(f"{GREEN}Description updated: {path}{RESET}")


def cmd_version(skill_path: str, new_version: str):
    path    = _resolve_skill_md(skill_path)
    _backup(path)
    content = _read_skill(path)
    updated = _update_version(content, new_version)
    path.write_text(updated, encoding="utf-8")
    print(f"{GREEN}Version updated: {path} → {new_version}{RESET}")


def cmd_rename(skill_path: str, new_name: str):
    # Resolve to directory
    p = Path(skill_path)
    if p.name == "SKILL.md":
        skill_dir = p.parent
    else:
        skill_dir = p

    if not skill_dir.is_dir():
        print(f"{RED}Not a directory: {skill_dir}{RESET}", file=sys.stderr)
        sys.exit(1)

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        print(f"{RED}No SKILL.md in: {skill_dir}{RESET}", file=sys.stderr)
        sys.exit(1)

    new_dir = skill_dir.parent / new_name

    if new_dir.exists():
        print(f"{RED}Target already exists: {new_dir}{RESET}", file=sys.stderr)
        sys.exit(1)

    # Backup SKILL.md before rename
    _backup(skill_md)

    # Update name field
    content = _read_skill(skill_md)
    updated = _update_field(content, "name", new_name)
    skill_md.write_text(updated, encoding="utf-8")

    # Move directory
    shutil.move(str(skill_dir), str(new_dir))

    print(f"{GREEN}Renamed: {skill_dir} → {new_dir}{RESET}")
    print(f"  name field updated to: {new_name}")


def cmd_diff(skill_path: str):
    path = _resolve_skill_md(skill_path)
    _show_diff(path)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter Skill Modifier")
    sub    = parser.add_subparsers(dest="command", required=True)

    # show
    p_show = sub.add_parser("show", help="Display current skill metadata")
    p_show.add_argument("skill_path")

    # triggers
    p_trig = sub.add_parser("triggers", help="Update trigger keywords")
    p_trig.add_argument("skill_path")
    p_trig.add_argument("new_triggers", help="New trigger keywords (comma-separated string)")

    # description
    p_desc = sub.add_parser("description", help="Update skill description")
    p_desc.add_argument("skill_path")
    p_desc.add_argument("new_description")

    # version
    p_ver = sub.add_parser("version", help="Bump version field")
    p_ver.add_argument("skill_path")
    p_ver.add_argument("new_version")

    # rename
    p_ren = sub.add_parser("rename", help="Rename skill (updates name + moves directory)")
    p_ren.add_argument("skill_path")
    p_ren.add_argument("new_name")

    # diff
    p_diff = sub.add_parser("diff", help="Show changes vs last backup")
    p_diff.add_argument("skill_path")

    args = parser.parse_args()

    if args.command == "show":
        cmd_show(args.skill_path)
    elif args.command == "triggers":
        cmd_triggers(args.skill_path, args.new_triggers)
    elif args.command == "description":
        cmd_description(args.skill_path, args.new_description)
    elif args.command == "version":
        cmd_version(args.skill_path, args.new_version)
    elif args.command == "rename":
        cmd_rename(args.skill_path, args.new_name)
    elif args.command == "diff":
        cmd_diff(args.skill_path)


if __name__ == "__main__":
    main()
