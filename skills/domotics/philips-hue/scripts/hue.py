#!/usr/bin/env python3
"""
Dexter — Philips Hue local bridge REST API client.
Pure stdlib, no external dependencies.

Usage:
  hue.py register                          — get API key (press bridge button first)
  hue.py lights                            — list all lights
  hue.py groups                            — list rooms/groups
  hue.py scenes                            — list all scenes
  hue.py on <light_id|all>                 — turn on
  hue.py off <light_id|all>               — turn off
  hue.py brightness <light_id|all> <0-254>
  hue.py colortemp <light_id|all> <K>     — Kelvin: 2000-6500
  hue.py color <light_id|all> <R> <G> <B> — 0-255 each
  hue.py scene <group_name> <scene_name>  — activate scene in room
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import math
from typing import Any, Optional

# ─── Config ───────────────────────────────────────────────────────────────────

BRIDGE_IP = os.environ.get("HUE_BRIDGE_IP", "")
API_KEY   = os.environ.get("HUE_API_KEY", "")


def check_config(need_key: bool = True):
    if not BRIDGE_IP:
        print("Error: HUE_BRIDGE_IP not set. Find it with: bash skills/domotics/device-discovery/scripts/discover.sh", file=sys.stderr)
        sys.exit(1)
    if need_key and not API_KEY:
        print("Error: HUE_API_KEY not set. Run: python3 hue.py register", file=sys.stderr)
        sys.exit(1)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def hue_request(method: str, path: str, payload: Optional[dict] = None) -> Any:
    url = f"http://{BRIDGE_IP}/api/{API_KEY}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        print(f"Cannot reach Hue bridge at {BRIDGE_IP}: {e.reason}", file=sys.stderr)
        print("Check HUE_BRIDGE_IP is correct and bridge is on the same network.", file=sys.stderr)
        sys.exit(1)


def hue_get(path: str) -> Any:
    return hue_request("GET", path)


def hue_put(path: str, payload: dict) -> Any:
    return hue_request("PUT", path, payload)


def hue_post(path: str, payload: dict) -> Any:
    return hue_request("POST", path, payload)


def check_errors(result: Any, action: str = ""):
    if isinstance(result, list):
        for item in result:
            if "error" in item:
                err = item["error"]
                print(f"  Hue error {err.get('type')}: {err.get('description')}", file=sys.stderr)
                return False
    return True


# ─── Color conversion ─────────────────────────────────────────────────────────

def rgb_to_xy(r: int, g: int, b: int) -> tuple[float, float]:
    """Convert RGB (0-255) to CIE xy for Hue API."""
    r_lin = pow(r / 255, 2.2)
    g_lin = pow(g / 255, 2.2)
    b_lin = pow(b / 255, 2.2)

    X = r_lin * 0.664511 + g_lin * 0.154324 + b_lin * 0.162028
    Y = r_lin * 0.283881 + g_lin * 0.668433 + b_lin * 0.047685
    Z = r_lin * 0.000088 + g_lin * 0.072310 + b_lin * 0.986039

    total = X + Y + Z
    if total == 0:
        return 0.0, 0.0
    return round(X / total, 4), round(Y / total, 4)


def kelvin_to_mired(kelvin: int) -> int:
    """Convert color temperature Kelvin to Hue mireds."""
    kelvin = max(2000, min(6500, kelvin))
    return int(1_000_000 / kelvin)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_register():
    """Create a new API user — requires bridge button press within 30s."""
    url = f"http://{BRIDGE_IP}/api"
    payload = {"devicetype": "dexter#agent"}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                  headers={"Content-Type": "application/json"})
    print(f"Connecting to bridge at {BRIDGE_IP}...")
    print("Make sure you pressed the button on the bridge within the last 30 seconds.")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        print(f"Cannot reach bridge: {e.reason}", file=sys.stderr)
        sys.exit(1)

    if isinstance(result, list) and "success" in result[0]:
        key = result[0]["success"]["username"]
        print(f"\nSuccess! Your API key:")
        print(f"  export HUE_API_KEY=\"{key}\"")
        print(f"\nAdd this to your shell profile (~/.bashrc or ~/.zshrc)")
    else:
        err = result[0].get("error", {}) if isinstance(result, list) else {}
        print(f"Failed: {err.get('description', result)}", file=sys.stderr)
        if err.get("type") == 101:
            print("You need to press the physical button on the Hue bridge first!", file=sys.stderr)
        sys.exit(1)


def cmd_lights():
    lights = hue_get("/lights")
    if not lights:
        print("No lights found.")
        return
    print(f"\nLights ({len(lights)} found):\n")
    for lid, light in sorted(lights.items(), key=lambda x: int(x[0])):
        state = light["state"]
        on = state.get("on", False)
        bri = state.get("bri", 0)
        name = light["name"]
        ltype = light.get("type", "")
        status = "\033[92mON \033[0m" if on else "\033[91mOFF\033[0m"
        bri_pct = f"{int(bri/254*100):3d}%" if on else "  0%"
        print(f"  [{lid:>2}] {status}  {bri_pct}  {name:<30}  {ltype}")


def cmd_groups():
    groups = hue_get("/groups")
    if not groups:
        print("No groups found.")
        return
    print(f"\nGroups ({len(groups)} found):\n")
    for gid, group in sorted(groups.items(), key=lambda x: int(x[0])):
        name = group["name"]
        gtype = group.get("type", "")
        lights = group.get("lights", [])
        action = group.get("action", {})
        on = action.get("on", False)
        status = "\033[92mON \033[0m" if on else "\033[91mOFF\033[0m"
        print(f"  [{gid:>2}] {status}  {name:<30}  {gtype}  ({len(lights)} lights: {', '.join(lights)})")


def cmd_scenes():
    scenes = hue_get("/scenes")
    if not scenes:
        print("No scenes found.")
        return
    print(f"\nScenes ({len(scenes)} found):\n")
    # Group by room/group
    by_group: dict[str, list] = {}
    for sid, scene in scenes.items():
        group = scene.get("group", "—")
        by_group.setdefault(group, []).append((sid, scene["name"]))

    groups = hue_get("/groups")
    for gid, scene_list in sorted(by_group.items()):
        group_name = groups.get(gid, {}).get("name", f"Group {gid}") if gid != "—" else "No group"
        print(f"  {group_name}:")
        for sid, sname in sorted(scene_list, key=lambda x: x[1]):
            print(f"    [{sid[:8]}]  {sname}")


def _set_light_state(light_id: str, state: dict):
    if light_id.lower() == "all":
        groups = hue_get("/groups")
        # Use group 0 (all lights)
        result = hue_put("/groups/0/action", state)
        check_errors(result, "set all lights")
        print(f"  All lights: {state}")
    else:
        result = hue_put(f"/lights/{light_id}/state", state)
        check_errors(result, f"set light {light_id}")
        print(f"  Light {light_id}: {state}")


def cmd_on(light_id: str):
    _set_light_state(light_id, {"on": True})


def cmd_off(light_id: str):
    _set_light_state(light_id, {"on": False})


def cmd_brightness(light_id: str, brightness: int):
    bri = max(1, min(254, brightness))
    _set_light_state(light_id, {"on": True, "bri": bri})


def cmd_colortemp(light_id: str, kelvin: int):
    ct = kelvin_to_mired(kelvin)
    _set_light_state(light_id, {"on": True, "ct": ct})
    print(f"  ({kelvin}K = {ct} mireds)")


def cmd_color(light_id: str, r: int, g: int, b: int):
    x, y = rgb_to_xy(r, g, b)
    _set_light_state(light_id, {"on": True, "xy": [x, y]})
    print(f"  (RGB {r},{g},{b} → xy [{x},{y}])")


def cmd_scene(group_name: str, scene_name: str):
    scenes = hue_get("/scenes")
    groups = hue_get("/groups")

    # Find group ID by name
    group_id = None
    for gid, group in groups.items():
        if group["name"].lower() == group_name.lower():
            group_id = gid
            break

    if not group_id:
        available = [g["name"] for g in groups.values()]
        print(f"Group '{group_name}' not found. Available: {', '.join(available)}", file=sys.stderr)
        sys.exit(1)

    # Find scene ID
    scene_id = None
    for sid, scene in scenes.items():
        if (scene["name"].lower() == scene_name.lower() and
                scene.get("group") == group_id):
            scene_id = sid
            break

    if not scene_id:
        available = [s["name"] for s in scenes.values() if s.get("group") == group_id]
        print(f"Scene '{scene_name}' not found in '{group_name}'. Available: {', '.join(available)}", file=sys.stderr)
        sys.exit(1)

    result = hue_put(f"/groups/{group_id}/action", {"scene": scene_id})
    check_errors(result, "activate scene")
    print(f"  Activated scene '{scene_name}' in '{group_name}'")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter Philips Hue Controller")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("register", help="Create API key (press bridge button first)")
    sub.add_parser("lights",   help="List all lights")
    sub.add_parser("groups",   help="List rooms/groups")
    sub.add_parser("scenes",   help="List all scenes")

    p_on = sub.add_parser("on", help="Turn light on")
    p_on.add_argument("light_id", help="Light ID or 'all'")

    p_off = sub.add_parser("off", help="Turn light off")
    p_off.add_argument("light_id", help="Light ID or 'all'")

    p_bri = sub.add_parser("brightness", help="Set brightness (1-254)")
    p_bri.add_argument("light_id")
    p_bri.add_argument("value", type=int)

    p_ct = sub.add_parser("colortemp", help="Set color temperature (Kelvin)")
    p_ct.add_argument("light_id")
    p_ct.add_argument("kelvin", type=int, help="2000 (warm) to 6500 (cool)")

    p_col = sub.add_parser("color", help="Set RGB color (0-255 each)")
    p_col.add_argument("light_id")
    p_col.add_argument("r", type=int)
    p_col.add_argument("g", type=int)
    p_col.add_argument("b", type=int)

    p_scene = sub.add_parser("scene", help="Activate a scene in a group")
    p_scene.add_argument("group_name")
    p_scene.add_argument("scene_name")

    args = parser.parse_args()

    if args.command == "register":
        check_config(need_key=False)
        cmd_register()
        return

    check_config()

    if args.command == "lights":       cmd_lights()
    elif args.command == "groups":     cmd_groups()
    elif args.command == "scenes":     cmd_scenes()
    elif args.command == "on":         cmd_on(args.light_id)
    elif args.command == "off":        cmd_off(args.light_id)
    elif args.command == "brightness": cmd_brightness(args.light_id, args.value)
    elif args.command == "colortemp":  cmd_colortemp(args.light_id, args.kelvin)
    elif args.command == "color":      cmd_color(args.light_id, args.r, args.g, args.b)
    elif args.command == "scene":      cmd_scene(args.group_name, args.scene_name)


if __name__ == "__main__":
    main()
