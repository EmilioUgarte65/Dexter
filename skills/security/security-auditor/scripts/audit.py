#!/usr/bin/env python3
"""
Dexter Security Auditor — Pre-execution skill scanner with auto-fix.

Modes:
  audit.py <skill-dir>           — scan only, report findings
  audit.py <skill-dir> --fix     — scan + auto-sanitize + ask user if intent unclear
  audit.py <skill-dir> --json    — scan, output JSON (for programmatic use)

Audit is ONE-TIME:
  - Skills with source: dexter → trusted, not audited
  - External skills (clawhub, gentle-ai) → audited once on install
  - skill-writer output → audited once on generation
  - After PASS: audited: true is written to SKILL.md frontmatter
"""

import sys
import os
import re
import json
import shutil
import textwrap
import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional


# ─── Audit log ────────────────────────────────────────────────────────────────

def log_audit_result(filepath: str, verdict: str, findings: List) -> None:
    """
    Append an audit result to ~/.dexter/audit-log.jsonl (JSON Lines).
    Silences all errors — logging must never break the main flow.
    """
    try:
        log_dir = Path.home() / ".dexter"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "audit-log.jsonl"

        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "file": str(filepath),
            "verdict": verdict,
            "findings": [
                {
                    "severity": f.severity,
                    "file": f.file,
                    "line": f.line,
                    "description": f.description,
                }
                for f in findings
            ],
            "rules_triggered": list({f.pattern for f in findings}),
        }

        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Log failures are silently swallowed


# ─── Finding ──────────────────────────────────────────────────────────────────

@dataclass
class Finding:
    severity: str       # CRITICAL | HIGH | MEDIUM | LOW
    file: str
    line: int
    pattern: str
    description: str
    fix_strategy: str   # remove | sanitize | ask | flag


# ─── Detection patterns ───────────────────────────────────────────────────────
# (severity, regex, description, fix_strategy)

SCRIPT_PATTERNS: List[Tuple[str, str, str, str]] = [

    # CRITICAL — reverse shells and disk destruction (remove, no legitimate use)
    ("CRITICAL", r"bash\s+-i\s+>&\s+/dev/tcp/",
     "Reverse shell via /dev/tcp", "remove"),
    ("CRITICAL", r"/dev/tcp/\d+\.\d+",
     "TCP redirect — potential reverse shell", "remove"),
    ("CRITICAL", r"nc\s+-e\s+/bin/(sh|bash)",
     "Netcat reverse shell", "remove"),
    ("CRITICAL", r"rm\s+-rf\s+/[^/\w]",
     "Filesystem destruction (rm -rf /)", "remove"),
    ("CRITICAL", r"dd\s+if=/dev/zero\s+of=/dev/sd",
     "Disk wipe via dd", "remove"),
    ("CRITICAL", r"mkfs\s+/dev/",
     "Filesystem format", "remove"),

    # HIGH — exfiltration: intent may be legitimate but execution is dangerous
    # Pattern A: curl/wget with a query string to a non-local URL (data in URL).
    # Pattern B: curl/wget with data-sending flags (-d, -F, -T, etc.) and a non-local URL.
    # Simple GETs like `curl https://api.example.com/data` are NOT flagged.
    ("HIGH", r"(curl|wget)\b(?!.*https?://(localhost|127\.0\.0\.1|internal)[/:]).*https?://(?!(localhost|127\.0\.0\.1|internal)[/:\s])[^\s]*\?",
     "Data exfiltration via HTTP — query string sent to external URL", "ask"),
    ("HIGH", r"(curl|wget)\b(?=.*(-d|--data\b|--data-raw|--data-binary|--data-urlencode|-F\b|--form\b|-T\b|--upload-file))(?!.*https?://(localhost|127\.0\.0\.1|internal)[/:]).*https?://(?!(localhost|127\.0\.0\.1|internal)[/:\s])",
     "Data exfiltration via HTTP — data/upload flag sending to external URL", "ask"),
    ("HIGH", r"base64\s+(--decode|-d)\s*\|",
     "Base64 decode piped to shell", "ask"),
    ("HIGH", r"echo\s+[A-Za-z0-9+/]{20,}={0,2}\s*\|\s*(bash|sh|python|node)",
     "Possible base64 payload execution", "ask"),
    ("HIGH", r"eval\s+\"\$\(",
     "Shell eval with command substitution", "sanitize"),
    ("HIGH", r"sudo\s+(bash|sh|su\b|-i\b)",
     "Privilege escalation attempt", "remove"),

    # MEDIUM — risky but often legitimate: sanitize or flag
    ("MEDIUM", r"eval\s*\(",
     "Dynamic eval() — code injection risk", "sanitize"),
    ("MEDIUM", r"exec\s*\(\s*[^\"'a-zA-Z]",
     "exec() with variable input", "sanitize"),
    ("MEDIUM", r"subprocess\.(run|call|Popen)\s*\(.*shell\s*=\s*True",
     "subprocess shell=True — use list form instead", "sanitize"),
    ("MEDIUM", r"os\.system\s*\(",
     "os.system() — prefer subprocess.run()", "sanitize"),

    # LOW — informational
    ("LOW", r"#.*curl\s+https?://",
     "Commented-out curl (informational)", "flag"),
    ("LOW", r"#.*eval\(",
     "Commented-out eval (informational)", "flag"),
]

# Prompt injection: only in frontmatter (CRITICAL) or script files (HIGH)
PROMPT_INJECTION_FRONTMATTER = [
    (r"ignore\s+previous\s+instructions",             "Prompt injection in frontmatter", "remove"),
    (r"disregard\s+your\s+(system\s+prompt|instructions)", "Prompt injection in frontmatter", "remove"),
    (r"forget\s+your\s+(previous\s+)?instructions",   "Prompt injection in frontmatter", "remove"),
    (r"you\s+are\s+now\s+a\s+different\s+(ai|model)", "Identity override in frontmatter", "remove"),
    (r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions", "Restriction bypass in frontmatter", "remove"),
    (r"DAN\s+mode",                                   "DAN jailbreak in frontmatter", "remove"),
    (r"jailbreak",                                    "Jailbreak keyword in frontmatter", "remove"),
]

PROMPT_INJECTION_SCRIPTS = [
    (r"ignore\s+previous\s+instructions",             "AI override command in script", "remove"),
    (r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions", "Restriction bypass in script", "remove"),
    (r"DAN\s+mode",                                   "DAN jailbreak in script", "remove"),
]


# ─── Sanitization strategies ──────────────────────────────────────────────────

def sanitize_line(line: str, finding: Finding) -> Optional[str]:
    """
    Given a line and its finding, return a sanitized replacement.
    Returns None if the line should be removed entirely.
    Returns the original line (unchanged) if no auto-fix applies.
    """
    strategy = finding.fix_strategy

    if strategy == "remove":
        return None  # Delete the line

    if strategy == "sanitize":
        # subprocess shell=True → list form
        if "shell=True" in line:
            sanitized = re.sub(r",?\s*shell\s*=\s*True", "", line)
            comment = "  # dexter-fix: removed shell=True — use list args to avoid injection"
            return sanitized.rstrip() + comment

        # eval( → raise NotImplementedError
        if re.search(r"\beval\s*\(", line):
            indent = len(line) - len(line.lstrip())
            return " " * indent + "raise NotImplementedError('eval() removed by Dexter security-auditor — rewrite with explicit logic')  # dexter-fix"

        # os.system( → subprocess.run()
        if "os.system(" in line:
            sanitized = line.replace("os.system(", "subprocess.run(")
            return sanitized.rstrip() + "  # dexter-fix: replaced os.system with subprocess.run"

        # Shell eval "$(...)" → log warning
        if re.search(r'eval\s+"\$\(', line):
            indent = len(line) - len(line.lstrip())
            return " " * indent + "# dexter-fix: eval \"$(...)\" removed — use explicit variable assignment instead"

    if strategy == "flag":
        return line + "  # dexter-audit: reviewed"

    return line  # ask strategy — handled interactively, return unchanged for now


def reverse_engineer_intent(filepath: Path, line: str, finding: Finding) -> str:
    """
    Analyze the context around a suspicious line to infer intent.
    Returns a human-readable description of what the code is trying to do.
    """
    try:
        lines = filepath.read_text().splitlines()
        lineno = finding.line - 1
        ctx_start = max(0, lineno - 3)
        ctx_end = min(len(lines), lineno + 4)
        context = "\n".join(f"  {i+1}: {l}" for i, l in enumerate(lines[ctx_start:ctx_end], ctx_start))
    except Exception:
        context = f"  {finding.line}: {line}"

    # Infer intent from patterns
    if "base64" in line.lower():
        return f"Encodes/decodes data in base64 — may be obfuscating a payload or handling binary data.\nContext:\n{context}"
    if "curl" in line.lower() or "wget" in line.lower():
        url_match = re.search(r"https?://[^\s\"']+", line)
        url = url_match.group(0) if url_match else "unknown URL"
        return f"Makes an HTTP request to: {url}\nContext:\n{context}"
    if "eval" in line.lower():
        return f"Dynamically evaluates code at runtime.\nContext:\n{context}"

    return f"Suspicious pattern: {finding.description}\nContext:\n{context}"


# ─── Frontmatter helpers ──────────────────────────────────────────────────────

def split_frontmatter(text: str) -> Tuple[str, str, str]:
    """Returns (before_fm, fm_content, body). before_fm is '' for normal files."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", "", text

    end = -1
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end = i
            break

    if end == -1:
        return "", "", text

    fm = "".join(lines[1:end])
    body = "".join(lines[end + 1:])
    return "---\n", fm, body


def set_audited_flag(skill_md_path: Path):
    """Add audited: true to SKILL.md frontmatter if not already present."""
    text = skill_md_path.read_text(encoding="utf-8")
    _, fm, body = split_frontmatter(text)

    if "audited:" in fm:
        fm = re.sub(r"audited:\s*(true|false)", "audited: true", fm)
    else:
        # Insert after source: line, or before last field
        if "source:" in fm:
            fm = re.sub(r"(source:.*\n)", r"\1  audited: true\n", fm, count=1)
        else:
            fm = fm.rstrip() + "\n  audited: true\n"

    skill_md_path.write_text(f"---\n{fm}---\n{body}", encoding="utf-8")


def get_frontmatter_lines(text: str) -> List[Tuple[int, str]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    result = []
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            break
        result.append((i + 1, line))
    return result


def get_body_lines(text: str) -> List[Tuple[int, str]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return list(enumerate(lines, 1))
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return [(j + 1, lines[j]) for j in range(i + 1, len(lines))]
    return []


# ─── Scanner ──────────────────────────────────────────────────────────────────

def scan_file(filepath: Path) -> List[Finding]:
    findings = []
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [Finding("LOW", str(filepath), 0, "read_error", f"Could not read: {e}", "flag")]

    lines = text.splitlines()

    if filepath.name == "SKILL.md":
        # Frontmatter: CRITICAL prompt injection only
        for lineno, line in get_frontmatter_lines(text):
            for pattern, description, fix in PROMPT_INJECTION_FRONTMATTER:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(Finding("CRITICAL", str(filepath), lineno, pattern, description, fix))

        # Body: only genuinely dangerous executable patterns (not behavioral language)
        for lineno, line in get_body_lines(text):
            if not line.strip():
                continue
            for severity, pattern, description, fix in SCRIPT_PATTERNS:
                if severity in ("CRITICAL", "HIGH") and re.search(pattern, line, re.IGNORECASE):
                    findings.append(Finding(severity, str(filepath), lineno, pattern, description, fix))
                    break
        return findings

    # Non-SKILL.md markdown: skip
    if filepath.suffix == ".md":
        return findings

    # Executable scripts
    for i, line in enumerate(lines, 1):
        # Prompt injection in scripts
        for pattern, description, fix in PROMPT_INJECTION_SCRIPTS:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(Finding("HIGH", str(filepath), i, pattern, description, fix))
                break

        # All script patterns
        for severity, pattern, description, fix in SCRIPT_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(Finding(severity, str(filepath), i, pattern, description, fix))
                break

    return findings


def scan_skill_dir(skill_dir: Path) -> List[Finding]:
    findings = []
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        findings.extend(scan_file(skill_md))
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists():
        for script in sorted(scripts_dir.iterdir()):
            if script.is_file() and script.suffix in (".py", ".sh", ".js", ".ts", ".rb"):
                findings.extend(scan_file(script))
    return findings


def severity_rank(s: str) -> int:
    return {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(s, 0)


def overall_result(findings: List[Finding]) -> str:
    if not findings:
        return "PASS"
    top = max(findings, key=lambda f: severity_rank(f.severity)).severity
    if top in ("CRITICAL", "HIGH"):
        return "BLOCK"
    if top == "MEDIUM":
        return "WARN"
    return "PASS"


# ─── Auto-fix engine ──────────────────────────────────────────────────────────

def fix_skill(skill_dir: Path, interactive: bool = True) -> bool:
    """
    Analyze findings, auto-sanitize what can be fixed, ask user for ambiguous cases.
    Returns True if skill is now safe (PASS/WARN), False if unfixable issues remain.
    """
    findings = scan_skill_dir(skill_dir)
    if not findings:
        print(f"  [PASS] No issues — nothing to fix")
        set_audited_flag(skill_dir / "SKILL.md")
        return True

    # Group findings by file
    by_file: dict[str, List[Finding]] = {}
    for f in findings:
        by_file.setdefault(f.file, []).append(f)

    all_fixed = True

    for filepath_str, file_findings in by_file.items():
        filepath = Path(filepath_str)

        print(f"\n  [FIX] Analyzing: {filepath.name}")
        print(f"  Found {len(file_findings)} issue(s):")
        for f in file_findings:
            print(f"    [{f.severity}] line {f.line}: {f.description}")

        # Backup original
        backup = filepath.with_suffix(filepath.suffix + ".pre-fix")
        if not backup.exists():
            shutil.copy2(filepath, backup)
            print(f"  Backed up to: {backup.name}")

        # Read lines
        lines = filepath.read_text(encoding="utf-8").splitlines(keepends=True)
        # Map line numbers to findings
        line_findings: dict[int, Finding] = {f.line: f for f in file_findings}

        new_lines = []
        for i, line in enumerate(lines, 1):
            finding = line_findings.get(i)
            if not finding:
                new_lines.append(line)
                continue

            strategy = finding.fix_strategy

            if strategy == "ask" and interactive:
                # Reverse engineer and ask user
                intent = reverse_engineer_intent(filepath, line.rstrip(), finding)
                print(f"\n  [VULNERABILITY] {finding.description}")
                print(f"  Line {i}: {line.rstrip()}")
                print(f"\n  Reverse engineering intent:")
                for l in intent.split("\n"):
                    print(f"    {l}")
                print(f"\n  Options:")
                print(f"    [k] Keep line as-is (I know it's safe)")
                print(f"    [r] Remove line entirely")
                print(f"    [e] Explain what this should do — I'll rewrite it safely")
                print(f"    [s] Skip (mark as unresolved)")

                choice = input("  Choice [k/r/e/s]: ").strip().lower()

                if choice == "r":
                    print(f"  Removed line {i}")
                    continue  # skip adding line
                elif choice == "k":
                    new_lines.append(line)
                    print(f"  Kept (user confirmed safe)")
                elif choice == "e":
                    explanation = input("  Describe what this should do: ").strip()
                    rewritten = f"# TODO: rewrite safely — original intent: {explanation}\n# dexter-fix: original line removed\n"
                    new_lines.append(rewritten)
                    print(f"  Replaced with TODO comment — you can now implement it safely")
                else:
                    new_lines.append(line)
                    all_fixed = False
                    print(f"  Skipped — issue remains unresolved")

            elif strategy == "remove":
                print(f"  Removed line {i} (no legitimate use for: {finding.description})")
                # Skip adding — effectively removes the line

            elif strategy in ("sanitize", "flag"):
                fixed = sanitize_line(line.rstrip(), finding)
                if fixed is None:
                    print(f"  Removed line {i}: {finding.description}")
                else:
                    new_lines.append(fixed + "\n")
                    print(f"  Sanitized line {i}: {finding.description}")

            else:
                # ask strategy but non-interactive — flag it
                new_lines.append(line.rstrip() + "  # dexter-audit: REVIEW THIS LINE\n")
                all_fixed = False

        # Write sanitized file
        filepath.write_text("".join(new_lines), encoding="utf-8")
        print(f"  Written: {filepath.name}")

    # Re-scan to confirm
    print(f"\n  Re-scanning after fixes...")
    remaining = scan_skill_dir(skill_dir)
    final_result = overall_result(remaining)
    print(f"  Result: {final_result}")

    if remaining:
        blocking = [f for f in remaining if severity_rank(f.severity) >= 3]
        if blocking:
            print(f"  Still has {len(blocking)} unresolved HIGH/CRITICAL issue(s):")
            for f in blocking:
                print(f"    [{f.severity}] {Path(f.file).name}:{f.line} — {f.description}")
            all_fixed = False

    if all_fixed and final_result in ("PASS", "WARN"):
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            set_audited_flag(skill_md)
            print(f"  Marked as audited: true in SKILL.md")

    log_audit_result(str(skill_dir), final_result, remaining)
    return all_fixed


# ─── Output helpers ───────────────────────────────────────────────────────────

C = {
    "CRITICAL": "\033[91m", "HIGH": "\033[91m",
    "MEDIUM": "\033[93m",   "LOW": "\033[94m",
    "PASS": "\033[92m",     "BLOCK": "\033[91m",
    "WARN": "\033[93m",     "RESET": "\033[0m",
}

def col(text: str, key: str) -> str:
    return f"{C.get(key,'')}{text}{C['RESET']}" if sys.stdout.isatty() else text


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Dexter Security Auditor")
    parser.add_argument("skill_dir", help="Path to skill directory")
    parser.add_argument("--fix", action="store_true",
                        help="Auto-fix vulnerabilities, ask user for ambiguous cases")
    parser.add_argument("--fix-silent", action="store_true",
                        help="Auto-fix without interaction (non-interactive CI mode)")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON (for programmatic use)")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    if not skill_dir.is_dir():
        print(f"Error: {skill_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    skill_name = skill_dir.name

    # Check if already audited (skip for external/community skills that haven't been)
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        if "audited: true" in text and not args.fix:
            if args.json:
                print(json.dumps({"skill": skill_name, "result": "PASS", "findings": [], "note": "already audited"}))
            else:
                print(f"\n{col('[PASS]', 'PASS')}  {skill_name} — already audited\n")
            sys.exit(0)

    if args.fix or args.fix_silent:
        print(f"\n{col('[FIX MODE]', 'WARN')}  Analyzing and sanitizing: {skill_name}")
        interactive = not args.fix_silent
        success = fix_skill(skill_dir, interactive=interactive)
        sys.exit(0 if success else 1)

    # Scan-only mode
    findings = scan_skill_dir(skill_dir)
    result = overall_result(findings)
    log_audit_result(str(skill_dir), result, findings)

    if args.json:
        print(json.dumps({
            "skill": skill_name,
            "result": result,
            "findings": [
                {"severity": f.severity, "file": f.file, "line": f.line,
                 "description": f.description, "fix_strategy": f.fix_strategy}
                for f in findings
            ]
        }, indent=2))
        sys.exit(0 if result in ("PASS", "WARN") else 1)

    # Human output
    print(f"\n{col(f'[{result}]', result)}  Security audit: {col(skill_name, 'RESET')}")

    if not findings:
        print(f"  {col('✓ No issues found', 'PASS')}")
        set_audited_flag(skill_md)
    else:
        findings.sort(key=lambda f: severity_rank(f.severity), reverse=True)
        for f in findings:
            loc = f"{Path(f.file).name}:{f.line}"
            fix_hint = f" [fix: {f.fix_strategy}]" if f.fix_strategy != "flag" else ""
            print(f"  {col(f'[{f.severity}]', f.severity)}  {loc} — {f.description}{fix_hint}")

        if result == "BLOCK":
            print(f"\n  {col('Run with --fix to auto-sanitize', 'WARN')}")

    print()
    sys.exit(0 if result in ("PASS", "WARN") else 1)


if __name__ == "__main__":
    main()
