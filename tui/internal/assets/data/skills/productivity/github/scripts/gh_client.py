#!/usr/bin/env python3
"""
Dexter — GitHub REST API v3 client.
Uses stdlib only (urllib). No external dependencies.

Usage:
  gh_client.py issues <owner/repo> [--state open|closed|all]
  gh_client.py create-issue <owner/repo> <title> <body>
  gh_client.py pr-list <owner/repo> [--state open|closed|all]
  gh_client.py pr-merge <owner/repo> <pr_number>
  gh_client.py release <owner/repo>
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

GITHUB_TOKEN       = os.environ.get("GITHUB_TOKEN", "")
DEFAULT_REPO       = os.environ.get("GITHUB_DEFAULT_REPO", "")

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"

BASE_URL = "https://api.github.com"


def check_config():
    if not GITHUB_TOKEN:
        print(
            "Warning: GITHUB_TOKEN not set — using unauthenticated API (60 req/hr limit).\n"
            "For private repos or higher limits:\n"
            "  export GITHUB_TOKEN=ghp_...",
            file=sys.stderr,
        )


def resolve_repo(repo: str) -> str:
    if repo:
        return repo
    if DEFAULT_REPO:
        return DEFAULT_REPO
    print(f"{RED}No repo provided and GITHUB_DEFAULT_REPO is not set.{RESET}", file=sys.stderr)
    sys.exit(1)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _headers() -> dict:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def gh_get(endpoint: str, params: Optional[dict] = None) -> Any:
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
            print(f"{RED}GitHub error {e.code}: {err.get('message', body)}{RESET}", file=sys.stderr)
        except Exception:
            print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach GitHub API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def gh_post(endpoint: str, payload: dict) -> Any:
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={**_headers(), "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            print(f"{RED}GitHub error {e.code}: {err.get('message', body)}{RESET}", file=sys.stderr)
        except Exception:
            print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach GitHub API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


def gh_put(endpoint: str, payload: dict) -> Any:
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={**_headers(), "Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            print(f"{RED}GitHub error {e.code}: {err.get('message', body)}{RESET}", file=sys.stderr)
        except Exception:
            print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach GitHub API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_issues(repo: str, state: str = "open"):
    r = resolve_repo(repo)
    issues = gh_get(f"/repos/{r}/issues", {"state": state, "per_page": 30})

    # Filter out pull requests (GitHub API returns PRs in /issues too)
    issues = [i for i in issues if not i.get("pull_request")]

    if not issues:
        print(f"No {state} issues in {r}.")
        return

    print(f"\n  {r} — {state.upper()} ISSUES ({len(issues)})\n")
    print(f"  {'#':<6} {'TITLE':<55} LABELS")
    print("  " + "-" * 80)
    for issue in issues:
        num    = issue.get("number", "?")
        title  = issue.get("title", "?")[:53]
        labels = ", ".join(l["name"] for l in issue.get("labels", []))
        color  = GREEN if state == "open" else RESET
        print(f"  {color}#{num:<5}{RESET} {title:<55} {labels}")


def cmd_create_issue(repo: str, title: str, body: str):
    r = resolve_repo(repo)
    result = gh_post(f"/repos/{r}/issues", {"title": title, "body": body})
    num = result.get("number", "?")
    url = result.get("html_url", "")
    print(f"{GREEN}Issue #{num} created in {r}{RESET}")
    print(f"  Title: {title}")
    print(f"  URL:   {url}")


def cmd_pr_list(repo: str, state: str = "open"):
    r = resolve_repo(repo)
    prs = gh_get(f"/repos/{r}/pulls", {"state": state, "per_page": 30})

    if not prs:
        print(f"No {state} pull requests in {r}.")
        return

    print(f"\n  {r} — {state.upper()} PULL REQUESTS ({len(prs)})\n")
    print(f"  {'#':<6} {'TITLE':<45} {'FROM':<25} REVIEWS")
    print("  " + "-" * 85)
    for pr in prs:
        num    = pr.get("number", "?")
        title  = pr.get("title", "?")[:43]
        head   = pr.get("head", {}).get("label", "?")[:23]
        color  = GREEN if state == "open" else RESET
        print(f"  {color}#{num:<5}{RESET} {title:<45} {head:<25}")


def cmd_pr_merge(repo: str, pr_number: int):
    r = resolve_repo(repo)
    # Get PR info first
    pr = gh_get(f"/repos/{r}/pulls/{pr_number}")
    title = pr.get("title", "?")
    state = pr.get("state", "?")

    if state != "open":
        print(f"{RED}PR #{pr_number} is not open (state: {state}){RESET}", file=sys.stderr)
        sys.exit(1)

    result = gh_put(f"/repos/{r}/pulls/{pr_number}/merge", {
        "merge_method": "squash",
        "commit_title": title,
    })
    merged = result.get("merged", False)
    msg    = result.get("message", "")
    if merged:
        sha = result.get("sha", "?")[:8]
        print(f"{GREEN}PR #{pr_number} merged into {r} (sha: {sha}){RESET}")
        print(f"  Title: {title}")
    else:
        print(f"{RED}Merge failed: {msg}{RESET}", file=sys.stderr)
        sys.exit(1)


def cmd_release(repo: str):
    r = resolve_repo(repo)
    releases = gh_get(f"/repos/{r}/releases", {"per_page": 10})

    if not releases:
        print(f"No releases found in {r}.")
        return

    print(f"\n  {r} — RELEASES\n")
    for rel in releases:
        tag         = rel.get("tag_name", "?")
        name        = rel.get("name", tag)
        published   = rel.get("published_at", "?")[:10]
        prerelease  = rel.get("prerelease", False)
        draft       = rel.get("draft", False)
        url         = rel.get("html_url", "")
        pre_label   = f"  {RED}[prerelease]{RESET}" if prerelease else ""
        draft_label = f"  {RED}[draft]{RESET}" if draft else ""
        print(f"  {GREEN}{tag}{RESET} — {name} ({published}){pre_label}{draft_label}")
        print(f"    {url}")
        body = rel.get("body", "").strip()
        if body:
            # Print first 2 lines of release notes
            lines = body.splitlines()[:2]
            for line in lines:
                print(f"    {line}")
        print()


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    check_config()

    parser = argparse.ArgumentParser(description="Dexter GitHub CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # issues
    p_issues = subparsers.add_parser("issues", help="List repository issues")
    p_issues.add_argument("repo", help="owner/repo (or empty string for GITHUB_DEFAULT_REPO)")
    p_issues.add_argument("--state", default="open", choices=["open", "closed", "all"], help="Issue state (default: open)")

    # create-issue
    p_create = subparsers.add_parser("create-issue", help="Create a new issue")
    p_create.add_argument("repo", help="owner/repo")
    p_create.add_argument("title", help="Issue title")
    p_create.add_argument("body", help="Issue body/description")

    # pr-list
    p_prs = subparsers.add_parser("pr-list", help="List pull requests")
    p_prs.add_argument("repo", help="owner/repo")
    p_prs.add_argument("--state", default="open", choices=["open", "closed", "all"], help="PR state (default: open)")

    # pr-merge
    p_merge = subparsers.add_parser("pr-merge", help="Merge a pull request (squash)")
    p_merge.add_argument("repo", help="owner/repo")
    p_merge.add_argument("pr_number", type=int, help="Pull request number")

    # release
    p_release = subparsers.add_parser("release", help="List releases")
    p_release.add_argument("repo", help="owner/repo")

    args = parser.parse_args()

    if args.command == "issues":
        cmd_issues(args.repo, state=args.state)
    elif args.command == "create-issue":
        cmd_create_issue(args.repo, args.title, args.body)
    elif args.command == "pr-list":
        cmd_pr_list(args.repo, state=args.state)
    elif args.command == "pr-merge":
        cmd_pr_merge(args.repo, args.pr_number)
    elif args.command == "release":
        cmd_release(args.repo)


if __name__ == "__main__":
    main()
