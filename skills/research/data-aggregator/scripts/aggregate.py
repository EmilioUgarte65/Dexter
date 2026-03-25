#!/usr/bin/env python3
"""
Dexter — Data aggregator. Fetch, merge, dedupe, and export data.
Pure stdlib. Supports JSON APIs, CSV files, and HTML tables.

Usage:
  aggregate.py fetch <url> [--format json|csv|html] [--jq FILTER]
  aggregate.py merge <file1> <file2> [--key FIELD] [--output merged.json]
  aggregate.py dedupe <file> [--key FIELD]
  aggregate.py export <file> [--format json|csv|markdown]
"""

import sys
import os
import json
import csv
import argparse
import hashlib
import time
import urllib.request
import urllib.error
import urllib.parse
import html.parser
import io
from pathlib import Path
from typing import Any, Optional

# ─── ANSI colors ──────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

# ─── Config ───────────────────────────────────────────────────────────────────

CACHE_DIR  = Path(os.environ.get(
    "AGGREGATOR_CACHE_DIR",
    os.path.expanduser("~/.local/share/dexter/cache")
))
CACHE_TTL  = 3600  # 1 hour


# ─── Cache ────────────────────────────────────────────────────────────────────

def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _cache_get(url: str) -> Optional[str]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{_cache_key(url)}.cache"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < CACHE_TTL:
            return cache_file.read_text(encoding="utf-8")
    return None


def _cache_set(url: str, content: str):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{_cache_key(url)}.cache"
    cache_file.write_text(content, encoding="utf-8")


# ─── HTTP fetch ───────────────────────────────────────────────────────────────

def http_get(url: str) -> tuple[str, str]:
    """Returns (content, content_type)."""
    cached = _cache_get(url)
    if cached:
        # Try to load cached metadata
        meta_file = CACHE_DIR / f"{_cache_key(url)}.meta"
        ctype = meta_file.read_text().strip() if meta_file.exists() else "application/json"
        print(f"{YELLOW}(cached){RESET}", file=sys.stderr)
        return cached, ctype

    headers = {"User-Agent": "Mozilla/5.0 (compatible; Dexter/1.0; data-aggregator)"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            ctype    = resp.headers.get("Content-Type", "application/json")
            encoding = resp.headers.get_content_charset("utf-8")
            content  = resp.read().decode(encoding, errors="replace")
    except urllib.error.HTTPError as e:
        print(f"{RED}HTTP {e.code}: {url}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach {url}: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)

    _cache_set(url, content)
    meta_file = CACHE_DIR / f"{_cache_key(url)}.meta"
    meta_file.write_text(ctype)
    return content, ctype


# ─── Format parsers ───────────────────────────────────────────────────────────

def parse_json(content: str) -> list[dict]:
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Try to unwrap common wrapper keys
            for key in ("data", "items", "results", "records", "rows"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]
        return [{"value": data}]
    except json.JSONDecodeError as e:
        print(f"{RED}JSON parse error: {e}{RESET}", file=sys.stderr)
        sys.exit(1)


def parse_csv(content: str) -> list[dict]:
    try:
        dialect = csv.Sniffer().sniff(content[:2048], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(content), dialect=dialect)
    return [dict(row) for row in reader]


class HTMLTableParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables  = []
        self._in_table = False
        self._in_row   = False
        self._in_cell  = False
        self._is_header = False
        self._current_row = []
        self._current_cell = []
        self._headers = []
        self._rows    = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._in_table  = True
            self._headers   = []
            self._rows      = []
        elif tag == "tr" and self._in_table:
            self._in_row       = True
            self._current_row  = []
        elif tag in ("th", "td") and self._in_row:
            self._in_cell     = True
            self._is_header   = (tag == "th")
            self._current_cell = []

    def handle_endtag(self, tag):
        if tag == "table":
            if self._headers and self._rows:
                self.tables.append({"headers": self._headers, "rows": self._rows})
            self._in_table = False
        elif tag == "tr" and self._in_row:
            if self._headers and self._current_row:
                self._rows.append(self._current_row)
            self._in_row = False
        elif tag in ("th", "td") and self._in_cell:
            cell_text = "".join(self._current_cell).strip()
            if self._is_header and not self._rows:
                self._headers.append(cell_text)
            else:
                self._current_row.append(cell_text)
            self._in_cell = False

    def handle_data(self, data):
        if self._in_cell:
            self._current_cell.append(data)


def parse_html(content: str) -> list[dict]:
    parser = HTMLTableParser()
    parser.feed(content)

    if not parser.tables:
        print(f"{YELLOW}No tables found in HTML.{RESET}", file=sys.stderr)
        return []

    table   = parser.tables[0]
    headers = table["headers"]
    rows    = table["rows"]

    result = []
    for row in rows:
        # Pad or trim to match headers
        row_padded = (row + [""] * len(headers))[:len(headers)]
        result.append(dict(zip(headers, row_padded)))
    return result


# ─── jq-style filter ──────────────────────────────────────────────────────────

def apply_jq(data: Any, filter_str: str) -> Any:
    """Simple dot-notation filter. e.g. '.items', '.data.users'"""
    if not filter_str or filter_str == ".":
        return data

    parts = filter_str.lstrip(".").split(".")
    current = data
    for part in parts:
        if not part:
            continue
        # Handle array index
        idx_match = None
        if "[" in part:
            key, idx_str = part.rstrip("]").split("[", 1)
            try:
                idx_match = int(idx_str)
            except ValueError:
                pass
            part = key

        if isinstance(current, dict) and part:
            current = current.get(part)
        elif isinstance(current, list) and part:
            try:
                current = [item.get(part) for item in current if isinstance(item, dict)]
            except Exception:
                pass

        if idx_match is not None and isinstance(current, list):
            try:
                current = current[idx_match]
            except IndexError:
                current = None

        if current is None:
            break

    return current


# ─── File I/O helpers ─────────────────────────────────────────────────────────

def load_file(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        print(f"{RED}File not found: {path}{RESET}", file=sys.stderr)
        sys.exit(1)
    content = p.read_text(encoding="utf-8")

    if p.suffix.lower() == ".json":
        return parse_json(content)
    elif p.suffix.lower() == ".csv":
        return parse_csv(content)
    else:
        # Try JSON first, then CSV
        try:
            return parse_json(content)
        except SystemExit:
            return parse_csv(content)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_fetch(url: str, fmt: Optional[str] = None, jq: Optional[str] = None):
    print(f"{BLUE}Fetching: {url}{RESET}", file=sys.stderr)
    content, ctype = http_get(url)

    # Detect format
    if not fmt:
        if "json" in ctype or url.endswith(".json"):
            fmt = "json"
        elif "csv" in ctype or url.endswith(".csv"):
            fmt = "csv"
        elif "html" in ctype or url.endswith(".html") or url.endswith(".htm"):
            fmt = "html"
        else:
            # Try JSON fallback
            try:
                json.loads(content)
                fmt = "json"
            except Exception:
                fmt = "html"

    if fmt == "json":
        data = parse_json(content)
    elif fmt == "csv":
        data = parse_csv(content)
    elif fmt == "html":
        data = parse_html(content)
    else:
        print(f"{RED}Unknown format: {fmt}{RESET}", file=sys.stderr)
        sys.exit(1)

    if jq:
        data = apply_jq(data, jq)

    result = json.dumps(data, indent=2, ensure_ascii=False)
    print(result)

    if isinstance(data, list):
        print(f"\n{GREEN}{len(data)} records fetched.{RESET}", file=sys.stderr)


def cmd_merge(file1: str, file2: str, key: Optional[str] = None, output: Optional[str] = None):
    data1 = load_file(file1)
    data2 = load_file(file2)

    if not key:
        # Simple concatenation
        merged = data1 + data2
        print(f"{YELLOW}No --key specified — concatenating datasets.{RESET}", file=sys.stderr)
    else:
        # Left join by key
        index2 = {}
        for record in data2:
            k = record.get(key)
            if k is not None:
                index2[str(k)] = record

        merged = []
        matched = 0
        for record in data1:
            k = str(record.get(key, ""))
            if k in index2:
                combined = {**record, **index2[k]}
                matched += 1
            else:
                combined = dict(record)
            merged.append(combined)

        print(f"{BLUE}Merged: {len(data1)} + {len(data2)} records, {matched} matches on '{key}'{RESET}", file=sys.stderr)

    result = json.dumps(merged, indent=2, ensure_ascii=False)

    if output:
        Path(output).write_text(result, encoding="utf-8")
        print(f"{GREEN}Saved: {output} ({len(merged)} records){RESET}")
    else:
        print(result)


def cmd_dedupe(file: str, key: Optional[str] = None):
    data = load_file(file)
    seen = set()
    unique = []

    for record in data:
        if key:
            fingerprint = str(record.get(key, ""))
        else:
            fingerprint = json.dumps(record, sort_keys=True)

        if fingerprint not in seen:
            seen.add(fingerprint)
            unique.append(record)

    removed = len(data) - len(unique)
    result  = json.dumps(unique, indent=2, ensure_ascii=False)
    Path(file).write_text(result, encoding="utf-8")

    print(f"{GREEN}Deduplicated: {file}{RESET}")
    print(f"  Before: {len(data):,} records")
    print(f"  After : {len(unique):,} records")
    print(f"  Removed: {removed:,} duplicates")


def cmd_export(file: str, fmt: str = "json"):
    data = load_file(file)

    if fmt == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))

    elif fmt == "csv":
        if not data:
            print("No data to export.")
            return
        # Collect all keys
        keys = list(dict.fromkeys(k for record in data for k in record.keys()))
        writer = csv.DictWriter(sys.stdout, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)

    elif fmt == "markdown":
        if not data:
            print("No data to export.")
            return
        keys = list(dict.fromkeys(k for record in data for k in record.keys()))

        # Header
        print("| " + " | ".join(keys) + " |")
        print("| " + " | ".join("---" for _ in keys) + " |")

        # Rows
        for record in data:
            row = [str(record.get(k, "")).replace("|", "\\|") for k in keys]
            print("| " + " | ".join(row) + " |")

        print(f"\n{GREEN}{len(data)} records{RESET}", file=sys.stderr)

    else:
        print(f"{RED}Unknown format: {fmt}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter Data Aggregator")
    sub    = parser.add_subparsers(dest="command", required=True)

    # fetch
    p_fetch = sub.add_parser("fetch", help="Fetch data from a URL")
    p_fetch.add_argument("url")
    p_fetch.add_argument("--format", choices=["json", "csv", "html"])
    p_fetch.add_argument("--jq", help="Simple dot-notation filter (e.g. '.items')")

    # merge
    p_merge = sub.add_parser("merge", help="Merge two datasets")
    p_merge.add_argument("file1")
    p_merge.add_argument("file2")
    p_merge.add_argument("--key",    help="Field to join on (left join)")
    p_merge.add_argument("--output", help="Output file (default: stdout)")

    # dedupe
    p_dd = sub.add_parser("dedupe", help="Remove duplicate records")
    p_dd.add_argument("file")
    p_dd.add_argument("--key", help="Field to use as unique key (default: full record)")

    # export
    p_exp = sub.add_parser("export", help="Export data to a format")
    p_exp.add_argument("file")
    p_exp.add_argument("--format", choices=["json", "csv", "markdown"], default="json")

    args = parser.parse_args()

    if args.command == "fetch":
        cmd_fetch(args.url, args.format, args.jq)
    elif args.command == "merge":
        cmd_merge(args.file1, args.file2, args.key, args.output)
    elif args.command == "dedupe":
        cmd_dedupe(args.file, args.key)
    elif args.command == "export":
        cmd_export(args.file, args.format)


if __name__ == "__main__":
    main()
