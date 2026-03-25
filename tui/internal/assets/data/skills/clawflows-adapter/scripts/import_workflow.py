#!/usr/bin/env python3
"""
Dexter ClawFlows Adapter — converts a ClawFlows WORKFLOW.md to Dexter SKILL.md format.

Usage:
  import_workflow.py <workflow.md>                          # print result to stdout
  import_workflow.py <workflow.md> --output <skill-dir>    # write to disk
  import_workflow.py <workflow.md> --dry-run               # show conversion without writing

ClawFlows input format (WORKFLOW.md frontmatter):
  name        — workflow slug
  emoji       — single emoji
  description — one-line summary
  author      — @github-handle
  schedule    — plain English: "9am", "9am, 1pm", "Monday 9am", "On-demand"

Dexter output format (SKILL.md):
  Standard Dexter frontmatter with metadata.source: clawflows + metadata.schedule preserved.
  Body is the original workflow steps — they are already agent instructions in Markdown.
"""

import sys
import argparse
import re
from pathlib import Path


# ─── Schedule parsing ─────────────────────────────────────────────────────────

# Maps plain-English ClawFlows schedule tokens to cron expressions.
# "On-demand" means no cron — manual trigger only.
_TIME_MAP = {
    "12am": "0 0", "1am": "0 1", "2am": "0 2", "3am": "0 3", "4am": "0 4",
    "5am": "0 5", "6am": "0 6", "7am": "0 7", "8am": "0 8", "9am": "0 9",
    "10am": "0 10", "11am": "0 11", "12pm": "0 12", "noon": "0 12",
    "1pm": "0 13", "2pm": "0 14", "3pm": "0 15", "4pm": "0 16",
    "5pm": "0 17", "6pm": "0 18", "7pm": "0 19", "8pm": "0 20",
    "9pm": "0 21", "10pm": "0 22", "11pm": "0 23",
    "morning": "0 7", "afternoon": "0 13", "evening": "0 18", "night": "0 21",
    "midnight": "0 0",
}
_DOW_MAP = {
    "sunday": "0", "monday": "1", "tuesday": "2", "wednesday": "3",
    "thursday": "4", "friday": "5", "saturday": "6",
    "sun": "0", "mon": "1", "tue": "2", "wed": "3",
    "thu": "4", "fri": "5", "sat": "6",
}


def schedule_to_cron(schedule: str) -> list[str]:
    """
    Convert a ClawFlows plain-English schedule to a list of cron expressions.
    Returns [] for "On-demand" or unrecognised schedules.

    Examples:
      "9am"             → ["0 9 * * *"]
      "9am, 1pm, 5pm"   → ["0 9 * * *", "0 13 * * *", "0 17 * * *"]
      "Monday 9am"      → ["0 9 * * 1"]
      "1st 9am"         → ["0 9 1 * *"]
      "every 2 hours"   → ["0 */2 * * *"]
      "hourly"          → ["0 * * * *"]
      "every 30 min"    → ["*/30 * * * *"]
      "On-demand"       → []
    """
    raw = schedule.strip()
    if not raw or raw.lower() in ("on-demand", "on demand", "manual"):
        return []

    # "every N hours"
    m = re.search(r"every\s+(\d+)\s+hours?", raw, re.I)
    if m:
        return [f"0 */{m.group(1)} * * *"]

    # "hourly"
    if re.search(r"\bhourly\b", raw, re.I):
        return ["0 * * * *"]

    # "every N min(utes)"
    m = re.search(r"every\s+(\d+)\s+min", raw, re.I)
    if m:
        return [f"*/{m.group(1)} * * * *"]

    # "every N hours" (alternate)
    m = re.search(r"every\s+(\d+)\s+hour", raw, re.I)
    if m:
        return [f"0 */{m.group(1)} * * *"]

    # "1st 9am" → day 1 of month
    m = re.search(r"\b1st\b", raw, re.I)
    if m:
        # find the time token
        for token, hm in _TIME_MAP.items():
            if re.search(rf"\b{re.escape(token)}\b", raw, re.I):
                return [f"{hm} 1 * *"]
        return ["0 9 1 * *"]  # fallback: 9am on 1st

    # "twice a day" → 9am + 6pm
    if re.search(r"twice\s+a\s+day", raw, re.I):
        return ["0 9 * * *", "0 18 * * *"]

    results = []
    # Split on commas for multi-time schedules: "9am, 1pm, 5pm"
    parts = [p.strip() for p in raw.split(",")]
    for part in parts:
        part_l = part.lower().strip()
        # "Monday 9am" or "Monday"
        dow_match = None
        for dow, dow_num in _DOW_MAP.items():
            if re.search(rf"\b{dow}\b", part_l):
                dow_match = dow_num
                part_l = re.sub(rf"\b{dow}\b", "", part_l).strip()
                break

        time_match = None
        # handle HH:MMam/pm style e.g. "5:14pm"
        hhmm = re.search(r"(\d{1,2}):(\d{2})(am|pm)?", part_l, re.I)
        if hhmm:
            h, m_val, meridiem = int(hhmm.group(1)), int(hhmm.group(2)), (hhmm.group(3) or "").lower()
            if meridiem == "pm" and h != 12:
                h += 12
            elif meridiem == "am" and h == 12:
                h = 0
            time_match = f"{m_val} {h}"
        else:
            for token, hm in _TIME_MAP.items():
                if re.search(rf"\b{re.escape(token)}\b", part_l, re.I):
                    time_match = hm
                    break

        if time_match:
            dow_field = f"* * {dow_match}" if dow_match else "* * *"
            results.append(f"{time_match} {dow_field}")
        elif dow_match:
            # Day only, no time → default 9am
            results.append(f"0 9 * * {dow_match}")

    return results


# ─── Frontmatter parsing ──────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Parse YAML-style frontmatter. Returns (fields, body).
    Only handles simple key: value pairs (no nested YAML needed for WORKFLOW.md).
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

    fields: dict = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        # Strip inline comments and surrounding quotes
        val = re.sub(r"\s+#.*$", "", val).strip()
        val = val.strip("\"'")
        if val:
            fields[key] = val

    body = "\n".join(lines[end + 1:]).strip()
    return fields, body


# ─── Skill reference mapping ──────────────────────────────────────────────────

# ClawFlows workflows reference "your **X skill**" (OpenClaw terminology).
# These map to Dexter bundle paths.
SKILL_REF_MAP = {
    "email skill":        "skills/productivity/gmail/",
    "calendar skill":     "skills/productivity/calendar/",
    "task manager skill": "skills/productivity/todoist/",
    "github skill":       "skills/productivity/github/",
    "slack skill":        "skills/communications/slack/",
    "discord skill":      "skills/communications/discord/",
    "telegram skill":     "skills/communications/telegram/",
    "whatsapp skill":     "skills/communications/whatsapp/",
    "obsidian skill":     "skills/knowledge/personal-kb/",
    "home assistant skill": "skills/domotics/home-assistant/",
    "tts skill":          "skills/productivity/elevenlabs/",
}


def build_skill_ref_note(body: str) -> str:
    """
    Scan the body for ClawFlows skill references and return a mapping note,
    or empty string if none found.
    """
    found = []
    body_l = body.lower()
    for ref, path in SKILL_REF_MAP.items():
        if ref in body_l:
            found.append(f"  - \"{ref}\" → `{path}`")
    if not found:
        return ""
    lines = ["## Dexter Skill Mapping", ""]
    lines.append("This workflow references OpenClaw skill names. Dexter equivalents:")
    lines.append("")
    lines.extend(found)
    lines.append("")
    return "\n".join(lines)


# ─── Conversion ───────────────────────────────────────────────────────────────

def convert(workflow_md: Path) -> tuple[str, list[str]]:
    """
    Convert a ClawFlows WORKFLOW.md to Dexter SKILL.md content.
    Returns (skill_md_content, cron_expressions).
    """
    text = workflow_md.read_text(encoding="utf-8")
    fields, body = parse_frontmatter(text)

    name = fields.get("name", workflow_md.parent.name)
    emoji = fields.get("emoji", "")
    description = fields.get("description", "")
    author = fields.get("author", "")
    schedule_raw = fields.get("schedule", "")

    crons = schedule_to_cron(schedule_raw)
    is_scheduled = bool(crons)
    is_on_demand = not is_scheduled

    # Build trigger line from description keywords
    trigger_words = re.findall(r"\b[a-z]{4,}\b", description.lower())
    trigger_words = list(dict.fromkeys(trigger_words))[:5]  # deduplicate, cap at 5
    trigger = name
    if trigger_words:
        trigger = f"{name}, " + ", ".join(trigger_words)

    # Full description with trigger
    desc_line = description
    if desc_line and not desc_line.endswith("."):
        desc_line += "."
    full_description = f"{emoji} {desc_line}".strip() if emoji else desc_line
    full_description += f"\n  Trigger: {trigger}"

    # Metadata block
    meta_lines = [
        "metadata:",
        "  author: dexter",
        "  version: \"1.0\"",
        "  source: clawflows",
    ]
    if author:
        meta_lines.append(f"  clawflows_author: \"{author}\"")
    if schedule_raw:
        meta_lines.append(f"  schedule: \"{schedule_raw}\"")
    if crons:
        meta_lines.append("  cron:")
        for c in crons:
            meta_lines.append(f"    - \"{c}\"")

    # Frontmatter
    fm = "\n".join([
        "---",
        f"name: {name}",
        f"description: >",
        f"  {full_description}",
        "license: MIT",
        *meta_lines,
        "allowed-tools: Read, Bash",
        "---",
    ])

    # Skill reference mapping note
    ref_note = build_skill_ref_note(body)

    # Schedule notice
    if is_scheduled:
        schedule_note = (
            f"## Schedule\n\n"
            f"ClawFlows schedule: `{schedule_raw}`\n\n"
            f"Cron equivalents:\n"
            + "\n".join(f"- `{c}`" for c in crons)
            + "\n\nTo activate, register with the **cron-tasks** skill:\n"
            "```bash\n"
            "python3 skills/productivity/cron/scripts/cron_manager.py add "
            f"--name {name} --cron \"{crons[0]}\" "
            f"--cmd \"# run workflow: {name}\"\n"
            "```\n"
        )
    else:
        schedule_note = "## Schedule\n\nOn-demand — no automatic schedule. Run manually when needed.\n"

    # Assemble final SKILL.md
    parts = [fm, ""]
    if ref_note:
        parts.append(ref_note)
    parts.append(schedule_note)
    parts.append("---")
    parts.append("")
    parts.append(body)
    parts.append("")

    return "\n".join(parts), crons


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert a ClawFlows WORKFLOW.md to a Dexter SKILL.md"
    )
    parser.add_argument("workflow", help="Path to ClawFlows WORKFLOW.md")
    parser.add_argument(
        "--output", "-o",
        help="Output directory for generated SKILL.md (default: stdout)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print result without writing to disk",
    )
    args = parser.parse_args()

    workflow_path = Path(args.workflow).resolve()
    if not workflow_path.exists():
        print(f"Error: {workflow_path} not found", file=sys.stderr)
        sys.exit(1)
    if workflow_path.is_dir():
        workflow_path = workflow_path / "WORKFLOW.md"
    if not workflow_path.exists():
        print(f"Error: no WORKFLOW.md found in {workflow_path.parent}", file=sys.stderr)
        sys.exit(1)

    skill_md, crons = convert(workflow_path)

    if args.output and not args.dry_run:
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "SKILL.md"
        out_file.write_text(skill_md, encoding="utf-8")
        print(f"Written: {out_file}")
        if crons:
            print(f"Schedule: {len(crons)} cron expression(s) — register with cron-tasks skill")
    else:
        print(skill_md)
        if crons and not args.dry_run:
            print(f"\n# Cron: {' | '.join(crons)}", file=sys.stderr)


if __name__ == "__main__":
    main()
