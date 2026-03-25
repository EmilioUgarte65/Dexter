#!/usr/bin/env python3
"""
Dexter — Obsidian Local REST API client.
Uses stdlib only (urllib). No external dependencies.

Requires: Obsidian Local REST API community plugin.
https://github.com/coddingtonbear/obsidian-local-rest-api

Usage:
  obsidian.py new <title> <content> [--folder PATH]
  obsidian.py append <note_path> <content>
  obsidian.py read <note_path>
  obsidian.py search <query>
  obsidian.py list [--folder PATH]
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
import ssl
from typing import Any, Optional

# ─── Config from env ──────────────────────────────────────────────────────────

API_URL = os.environ.get("OBSIDIAN_API_URL", "http://localhost:27123").rstrip("/")
API_KEY = os.environ.get("OBSIDIAN_API_KEY", "")

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"


def check_config():
    if not API_KEY:
        print(
            "Error: OBSIDIAN_API_KEY not set.\n"
            "1. Install 'Local REST API' plugin in Obsidian\n"
            "2. Copy the API key from plugin settings\n"
            "3. export OBSIDIAN_API_KEY=your-key-here",
            file=sys.stderr,
        )
        sys.exit(1)


# ─── SSL context (plugin uses self-signed cert by default) ────────────────────

def _ssl_ctx() -> Optional[ssl.SSLContext]:
    """Allow self-signed certs from local Obsidian plugin."""
    if API_URL.startswith("https://"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _headers(content_type: str = "application/json") -> dict:
    h = {"Authorization": f"Bearer {API_KEY}"}
    if content_type:
        h["Content-Type"] = content_type
    return h


def obs_get(endpoint: str, params: Optional[dict] = None) -> Any:
    url = f"{API_URL}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_headers(content_type=""), method="GET")
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=10) as resp:
            body = resp.read().decode()
            if resp.headers.get("Content-Type", "").startswith("application/json"):
                return json.loads(body) if body.strip() else {}
            return body
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"{RED}Obsidian API error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(
            f"{RED}Cannot reach Obsidian at {API_URL}: {e.reason}{RESET}\n"
            "Is Obsidian running with the Local REST API plugin enabled?",
            file=sys.stderr,
        )
        sys.exit(1)


def obs_put(endpoint: str, content: str, content_type: str = "text/markdown") -> Any:
    url = f"{API_URL}{endpoint}"
    data = content.encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={**_headers(content_type=content_type)},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=10) as resp:
            body = resp.read().decode()
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"{RED}Obsidian API error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Obsidian at {API_URL}: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def obs_patch(endpoint: str, content: str) -> Any:
    url = f"{API_URL}{endpoint}"
    data = content.encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={**_headers(content_type="text/markdown")},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=10) as resp:
            body = resp.read().decode()
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"{RED}Obsidian API error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Obsidian at {API_URL}: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def obs_post(endpoint: str, payload: dict) -> Any:
    url = f"{API_URL}{endpoint}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers=_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=10) as resp:
            body = resp.read().decode()
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"{RED}Obsidian API error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Obsidian at {API_URL}: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def _note_path(title: str, folder: Optional[str] = None) -> str:
    """Build note path, ensuring .md extension."""
    if not title.endswith(".md"):
        title = title + ".md"
    if folder:
        return f"{folder.rstrip('/')}/{title}"
    return title


def _url_encode_path(path: str) -> str:
    return urllib.parse.quote(path, safe="")


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_new(title: str, content: str, folder: Optional[str] = None):
    path = _note_path(title, folder)
    encoded = _url_encode_path(path)
    obs_put(f"/vault/{encoded}", content)
    print(f"{GREEN}Created note: {path}{RESET}")
    print(f"  Content: {content[:60]}{'...' if len(content) > 60 else ''}")


def cmd_append(note_path: str, content: str):
    if not note_path.endswith(".md"):
        note_path += ".md"
    encoded = _url_encode_path(note_path)

    # Read existing content, then rewrite with appended text
    existing = obs_get(f"/vault/{encoded}")
    if isinstance(existing, str):
        new_content = existing + content
    else:
        new_content = content

    obs_put(f"/vault/{encoded}", new_content)
    print(f"{GREEN}Appended to: {note_path}{RESET}")
    print(f"  Added: {content[:60]}{'...' if len(content) > 60 else ''}")


def cmd_read(note_path: str):
    if not note_path.endswith(".md"):
        note_path += ".md"
    encoded = _url_encode_path(note_path)
    content = obs_get(f"/vault/{encoded}")

    print(f"\n── {note_path} {'─' * max(1, 50 - len(note_path))}\n")
    if isinstance(content, str):
        print(content)
    else:
        print(json.dumps(content, indent=2))


def cmd_search(query: str):
    result = obs_post("/search/simple/", {"query": query})
    items = result if isinstance(result, list) else result.get("results", [])

    if not items:
        print(f"No results for: {query}")
        return

    print(f"\nSearch results for '{query}' ({len(items)} found):\n")
    for item in items:
        filename = item.get("filename", item.get("path", "?"))
        score    = item.get("score", "")
        score_str = f"  (score: {score:.2f})" if isinstance(score, float) else ""
        print(f"  {GREEN}{filename}{RESET}{score_str}")
        # Show context matches
        matches = item.get("matches", [])
        for match in matches[:2]:
            context = match.get("context", "").strip()[:80]
            if context:
                print(f"    → {context}")


def cmd_list(folder: Optional[str] = None):
    endpoint = "/vault/"
    if folder:
        encoded = _url_encode_path(folder.rstrip("/") + "/")
        endpoint = f"/vault/{encoded}"

    result = obs_get(endpoint)
    files = result.get("files", []) if isinstance(result, dict) else []

    if not files:
        print(f"No notes found{f' in {folder}' if folder else ''}.")
        return

    md_files = [f for f in files if isinstance(f, str) and f.endswith(".md")]
    other    = [f for f in files if isinstance(f, str) and not f.endswith(".md")]

    location = folder or "vault root"
    print(f"\n  {len(md_files)} note(s) in {location}:\n")
    for f in sorted(md_files):
        print(f"  {GREEN}{f}{RESET}")
    if other:
        print(f"\n  Other files ({len(other)}):")
        for f in sorted(other):
            print(f"  {f}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    check_config()

    parser = argparse.ArgumentParser(description="Dexter Obsidian CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # new
    p_new = subparsers.add_parser("new", help="Create a new note")
    p_new.add_argument("title", help="Note title (becomes filename)")
    p_new.add_argument("content", help="Note content (Markdown)")
    p_new.add_argument("--folder", help="Folder path relative to vault root (e.g. 'Projects')")

    # append
    p_append = subparsers.add_parser("append", help="Append content to a note")
    p_append.add_argument("note_path", help="Path to note relative to vault root")
    p_append.add_argument("content", help="Content to append")

    # read
    p_read = subparsers.add_parser("read", help="Read a note")
    p_read.add_argument("note_path", help="Path to note relative to vault root")

    # search
    p_search = subparsers.add_parser("search", help="Search notes")
    p_search.add_argument("query", help="Search query")

    # list
    p_list = subparsers.add_parser("list", help="List notes")
    p_list.add_argument("--folder", help="Filter by folder (relative to vault root)")

    args = parser.parse_args()

    if args.command == "new":
        cmd_new(args.title, args.content, folder=getattr(args, "folder", None))
    elif args.command == "append":
        cmd_append(args.note_path, args.content)
    elif args.command == "read":
        cmd_read(args.note_path)
    elif args.command == "search":
        cmd_search(args.query)
    elif args.command == "list":
        cmd_list(folder=getattr(args, "folder", None))


if __name__ == "__main__":
    main()
