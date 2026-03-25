#!/usr/bin/env python3
"""
Dexter — Home Assistant REST API client.
Uses stdlib only (urllib). No external dependencies.

Usage:
  ha.py list [--domain <domain>]
  ha.py state <entity_id>
  ha.py turn_on <entity_id> [--brightness N] [--color_temp N] [--rgb R,G,B]
  ha.py turn_off <entity_id>
  ha.py toggle <entity_id>
  ha.py call <domain> <service> [json_payload]
  ha.py sensors
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
from typing import Any, Optional

# ─── Config from env ──────────────────────────────────────────────────────────

HASS_URL   = os.environ.get("HASS_URL", "").rstrip("/")
HASS_TOKEN = os.environ.get("HASS_TOKEN", "")
VERIFY_SSL = os.environ.get("HASS_VERIFY_SSL", "true").lower() != "false"


def check_config():
    if not HASS_URL:
        print("Error: HASS_URL not set. Export it: export HASS_URL=http://192.168.1.10:8123", file=sys.stderr)
        sys.exit(1)
    if not HASS_TOKEN:
        print("Error: HASS_TOKEN not set. Get it from HA → Profile → Long-Lived Access Tokens", file=sys.stderr)
        sys.exit(1)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def ha_request(method: str, endpoint: str, payload: Optional[dict] = None) -> Any:
    url = f"{HASS_URL}/api{endpoint}"
    headers = {
        "Authorization": f"Bearer {HASS_TOKEN}",
        "Content-Type": "application/json",
    }

    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    # Handle SSL verification
    ctx = None
    if not VERIFY_SSL:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            body = resp.read().decode()
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HA API error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Cannot reach Home Assistant at {HASS_URL}: {e.reason}", file=sys.stderr)
        print("Check: HASS_URL is correct and HA is running.", file=sys.stderr)
        sys.exit(1)


def get(endpoint: str) -> Any:
    return ha_request("GET", endpoint)


def post(endpoint: str, payload: dict = None) -> Any:
    return ha_request("POST", endpoint, payload or {})


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_list(domain: Optional[str] = None):
    states = get("/states")
    if domain:
        states = [s for s in states if s["entity_id"].startswith(f"{domain}.")]

    if not states:
        print(f"No entities found{f' for domain: {domain}' if domain else ''}.")
        return

    # Group by domain
    groups: dict[str, list] = {}
    for s in states:
        d = s["entity_id"].split(".")[0]
        groups.setdefault(d, []).append(s)

    for d, entities in sorted(groups.items()):
        print(f"\n  {d.upper()}")
        for e in sorted(entities, key=lambda x: x["entity_id"]):
            eid = e["entity_id"]
            state = e["state"]
            name = e.get("attributes", {}).get("friendly_name", "")
            state_color = "\033[92m" if state == "on" else ("\033[91m" if state == "off" else "\033[94m")
            reset = "\033[0m"
            label = f" ({name})" if name and name != eid.split(".")[1].replace("_", " ").title() else ""
            print(f"    {eid:<45} {state_color}{state}{reset}{label}")


def cmd_state(entity_id: str):
    state = get(f"/states/{entity_id}")
    print(f"\nEntity: {state['entity_id']}")
    print(f"State:  {state['state']}")
    attrs = state.get("attributes", {})
    if attrs:
        print("Attributes:")
        for k, v in sorted(attrs.items()):
            print(f"  {k}: {v}")
    print(f"Updated: {state.get('last_updated', 'unknown')}")


def cmd_turn_on(entity_id: str, brightness: Optional[int] = None,
                color_temp: Optional[int] = None, rgb: Optional[str] = None):
    payload: dict[str, Any] = {"entity_id": entity_id}
    if brightness is not None:
        payload["brightness"] = max(0, min(255, brightness))
    if color_temp is not None:
        # Convert Kelvin to mireds (HA uses mireds: 1,000,000 / K)
        payload["color_temp"] = int(1_000_000 / color_temp) if color_temp > 1000 else color_temp
    if rgb:
        r, g, b = [int(x) for x in rgb.split(",")]
        payload["rgb_color"] = [r, g, b]

    domain = entity_id.split(".")[0]
    result = post(f"/services/{domain}/turn_on", payload)
    _print_service_result("turn_on", entity_id, result)


def cmd_turn_off(entity_id: str):
    domain = entity_id.split(".")[0]
    payload = {"entity_id": entity_id}
    result = post(f"/services/{domain}/turn_off", payload)
    _print_service_result("turn_off", entity_id, result)


def cmd_toggle(entity_id: str):
    domain = entity_id.split(".")[0]
    payload = {"entity_id": entity_id}
    result = post(f"/services/{domain}/toggle", payload)
    _print_service_result("toggle", entity_id, result)


def cmd_call(domain: str, service: str, payload_str: Optional[str] = None):
    payload = json.loads(payload_str) if payload_str else {}
    result = post(f"/services/{domain}/{service}", payload)
    print(f"Called {domain}.{service}")
    if result:
        print(f"Result: {json.dumps(result, indent=2)}")


def cmd_sensors():
    states = get("/states")
    sensors = [s for s in states if s["entity_id"].startswith("sensor.")]

    print(f"\nSensors ({len(sensors)} found):\n")
    for s in sorted(sensors, key=lambda x: x["entity_id"]):
        eid = s["entity_id"]
        state = s["state"]
        attrs = s.get("attributes", {})
        unit = attrs.get("unit_of_measurement", "")
        name = attrs.get("friendly_name", eid.split(".", 1)[1].replace("_", " ").title())
        print(f"  {name:<40} {state} {unit}")


def _print_service_result(service: str, entity_id: str, result: Any):
    if isinstance(result, list) and result:
        new_state = result[0].get("state", "unknown")
        print(f"  {service}: {entity_id} → {new_state}")
    else:
        print(f"  {service}: {entity_id}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter Home Assistant CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List entities")
    p_list.add_argument("--domain", help="Filter by domain (light, sensor, switch...)")

    # state
    p_state = subparsers.add_parser("state", help="Get entity state")
    p_state.add_argument("entity_id")

    # turn_on
    p_on = subparsers.add_parser("turn_on", help="Turn on an entity")
    p_on.add_argument("entity_id")
    p_on.add_argument("--brightness", type=int, help="Brightness 0-255")
    p_on.add_argument("--color_temp", type=int, help="Color temperature in Kelvin (e.g. 4000)")
    p_on.add_argument("--rgb", help="RGB color as R,G,B (e.g. 255,128,0)")

    # turn_off
    p_off = subparsers.add_parser("turn_off", help="Turn off an entity")
    p_off.add_argument("entity_id")

    # toggle
    p_tog = subparsers.add_parser("toggle", help="Toggle an entity")
    p_tog.add_argument("entity_id")

    # call
    p_call = subparsers.add_parser("call", help="Call any HA service")
    p_call.add_argument("domain")
    p_call.add_argument("service")
    p_call.add_argument("payload", nargs="?", help="JSON payload string")

    # sensors
    subparsers.add_parser("sensors", help="List all sensor readings")

    args = parser.parse_args()
    check_config()

    if args.command == "list":
        cmd_list(domain=getattr(args, "domain", None))
    elif args.command == "state":
        cmd_state(args.entity_id)
    elif args.command == "turn_on":
        cmd_turn_on(args.entity_id,
                    brightness=getattr(args, "brightness", None),
                    color_temp=getattr(args, "color_temp", None),
                    rgb=getattr(args, "rgb", None))
    elif args.command == "turn_off":
        cmd_turn_off(args.entity_id)
    elif args.command == "toggle":
        cmd_toggle(args.entity_id)
    elif args.command == "call":
        cmd_call(args.domain, args.service, getattr(args, "payload", None))
    elif args.command == "sensors":
        cmd_sensors()


if __name__ == "__main__":
    main()
