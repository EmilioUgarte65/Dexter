#!/usr/bin/env python3
"""
Dexter — Sentry REST API client.
Uses stdlib only (urllib). No external dependencies.

Usage:
  sentry.py list-issues <project_slug> [--limit 25]
  sentry.py get-issue <issue_id>
  sentry.py resolve <issue_id>
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

SENTRY_AUTH_TOKEN = os.environ.get("SENTRY_AUTH_TOKEN", "")
SENTRY_ORG        = os.environ.get("SENTRY_ORG", "")

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

BASE_URL = "https://sentry.io/api/0"


def _masked_token() -> str:
    """Return a masked token for safe logging (first 4 chars only)."""
    if not SENTRY_AUTH_TOKEN:
        return "(not set)"
    return SENTRY_AUTH_TOKEN[:4] + "****"


def check_config():
    errors = []
    if not SENTRY_AUTH_TOKEN:
        errors.append("SENTRY_AUTH_TOKEN is not set.")
    if not SENTRY_ORG:
        errors.append("SENTRY_ORG is not set.")
    if errors:
        for e in errors:
            print(f"{RED}Error: {e}{RESET}", file=sys.stderr)
        print(
            "\nGenerate a token at: Sentry → Settings → API → Auth Tokens\n"
            "  export SENTRY_AUTH_TOKEN=your_token\n"
            "  export SENTRY_ORG=your-org-slug",
            file=sys.stderr,
        )
        sys.exit(1)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {SENTRY_AUTH_TOKEN}",
        "Content-Type": "application/json",
    }


def sentry_get(endpoint: str, params: Optional[dict] = None) -> Any:
    url = f"{BASE_URL}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            detail = err.get("detail", err.get("error", body))
            print(f"{RED}Sentry error {e.code}: {detail}{RESET}", file=sys.stderr)
        except Exception:
            print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Sentry API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def sentry_patch(endpoint: str, payload: dict) -> Any:
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=_headers(), method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            detail = err.get("detail", err.get("error", body))
            print(f"{RED}Sentry error {e.code}: {detail}{RESET}", file=sys.stderr)
        except Exception:
            print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Sentry API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_list_issues(project_slug: str, limit: int = 25):
    """List unresolved issues for a Sentry project."""
    issues = sentry_get(
        f"/projects/{SENTRY_ORG}/{project_slug}/issues/",
        {"query": "is:unresolved", "limit": limit},
    )

    if not issues:
        print(f"No unresolved issues found in project '{project_slug}'.")
        return

    print(f"\n  {SENTRY_ORG}/{project_slug} — UNRESOLVED ISSUES ({len(issues)})\n")
    print(f"  {'ID':<14} {'LEVEL':<8} {'TIMES SEEN':<12} TITLE")
    print("  " + "-" * 85)
    for issue in issues:
        issue_id    = issue.get("id", "?")
        title       = issue.get("title", "?")[:55]
        level       = issue.get("level", "?").upper()
        times_seen  = issue.get("count", "?")
        level_color = RED if level == "ERROR" else (YELLOW if level == "WARNING" else RESET)
        print(f"  {issue_id:<14} {level_color}{level:<8}{RESET} {str(times_seen):<12} {title}")
    print()


def cmd_get_issue(issue_id: str):
    """Get full details for a Sentry issue."""
    issue = sentry_get(f"/issues/{issue_id}/")

    title       = issue.get("title", "?")
    level       = issue.get("level", "?").upper()
    status      = issue.get("status", "?")
    project     = issue.get("project", {}).get("slug", "?")
    times_seen  = issue.get("count", "?")
    first_seen  = issue.get("firstSeen", "?")[:19] if issue.get("firstSeen") else "?"
    last_seen   = issue.get("lastSeen", "?")[:19] if issue.get("lastSeen") else "?"
    culprit     = issue.get("culprit", "")
    permalink   = issue.get("permalink", "")

    level_color  = RED if level == "ERROR" else (YELLOW if level == "WARNING" else RESET)
    status_color = GREEN if status == "resolved" else YELLOW

    print(f"\n  ISSUE #{issue_id}\n")
    print(f"  Title:      {title}")
    print(f"  Level:      {level_color}{level}{RESET}")
    print(f"  Status:     {status_color}{status}{RESET}")
    print(f"  Project:    {project}")
    print(f"  Times seen: {times_seen}")
    print(f"  First seen: {first_seen}")
    print(f"  Last seen:  {last_seen}")
    if culprit:
        print(f"  Culprit:    {culprit}")
    if permalink:
        print(f"  URL:        {permalink}")
    print()


def cmd_resolve(issue_id: str):
    """Resolve a Sentry issue by ID."""
    result = sentry_patch(f"/issues/{issue_id}/", {"status": "resolved"})
    status = result.get("status", "?")
    title  = result.get("title", "?")

    if status == "resolved":
        print(f"{GREEN}Issue #{issue_id} resolved.{RESET}")
        print(f"  Title: {title}")
    else:
        print(f"{YELLOW}Unexpected status after patch: {status}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter Sentry CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-issues
    p_list = subparsers.add_parser("list-issues", help="List unresolved issues for a project")
    p_list.add_argument("project_slug", help="Sentry project slug")
    p_list.add_argument("--limit", type=int, default=25, help="Max number of issues (default: 25)")

    # get-issue
    p_get = subparsers.add_parser("get-issue", help="Get full details of an issue")
    p_get.add_argument("issue_id", help="Sentry issue ID")

    # resolve
    p_resolve = subparsers.add_parser("resolve", help="Resolve an issue")
    p_resolve.add_argument("issue_id", help="Sentry issue ID to resolve")

    args = parser.parse_args()
    check_config()

    if args.command == "list-issues":
        cmd_list_issues(args.project_slug, limit=args.limit)
    elif args.command == "get-issue":
        cmd_get_issue(args.issue_id)
    elif args.command == "resolve":
        cmd_resolve(args.issue_id)


if __name__ == "__main__":
    main()
