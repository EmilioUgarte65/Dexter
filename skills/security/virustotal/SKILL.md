---
name: virustotal
description: >
  Scan files and URLs against 70+ antivirus engines via VirusTotal API.
  Trigger: "scan file", "check malware", "virustotal", "analyze URL for malware", "is this file safe".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
allowed-tools: Bash, Read
---

# VirusTotal Scanner

Analyzes files or URLs against 70+ AV engines using the VirusTotal public API.

## Setup

```bash
export VIRUSTOTAL_API_KEY="your-api-key"  # Free key at virustotal.com
```

## Usage

```bash
# Scan a file
python3 skills/security/virustotal/scripts/vt.py --file /path/to/file

# Scan a URL
python3 skills/security/virustotal/scripts/vt.py --url https://suspicious-site.com

# Get report for a known hash
python3 skills/security/virustotal/scripts/vt.py --hash <sha256>
```

## Output

```
File: suspicious.py
SHA256: abc123...
Result: 3/72 engines detected
  ─ Malwarebytes: Trojan.Generic
  ─ Kaspersky: HEUR:Trojan.Python.Generic
  ─ Avast: Python:Malware-gen
Verdict: SUSPICIOUS (≥1 detection)
```

## Verdict Thresholds

| Detections | Verdict |
|-----------|---------|
| 0 | CLEAN |
| 1-2 | SUSPICIOUS — manual review recommended |
| 3+ | MALICIOUS — do not execute |

## Notes

- Free API: 4 requests/minute, 500/day
- File upload limit: 32 MB (free tier)
- Large files: only hash is sent, not the file itself
- API key stored in env var — NEVER hardcoded
