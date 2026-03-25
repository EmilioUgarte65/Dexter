#!/usr/bin/env python3
"""
Dexter — AviationStack flight and airport client.
Uses stdlib only (urllib). No external dependencies.

Usage:
  travel.py flight-status <flight_number>
  travel.py airport-info <iata_code>
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Optional

# ─── Config from env ──────────────────────────────────────────────────────────

AVIATIONSTACK_API_KEY = os.environ.get("AVIATIONSTACK_API_KEY", "")

GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

BASE_URL = "http://api.aviationstack.com/v1"


def _masked_key() -> str:
    """Return a masked version of the API key for safe logging."""
    if not AVIATIONSTACK_API_KEY:
        return "(not set)"
    return AVIATIONSTACK_API_KEY[:4] + "****"


def check_config():
    if not AVIATIONSTACK_API_KEY:
        print(
            f"{RED}Error: AVIATIONSTACK_API_KEY is not set.{RESET}\n"
            "Sign up at https://aviationstack.com and export your key:\n"
            "  export AVIATIONSTACK_API_KEY=your_key_here",
            file=sys.stderr,
        )
        sys.exit(1)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def api_get(endpoint: str, params: Optional[dict] = None) -> Any:
    """Perform a GET request to AviationStack. API key is always sent as param, never logged."""
    query = {"access_key": AVIATIONSTACK_API_KEY}
    if params:
        query.update(params)
    url = f"{BASE_URL}/{endpoint}?" + urllib.parse.urlencode(query)

    # Log URL with masked key
    safe_params = {k: (v if k != "access_key" else _masked_key()) for k, v in query.items()}
    safe_url = f"{BASE_URL}/{endpoint}?" + urllib.parse.urlencode(safe_params)
    print(f"  GET {safe_url}", file=sys.stderr)

    req = urllib.request.Request(url, headers={"User-Agent": "Dexter/1.0"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            msg = err.get("error", {}).get("message", body)
            print(f"{RED}API error {e.code}: {msg}{RESET}", file=sys.stderr)
        except Exception:
            print(f"{RED}HTTP error {e.code}: {body}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach AviationStack API: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_flight_status(flight_number: str):
    """Fetch and display real-time status for a flight."""
    data = api_get("flights", {"flight_iata": flight_number.upper()})

    flights = data.get("data", [])
    if not flights:
        print(f"No data found for flight {flight_number.upper()}.")
        return

    print(f"\n  FLIGHT STATUS — {flight_number.upper()} ({len(flights)} result(s))\n")

    for flight in flights[:5]:  # cap at 5 results
        airline     = flight.get("airline", {}).get("name", "Unknown Airline")
        fn          = flight.get("flight", {}).get("iata", flight_number.upper())
        status      = flight.get("flight_status", "unknown").upper()
        dep_airport = flight.get("departure", {}).get("airport", "?")
        dep_iata    = flight.get("departure", {}).get("iata", "?")
        dep_sched   = flight.get("departure", {}).get("scheduled", "?")[:16] if flight.get("departure", {}).get("scheduled") else "?"
        dep_actual  = flight.get("departure", {}).get("actual", "") or ""
        dep_delay   = flight.get("departure", {}).get("delay")
        arr_airport = flight.get("arrival", {}).get("airport", "?")
        arr_iata    = flight.get("arrival", {}).get("iata", "?")
        arr_sched   = flight.get("arrival", {}).get("scheduled", "?")[:16] if flight.get("arrival", {}).get("scheduled") else "?"
        arr_actual  = flight.get("arrival", {}).get("actual", "") or ""

        status_color = GREEN if status == "LANDED" else (YELLOW if status == "ACTIVE" else RESET)

        print(f"  {fn} — {airline}")
        print(f"  Status: {status_color}{status}{RESET}")
        print(f"  Departure: {dep_airport} ({dep_iata})  scheduled {dep_sched}" +
              (f"  actual {dep_actual[:16]}" if dep_actual else "") +
              (f"  {YELLOW}delay {dep_delay} min{RESET}" if dep_delay else ""))
        print(f"  Arrival:   {arr_airport} ({arr_iata})  scheduled {arr_sched}" +
              (f"  actual {arr_actual[:16]}" if arr_actual else ""))
        print()


def cmd_airport_info(iata_code: str):
    """Fetch and display airport information by IATA code."""
    data = api_get("airports", {"search": iata_code.upper()})

    airports = data.get("data", [])
    if not airports:
        print(f"No airport found for IATA code {iata_code.upper()}.")
        return

    # Try to find an exact IATA match first
    exact = [a for a in airports if a.get("iata_code", "").upper() == iata_code.upper()]
    results = exact if exact else airports[:3]

    print(f"\n  AIRPORT INFO — {iata_code.upper()}\n")
    for airport in results:
        name      = airport.get("airport_name", "?")
        iata      = airport.get("iata_code", "?")
        icao      = airport.get("icao_code", "?")
        city      = airport.get("city_iata_code", "?")
        country   = airport.get("country_name", "?")
        timezone  = airport.get("timezone", "?")
        lat       = airport.get("latitude", "?")
        lon       = airport.get("longitude", "?")

        print(f"  {GREEN}{name}{RESET} ({iata} / {icao})")
        print(f"  City:     {city}")
        print(f"  Country:  {country}")
        print(f"  Timezone: {timezone}")
        print(f"  Coords:   {lat}, {lon}")
        print()


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    check_config()

    parser = argparse.ArgumentParser(description="Dexter Travel CLI — AviationStack")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # flight-status
    p_flight = subparsers.add_parser("flight-status", help="Get real-time flight status")
    p_flight.add_argument("flight_number", help="IATA flight number (e.g. AA123, BA456)")

    # airport-info
    p_airport = subparsers.add_parser("airport-info", help="Get airport information by IATA code")
    p_airport.add_argument("iata_code", help="3-letter IATA airport code (e.g. JFK, LHR, EZE)")

    args = parser.parse_args()

    if args.command == "flight-status":
        cmd_flight_status(args.flight_number)
    elif args.command == "airport-info":
        cmd_airport_info(args.iata_code)


if __name__ == "__main__":
    main()
