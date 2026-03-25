#!/usr/bin/env python3
"""
Dexter — Todoist REST API v2 client.
Uses stdlib only (urllib). No external dependencies.
Token is masked in all log output.

Usage:
  todoist.py list [--project-id ID]
  todoist.py add <content> [--due DUE_STRING] [--priority 1-4]
  todoist.py complete <task_id>
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
from typing import Any, Optional

# ─── Config from env ──────────────────────────────────────────────────────────

API_TOKEN = os.environ.get("TODOIST_API_TOKEN", "")
API_BASE  = "https://api.todoist.com/rest/v2"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

PRIORITY_LABELS = {1: "normal", 2: "medium", 3: "high", 4: "urgent"}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _mask_token(token: str) -> str:
    """Return token with all but first 4 chars replaced by ***."""
    if len(token) <= 4:
        return "***"
    return token[:4] + "***"


def check_config() -> None:
    if not API_TOKEN:
        print(
            f"{RED}Error: TODOIST_API_TOKEN not set.\n"
            "Get your token from: https://app.todoist.com/app/settings/integrations/developer\n"
            f"Then: export TODOIST_API_TOKEN=your_token{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)


def _request(method: str, path: str, payload: Optional[dict] = None) -> Any:
    url = f"{API_BASE}{path}"
    data = json.dumps(payload).encode() if payload else None
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
            return json.loads(body) if body.strip() else None
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        # Never log the token — mask it if it somehow appears in the error body
        safe_body = body.replace(API_TOKEN, _mask_token(API_TOKEN))
        try:
            err = json.loads(safe_body)
            msg = err.get("error", safe_body)
        except Exception:
            msg = safe_body
        print(f"{RED}Todoist API error {e.code}: {msg}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach Todoist API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_list(project_id: Optional[str]) -> None:
    path = "/tasks"
    if project_id:
        path += f"?project_id={project_id}"

    tasks = _request("GET", path)
    if not tasks:
        print("No active tasks found.")
        return

    print(f"Active tasks ({len(tasks)}):\n")
    for task in tasks:
        tid      = task.get("id", "?")
        content  = task.get("content", "(no content)")
        priority = task.get("priority", 1)
        due      = task.get("due", {})
        due_str  = due.get("string", "no due date") if due else "no due date"
        prio_label = PRIORITY_LABELS.get(priority, str(priority))
        print(f"  [{tid}]  {content}")
        print(f"           due={due_str}  priority={prio_label}")
        print()


def cmd_add(content: str, due_string: Optional[str], priority: int) -> None:
    if priority not in (1, 2, 3, 4):
        print(f"{RED}Error: priority must be 1, 2, 3, or 4.{RESET}", file=sys.stderr)
        sys.exit(1)

    payload: dict = {"content": content, "priority": priority}
    if due_string:
        payload["due_string"] = due_string

    task = _request("POST", "/tasks", payload)
    if not task:
        print(f"{RED}Error: no response from Todoist API.{RESET}", file=sys.stderr)
        sys.exit(1)

    tid = task.get("id", "?")
    # Log only the task ID to avoid echoing sensitive content
    print(f"{GREEN}Task created: id={tid}{RESET}")


def cmd_complete(task_id: str) -> None:
    _request("POST", f"/tasks/{task_id}/close")
    print(f"{GREEN}Task {task_id} marked as complete.{RESET}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Dexter Todoist CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List active tasks")
    p_list.add_argument("--project-id", default=None,
                        help="Filter by project ID (optional)")

    # add
    p_add = subparsers.add_parser("add", help="Add a new task")
    p_add.add_argument("content", help="Task content/title")
    p_add.add_argument("--due", dest="due_string", default=None,
                       help="Due date as natural language string (e.g. 'next Monday')")
    p_add.add_argument("--priority", type=int, default=1,
                       choices=[1, 2, 3, 4],
                       help="Priority: 1=normal, 2=medium, 3=high, 4=urgent (default: 1)")

    # complete
    p_complete = subparsers.add_parser("complete", help="Mark a task as complete")
    p_complete.add_argument("task_id", help="Todoist task ID")

    args = parser.parse_args()
    check_config()

    if args.command == "list":
        cmd_list(args.project_id)
    elif args.command == "add":
        cmd_add(args.content, args.due_string, args.priority)
    elif args.command == "complete":
        cmd_complete(args.task_id)


if __name__ == "__main__":
    main()
