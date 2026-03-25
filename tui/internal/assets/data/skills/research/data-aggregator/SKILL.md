---
name: data-aggregator
description: >
  Fetch data from JSON APIs, CSV files, and HTML tables. Merge, deduplicate, and export.
  Pure stdlib. Supports jq-style filters. Caches responses locally.
  Trigger: "agregar datos", "data aggregator", "merge data", "fetch api", "consolidar datos".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Data Aggregator

Fetches data from multiple sources and merges them into a unified dataset. Pure Python stdlib.

## Setup

```bash
# Optional: set cache directory (default: ~/.local/share/dexter/cache/)
export AGGREGATOR_CACHE_DIR="/path/to/cache"
```

## Usage

```bash
# Fetch a JSON API
python3 skills/research/data-aggregator/scripts/aggregate.py fetch https://api.example.com/data

# Fetch with format hint and jq-style filter
python3 skills/research/data-aggregator/scripts/aggregate.py fetch https://api.example.com/users \
  --format json --jq ".items"

# Fetch an HTML table (auto-detected)
python3 skills/research/data-aggregator/scripts/aggregate.py fetch https://example.com/table.html \
  --format html

# Merge two datasets by a common key
python3 skills/research/data-aggregator/scripts/aggregate.py merge users.json orders.json \
  --key id --output merged.json

# Remove duplicates from a file
python3 skills/research/data-aggregator/scripts/aggregate.py dedupe data.json --key email

# Export to different formats
python3 skills/research/data-aggregator/scripts/aggregate.py export data.json --format csv
python3 skills/research/data-aggregator/scripts/aggregate.py export data.json --format markdown
python3 skills/research/data-aggregator/scripts/aggregate.py export data.json --format json
```

## Supported Formats

| Format | Detection | Notes |
|--------|-----------|-------|
| `json` | `.json` extension or Content-Type | Arrays and objects |
| `csv` | `.csv` extension or Content-Type | Auto-detects delimiter |
| `html` | `.html` or Content-Type | Extracts first `<table>` |

## Notes

- Responses are cached in `AGGREGATOR_CACHE_DIR` to avoid repeated requests
- Cache uses URL hash as key; expires after 1 hour by default
- `--jq` filter supports simple dot-notation paths: `.key`, `.key.subkey`, `.items[0]`
- Merge performs a left-join: all records from file1, matched with file2 by key
