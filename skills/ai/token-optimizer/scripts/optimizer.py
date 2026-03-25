#!/usr/bin/env python3
"""
Dexter Token Optimizer — tracks token usage and suggests skill creation.
Storage: ~/.local/share/dexter/token_log.jsonl
"""

import argparse
import json
import os
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── Config ──────────────────────────────────────────────────────────────────

STORAGE_DIR  = os.path.expanduser("~/.local/share/dexter")
LOG_FILE     = os.path.join(STORAGE_DIR, "token_log.jsonl")
SUGGEST_THRESHOLD = 3  # occurrences before suggesting skill creation

# Claude Sonnet pricing (per token)
COST_INPUT_PER_TOKEN  = 0.000003   # $3 per million
COST_OUTPUT_PER_TOKEN = 0.000015   # $15 per million

# ─── Colors ──────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

def ok(msg: str) -> None:
    print(f"{GREEN}✓ {msg}{RESET}")

def err(msg: str) -> None:
    print(f"{RED}✗ {msg}{RESET}", file=sys.stderr)

def warn(msg: str) -> None:
    print(f"{YELLOW}⚠ {msg}{RESET}")

def info(msg: str) -> None:
    print(f"{BLUE}ℹ {msg}{RESET}")

# ─── Storage ─────────────────────────────────────────────────────────────────

def ensure_storage() -> None:
    os.makedirs(STORAGE_DIR, exist_ok=True)
    if not os.path.exists(LOG_FILE):
        Path(LOG_FILE).touch()


def load_logs(since_days: int | None = None) -> list[dict]:
    ensure_storage()
    records = []
    cutoff = None
    if since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if cutoff is not None:
                        ts = datetime.fromisoformat(record["ts"])
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        if ts < cutoff:
                            continue
                    records.append(record)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
    except FileNotFoundError:
        pass

    return records


def append_log(record: dict) -> None:
    ensure_storage()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

# ─── Cost Calculation ────────────────────────────────────────────────────────

def calc_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * COST_INPUT_PER_TOKEN) + (output_tokens * COST_OUTPUT_PER_TOKEN)

# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_log(args: argparse.Namespace) -> int:
    session_id = args.session or str(uuid.uuid4())[:8]
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task_type": args.task_type,
        "in": args.input_tokens,
        "out": args.output_tokens,
        "session": session_id,
    }
    append_log(record)
    cost = calc_cost(args.input_tokens, args.output_tokens)
    ok(f"Logged — task_type={args.task_type}  in={args.input_tokens}  out={args.output_tokens}  cost=${cost:.4f}  session={session_id}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    days = args.days
    records = load_logs(since_days=days)

    if not records:
        warn(f"No logs found{f' in the last {days} days' if days else ''}.")
        return 0

    # Aggregate by task_type
    by_type: dict[str, dict] = defaultdict(lambda: {"count": 0, "in": 0, "out": 0, "cost": 0.0})
    total_in = total_out = 0
    total_cost = 0.0

    for r in records:
        t = r.get("task_type", "unknown")
        i = r.get("in", 0)
        o = r.get("out", 0)
        c = calc_cost(i, o)
        by_type[t]["count"] += 1
        by_type[t]["in"] += i
        by_type[t]["out"] += o
        by_type[t]["cost"] += c
        total_in += i
        total_out += o
        total_cost += c

    label = f"last {days} days" if days else "all time"
    print(f"\n{BLUE}Token Usage Report — {label} ({len(records)} tasks){RESET}")
    print("─" * 70)
    print(f"{'Task Type':<30} {'Count':>6}  {'Input':>9}  {'Output':>9}  {'Cost USD':>10}")
    print("─" * 70)

    sorted_types = sorted(by_type.items(), key=lambda x: x[1]["cost"], reverse=True)
    for task_type, stats in sorted_types:
        flag = f"{YELLOW}★{RESET}" if stats["count"] >= SUGGEST_THRESHOLD else " "
        print(
            f"{flag}{task_type:<29} {stats['count']:>6}  "
            f"{stats['in']:>9,}  {stats['out']:>9,}  "
            f"{GREEN}${stats['cost']:>9.4f}{RESET}"
        )

    print("─" * 70)
    print(f"{'TOTAL':<30} {len(records):>6}  {total_in:>9,}  {total_out:>9,}  {GREEN}${total_cost:>9.4f}{RESET}")
    print()

    repeated = [(t, s) for t, s in sorted_types if s["count"] >= SUGGEST_THRESHOLD]
    if repeated:
        print(f"{YELLOW}★ = repeated {SUGGEST_THRESHOLD}+ times — run 'suggest' for skill creation recommendations{RESET}")
        print()

    return 0


def cmd_suggest(args: argparse.Namespace) -> int:
    records = load_logs()

    if not records:
        warn("No logs found. Start logging tasks with: optimizer.py log <task_type> <in> <out>")
        return 0

    by_type: dict[str, dict] = defaultdict(lambda: {"count": 0, "in": 0, "out": 0, "cost": 0.0})

    for r in records:
        t = r.get("task_type", "unknown")
        i = r.get("in", 0)
        o = r.get("out", 0)
        c = calc_cost(i, o)
        by_type[t]["count"] += 1
        by_type[t]["in"] += i
        by_type[t]["out"] += o
        by_type[t]["cost"] += c

    candidates = [(t, s) for t, s in by_type.items() if s["count"] >= SUGGEST_THRESHOLD]

    if not candidates:
        ok(f"No repeated patterns found ({SUGGEST_THRESHOLD}+ occurrences threshold). Nothing to suggest yet.")
        return 0

    print(f"\n{BLUE}Skill Creation Suggestions{RESET}")
    print("─" * 60)
    print(f"These task types have been solved {SUGGEST_THRESHOLD}+ times from scratch.")
    print("Creating a skill will cache the reasoning and save cost.\n")

    for task_type, stats in sorted(candidates, key=lambda x: x[1]["cost"], reverse=True):
        avg_cost = stats["cost"] / stats["count"]
        # Estimate future savings: assume 10 more occurrences
        projected_savings = avg_cost * 10
        skill_name = task_type.lower().replace(" ", "-").replace("_", "-")

        print(f"{YELLOW}⚡ {task_type}{RESET}")
        print(f"   Occurrences:       {stats['count']}")
        print(f"   Total cost so far: ${stats['cost']:.4f}")
        print(f"   Avg cost/task:     ${avg_cost:.4f}")
        print(f"   Projected savings (next 10): {GREEN}${projected_savings:.4f}{RESET}")
        print(f"   {BLUE}Create skill:{RESET}")
        print(f"   python3 skills/skill-creator/scripts/create.py new {skill_name}")
        print()

    print(f"{YELLOW}→ After creating the skill, populate its SKILL.md with the recurring")
    print(f"  pattern so future tasks skip the reasoning entirely.{RESET}\n")

    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    days = args.days

    if days is None:
        # Clear all
        ensure_storage()
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("")
        ok("All logs cleared.")
        return 0

    # Keep only records newer than `days`
    records = load_logs()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    kept = []
    removed = 0

    for r in records:
        try:
            ts = datetime.fromisoformat(r["ts"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                kept.append(r)
            else:
                removed += 1
        except (KeyError, ValueError):
            kept.append(r)  # keep malformed records

    ensure_storage()
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r) + "\n")

    ok(f"Removed {removed} records older than {days} days. Kept {len(kept)} records.")
    return 0

# ─── Parser ──────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="optimizer.py",
        description="Dexter Token Optimizer — track usage, find patterns, suggest skills",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # log
    p_log = sub.add_parser("log", help="Log a completed task's token usage")
    p_log.add_argument("task_type", help="Type/category of the task (e.g. 'code-format', 'sdd-spec')")
    p_log.add_argument("input_tokens", type=int, help="Number of input tokens")
    p_log.add_argument("output_tokens", type=int, help="Number of output tokens")
    p_log.add_argument("--session", "-s", default=None, help="Session ID (auto-generated if omitted)")

    # report
    p_report = sub.add_parser("report", help="Show token usage report")
    p_report.add_argument("--days", "-d", type=int, default=None, help="Limit to last N days")

    # suggest
    sub.add_parser("suggest", help="Suggest skills for repeated task patterns")

    # reset
    p_reset = sub.add_parser("reset", help="Clear old logs")
    p_reset.add_argument("--days", "-d", type=int, default=None,
                         help="Delete logs older than N days (omit to clear all)")

    return parser

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "log":     cmd_log,
        "report":  cmd_report,
        "suggest": cmd_suggest,
        "reset":   cmd_reset,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
