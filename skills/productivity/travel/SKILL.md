---
name: travel
description: >
  Search for flight offers via the Amadeus API. Returns top 3 results with price, duration, and stops.
  Trigger: "viaje", "travel", "vuelo", "hotel", "itinerario".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
allowed-tools: Read, Bash
---

# Travel (Flight Search)

Searches for flight offers using the Amadeus API. Returns the top 3 options with price, total duration, and number of stops.

## Setup

1. Register at [Amadeus for Developers](https://developers.amadeus.com/)
2. Create an app → copy Client ID and Client Secret
3. Note: free tier uses the test environment (`test.api.amadeus.com`)

```bash
export AMADEUS_CLIENT_ID="your_client_id_here"
export AMADEUS_CLIENT_SECRET="your_client_secret_here"
```

**Install dependencies:**
```bash
pip install requests
```

## Usage

```bash
# Search one-way flights (1 passenger by default)
python3 skills/productivity/travel/scripts/search.py \
  --from BUE \
  --to MAD \
  --date 2026-04-15

# Search with multiple passengers
python3 skills/productivity/travel/scripts/search.py \
  --from EZE \
  --to JFK \
  --date 2026-05-01 \
  --passengers 2
```

## Requirements

- `AMADEUS_CLIENT_ID` — Client ID from Amadeus developer portal
- `AMADEUS_CLIENT_SECRET` — Client Secret from Amadeus developer portal
- pip: `requests`
- Airport codes must be IATA format (e.g. `EZE`, `MAD`, `JFK`, `LHR`)

## How to use

"Buscar vuelos de Buenos Aires a Madrid para el 15 de abril"
"Qué vuelos hay de EZE a JFK el 1 de mayo para 2 personas"
"Mostrar opciones de vuelo de BUE a BCN"

## Script

Run `scripts/search.py --from {IATA} --to {IATA} --date {YYYY-MM-DD} [--passengers N]`

| Arg            | Required | Default | Description                   |
|----------------|----------|---------|-------------------------------|
| `--from`       | yes      | —       | Origin IATA airport code      |
| `--to`         | yes      | —       | Destination IATA airport code |
| `--date`       | yes      | —       | Departure date (YYYY-MM-DD)   |
| `--passengers` | no       | 1       | Number of adult passengers    |
