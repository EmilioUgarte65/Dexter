#!/usr/bin/env python3
"""
Dexter — GUI macro persistence layer.
Saves/retrieves step sequences to/from Engram (primary) or ~/.dexter/gui-macros.json (fallback).

Public API:
  slugify(task: str) -> str
  save(task: str, steps: list, platform: str) -> str   # returns topic_key
  find(task: str) -> list | None
  list_all() -> list
  delete(slug: str) -> bool
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─── Engram availability ──────────────────────────────────────────────────────

ENGRAM_AVAILABLE = shutil.which("engram") is not None

# ─── Fallback store path ───────────────────────────────────────────────────────

FALLBACK_PATH = Path.home() / ".dexter" / "gui-macros.json"

# ─── Slug helpers ─────────────────────────────────────────────────────────────

def slugify(task: str) -> str:
    """
    Convert a task description to a URL-safe slug.
    Lowercase, spaces → hyphens, strip non-alphanumeric except hyphens, max 60 chars.

    Examples:
      "Open a new terminal tab"  → "open-a-new-terminal-tab"
      "Click 'Send' button!"     → "click-send-button"
    """
    slug = task.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)   # strip special chars (keep word chars, spaces, hyphens)
    slug = re.sub(r"[\s_]+", "-", slug)    # spaces and underscores → hyphens
    slug = re.sub(r"-+", "-", slug)        # collapse multiple hyphens
    slug = slug.strip("-")                 # trim leading/trailing hyphens
    return slug[:60]


def topic_key(slug: str) -> str:
    return f"gui-macros/default/{slug}"


# ─── Engram backend ───────────────────────────────────────────────────────────

def _engram_save(slug: str, task: str, steps: list, platform: str) -> bool:
    """Save macro to Engram via CLI. Returns True on success."""
    if not ENGRAM_AVAILABLE:
        return False

    content = json.dumps({
        "task": task,
        "slug": slug,
        "platform": platform,
        "origin": "dexter",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "steps": steps,
    }, indent=2)

    title = f"GUI macro: {slug}"
    key   = topic_key(slug)

    try:
        result = subprocess.run(
            ["engram", "save", title, content,
             "--type",    "architecture",
             "--project", "Dexter",
             "--scope",   "project",
             "--topic",   key],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _engram_search(query: str) -> list[dict]:
    """Search Engram for macros. Returns list of raw result dicts."""
    if not ENGRAM_AVAILABLE:
        return []

    try:
        result = subprocess.run(
            ["engram", "search", query,
             "--project", "Dexter",
             "--type",    "architecture"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return []

        # Parse the plain-text output from `engram search`.
        # Format per result block:
        #   [N] #ID (type) — title
        #   <content preview>
        #   date | project: X | scope: Y
        # We return dicts with {id, title, preview}.
        entries = []
        current: Optional[dict] = None
        for line in result.stdout.splitlines():
            header_match = re.match(r"\[(\d+)\] #(\d+) \([^)]+\) — (.+)$", line.strip())
            if header_match:
                if current:
                    entries.append(current)
                current = {
                    "id":      int(header_match.group(2)),
                    "title":   header_match.group(3).strip(),
                    "preview": "",
                }
            elif current and line.strip() and not line.strip().startswith("20"):
                # Accumulate content lines (skip the date metadata line)
                current["preview"] += line.strip() + " "
        if current:
            entries.append(current)

        return entries
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def _engram_get_observation(obs_id: int) -> Optional[dict]:
    """
    Retrieve full macro content from Engram using the HTTP API.
    Engram runs an HTTP API on port 7437 by default.
    Falls back to None if unavailable.
    """
    if not ENGRAM_AVAILABLE:
        return None

    import urllib.request
    import urllib.error

    port = int(os.environ.get("ENGRAM_PORT", "7437"))
    url  = f"http://localhost:{port}/observations/{obs_id}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # Content is in data["content"] or data["body"]
            raw = data.get("content") or data.get("body") or ""
            return json.loads(raw) if raw else None
    except Exception:
        return None


# ─── Fallback JSON backend ────────────────────────────────────────────────────

def _fallback_load() -> dict:
    """Load fallback macro store. Returns dict keyed by slug."""
    if FALLBACK_PATH.exists():
        try:
            return json.loads(FALLBACK_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _fallback_save_store(store: dict) -> None:
    """Write fallback macro store to disk."""
    FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    FALLBACK_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")


def _fallback_save(slug: str, task: str, steps: list, platform: str) -> bool:
    """Save macro to fallback JSON file."""
    try:
        store = _fallback_load()
        store[slug] = {
            "task":     task,
            "slug":     slug,
            "platform": platform,
            "origin":   "dexter",
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "steps":    steps,
            "deleted":  False,
        }
        _fallback_save_store(store)
        return True
    except OSError:
        return False


def _fallback_find(slug_or_task: str) -> Optional[list]:
    """Find macro steps in fallback store by slug or fuzzy task match."""
    store = _fallback_load()

    # Exact slug match
    if slug_or_task in store:
        entry = store[slug_or_task]
        if not entry.get("deleted"):
            return entry["steps"]

    # Try slugifying the input and matching
    slug = slugify(slug_or_task)
    if slug in store:
        entry = store[slug]
        if not entry.get("deleted"):
            return entry["steps"]

    return None


def _fallback_list() -> list:
    """List all non-deleted macros from fallback store."""
    store = _fallback_load()
    results = []
    for slug, entry in store.items():
        if not entry.get("deleted"):
            results.append({
                "slug":        slug,
                "description": entry.get("task", slug),
                "platform":    entry.get("platform", "unknown"),
                "step_count":  len(entry.get("steps", [])),
                "saved_at":    entry.get("saved_at", ""),
            })
    return results


def _fallback_delete(slug: str) -> bool:
    """Mark macro as deleted in fallback store."""
    store = _fallback_load()
    if slug not in store:
        return False
    store[slug]["deleted"] = True
    try:
        _fallback_save_store(store)
        return True
    except OSError:
        return False


# ─── Public API ───────────────────────────────────────────────────────────────

def save(task: str, steps: list, platform: str) -> str:
    """
    Save a completed macro (Engram-first, fallback to JSON).
    Returns the topic_key used.
    """
    slug = slugify(task)
    key  = topic_key(slug)

    if ENGRAM_AVAILABLE:
        if _engram_save(slug, task, steps, platform):
            return key

    # Fallback
    _fallback_save(slug, task, steps, platform)
    return key


def find(task: str) -> Optional[list]:
    """
    Search for a macro matching task description or slug.
    Returns steps list if found, None otherwise.
    Checks Engram first, then fallback JSON.
    """
    slug = slugify(task)

    if ENGRAM_AVAILABLE:
        entries = _engram_search(f"gui-macros/default/{slug}")
        if not entries:
            # Broader search by task keywords
            entries = _engram_search(task)

        # Filter to gui-macro entries
        macro_entries = [
            e for e in entries
            if "GUI macro:" in e.get("title", "") or "gui-macros" in e.get("preview", "")
        ]

        if macro_entries:
            # Try to get full content via HTTP API
            obs_id = macro_entries[0]["id"]
            full   = _engram_get_observation(obs_id)
            if full and "steps" in full:
                return full["steps"]

    # Fallback
    return _fallback_find(task)


def list_all() -> list:
    """
    Return all saved macros as list of {slug, description, platform, step_count, saved_at}.
    Merges Engram and fallback results.
    """
    results = []
    seen_slugs: set[str] = set()

    if ENGRAM_AVAILABLE:
        entries = _engram_search("gui-macros")
        for entry in entries:
            # Extract slug from title "GUI macro: {slug}"
            title_match = re.match(r"GUI macro:\s*(.+)$", entry.get("title", ""))
            if not title_match:
                continue
            slug = title_match.group(1).strip()
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            # Try to get step count from HTTP API
            step_count = 0
            full = _engram_get_observation(entry["id"])
            if full:
                step_count = len(full.get("steps", []))

            results.append({
                "slug":        slug,
                "description": full.get("task", slug) if full else slug,
                "platform":    full.get("platform", "unknown") if full else "unknown",
                "step_count":  step_count,
                "saved_at":    full.get("saved_at", "") if full else "",
                "origin":      "engram",
            })

    # Merge fallback (avoid duplicates already found in Engram)
    for entry in _fallback_list():
        if entry["slug"] not in seen_slugs:
            entry["origin"] = "fallback"
            results.append(entry)
            seen_slugs.add(entry["slug"])

    return results


def delete(slug: str) -> bool:
    """
    Delete a macro by slug.
    Engram CLI has no delete command — marks deleted in fallback JSON tombstone.
    Also removes from fallback if present.
    Returns True if the macro existed and was marked deleted.
    """
    found = False

    if ENGRAM_AVAILABLE:
        # Engram CLI does not support deletion — write a tombstone in fallback JSON
        # so find() / list_all() can filter it out on future lookups.
        entries = _engram_search(f"gui-macros/default/{slug}")
        macro_entries = [
            e for e in entries
            if "GUI macro:" in e.get("title", "") and slug in e.get("title", "")
        ]
        if macro_entries:
            found = True
            # Write tombstone
            store = _fallback_load()
            if slug not in store:
                store[slug] = {}
            store[slug]["deleted"] = True
            store[slug]["slug"]    = slug
            try:
                _fallback_save_store(store)
            except OSError:
                pass

    # Also handle fallback-only entry
    if _fallback_delete(slug):
        found = True

    return found
