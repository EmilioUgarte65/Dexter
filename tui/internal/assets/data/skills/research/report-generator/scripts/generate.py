#!/usr/bin/env python3
"""
Dexter — Structured report generator.
Pure stdlib. Outputs markdown, HTML, or PDF (weasyprint if available).

Usage:
  generate.py new <title> [--template research|summary|comparison|incident] [--output file.md]
  generate.py from-data <json_file> [--template TEMPLATE] [--output file.md]
  generate.py section add <report_file> <section_title> <content>
  generate.py finalize <report_file> [--format md|html|pdf]
"""

import sys
import os
import json
import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── ANSI colors ──────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

# ─── Templates ────────────────────────────────────────────────────────────────

TEMPLATES = {
    "research": {
        "sections": [
            "Executive Summary",
            "Findings",
            "Analysis",
            "Recommendations",
            "Sources",
        ],
        "description": "Research report with findings and recommendations",
    },
    "summary": {
        "sections": [
            "TL;DR",
            "Key Points",
            "Details",
        ],
        "description": "Concise summary format",
    },
    "comparison": {
        "sections": [
            "Overview",
            "Options",
            "Pros and Cons",
            "Verdict",
        ],
        "description": "Comparison report with pros/cons table",
    },
    "incident": {
        "sections": [
            "Timeline",
            "Impact",
            "Root Cause",
            "Mitigation",
            "Prevention",
        ],
        "description": "Incident post-mortem report",
    },
}


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


# ─── Report generation ────────────────────────────────────────────────────────

def _build_report_md(title: str, template_name: str, data: dict = None) -> str:
    template = TEMPLATES[template_name]
    lines    = []

    lines.append(f"# {title}")
    lines.append(f"")
    lines.append(f"**Template**: {template_name}  ")
    lines.append(f"**Date**: {_today()}  ")
    lines.append(f"**Generated**: {_now()}  ")
    lines.append(f"")
    lines.append("---")
    lines.append("")

    for section in template["sections"]:
        lines.append(f"## {section}")
        lines.append("")

        # If data provided, look for matching key
        if data:
            key_candidates = [
                section,
                section.lower(),
                section.lower().replace(" ", "_"),
                section.lower().replace(" ", "-"),
                _slugify(section),
            ]
            for k in key_candidates:
                if k in data:
                    content = data[k]
                    if isinstance(content, list):
                        for item in content:
                            lines.append(f"- {item}")
                    elif isinstance(content, dict):
                        for ck, cv in content.items():
                            lines.append(f"**{ck}**: {cv}  ")
                    else:
                        lines.append(str(content))
                    break
            else:
                lines.append(f"_{section} content here._")
        else:
            if template_name == "comparison" and section == "Pros and Cons":
                lines.append("| Option | Pros | Cons |")
                lines.append("|--------|------|------|")
                lines.append("| Option A | + Pro 1 | - Con 1 |")
                lines.append("| Option B | + Pro 1 | - Con 1 |")
            elif template_name == "incident" and section == "Timeline":
                lines.append("| Time | Event |")
                lines.append("|------|-------|")
                lines.append(f"| {_now()} | Incident detected |")
                lines.append(f"| {_now()} | Investigation started |")
                lines.append(f"| {_now()} | Resolved |")
            else:
                lines.append(f"_{section} content here._")

        lines.append("")

    return "\n".join(lines)


# ─── HTML converter ───────────────────────────────────────────────────────────

def _md_to_html(title: str, md_content: str) -> str:
    # Basic markdown → HTML
    lines  = md_content.splitlines()
    html   = []
    in_table = False
    in_ul    = False

    for line in lines:
        if line.startswith("# "):
            if in_ul: html.append("</ul>"); in_ul = False
            html.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            if in_ul: html.append("</ul>"); in_ul = False
            html.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            html.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("---"):
            html.append("<hr>")
        elif line.startswith("| "):
            if not in_table:
                html.append("<table>")
                in_table = True
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.match(r"^[-:]+$", c) for c in cells if c.strip()):
                pass  # separator row
            else:
                tag = "th" if not any("<tr>" in h for h in html[-5:]) else "td"
                row = "".join(f"<{tag}>{c}</{tag}>" for c in cells)
                html.append(f"<tr>{row}</tr>")
        elif line.startswith("- "):
            if not in_ul:
                html.append("<ul>")
                in_ul = True
            html.append(f"<li>{line[2:]}</li>")
        elif line.strip() == "":
            if in_table:
                html.append("</table>")
                in_table = False
            if in_ul:
                html.append("</ul>")
                in_ul = False
            html.append("")
        else:
            if in_ul: html.append("</ul>"); in_ul = False
            # Inline formatting
            processed = line
            processed = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", processed)
            processed = re.sub(r"_(.*?)_",       r"<em>\1</em>",         processed)
            processed = re.sub(r"`(.*?)`",        r"<code>\1</code>",     processed)
            html.append(f"<p>{processed}</p>")

    if in_table: html.append("</table>")
    if in_ul:    html.append("</ul>")

    body = "\n".join(html)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            max-width: 860px; margin: 40px auto; padding: 0 20px;
            color: #222; line-height: 1.6; }}
    h1   {{ border-bottom: 2px solid #333; padding-bottom: 8px; }}
    h2   {{ border-bottom: 1px solid #ddd; padding-bottom: 4px; color: #444; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
    th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
    th {{ background: #f5f5f5; font-weight: 600; }}
    tr:nth-child(even) {{ background: #fafafa; }}
    code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px;
            font-family: monospace; }}
    hr {{ border: none; border-top: 1px solid #ddd; margin: 24px 0; }}
    em  {{ color: #888; }}
  </style>
</head>
<body>
{body}
</body>
</html>"""


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_new(title: str, template: str, output: Optional[str] = None):
    if template not in TEMPLATES:
        print(f"{RED}Unknown template: {template}. Choose: {', '.join(TEMPLATES)}{RESET}", file=sys.stderr)
        sys.exit(1)

    content   = _build_report_md(title, template)
    out_path  = Path(output) if output else Path(f"{_slugify(title)}.md")

    out_path.write_text(content, encoding="utf-8")
    print(f"{GREEN}Report created: {out_path}{RESET}")
    print(f"  Template : {template} ({TEMPLATES[template]['description']})")
    print(f"  Sections : {', '.join(TEMPLATES[template]['sections'])}")
    print(f"\nEdit {out_path} to fill in the sections, then run:")
    print(f"  python3 generate.py finalize {out_path} --format html")


def cmd_from_data(json_file: str, template: str = "summary", output: Optional[str] = None):
    path = Path(json_file)
    if not path.exists():
        print(f"{RED}File not found: {json_file}{RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"{RED}Invalid JSON: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    if template not in TEMPLATES:
        print(f"{RED}Unknown template: {template}{RESET}", file=sys.stderr)
        sys.exit(1)

    title     = data.get("title", path.stem.replace("-", " ").replace("_", " ").title())
    content   = _build_report_md(title, template, data)
    out_path  = Path(output) if output else Path(f"{_slugify(title)}.md")

    out_path.write_text(content, encoding="utf-8")
    print(f"{GREEN}Report generated from {json_file}: {out_path}{RESET}")
    print(f"  Template : {template}")
    print(f"  Keys used: {list(data.keys())}")


def cmd_section_add(report_file: str, section_title: str, content: str):
    path = Path(report_file)
    if not path.exists():
        print(f"{RED}File not found: {report_file}{RESET}", file=sys.stderr)
        sys.exit(1)

    existing = path.read_text(encoding="utf-8")
    section  = f"\n## {section_title}\n\n{content}\n"
    updated  = existing + section

    path.write_text(updated, encoding="utf-8")
    print(f"{GREEN}Section '{section_title}' added to {report_file}{RESET}")


def cmd_finalize(report_file: str, fmt: str = "md"):
    path = Path(report_file)
    if not path.exists():
        print(f"{RED}File not found: {report_file}{RESET}", file=sys.stderr)
        sys.exit(1)

    content = path.read_text(encoding="utf-8")

    # Extract title
    title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
    title       = title_match.group(1) if title_match else path.stem

    if fmt == "md":
        print(f"{GREEN}Report is already markdown: {report_file}{RESET}")
        print(f"  Size: {len(content):,} chars")
        return

    elif fmt == "html":
        html_content = _md_to_html(title, content)
        out_path     = path.with_suffix(".html")
        out_path.write_text(html_content, encoding="utf-8")
        print(f"{GREEN}HTML report: {out_path}{RESET}")
        print(f"  Size: {len(html_content):,} chars")

    elif fmt == "pdf":
        try:
            import weasyprint
        except ImportError:
            print(f"{RED}weasyprint not installed.{RESET}", file=sys.stderr)
            print("Install with: pip install weasyprint", file=sys.stderr)
            sys.exit(1)

        html_content = _md_to_html(title, content)
        out_path     = path.with_suffix(".pdf")

        try:
            weasyprint.HTML(string=html_content).write_pdf(str(out_path))
            size = out_path.stat().st_size
            print(f"{GREEN}PDF report: {out_path}{RESET}")
            print(f"  Size: {size / 1024:.1f} KB")
        except Exception as e:
            print(f"{RED}PDF generation failed: {e}{RESET}", file=sys.stderr)
            sys.exit(1)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter Report Generator")
    sub    = parser.add_subparsers(dest="command", required=True)

    # new
    p_new = sub.add_parser("new", help="Create a new report from template")
    p_new.add_argument("title",    help="Report title")
    p_new.add_argument("--template", choices=list(TEMPLATES), default="research")
    p_new.add_argument("--output",   help="Output file (default: <slug>.md)")

    # from-data
    p_data = sub.add_parser("from-data", help="Generate report from JSON data")
    p_data.add_argument("json_file")
    p_data.add_argument("--template", choices=list(TEMPLATES), default="summary")
    p_data.add_argument("--output")

    # section
    p_sec  = sub.add_parser("section", help="Section operations")
    p_sec_sub = p_sec.add_subparsers(dest="section_cmd", required=True)
    p_sec_add = p_sec_sub.add_parser("add", help="Add a section to a report")
    p_sec_add.add_argument("report_file")
    p_sec_add.add_argument("section_title")
    p_sec_add.add_argument("content")

    # finalize
    p_fin = sub.add_parser("finalize", help="Export report to md/html/pdf")
    p_fin.add_argument("report_file")
    p_fin.add_argument("--format", choices=["md", "html", "pdf"], default="md")

    args = parser.parse_args()

    if args.command == "new":
        cmd_new(args.title, args.template, args.output)
    elif args.command == "from-data":
        cmd_from_data(args.json_file, args.template, args.output)
    elif args.command == "section":
        if args.section_cmd == "add":
            cmd_section_add(args.report_file, args.section_title, args.content)
    elif args.command == "finalize":
        cmd_finalize(args.report_file, args.format)


if __name__ == "__main__":
    main()
