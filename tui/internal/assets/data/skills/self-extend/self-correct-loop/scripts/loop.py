#!/usr/bin/env python3
"""
Dexter — Self-Correct Loop meta-skill.
Runs a shell command, captures output, and retries with self-correction on failure.
Uses stdlib only. No external dependencies.

Usage:
  loop.py run <cmd> [--max-iterations N]
  loop.py check <cmd>
"""

import sys
import os
import json
import re
import argparse
import subprocess
from typing import Optional

# ─── Security denylist ────────────────────────────────────────────────────────

# Each entry is a regex pattern. If ANY pattern matches the command, execution is refused.
DENYLIST_PATTERNS = [
    r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f",          # rm -rf, rm -fr, rm -Rf, etc.
    r"rm\s+-[a-zA-Z]*f[a-zA-Z]*r",          # rm -fr
    r"\bsudo\b",                              # sudo
    r"\bsu\b(\s|$)",                          # su (standalone)
    r"\bmkfs\b",                              # mkfs
    r"\bdd\b.*\bof=/dev/",                   # dd writing to device
    r">\s*/dev/[^n]",                        # write to /dev/* (except /dev/null)
    r">\s*/(etc|usr|bin|sbin|boot)/",        # overwrite system paths
    r"\bcurl\b.*https?://(?!localhost|127\.)[\w.-]+",   # curl to external hosts
    r"\bwget\b.*https?://(?!localhost|127\.)[\w.-]+",   # wget to external hosts
]

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"


def is_command_allowed(cmd: str) -> tuple[bool, Optional[str]]:
    """Check command against denylist. Returns (allowed, reason)."""
    for pattern in DENYLIST_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return False, f"Command matches denylist pattern: {pattern}"
    return True, None


def run_command(cmd: str) -> tuple[int, str, str]:
    """Run a shell command. Returns (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out after 120 seconds."
    except Exception as e:
        return 1, "", f"Failed to run command: {e}"


def build_correction_prompt(cmd: str, iteration: int, stderr: str, stdout: str) -> str:
    """Build the self-correction context message printed to stdout for agent consumption."""
    return (
        f"[self-correct-loop] Iteration {iteration} failed.\n"
        f"Command: {cmd}\n"
        f"--- STDOUT ---\n{stdout}\n"
        f"--- STDERR ---\n{stderr}\n"
        f"--- END ---\n"
        f"Please analyze the error above and suggest a corrected command."
    )


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_check(cmd: str):
    """Validate a command against the denylist without executing it."""
    allowed, reason = is_command_allowed(cmd)
    if allowed:
        print(f"{GREEN}Command is allowed.{RESET}")
        print(f"  Command: {cmd}")
    else:
        print(f"{RED}Command BLOCKED.{RESET}", file=sys.stderr)
        print(f"  Command: {cmd}", file=sys.stderr)
        print(f"  Reason:  {reason}", file=sys.stderr)
        sys.exit(1)


def cmd_run(cmd: str, max_iterations: int = 3):
    """Run a command with self-correction loop on failure."""
    # Security check first
    allowed, reason = is_command_allowed(cmd)
    if not allowed:
        result = {
            "exit_code": 1,
            "iterations_used": 0,
            "stdout": "",
            "stderr": f"Command blocked by security denylist: {reason}",
        }
        print(json.dumps(result, indent=2))
        sys.exit(1)

    iterations_used = 0
    current_cmd = cmd

    for iteration in range(1, max_iterations + 1):
        iterations_used = iteration
        print(f"{YELLOW}[loop] Iteration {iteration}/{max_iterations}: {current_cmd}{RESET}", file=sys.stderr)

        exit_code, stdout, stderr = run_command(current_cmd)

        if exit_code == 0:
            result = {
                "exit_code": 0,
                "iterations_used": iterations_used,
                "stdout": stdout,
                "stderr": stderr,
            }
            print(json.dumps(result, indent=2))
            return

        # Command failed
        print(f"{RED}[loop] Iteration {iteration} failed (exit {exit_code}).{RESET}", file=sys.stderr)

        if iteration < max_iterations:
            # Emit self-correction prompt to stdout for agent to consume
            print(build_correction_prompt(current_cmd, iteration, stderr, stdout))
            print(
                f"{YELLOW}[loop] Waiting for corrected command on stdin "
                f"(or press Ctrl+C to abort)...{RESET}",
                file=sys.stderr,
            )
            try:
                corrected = input().strip()
                if not corrected:
                    print(f"{RED}[loop] No correction provided — aborting.{RESET}", file=sys.stderr)
                    break

                # Security check on the corrected command too
                allowed, reason = is_command_allowed(corrected)
                if not allowed:
                    print(
                        f"{RED}[loop] Corrected command blocked: {reason}{RESET}",
                        file=sys.stderr,
                    )
                    break

                current_cmd = corrected
            except (EOFError, KeyboardInterrupt):
                print(f"\n{RED}[loop] Aborted by user.{RESET}", file=sys.stderr)
                break

    # All iterations exhausted or aborted
    exit_code, stdout, stderr = run_command(current_cmd) if iterations_used < max_iterations else (exit_code, stdout, stderr)
    result = {
        "exit_code": exit_code,
        "iterations_used": iterations_used,
        "stdout": stdout,
        "stderr": stderr,
    }
    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter Self-Correct Loop")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run
    p_run = subparsers.add_parser("run", help="Run a command with self-correction on failure")
    p_run.add_argument("cmd", help="Shell command to run")
    p_run.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        dest="max_iterations",
        help="Max self-correction iterations (default: 3)",
    )

    # check
    p_check = subparsers.add_parser("check", help="Validate command against denylist (no execution)")
    p_check.add_argument("cmd", help="Shell command to validate")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args.cmd, max_iterations=args.max_iterations)
    elif args.command == "check":
        cmd_check(args.cmd)


if __name__ == "__main__":
    main()
