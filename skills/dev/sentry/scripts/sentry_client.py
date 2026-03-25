#!/usr/bin/env python3
"""
Dexter — Sentry REST API client.
Uses stdlib only (urllib). No external dependencies.

Usage:
  sentry_client.py --action list-issues [--project PROJECT]
  sentry_client.py --action get-issue --issue-id ISSUE_ID
  sentry_client.py --action resolve-issue --issue-id ISSUE_ID
  sentry_client.py --action list-events --issue-id ISSUE_ID
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
SENTRY_PROJECT    = os.environ.get("SENTRY_PROJECT", "")

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


def check_config(require_project: bool = False, project_override: Optional[str] = None):
    """Validate required env vars before any API call."""
    errors = []
    if not SENTRY_AUTH_TOKEN:
        errors.append("SENTRY_AUTH_TOKEN is not set.")
    if not SENTRY_ORG:
        errors.append("SENTRY_ORG is not set.")
    if require_project and not project_override and not SENTRY_PROJECT:
        errors.append("SENTRY_PROJECT is not set and --project was not provided.")
    if errors:
        for e in errors:
            print(f"{RED}Error: {e}{RESET}", file=sys.stderr)
        print(
            "\nGenerate a token at: Sentry → Settings → API → Auth Tokens\n"
            "  export SENTRY_AUTH_TOKEN=your_token\n"
            "  export SENTRY_ORG=your-org-slug\n"
            "  export SENTRY_PROJECT=your-project-slug",
            file=sys.stderr,
        )
        sys.exit(1)


def resolve_project(project_override: Optional[str]) -> str:
    """Return project slug from override arg or SENTRY_PROJECT env var."""
    project = project_override or SENTRY_PROJECT
    if not project:
        print(
            f"{RED}No project specified. Provide --project or set SENTRY_PROJECT.{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)
    return project


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


def sentry_put(endpoint: str, payload: dict) -> Any:
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=_headers(), method="PUT")
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

def cmd_list_issues(project_override: Optional[str] = None):
    """List unresolved issues — GET /organizations/{org}/issues/?project={project}&query=is:unresolved&limit=10"""
    check_config(require_project=True, project_override=project_override)
    project = resolve_project(project_override)

    issues = sentry_get(
        f"/organizations/{SENTRY_ORG}/issues/",
        {"project": project, "query": "is:unresolved", "limit": 10},
    )

    if not issues:
        print(f"No unresolved issues found in project '{project}'.")
        return

    print(f"\n  {SENTRY_ORG}/{project} — UNRESOLVED ISSUES ({len(issues)})\n")
    print(f"  {'ID':<14} {'COUNT':<8} {'LAST SEEN':<22} {'CULPRIT':<30} TITLE")
    print("  " + "-" * 100)
    for issue in issues:
        issue_id  = issue.get("id", "?")
        title     = issue.get("title", "?")[:45]
        culprit   = (issue.get("culprit") or "")[:28]
        count     = str(issue.get("count", "?"))
        last_seen = (issue.get("lastSeen") or "?")[:19]
        print(f"  {issue_id:<14} {YELLOW}{count:<8}{RESET} {last_seen:<22} {culprit:<30} {title}")
    print()


def cmd_get_issue(issue_id: str):
    """Get full details, stacktrace and tags — GET /issues/{issue_id}/"""
    check_config()
    issue = sentry_get(f"/issues/{issue_id}/")

    title      = issue.get("title", "?")
    level      = issue.get("level", "?").upper()
    status     = issue.get("status", "?")
    project    = issue.get("project", {}).get("slug", "?")
    culprit    = issue.get("culprit", "")
    count      = issue.get("count", "?")
    first_seen = (issue.get("firstSeen") or "?")[:19]
    last_seen  = (issue.get("lastSeen") or "?")[:19]
    permalink  = issue.get("permalink", "")

    level_color  = RED if level == "ERROR" else (YELLOW if level == "WARNING" else RESET)
    status_color = GREEN if status == "resolved" else YELLOW

    print(f"\n  ISSUE #{issue_id}\n")
    print(f"  Title:      {title}")
    print(f"  Level:      {level_color}{level}{RESET}")
    print(f"  Status:     {status_color}{status}{RESET}")
    print(f"  Project:    {project}")
    print(f"  Count:      {count}")
    print(f"  First seen: {first_seen}")
    print(f"  Last seen:  {last_seen}")
    if culprit:
        print(f"  Culprit:    {culprit}")
    if permalink:
        print(f"  URL:        {permalink}")

    # Stacktrace: first frame from the latest event
    metadata = issue.get("metadata", {})
    filename = metadata.get("filename", "")
    function = metadata.get("function", "")
    if filename or function:
        print(f"\n  STACKTRACE (top frame)")
        print(f"  {'─' * 40}")
        if filename:
            print(f"  File:     {filename}")
        if function:
            print(f"  Function: {function}")

    # Relevant tags
    tags = issue.get("tags", [])
    if tags:
        print(f"\n  TAGS")
        print(f"  {'─' * 40}")
        for tag in tags[:8]:
            key   = tag.get("key", "?")
            value = tag.get("topValues", [{}])[0].get("value", "?") if tag.get("topValues") else "?"
            print(f"  {key}: {value}")
    print()


def cmd_resolve_issue(issue_id: str):
    """Resolve an issue — PUT /issues/{issue_id}/ body {\"status\": \"resolved\"}"""
    check_config()
    result = sentry_put(f"/issues/{issue_id}/", {"status": "resolved"})
    status = result.get("status", "?")
    title  = result.get("title", "?")

    if status == "resolved":
        print(f"{GREEN}Issue #{issue_id} resolved.{RESET}")
        print(f"  Title: {title}")
    else:
        print(f"{YELLOW}Unexpected status after update: {status}{RESET}", file=sys.stderr)
        sys.exit(1)


def cmd_list_events(issue_id: str):
    """List recent events — GET /issues/{issue_id}/events/?limit=5"""
    check_config()
    events = sentry_get(f"/issues/{issue_id}/events/", {"limit": 5})

    if not events:
        print(f"No events found for issue #{issue_id}.")
        return

    print(f"\n  ISSUE #{issue_id} — RECENT EVENTS ({len(events)})\n")
    for i, event in enumerate(events, 1):
        timestamp = (event.get("dateCreated") or event.get("dateReceived") or "?")[:19]
        message   = event.get("message") or event.get("title") or "?"
        print(f"  [{i}] {timestamp}")
        print(f"      {message[:120]}")
        print()


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Dexter Sentry CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["list-issues", "get-issue", "resolve-issue", "list-events"],
        help="Action to perform",
    )
    parser.add_argument(
        "--issue-id",
        help="Sentry issue ID (required for get-issue, resolve-issue, list-events)",
    )
    parser.add_argument(
        "--project",
        help="Sentry project slug (overrides SENTRY_PROJECT env var)",
    )

    args = parser.parse_args()

    if args.action == "list-issues":
        cmd_list_issues(project_override=args.project)

    elif args.action == "get-issue":
        if not args.issue_id:
            parser.error("--issue-id is required for get-issue")
        cmd_get_issue(args.issue_id)

    elif args.action == "resolve-issue":
        if not args.issue_id:
            parser.error("--issue-id is required for resolve-issue")
        cmd_resolve_issue(args.issue_id)

    elif args.action == "list-events":
        if not args.issue_id:
            parser.error("--issue-id is required for list-events")
        cmd_list_events(args.issue_id)


if __name__ == "__main__":
    main()
