#!/usr/bin/env python3
"""
Dexter — Personal Knowledge Base. Local markdown-based notes.
No cloud required. Each note = one .md file with YAML frontmatter.

Usage:
  kb.py add <title> <content> [--tags tag1,tag2] [--folder FOLDER]
  kb.py search <query>
  kb.py list [--folder FOLDER] [--tag TAG]
  kb.py get <title_or_path>
  kb.py update <title> <new_content>
  kb.py delete <title>
  kb.py export [--format json|zip]
"""

import sys
import os
import re
import json
import argparse
import zipfile
import io
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── ANSI colors ──────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

# ─── Config ───────────────────────────────────────────────────────────────────

KB_DIR = Path(os.environ.get("PERSONAL_KB_DIR", os.path.expanduser("~/knowledge")))


def _ensure_kb():
    KB_DIR.mkdir(parents=True, exist_ok=True)


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# ─── Frontmatter helpers ──────────────────────────────────────────────────────

def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML-lite frontmatter. Returns (meta, body)."""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    meta = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()

    return meta, parts[2].strip()


def _build_frontmatter(title: str, tags: list[str], folder: str = "") -> str:
    tag_str = ", ".join(tags) if tags else ""
    return f"---\ntitle: {title}\ntags: {tag_str}\ncreated: {_today()}\n---\n\n"


def _find_note(title_or_path: str) -> Optional[Path]:
    """Find a note by title or relative path."""
    # Direct path
    p = KB_DIR / title_or_path
    if p.exists():
        return p

    # Try slug
    slug  = _slugify(title_or_path)
    exact = KB_DIR / f"{slug}.md"
    if exact.exists():
        return exact

    # Search recursively
    for md in KB_DIR.rglob("*.md"):
        meta, _ = _parse_frontmatter(md.read_text(encoding="utf-8"))
        if meta.get("title", "").lower() == title_or_path.lower():
            return md
        if md.stem == slug or md.stem == _slugify(title_or_path):
            return md

    return None


def _all_notes() -> list[Path]:
    return sorted(KB_DIR.rglob("*.md"))


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_add(title: str, content: str, tags: list[str] = None, folder: str = ""):
    _ensure_kb()

    slug    = _slugify(title)
    tags    = tags or []

    if folder:
        target_dir = KB_DIR / folder
        target_dir.mkdir(parents=True, exist_ok=True)
    else:
        target_dir = KB_DIR

    note_path = target_dir / f"{slug}.md"
    if note_path.exists():
        print(f"{YELLOW}Note already exists: {note_path.relative_to(KB_DIR)}{RESET}")
        print("Use 'update' to modify it.")
        sys.exit(1)

    frontmatter = _build_frontmatter(title, tags, folder)
    note_path.write_text(frontmatter + content, encoding="utf-8")

    print(f"{GREEN}Note saved: {note_path.relative_to(KB_DIR)}{RESET}")
    if tags:
        print(f"  Tags: {', '.join(tags)}")


def cmd_search(query: str):
    _ensure_kb()
    notes   = _all_notes()
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    matches = []

    for note in notes:
        content = note.read_text(encoding="utf-8", errors="replace")
        if pattern.search(content):
            meta, body = _parse_frontmatter(content)
            # Find matching line
            for i, line in enumerate(body.splitlines(), 1):
                if pattern.search(line):
                    matches.append({
                        "path":    note.relative_to(KB_DIR),
                        "title":   meta.get("title", note.stem),
                        "line":    i,
                        "excerpt": line.strip()[:100],
                    })
                    break

    if not matches:
        print(f"{YELLOW}No results for: {query}{RESET}")
        return

    print(f"\n{BLUE}Search results for: {query}{RESET}\n")
    for m in matches:
        print(f"  {GREEN}{m['path']}{RESET}")
        print(f"    {m['title']}")
        print(f"    ...{m['excerpt']}...")
        print()
    print(f"  {len(matches)} result(s) found.")


def cmd_list(folder: str = "", tag: str = ""):
    _ensure_kb()

    if folder:
        search_dir = KB_DIR / folder
        notes = sorted(search_dir.rglob("*.md")) if search_dir.exists() else []
    else:
        notes = _all_notes()

    if tag:
        filtered = []
        for note in notes:
            content = note.read_text(encoding="utf-8", errors="replace")
            meta, _ = _parse_frontmatter(content)
            note_tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
            if tag.lower() in [t.lower() for t in note_tags]:
                filtered.append(note)
        notes = filtered

    if not notes:
        print(f"{YELLOW}No notes found.{RESET}")
        return

    # Group by folder
    groups: dict[str, list] = {}
    for note in notes:
        rel  = note.relative_to(KB_DIR)
        grp  = str(rel.parent) if str(rel.parent) != "." else "(root)"
        groups.setdefault(grp, []).append((note, rel))

    print(f"\n{BLUE}Knowledge Base — {KB_DIR}{RESET}\n")
    for grp, items in sorted(groups.items()):
        print(f"  {grp}/")
        for note, rel in sorted(items, key=lambda x: x[0].stem):
            meta, _ = _parse_frontmatter(note.read_text(encoding="utf-8", errors="replace"))
            title   = meta.get("title", note.stem)
            created = meta.get("created", "")
            tags_s  = meta.get("tags", "")
            print(f"    {note.stem:<35}  {title:<40}  {created}  {tags_s}")

    print(f"\n  {len(notes)} note(s) total.")


def cmd_get(title_or_path: str):
    note = _find_note(title_or_path)
    if not note:
        print(f"{RED}Note not found: {title_or_path}{RESET}", file=sys.stderr)
        sys.exit(1)

    content = note.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(content)

    print(f"\n{BLUE}{'─' * 60}{RESET}")
    print(f"{GREEN}{meta.get('title', note.stem)}{RESET}")
    if meta.get("tags"):
        print(f"Tags: {meta['tags']}")
    if meta.get("created"):
        print(f"Created: {meta['created']}")
    print(f"{BLUE}{'─' * 60}{RESET}\n")
    print(body)


def cmd_update(title: str, new_content: str):
    note = _find_note(title)
    if not note:
        print(f"{RED}Note not found: {title}{RESET}", file=sys.stderr)
        sys.exit(1)

    existing = note.read_text(encoding="utf-8")
    meta, _  = _parse_frontmatter(existing)

    tags    = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
    updated = _build_frontmatter(meta.get("title", title), tags) + new_content

    note.write_text(updated, encoding="utf-8")
    print(f"{GREEN}Updated: {note.relative_to(KB_DIR)}{RESET}")


def cmd_delete(title: str):
    note = _find_note(title)
    if not note:
        print(f"{RED}Note not found: {title}{RESET}", file=sys.stderr)
        sys.exit(1)

    rel = note.relative_to(KB_DIR)
    note.unlink()
    print(f"{GREEN}Deleted: {rel}{RESET}")


def cmd_export(fmt: str = "json"):
    _ensure_kb()
    notes = _all_notes()

    if not notes:
        print(f"{YELLOW}No notes to export.{RESET}")
        return

    if fmt == "json":
        export_data = []
        for note in notes:
            content = note.read_text(encoding="utf-8", errors="replace")
            meta, body = _parse_frontmatter(content)
            export_data.append({
                "path":    str(note.relative_to(KB_DIR)),
                "title":   meta.get("title", note.stem),
                "tags":    [t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
                "created": meta.get("created", ""),
                "content": body,
            })
        print(json.dumps(export_data, indent=2, ensure_ascii=False))
        print(f"\n{GREEN}{len(notes)} notes exported as JSON{RESET}", file=sys.stderr)

    elif fmt == "zip":
        import tempfile
        out_path = Path.cwd() / f"knowledge-export-{_today()}.zip"
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for note in notes:
                arcname = note.relative_to(KB_DIR)
                zf.write(note, arcname)

        size = out_path.stat().st_size
        print(f"{GREEN}ZIP export: {out_path}{RESET}")
        print(f"  {len(notes)} notes, {size / 1024:.1f} KB")

    else:
        print(f"{RED}Unknown format: {fmt}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter Personal Knowledge Base")
    sub    = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Add a new note")
    p_add.add_argument("title")
    p_add.add_argument("content")
    p_add.add_argument("--tags",   default="", help="Comma-separated tags")
    p_add.add_argument("--folder", default="", help="Subfolder")

    # search
    p_search = sub.add_parser("search", help="Full-text search")
    p_search.add_argument("query")

    # list
    p_list = sub.add_parser("list", help="List notes")
    p_list.add_argument("--folder", default="")
    p_list.add_argument("--tag",    default="")

    # get
    p_get = sub.add_parser("get", help="Show a note")
    p_get.add_argument("title_or_path")

    # update
    p_upd = sub.add_parser("update", help="Update note content")
    p_upd.add_argument("title")
    p_upd.add_argument("new_content")

    # delete
    p_del = sub.add_parser("delete", help="Delete a note")
    p_del.add_argument("title")

    # export
    p_exp = sub.add_parser("export", help="Export all notes")
    p_exp.add_argument("--format", choices=["json", "zip"], default="json")

    args = parser.parse_args()

    if args.command == "add":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
        cmd_add(args.title, args.content, tags, args.folder)
    elif args.command == "search":
        cmd_search(args.query)
    elif args.command == "list":
        cmd_list(args.folder, args.tag)
    elif args.command == "get":
        cmd_get(args.title_or_path)
    elif args.command == "update":
        cmd_update(args.title, args.new_content)
    elif args.command == "delete":
        cmd_delete(args.title)
    elif args.command == "export":
        cmd_export(args.format)


if __name__ == "__main__":
    main()
