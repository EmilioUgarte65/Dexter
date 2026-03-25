#!/usr/bin/env python3
"""
Dexter — Cron job manager wrapping the crontab CLI.

Usage:
  cron_manager.py list
  cron_manager.py add <schedule> <command> [--comment TEXT]
  cron_manager.py remove <pattern>
  cron_manager.py run-now <command>
  cron_manager.py logs [--tail N]
"""

import sys
import os
import argparse
import subprocess
import re
from typing import Optional

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"


# ─── Human → Cron schedule conversion ────────────────────────────────────────

HUMAN_SCHEDULES = [
    (r"every\s+minute",                  "* * * * *"),
    (r"every\s+(\d+)\s+minutes?",        lambda m: f"*/{m.group(1)} * * * *"),
    (r"every\s+half\s+hour",             "*/30 * * * *"),
    (r"every\s+(\d+)\s+hours?",          lambda m: f"0 */{m.group(1)} * * *"),
    (r"every\s+hour",                    "0 * * * *"),
    (r"every\s+day|daily",               "0 0 * * *"),
    (r"every\s+week|weekly",             "0 0 * * 0"),
    (r"every\s+month|monthly",           "0 0 1 * *"),
    (r"at\s+midnight",                   "0 0 * * *"),
    (r"at\s+noon",                       "0 12 * * *"),
    (r"every\s+(\d+)\s+seconds?",        None),   # not supported — warn below
]

_CRON_PATTERN = re.compile(
    r"^(@(annually|yearly|monthly|weekly|daily|hourly|reboot))|"
    r"^(\S+\s+\S+\s+\S+\s+\S+\s+\S+)$"
)


def parse_schedule(schedule: str) -> str:
    """Convert a human schedule or pass-through a cron expression."""
    s = schedule.strip().lower()

    # Already looks like a cron expression?
    if _CRON_PATTERN.match(s) or len(s.split()) == 5:
        return schedule

    for pattern, replacement in HUMAN_SCHEDULES:
        m = re.search(pattern, s)
        if m:
            if replacement is None:
                print(f"{RED}Cron does not support sub-minute schedules.{RESET}", file=sys.stderr)
                sys.exit(1)
            if callable(replacement):
                return replacement(m)
            return replacement

    print(
        f"{RED}Could not parse schedule: '{schedule}'\n"
        f"Use a cron expression (e.g. '*/5 * * * *') or a human phrase like 'every 5 minutes'.{RESET}",
        file=sys.stderr,
    )
    sys.exit(1)


# ─── Crontab helpers ──────────────────────────────────────────────────────────

def _get_crontab() -> list[str]:
    """Return current crontab lines (empty list if none)."""
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        if "no crontab" in result.stderr.lower():
            return []
        print(f"{RED}crontab -l failed: {result.stderr}{RESET}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.splitlines()


def _set_crontab(lines: list[str]):
    """Write lines to crontab."""
    content = "\n".join(lines) + "\n" if lines else ""
    proc = subprocess.run(["crontab", "-"], input=content, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"{RED}Failed to write crontab: {proc.stderr}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_list():
    lines = _get_crontab()
    jobs = [l for l in lines if l.strip() and not l.strip().startswith("#")]

    if not jobs:
        print("No cron jobs configured.")
        return

    print(f"\n  {len(jobs)} cron job(s):\n")
    for i, job in enumerate(lines, 1):
        stripped = job.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            print(f"  {YELLOW}{job}{RESET}")
        else:
            parts = stripped.split(None, 5)
            if len(parts) >= 6:
                schedule = " ".join(parts[:5])
                command  = parts[5]
                print(f"  {GREEN}{schedule}{RESET}  {command}")
            else:
                print(f"  {job}")


def cmd_add(schedule: str, command: str, comment: Optional[str] = None):
    cron_expr = parse_schedule(schedule)
    lines = _get_crontab()

    new_lines = list(lines)
    if comment:
        new_lines.append(f"# {comment}")
    new_lines.append(f"{cron_expr} {command}")

    _set_crontab(new_lines)
    print(f"{GREEN}Added cron job:{RESET}")
    print(f"  Schedule: {cron_expr}")
    print(f"  Command:  {command}")
    if comment:
        print(f"  Comment:  {comment}")


def cmd_remove(pattern: str):
    lines = _get_crontab()
    before = len([l for l in lines if l.strip() and not l.startswith("#")])

    # Remove lines (and their preceding comment if it exists)
    new_lines = []
    skip_next_comment = False
    for i, line in enumerate(lines):
        if pattern in line and not line.strip().startswith("#"):
            # Also remove the comment immediately before this job (if any)
            if new_lines and new_lines[-1].strip().startswith("#"):
                new_lines.pop()
            print(f"  Removing: {line}")
        else:
            new_lines.append(line)

    after = len([l for l in new_lines if l.strip() and not l.startswith("#")])
    removed = before - after

    if removed == 0:
        print(f"{YELLOW}No jobs matched pattern: {pattern}{RESET}")
        return

    _set_crontab(new_lines)
    print(f"{GREEN}Removed {removed} job(s) matching '{pattern}'.{RESET}")


def cmd_run_now(command: str):
    print(f"Running: {command}\n")
    result = subprocess.run(command, shell=True, capture_output=False)
    if result.returncode == 0:
        print(f"\n{GREEN}Command completed successfully (exit 0).{RESET}")
    else:
        print(f"\n{RED}Command exited with code {result.returncode}.{RESET}", file=sys.stderr)
        sys.exit(result.returncode)


def cmd_logs(tail: int = 20):
    """Read cron logs from syslog or /var/log/cron."""
    log_files = ["/var/log/syslog", "/var/log/cron", "/var/log/cron.log"]
    log_file = None
    for f in log_files:
        if os.path.isfile(f):
            log_file = f
            break

    if not log_file:
        # Try journalctl as fallback
        result = subprocess.run(
            ["journalctl", "-u", "cron", "-u", "crond", "--no-pager", f"-n{tail}"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            print(result.stdout)
            return
        print(f"{RED}No cron log found. Tried: {', '.join(log_files)} and journalctl.{RESET}", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        ["grep", "-i", "cron", log_file],
        capture_output=True, text=True
    )
    lines = result.stdout.splitlines()
    if not lines:
        print(f"No cron entries found in {log_file}.")
        return

    print(f"Last {min(tail, len(lines))} cron log entries from {log_file}:\n")
    for line in lines[-tail:]:
        print(f"  {line}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter Cron Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    subparsers.add_parser("list", help="List current cron jobs")

    # add
    p_add = subparsers.add_parser("add", help="Add a cron job")
    p_add.add_argument("schedule", help="Cron expression or human phrase (e.g. 'every 5 minutes')")
    p_add.add_argument("command", help="Command to run")
    p_add.add_argument("--comment", help="Optional comment/description for the job")

    # remove
    p_remove = subparsers.add_parser("remove", help="Remove cron jobs matching a pattern")
    p_remove.add_argument("pattern", help="String pattern to match against job lines")

    # run-now
    p_run = subparsers.add_parser("run-now", help="Run a command immediately")
    p_run.add_argument("command", help="Command to execute now")

    # logs
    p_logs = subparsers.add_parser("logs", help="View recent cron log entries")
    p_logs.add_argument("--tail", type=int, default=20, help="Number of log lines to show (default: 20)")

    args = parser.parse_args()

    if args.command == "list":
        cmd_list()
    elif args.command == "add":
        cmd_add(args.schedule, args.command, comment=getattr(args, "comment", None))
    elif args.command == "remove":
        cmd_remove(args.pattern)
    elif args.command == "run-now":
        cmd_run_now(args.command)
    elif args.command == "logs":
        cmd_logs(tail=args.tail)


if __name__ == "__main__":
    main()
