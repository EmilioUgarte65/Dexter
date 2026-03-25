#!/usr/bin/env python3
"""Manage Todoist tasks via the REST API v2."""
import argparse
import os
import sys

import requests

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

BASE_URL = "https://api.todoist.com/rest/v2"


def check_config():
    missing = [v for v in ["TODOIST_API_TOKEN"] if not os.getenv(v)]
    if missing:
        print(
            f"{RED}Missing env vars: {', '.join(missing)}{RESET}\n"
            "\nSetup:\n"
            "  1. Go to https://app.todoist.com/app/settings/integrations/developer\n"
            "  2. Copy your API token\n"
            "  3. export TODOIST_API_TOKEN=your_token_here",
            file=sys.stderr,
        )
        sys.exit(1)


def get_headers() -> dict:
    token = os.environ["TODOIST_API_TOKEN"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def api_get(path: str, params: dict = None) -> dict:
    url = f"{BASE_URL}{path}"
    resp = requests.get(url, headers=get_headers(), params=params, timeout=15)
    if not resp.ok:
        print(f"{RED}Todoist API error {resp.status_code}: {resp.text}{RESET}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def api_post(path: str, payload: dict) -> dict:
    url = f"{BASE_URL}{path}"
    resp = requests.post(url, headers=get_headers(), json=payload, timeout=15)
    if not resp.ok:
        print(f"{RED}Todoist API error {resp.status_code}: {resp.text}{RESET}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def api_post_empty(path: str) -> None:
    """POST with no body, expects 204 No Content."""
    url = f"{BASE_URL}{path}"
    resp = requests.post(url, headers=get_headers(), timeout=15)
    if resp.status_code not in (200, 204):
        print(f"{RED}Todoist API error {resp.status_code}: {resp.text}{RESET}", file=sys.stderr)
        sys.exit(1)


def api_delete(path: str) -> None:
    url = f"{BASE_URL}{path}"
    resp = requests.delete(url, headers=get_headers(), timeout=15)
    if resp.status_code not in (200, 204):
        print(f"{RED}Todoist API error {resp.status_code}: {resp.text}{RESET}", file=sys.stderr)
        sys.exit(1)


def cmd_list():
    """List all active tasks."""
    tasks = api_get("/tasks")
    if not tasks:
        print("No active tasks found.")
        return

    print(f"\n  {'ID':<15} {'DUE':<15} CONTENT")
    print("  " + "-" * 70)
    for task in tasks:
        task_id = str(task.get("id", "?"))[:13]
        due = task.get("due", {})
        due_str = (due.get("date", "—") if due else "—")[:13]
        content = task.get("content", "(no content)")[:50]
        print(f"  {task_id:<15} {due_str:<15} {content}")


def cmd_add(content: str, project_id: str = None, due_string: str = None):
    """Add a new task."""
    payload: dict = {"content": content}
    if project_id:
        payload["project_id"] = project_id
    if due_string:
        payload["due_string"] = due_string

    task = api_post("/tasks", payload)
    task_id = task.get("id", "?")
    print(f"{GREEN}Task added:{RESET} {content}")
    print(f"  ID: {task_id}")
    if due_string:
        print(f"  Due: {task.get('due', {}).get('date', due_string)}")


def cmd_complete(task_id: str):
    """Mark a task as complete."""
    api_post_empty(f"/tasks/{task_id}/close")
    print(f"{GREEN}Task completed:{RESET} {task_id}")


def cmd_delete(task_id: str):
    """Delete a task."""
    api_delete(f"/tasks/{task_id}")
    print(f"{GREEN}Task deleted:{RESET} {task_id}")


def main():
    parser = argparse.ArgumentParser(description="Dexter — Todoist task manager")
    parser.add_argument(
        "--action",
        choices=["list", "add", "complete", "delete"],
        required=True,
        help="Action to perform",
    )
    parser.add_argument("--content", help="Task content/title (required for add)")
    parser.add_argument("--task-id", dest="task_id", help="Task ID (required for complete/delete)")
    parser.add_argument("--project-id", dest="project_id", help="Project ID (optional for add)")
    parser.add_argument(
        "--due-string",
        dest="due_string",
        help='Natural language due date, e.g. "tomorrow", "next monday" (optional for add)',
    )

    args = parser.parse_args()
    check_config()

    if args.action == "list":
        cmd_list()

    elif args.action == "add":
        if not args.content:
            print(f"{RED}Error:{RESET} --content is required for add.", file=sys.stderr)
            sys.exit(1)
        cmd_add(args.content, project_id=args.project_id, due_string=args.due_string)

    elif args.action == "complete":
        if not args.task_id:
            print(f"{RED}Error:{RESET} --task-id is required for complete.", file=sys.stderr)
            sys.exit(1)
        cmd_complete(args.task_id)

    elif args.action == "delete":
        if not args.task_id:
            print(f"{RED}Error:{RESET} --task-id is required for delete.", file=sys.stderr)
            sys.exit(1)
        cmd_delete(args.task_id)


if __name__ == "__main__":
    main()
