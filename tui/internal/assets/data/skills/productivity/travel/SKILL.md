---
name: travel
description: >
  Check real-time flight status and airport information via AviationStack API.
  Trigger: "flight", "flight status", "airport", "IATA", "departure", "arrival", "delay".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Travel

Retrieves real-time flight status and airport details via the AviationStack API. Pure Python, no external dependencies.

## Setup

1. Sign up at https://aviationstack.com and get a free or paid API key
2. Export the key:

```bash
export AVIATIONSTACK_API_KEY="your_api_key_here"
```

## Usage

```bash
# Get flight status by flight number (IATA format, e.g. AA123, BA456)
python3 skills/productivity/travel/scripts/travel.py flight-status AA123

# Get airport information by IATA code (e.g. JFK, LHR, EZE)
python3 skills/productivity/travel/scripts/travel.py airport-info JFK
```

## Notes

- `AVIATIONSTACK_API_KEY` — required. The free tier supports 100 requests/month.
- Flight numbers must be in IATA format: 2-letter airline code + flight number (e.g. `AA123`)
- IATA airport codes are 3 letters (e.g. `JFK`, `LHR`, `EZE`)
- API key is masked in all log output — it is never printed in full
- No PII (passenger names, seat numbers) is included in any output
- Free tier only allows HTTP (not HTTPS) — paid plans support HTTPS
