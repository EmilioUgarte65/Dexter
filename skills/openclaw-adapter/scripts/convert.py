#!/usr/bin/env python3
"""
Dexter OpenClaw/ClawHub Adapter — converts ClawHub skill format to Dexter format.
Usage: python3 convert.py <skill-dir> [--dry-run] [--skip-audit]

ClawHub input format:
  SKILL.md           — frontmatter with inline JSON metadata field
  _meta.json         — {"ownerId", "slug", "version", "publishedAt"}
  .clawhub/origin.json — {"version", "registry", "slug", "installedVersion", "installedAt"}

Dexter output format:
  SKILL.md           — converted with proper YAML frontmatter
  SKILL.md.clawhub-original  — backup of original
"""

import sys
import os
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional


# ─── Frontmatter parsing ──────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Parse YAML-ish frontmatter from markdown.
    Returns (fields_dict, body_text).
    Handles ClawHub's inline JSON metadata field.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    end = -1
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end = i
            break

    if end == -1:
        return {}, text

    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1:]).strip()

    fields = {}
    for line in fm_lines:
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val:
            fields[key] = val

    return fields, body


def parse_clawbot_metadata(metadata_str: str) -> Optional[dict]:
    """Parse the inline JSON metadata field from ClawHub SKILL.md."""
    if not metadata_str:
        return None
    try:
        data = json.loads(metadata_str)
        return data.get("clawdbot", data)
    except json.JSONDecodeError:
        return None


# ─── Binary checker ───────────────────────────────────────────────────────────

def check_bins(required_bins: list) -> tuple[list, list]:
    """Returns (installed, missing) lists."""
    installed = []
    missing = []
    for b in required_bins:
        if shutil.which(b):
            installed.append(b)
        else:
            missing.append(b)
    return installed, missing


def format_install_instructions(install_entries: list) -> list:
    """Format install instructions from clawdbot.install array."""
    instructions = []
    for entry in install_entries:
        kind = entry.get("kind", "")
        module = entry.get("module", "")
        label = entry.get("label", f"Install via {kind}")
        bins = entry.get("bins", [])

        if kind == "go":
            cmd = f"go install {module}"
        elif kind == "npm":
            cmd = f"npm install -g {module}"
        elif kind == "brew":
            cmd = f"brew install {module}"
        elif kind == "pip":
            cmd = f"pip3 install {module}"
        else:
            cmd = f"# {label}"

        instructions.append({"label": label, "command": cmd, "bins": bins})

    return instructions


# ─── Trigger keyword derivation ───────────────────────────────────────────────

def derive_trigger_keywords(name: str, description: str) -> str:
    """Derive trigger keywords from skill name and description."""
    keywords = [name]
    # Add meaningful words from description (filter stopwords)
    stopwords = {"a", "an", "the", "and", "or", "to", "of", "for", "in", "on", "with",
                 "via", "is", "it", "this", "that", "control", "use", "using"}
    desc_words = re.findall(r"\b[a-zA-Z]{3,}\b", description.lower())
    for w in desc_words:
        if w not in stopwords and w not in keywords and len(keywords) < 6:
            keywords.append(w)
    return ", ".join(keywords)


# ─── Dexter frontmatter builder ───────────────────────────────────────────────

def build_dexter_frontmatter(
    name: str,
    description: str,
    clawdbot: dict,
    meta: dict,
    origin: dict,
) -> str:
    version = meta.get("version", "1.0.0")
    slug = origin.get("slug", name)
    registry = origin.get("registry", "https://clawhub.ai")
    installed_version = origin.get("installedVersion", version)

    trigger_keywords = derive_trigger_keywords(name, description)

    # Build clawdbot YAML block
    required_bins = clawdbot.get("requires", {}).get("bins", [])
    install_entries = clawdbot.get("install", [])

    bins_yaml = ""
    if required_bins:
        bins_list = "\n".join(f'      - "{b}"' for b in required_bins)
        bins_yaml = f"    requires:\n      bins:\n{bins_list}"

    install_yaml = ""
    if install_entries:
        items = []
        for entry in install_entries:
            item_lines = [f'      - id: {entry.get("id", "unknown")}']
            item_lines.append(f'        kind: {entry.get("kind", "unknown")}')
            if "module" in entry:
                item_lines.append(f'        module: {entry["module"]}')
            if "bins" in entry:
                bin_list = ", ".join(f'"{b}"' for b in entry["bins"])
                item_lines.append(f"        bins: [{bin_list}]")
            if "label" in entry:
                item_lines.append(f'        label: "{entry["label"]}"')
            items.append("\n".join(item_lines))
        install_yaml = f"    install:\n" + "\n".join(items)

    clawdbot_yaml_parts = []
    if bins_yaml:
        clawdbot_yaml_parts.append(bins_yaml)
    if install_yaml:
        clawdbot_yaml_parts.append(install_yaml)
    clawdbot_yaml = "\n".join(clawdbot_yaml_parts)

    fm = f"""---
name: {name}
description: >
  {description}
  Trigger: {trigger_keywords}
license: Apache-2.0
metadata:
  author: dexter
  version: "{version}"
  source: clawhub
  clawhub:
    registry: {registry}
    slug: {slug}
    installedVersion: {installed_version}
  clawdbot:
{clawdbot_yaml}
allowed-tools: Bash, Read
---"""

    return fm


# ─── Security audit runner ────────────────────────────────────────────────────

def run_security_audit(skill_dir: Path) -> tuple[str, str]:
    """
    Run security-auditor on the skill directory.
    Returns (result, output) where result is PASS/WARN/BLOCK.
    """
    # Find audit.py relative to this script or from known Dexter paths
    candidates = [
        Path(__file__).parent.parent.parent / "security" / "security-auditor" / "scripts" / "audit.py",
        Path.home() / ".claude" / "skills" / "security" / "security-auditor" / "scripts" / "audit.py",
        Path.home() / "proyectos" / "Dexter" / "skills" / "security" / "security-auditor" / "scripts" / "audit.py",
    ]

    audit_script = None
    for c in candidates:
        if c.exists():
            audit_script = c
            break

    if not audit_script:
        return "WARN", "security-auditor not found — skipping audit (install Dexter first)"

    try:
        result = subprocess.run(
            [sys.executable, str(audit_script), str(skill_dir), "--json"],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        try:
            data = json.loads(output)
            return data.get("result", "WARN"), output
        except json.JSONDecodeError:
            return "WARN", output or result.stderr
    except subprocess.TimeoutExpired:
        return "WARN", "Audit timed out"
    except Exception as e:
        return "WARN", f"Audit error: {e}"


# ─── Main converter ───────────────────────────────────────────────────────────

def convert_skill(skill_dir: Path, dry_run: bool = False, skip_audit: bool = False) -> bool:
    """
    Convert a ClawHub skill to Dexter format.
    Returns True on success, False on BLOCK.
    """
    print(f"\n[Dexter] Converting: {skill_dir.name}")

    # 1. Read input files
    skill_md_path = skill_dir / "SKILL.md"
    meta_path = skill_dir / "_meta.json"
    origin_path = skill_dir / ".clawhub" / "origin.json"

    if not skill_md_path.exists():
        print(f"  [ERROR] SKILL.md not found in {skill_dir}")
        return False

    skill_md_text = skill_md_path.read_text(encoding="utf-8")
    fm_fields, body = parse_frontmatter(skill_md_text)

    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except json.JSONDecodeError:
            print(f"  [WARN] Could not parse _meta.json")

    origin = {}
    if origin_path.exists():
        try:
            origin = json.loads(origin_path.read_text())
        except json.JSONDecodeError:
            print(f"  [WARN] Could not parse .clawhub/origin.json")

    # 2. Parse clawdbot metadata
    metadata_str = fm_fields.get("metadata", "")
    clawdbot = parse_clawbot_metadata(metadata_str) or {}

    name = fm_fields.get("name", skill_dir.name)
    description = fm_fields.get("description", "No description provided.")

    # 3. Check required bins
    required_bins = clawdbot.get("requires", {}).get("bins", [])
    if required_bins:
        installed, missing = check_bins(required_bins)
        if installed:
            print(f"  [PASS] Required binaries found: {', '.join(installed)}")
        if missing:
            install_entries = clawdbot.get("install", [])
            instructions = format_install_instructions(install_entries)
            print(f"  [WARN] Missing binaries: {', '.join(missing)}")
            for inst in instructions:
                print(f"  Install: {inst['label']}")
                print(f"    $ {inst['command']}")

    # 4. Run security audit (on original files)
    if not skip_audit:
        print(f"  Running security-auditor...")
        audit_result, audit_output = run_security_audit(skill_dir)
        print(f"  Audit result: {audit_result}")

        if audit_result == "BLOCK":
            print(f"  [BLOCK] Skill rejected by security-auditor. Original files preserved.")
            try:
                data = json.loads(audit_output)
                for finding in data.get("findings", []):
                    if finding.get("severity") in ("CRITICAL", "HIGH"):
                        print(f"    [{finding['severity']}] {finding['description']} ({Path(finding['file']).name}:{finding['line']})")
            except Exception:
                print(f"  Details: {audit_output}")
            return False
    else:
        print(f"  [SKIP] Security audit skipped (--skip-audit)")

    # 5. Build Dexter frontmatter
    new_fm = build_dexter_frontmatter(name, description, clawdbot, meta, origin)
    new_content = f"{new_fm}\n\n{body}\n"

    if dry_run:
        print(f"\n  [DRY-RUN] Would write converted SKILL.md:")
        print("  " + "\n  ".join(new_content.split("\n")[:20]))
        print(f"\n  [DRY-RUN] Would backup original to SKILL.md.clawhub-original")
        return True

    # 6. Backup original + write converted
    backup_path = skill_dir / "SKILL.md.clawhub-original"
    if not backup_path.exists():
        shutil.copy2(skill_md_path, backup_path)
        print(f"  Backed up original to SKILL.md.clawhub-original")

    skill_md_path.write_text(new_content, encoding="utf-8")
    print(f"  [PASS] Converted SKILL.md written")
    print(f"  Skill '{name}' is ready to use in Dexter.")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Dexter OpenClaw/ClawHub Adapter")
    parser.add_argument("skill_dir", help="Path to installed ClawHub skill directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview conversion without writing files")
    parser.add_argument("--skip-audit", action="store_true", help="Skip security audit (not recommended)")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    if not skill_dir.is_dir():
        print(f"Error: {skill_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    success = convert_skill(skill_dir, dry_run=args.dry_run, skip_audit=args.skip_audit)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
