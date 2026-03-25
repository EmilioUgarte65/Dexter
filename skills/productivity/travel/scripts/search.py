#!/usr/bin/env python3
"""Search for flight offers via the Amadeus API."""
import argparse
import os
import sys

import requests

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
FLIGHTS_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"


def check_config():
    missing = [v for v in ["AMADEUS_CLIENT_ID", "AMADEUS_CLIENT_SECRET"] if not os.getenv(v)]
    if missing:
        print(
            f"{RED}Missing env vars: {', '.join(missing)}{RESET}\n"
            "\nSetup:\n"
            "  1. Register at https://developers.amadeus.com\n"
            "  2. Create an app and copy Client ID and Client Secret\n"
            "  3. export AMADEUS_CLIENT_ID=your_client_id\n"
            "  4. export AMADEUS_CLIENT_SECRET=your_client_secret",
            file=sys.stderr,
        )
        sys.exit(1)


def get_access_token() -> str:
    """Obtain an OAuth2 access token from Amadeus."""
    client_id = os.environ["AMADEUS_CLIENT_ID"]
    client_secret = os.environ["AMADEUS_CLIENT_SECRET"]

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    if not resp.ok:
        print(
            f"{RED}Amadeus auth error {resp.status_code}: {resp.text}{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    return resp.json()["access_token"]


def parse_duration(iso_duration: str) -> str:
    """Convert ISO 8601 duration (PT2H30M) to human-readable string."""
    import re

    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", iso_duration)
    if not match:
        return iso_duration
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    return " ".join(parts) if parts else iso_duration


def cmd_search(origin: str, destination: str, date: str, passengers: int = 1):
    """Search for flight offers and display top 3 results."""
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    params = {
        "originLocationCode": origin.upper(),
        "destinationLocationCode": destination.upper(),
        "departureDate": date,
        "adults": passengers,
        "max": 10,
        "currencyCode": "USD",
    }

    resp = requests.get(FLIGHTS_URL, headers=headers, params=params, timeout=20)
    if not resp.ok:
        print(
            f"{RED}Amadeus API error {resp.status_code}: {resp.text}{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    data = resp.json()
    offers = data.get("data", [])

    if not offers:
        print(f"No flights found from {origin.upper()} to {destination.upper()} on {date}.")
        return

    top = offers[:3]
    print(
        f"\n{GREEN}Top {len(top)} flight(s) from {origin.upper()} → {destination.upper()} "
        f"on {date} ({passengers} passenger{'s' if passengers > 1 else ''}){RESET}\n"
    )

    for i, offer in enumerate(top, start=1):
        price = offer.get("price", {})
        total_price = price.get("grandTotal", price.get("total", "N/A"))
        currency = price.get("currency", "USD")

        itineraries = offer.get("itineraries", [])
        if not itineraries:
            continue

        itin = itineraries[0]
        duration = parse_duration(itin.get("duration", "?"))
        segments = itin.get("segments", [])
        stops = max(len(segments) - 1, 0)
        stops_label = "Direct" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}"

        carrier = segments[0].get("carrierCode", "?") if segments else "?"
        flight_number = segments[0].get("number", "?") if segments else "?"
        dep_time = segments[0].get("departure", {}).get("at", "?") if segments else "?"
        arr_time = segments[-1].get("arrival", {}).get("at", "?") if segments else "?"

        print(f"  {YELLOW}Option {i}{RESET}")
        print(f"    Price:    {total_price} {currency}")
        print(f"    Duration: {duration}  ({stops_label})")
        print(f"    Flight:   {carrier}{flight_number}")
        print(f"    Departs:  {dep_time}")
        print(f"    Arrives:  {arr_time}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Dexter — Amadeus flight search")
    parser.add_argument("--from", dest="origin", required=True, help="Origin IATA airport code (e.g. EZE)")
    parser.add_argument("--to", dest="destination", required=True, help="Destination IATA airport code (e.g. MAD)")
    parser.add_argument("--date", required=True, help="Departure date in YYYY-MM-DD format")
    parser.add_argument("--passengers", type=int, default=1, help="Number of adult passengers (default: 1)")

    args = parser.parse_args()
    check_config()
    cmd_search(args.origin, args.destination, args.date, args.passengers)


if __name__ == "__main__":
    main()
