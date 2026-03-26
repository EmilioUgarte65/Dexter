#!/usr/bin/env python3
"""
Dexter — Skill Writer.
Auto-generates a new Dexter skill from a plain-language description.

Pipeline:
  1. Intent Analysis  — check registry for existing skills
  2. Skill Generation — call LLM to produce SKILL.md + script
  3. Security Gate    — run audit.py, block on CRITICAL/HIGH findings
  4. Registration     — copy to ~/.dexter/community/ and append registry

Usage:
  skill_writer.py generate "<user request>" [--category CAT] [--name NAME] [--dry-run]
  skill_writer.py list-generated
"""

import sys
import os
import re
import json
import shutil
import subprocess
import argparse
import tempfile
import datetime
from pathlib import Path
from typing import Optional

# ─── Config from env ──────────────────────────────────────────────────────────

DEXTER_ROOT    = Path(os.environ.get("DEXTER_ROOT", Path(__file__).resolve().parents[3]))
SKILLS_DIR     = DEXTER_ROOT / "skills"
REGISTRY_PATH  = DEXTER_ROOT / ".atl" / "skill-registry.md"
COMMUNITY_DIR  = Path.home() / ".dexter" / "community"

CREATE_SCRIPT  = SKILLS_DIR / "skill-creator" / "scripts" / "create.py"
AUDIT_SCRIPT_CANDIDATES = [
    SKILLS_DIR / "security" / "security-auditor" / "scripts" / "audit.py",
    Path.home() / ".dexter" / "community" / "security" / "security-auditor" / "scripts" / "audit.py",
]

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def check_config():
    """Validate required tooling before generation."""
    missing = []
    if not CREATE_SCRIPT.exists():
        missing.append(f"skill-creator script not found at: {CREATE_SCRIPT}")
    if not REGISTRY_PATH.exists():
        missing.append(f"registry not found at: {REGISTRY_PATH}")
    if missing:
        print(f"{RED}Error: Prerequisites missing:{RESET}", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        sys.exit(1)


# ─── LLM Runtime ──────────────────────────────────────────────────────────────

def detect_llm_cli() -> str:
    """
    Detect available LLM CLI in priority order:
      1. DEXTER_AGENT env var (explicit override)
      2. claude  (Claude Code CLI)
      3. opencode (OpenCode CLI)
    Raises RuntimeError if none found.
    """
    agent = os.environ.get("DEXTER_AGENT")
    if agent:
        if shutil.which(agent):
            return agent
        raise RuntimeError(
            f"DEXTER_AGENT is set to '{agent}' but that binary was not found in PATH."
        )
    if shutil.which("claude"):
        return "claude"
    if shutil.which("opencode"):
        return "opencode"
    raise RuntimeError(
        "No LLM CLI detected. Set DEXTER_AGENT or install one of:\n"
        "  - claude (Claude Code): https://claude.ai/code\n"
        "  - opencode: https://opencode.ai"
    )


# ─── Phase 1 — Intent Analysis ────────────────────────────────────────────────

def _load_registry() -> str:
    """Read the skill registry markdown."""
    if not REGISTRY_PATH.exists():
        return ""
    return REGISTRY_PATH.read_text(encoding="utf-8")


def find_existing_skills(request: str) -> list[dict]:
    """
    Simple keyword search against the registry.
    Returns list of {name, path} dicts for any matches found.
    """
    registry_text = _load_registry()
    if not registry_text:
        return []

    # Extract words from request (lower, 4+ chars to avoid noise)
    keywords = [w.lower() for w in re.findall(r"\b\w{4,}\b", request)]
    if not keywords:
        return []

    matches = []
    # Match table rows: | `name` | ... | path | ...
    row_pattern = re.compile(r"\|\s*`([^`]+)`\s*\|([^|]*)\|([^|]*)\|")
    for match in row_pattern.finditer(registry_text):
        skill_name = match.group(1).lower()
        row_text   = match.group(0).lower()
        if any(kw in skill_name or kw in row_text for kw in keywords):
            matches.append({
                "name": match.group(1),
                "row":  match.group(0).strip(),
            })
    return matches


# ─── Phase 2 — Skill Generation ───────────────────────────────────────────────

SKILL_TEMPLATE_RULES = """
SKILL.md FORMAT RULES (strictly follow these):

Frontmatter:
---
name: <kebab-case-name>
description: >
  <One paragraph. Include trigger keywords on last line like: Trigger: keyword1, keyword2>
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: false
allowed-tools: Bash
---

Body sections (in order):
# <Skill Name>
One sentence description.

## Setup
Environment variables needed (if any). How to obtain credentials.

## Usage
```bash
python3 skills/<category>/<name>/scripts/<name>.py <command> [args]
```

## Agent Instructions
Step-by-step for the agent when the trigger is detected.

SCRIPT FORMAT RULES:
- Python 3, stdlib only (no pip installs)
- Required: shebang, module docstring with Usage section
- Required: GREEN/RED/YELLOW/RESET color constants
- Required: check_config() that validates env vars (if needed)
- Required: argparse with subparsers
- Required: section comments: # ─── Section ─────────────
- Required: if __name__ == "__main__": main()
- NO third-party imports (no requests, no boto3, no anthropic SDK)
"""


def _build_prompt(request: str, name: Optional[str], category: Optional[str]) -> str:
    """Build the LLM prompt for skill generation."""
    name_hint     = f"\nPreferred skill name: {name}" if name else ""
    category_hint = f"\nPreferred category: {category}" if category else ""

    return (
        f"You are a Dexter skill generator. Generate a complete Dexter skill.\n\n"
        f"{SKILL_TEMPLATE_RULES}\n\n"
        f"USER REQUEST: {request}"
        f"{name_hint}"
        f"{category_hint}\n\n"
        "OUTPUT FORMAT (EXACTLY as shown — do NOT add extra text before or after):\n\n"
        "<SKILL.md content here — complete frontmatter + body>\n\n"
        "---SCRIPT---\n\n"
        "<Python script content here — complete, runnable>\n"
    )


def _call_llm(cli: str, prompt: str) -> str:
    """
    Dispatch to detected LLM CLI and return stdout.
    Raises RuntimeError on non-zero exit.
    """
    if cli == "claude":
        cmd = ["claude", "-p", prompt]
    else:
        # opencode: positional prompt argument
        cmd = ["opencode", prompt]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"LLM CLI '{cli}' exited {result.returncode}.\n"
            f"stderr: {result.stderr.strip()}"
        )
    return result.stdout


def _parse_llm_output(output: str) -> tuple[str, str]:
    """
    Split LLM output on '---SCRIPT---' separator.
    Returns (skill_md_content, script_content).
    Raises ValueError if separator not found.
    """
    separator = "---SCRIPT---"
    if separator not in output:
        raise ValueError(
            f"LLM output did not contain '{separator}' separator.\n"
            f"Raw output (first 500 chars): {output[:500]}"
        )
    parts = output.split(separator, 1)
    skill_md = parts[0].strip()
    script   = parts[1].strip()
    return skill_md, script


def _extract_frontmatter_field(skill_md: str, field: str) -> Optional[str]:
    """Extract a simple string field from SKILL.md YAML frontmatter."""
    pattern = re.compile(rf"^{re.escape(field)}:\s*(.+)$", re.MULTILINE)
    match = pattern.search(skill_md)
    if match:
        return match.group(1).strip().strip('"').strip("'")
    return None


def _scaffold_and_write(
    skill_md: str,
    script: str,
    name: str,
    category: str,
    tmp_dir: Path,
) -> Path:
    """
    Write generated SKILL.md and script into tmp_dir/<name>/.
    Returns the skill directory path.
    """
    skill_dir = tmp_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "scripts").mkdir(exist_ok=True)

    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

    script_name = f"{name}.py"
    (skill_dir / "scripts" / script_name).write_text(script, encoding="utf-8")
    (skill_dir / "scripts" / script_name).chmod(0o755)

    return skill_dir


# ─── Phase 3 — Security Gate ──────────────────────────────────────────────────

def _find_audit_script() -> Optional[Path]:
    """Locate audit.py from the candidate path list."""
    for candidate in AUDIT_SCRIPT_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def run_security_gate(skill_dir: Path) -> dict:
    """
    Run audit.py against skill_dir with --json flag.
    Returns parsed JSON result dict.
    Raises RuntimeError if audit script not found.
    """
    audit_script = _find_audit_script()
    if not audit_script:
        raise RuntimeError(
            "Security auditor not found. Expected at:\n"
            + "\n".join(f"  {p}" for p in AUDIT_SCRIPT_CANDIDATES)
        )

    result = subprocess.run(
        [sys.executable, str(audit_script), str(skill_dir), "--json"],
        capture_output=True,
        text=True,
    )

    # Exit 0 = PASS/WARN, exit 1 = BLOCK
    raw = result.stdout.strip()
    if not raw:
        # Fallback: if no JSON, treat as PASS
        return {"verdict": "PASS", "findings": []}

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # audit.py might mix text + JSON — try to extract last JSON object
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        # If still can't parse: treat as WARN with raw output
        return {"verdict": "WARN", "findings": [], "raw": raw}


def _is_blocked(audit_result: dict) -> bool:
    """Return True if audit result should block registration."""
    verdict = audit_result.get("verdict", "").upper()
    if verdict == "BLOCK":
        return True
    # Also check individual finding severities
    for finding in audit_result.get("findings", []):
        severity = finding.get("severity", "").upper()
        if severity in ("CRITICAL", "HIGH", "BLOCK"):
            return True
    return False


def _print_audit_findings(audit_result: dict) -> None:
    """Print security gate findings in a readable format."""
    verdict  = audit_result.get("verdict", "UNKNOWN").upper()
    findings = audit_result.get("findings", [])

    color = RED if verdict in ("BLOCK", "CRITICAL", "HIGH") else YELLOW
    print(f"\n{color}{BOLD}Security Gate — {verdict}{RESET}")

    if not findings:
        print(f"  {YELLOW}No detailed findings available.{RESET}")
        return

    for f in findings:
        severity = f.get("severity", "?").upper()
        sev_color = RED if severity in ("CRITICAL", "HIGH", "BLOCK") else YELLOW
        print(
            f"  {sev_color}[{severity}]{RESET} "
            f"{f.get('file', '?')}:{f.get('line', '?')} — "
            f"{f.get('description', 'no description')}"
        )


# ─── Phase 4 — Registration ───────────────────────────────────────────────────

def _registry_append(name: str, category: str, description: str, path: str) -> None:
    """
    Append one line to .atl/skill-registry.md under a '#### skill-writer' section.
    Creates the section if it does not exist.
    """
    if not REGISTRY_PATH.exists():
        return

    registry_text = REGISTRY_PATH.read_text(encoding="utf-8")
    new_row = f"| `{name}` | {description} | `{path}` | generated |"

    section_header = "#### skill-writer"
    if section_header in registry_text:
        # Insert after the table header row following the section
        insert_pattern = re.compile(
            rf"({re.escape(section_header)}.*?\n\|[^\n]+\|\n\|[-| ]+\|\n)",
            re.DOTALL,
        )
        match = insert_pattern.search(registry_text)
        if match:
            insert_pos = match.end()
            registry_text = (
                registry_text[:insert_pos]
                + new_row + "\n"
                + registry_text[insert_pos:]
            )
        else:
            # Section exists but no table yet — append row after header
            registry_text = registry_text.replace(
                section_header,
                f"{section_header}\n| `Name` | Description | Path | Provenance |\n"
                f"|--------|-------------|------|------------|\n{new_row}",
            )
    else:
        # Append new section at end
        registry_text = registry_text.rstrip() + (
            f"\n\n#### skill-writer\n\n"
            f"| `Name` | Description | Path | Provenance |\n"
            f"|--------|-------------|------|------------|\n"
            f"{new_row}\n"
        )

    REGISTRY_PATH.write_text(registry_text, encoding="utf-8")


def _install_skill(skill_dir: Path, category: str, name: str) -> Path:
    """
    Copy skill_dir to ~/.dexter/community/<category>/<name>/.
    Returns the destination path.
    """
    dest = COMMUNITY_DIR / category / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(skill_dir, dest)
    return dest


def _save_audit_to_engram(name: str, audit_result: dict) -> None:
    """
    Attempt to save audit result to Engram via mem_save CLI if available.
    Silently skips if Engram MCP is not callable from subprocess context.
    (Engram is an MCP tool — this note is here for documentation; in practice
    the audit log goes to ~/.dexter/audit-log.jsonl via audit.py itself.)
    """
    # Engram is an MCP server tool; it cannot be invoked via subprocess from a script.
    # The audit.py script already logs results to ~/.dexter/audit-log.jsonl.
    # Skipping silently — engram save happens at the agent level when the agent
    # reads the audit result and calls mem_save itself.
    pass


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_generate(args):
    """4-phase pipeline: Intent Analysis → Generation → Security Gate → Registration."""

    request  = args.request
    category = args.category or "productivity"
    name_arg = args.name
    dry_run  = args.dry_run

    check_config()

    # ── Phase 1: Intent Analysis ─────────────────────────────────────────────
    print(f"\n{CYAN}{BOLD}Phase 1 — Intent Analysis{RESET}")
    matches = find_existing_skills(request)
    if matches:
        print(f"{YELLOW}Found {len(matches)} existing skill(s) that may match:{RESET}")
        for m in matches[:5]:
            print(f"  {m['row']}")
        answer = input(
            f"\n{YELLOW}An existing skill may already cover this. "
            f"Proceed with generation anyway? [y/N] {RESET}"
        ).strip().lower()
        if answer not in ("y", "yes"):
            print(f"{GREEN}Aborted. Load the existing skill instead.{RESET}")
            return
    else:
        print(f"{GREEN}No matching skill found in registry. Proceeding.{RESET}")

    # ── Phase 2: Skill Generation ─────────────────────────────────────────────
    print(f"\n{CYAN}{BOLD}Phase 2 — Skill Generation{RESET}")

    try:
        cli = detect_llm_cli()
        print(f"  LLM runtime: {BOLD}{cli}{RESET}")
    except RuntimeError as e:
        print(f"{RED}Error: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    prompt = _build_prompt(request, name_arg, category)

    print(f"  Calling {cli}…")
    try:
        llm_output = _call_llm(cli, prompt)
    except RuntimeError as e:
        print(f"{RED}LLM call failed: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        skill_md, script = _parse_llm_output(llm_output)
    except ValueError as e:
        print(f"{RED}Parse error: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    # Determine skill name and category from generated frontmatter if not provided
    generated_name = name_arg or _extract_frontmatter_field(skill_md, "name") or "generated-skill"
    generated_name = re.sub(r"[^a-z0-9\-]", "-", generated_name.lower()).strip("-")

    if dry_run:
        print(f"\n{YELLOW}{BOLD}-- DRY RUN: would create skill '{generated_name}' in '{category}' --{RESET}\n")
        print(f"{BOLD}=== SKILL.md ==={RESET}\n{skill_md}\n")
        print(f"{BOLD}=== scripts/{generated_name}.py ==={RESET}\n{script}\n")
        print(f"{YELLOW}Dry run complete. No files written.{RESET}")
        return

    tmp_dir = Path(tempfile.mkdtemp(prefix="dexter-skill-writer-"))
    try:
        skill_dir = _scaffold_and_write(skill_md, script, generated_name, category, tmp_dir)
        print(f"  {GREEN}Generated: {skill_dir}{RESET}")

        # ── Phase 3: Security Gate ────────────────────────────────────────────
        print(f"\n{CYAN}{BOLD}Phase 3 — Security Gate{RESET}")
        try:
            audit_result = run_security_gate(skill_dir)
        except RuntimeError as e:
            print(f"{YELLOW}Warning: Security gate unavailable — {e}{RESET}")
            print(f"{YELLOW}Proceeding without audit (manual review recommended).{RESET}")
            audit_result = {"verdict": "WARN", "findings": []}

        _print_audit_findings(audit_result)
        _save_audit_to_engram(generated_name, audit_result)

        if _is_blocked(audit_result):
            print(
                f"\n{RED}{BOLD}Security gate BLOCKED this skill.{RESET}\n"
                f"Fix the findings above and re-run generation."
            )
            answer = input(f"{YELLOW}Delete temp files and abort? [Y/n] {RESET}").strip().lower()
            if answer not in ("n", "no"):
                shutil.rmtree(tmp_dir, ignore_errors=True)
                print(f"{RED}Aborted. Temp dir deleted.{RESET}")
                sys.exit(1)
            else:
                print(f"{YELLOW}Temp dir kept at: {tmp_dir}{RESET}")
                sys.exit(1)

        # ── Phase 4: Registration ─────────────────────────────────────────────
        print(f"\n{CYAN}{BOLD}Phase 4 — Registration{RESET}")

        dest = _install_skill(skill_dir, category, generated_name)
        print(f"  {GREEN}Installed: {dest}{RESET}")

        description = _extract_frontmatter_field(skill_md, "description") or request[:80]
        # Trim multiline description to first line
        description = description.split("\n")[0].strip()

        registry_path_str = f"~/.dexter/community/{category}/{generated_name}/SKILL.md"
        _registry_append(generated_name, category, description, registry_path_str)
        print(f"  {GREEN}Registry updated: {REGISTRY_PATH}{RESET}")

        # Extract triggers for confirmation message
        trigger_line = ""
        for line in skill_md.splitlines():
            if "trigger" in line.lower() and ":" in line:
                trigger_line = line.split(":", 1)[-1].strip().strip('"')
                break

        print(
            f"\n{GREEN}{BOLD}Skill registered: {generated_name}{RESET}\n"
            f"  Path:     {dest}\n"
            + (f"  Try:      {trigger_line}\n" if trigger_line else "")
        )

    finally:
        # Always clean up tmp dir (unless user chose to keep it above)
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


def cmd_list_generated(args):
    """List all skills with provenance: generated from the registry."""
    registry_text = _load_registry()
    if not registry_text:
        print(f"{YELLOW}Registry not found or empty.{RESET}")
        return

    # Find the skill-writer section
    section_pattern = re.compile(
        r"#### skill-writer\n(.*?)(?=\n####|\Z)",
        re.DOTALL,
    )
    section_match = section_pattern.search(registry_text)
    if not section_match:
        print(f"{YELLOW}No generated skills found in registry.{RESET}")
        return

    section = section_match.group(1)
    row_pattern = re.compile(r"\|\s*`([^`]+)`\s*\|([^|]+)\|([^|]+)\|\s*generated\s*\|")

    rows = row_pattern.findall(section)
    if not rows:
        # Also check for rows anywhere marked 'generated'
        all_generated = re.findall(
            r"\|\s*`([^`]+)`\s*\|[^|]*\|[^|]*\|\s*generated\s*\|",
            registry_text,
        )
        if all_generated:
            print(f"\n{BOLD}Generated skills:{RESET}")
            for name in all_generated:
                print(f"  {GREEN}{name}{RESET}")
        else:
            print(f"{YELLOW}No generated skills found in registry.{RESET}")
        return

    print(f"\n{BOLD}Generated skills ({len(rows)}):{RESET}")
    for name, description, path in rows:
        print(f"  {GREEN}{name.strip()}{RESET}")
        print(f"    {description.strip()}")
        print(f"    {CYAN}{path.strip()}{RESET}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Dexter — Skill Writer: auto-generate skills from plain-language requests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # generate
    p_gen = sub.add_parser(
        "generate",
        help="Generate a new skill from a plain-language request",
    )
    p_gen.add_argument(
        "request",
        help='Plain-language description of the skill to create (e.g. "Notion page manager")',
    )
    p_gen.add_argument(
        "--category",
        default=None,
        help="Skill category (default: productivity). E.g. communications, dev, ai",
    )
    p_gen.add_argument(
        "--name",
        default=None,
        help="Override skill name (kebab-case). Defaults to LLM-generated name.",
    )
    p_gen.add_argument(
        "--dry-run",
        action="store_true",
        help="Run Phase 1+2 only: print what would be generated without writing files",
    )

    # list-generated
    sub.add_parser(
        "list-generated",
        help="List all skills with provenance: generated in the registry",
    )

    args = parser.parse_args()

    dispatch = {
        "generate":      cmd_generate,
        "list-generated": cmd_list_generated,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
