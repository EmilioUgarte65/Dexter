---
name: report-generator
description: >
  Generate structured reports in markdown, HTML, or PDF format using templates.
  Pure stdlib. PDF export via weasyprint if available. Templates: research, summary, comparison, incident.
  Trigger: "generar reporte", "report", "informe", "documento", "report generator".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Report Generator

Generates structured reports in markdown, HTML, or PDF formats. Pure Python stdlib, no dependencies required. PDF output requires `weasyprint`.

## Setup (PDF support only)

```bash
pip install weasyprint
```

## Usage

```bash
# Create a new report from a template
python3 skills/research/report-generator/scripts/generate.py new "Q3 Security Audit" --template research
python3 skills/research/report-generator/scripts/generate.py new "System Outage 2024-03-15" --template incident --output incident.md
python3 skills/research/report-generator/scripts/generate.py new "Redis vs Postgres" --template comparison

# Add a section to an existing report
python3 skills/research/report-generator/scripts/generate.py section add report.md "Key Findings" "Content goes here..."

# Generate from JSON data
python3 skills/research/report-generator/scripts/generate.py from-data data.json --template summary

# Finalize (convert to HTML or PDF)
python3 skills/research/report-generator/scripts/generate.py finalize report.md --format html
python3 skills/research/report-generator/scripts/generate.py finalize report.md --format pdf
```

## Templates

| Template | Sections |
|----------|----------|
| `research` | Executive Summary, Findings, Analysis, Recommendations, Sources |
| `summary` | TL;DR, Key Points, Details |
| `comparison` | Overview, Options, Pros/Cons Table, Verdict |
| `incident` | Timeline, Impact, Root Cause, Mitigation, Prevention |

## Notes

- All reports start as `.md` files — easy to edit in any text editor
- HTML export is self-contained (no external CSS dependencies)
- PDF requires `weasyprint`: `pip install weasyprint`
- `from-data` reads JSON and maps keys to template sections
