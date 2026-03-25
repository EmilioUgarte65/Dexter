---
name: linkedin
description: >
  LinkedIn content generator. Drafts optimized posts, generates hashtags, and creates
  viral opening hooks. Copies result to clipboard. NO API calls — paste manually to avoid ToS violations.
  Trigger: "linkedin", "post linkedin", "contenido linkedin".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# LinkedIn Content Generator

Generates optimized LinkedIn post content and copies it to your clipboard for manual posting.

## IMPORTANT: Why no LinkedIn API?

LinkedIn's API has **strict usage policies**. Automated posting via unofficial means leads to:
- Permanent account suspension
- Legal risk under LinkedIn ToS Section 8.2
- IP bans

**This tool generates content only — you paste it yourself.**
This is the only safe, sustainable approach.

## Usage

```bash
# Draft a post about a topic
python3 skills/social/linkedin/scripts/content.py draft "How I scaled my startup to 1M users"

# Draft with tone and length options
python3 skills/social/linkedin/scripts/content.py draft "Remote work productivity tips" --tone casual --length medium
python3 skills/social/linkedin/scripts/content.py draft "Q3 results" --tone professional --length short
python3 skills/social/linkedin/scripts/content.py draft "My journey as a developer" --tone storytelling --length long

# Generate 10 relevant hashtags
python3 skills/social/linkedin/scripts/content.py hashtags "machine learning in healthcare"

# Generate 5 viral opening hooks
python3 skills/social/linkedin/scripts/content.py hook "lessons from 10 years of freelancing"
```

## Output

All commands:
1. Print the generated content to stdout
2. Copy to clipboard automatically (via `xclip`, `pbcopy`, or `clip.exe`)

## Tones

| Tone | Style |
|------|-------|
| `professional` | Formal, data-driven, executive voice |
| `casual` | Conversational, approachable, relatable |
| `storytelling` | Narrative arc, personal journey, emotion |

## Lengths

| Length | Chars |
|--------|-------|
| `short` | ~300 chars (hook + 2 points + CTA) |
| `medium` | ~600 chars (hook + 4 points + CTA) |
| `long` | ~1200 chars (full story arc) |

## Notes

- No API keys required — content is generated via templates
- Clipboard support: Linux (`xclip`/`xsel`), macOS (`pbcopy`), Windows (`clip.exe`)
- For AI-enhanced drafts, set `OPENAI_API_KEY` and the script will use GPT to generate richer content
