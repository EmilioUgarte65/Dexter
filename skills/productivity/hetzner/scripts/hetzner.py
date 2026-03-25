#!/usr/bin/env python3
"""
Dexter — Hetzner Cloud API client.
Manages Hetzner Cloud servers via the REST API v1 with stdlib urllib.

Usage:
  hetzner.py list-servers
  hetzner.py server-status <name_or_id>
  hetzner.py start  <name_or_id>
  hetzner.py stop   <name_or_id>
  hetzner.py reboot <name_or_id>
  hetzner.py create-server <name> --type <cx22> --image <ubuntu-24.04> [--ssh-key KEY]
  hetzner.py delete-server <name_or_id>
  hetzner.py ssh <name_or_id> [--cmd CMD] [--user USER]

Environment:
  HETZNER_API_TOKEN         Hetzner Cloud API token (required)
  HETZNER_DEFAULT_SSH_KEY   Default SSH key name for new servers (optional)
"""

import sys
import os
import json
import argparse
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Optional

# ─── Config from env ──────────────────────────────────────────────────────────

API_TOKEN       = os.environ.get("HETZNER_API_TOKEN", "")
DEFAULT_SSH_KEY = os.environ.get("HETZNER_DEFAULT_SSH_KEY", "")
BASE_URL        = "https://api.hetzner.cloud/v1"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

STATUS_COLORS = {
    "running":     GREEN,
    "off":         RED,
    "stopping":    YELLOW,
    "starting":    YELLOW,
    "rebuilding":  YELLOW,
    "migrating":   YELLOW,
    "deleting":    RED,
    "initializing": YELLOW,
}


# ─── Config check ─────────────────────────────────────────────────────────────

def check_config():
    """Validate required env vars. Exits 1 with instructions if missing."""
    if not API_TOKEN:
        print(
            f"{RED}Error: HETZNER_API_TOKEN is not set.{RESET}\n"
            "\nGet your token:\n"
            "  1. Go to https://console.hetzner.cloud/\n"
            "  2. Select your project → Security → API Tokens\n"
            "  3. Click 'Generate API Token' → Read/Write\n"
            "\nThen set it:\n"
            "  export HETZNER_API_TOKEN=your_token_here",
            file=sys.stderr,
        )
        sys.exit(1)


# ─── API helpers ──────────────────────────────────────────────────────────────

def api_request(method: str, path: str, data: dict | None = None) -> Any:
    """Make an authenticated Hetzner API request. Exits on HTTP error."""
    url  = f"{BASE_URL}{path}"
    body = json.dumps(data).encode() if data else None
    req  = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        try:
            error_json = json.loads(error_body)
            msg = error_json.get("error", {}).get("message", error_body)
        except json.JSONDecodeError:
            msg = error_body
        print(f"{RED}API error {e.code}: {msg}{RESET}", file=sys.stderr)
        sys.exit(1)


def _paginate(path: str, key: str) -> list:
    """Fetch all pages of a paginated resource."""
    results = []
    page = 1
    while True:
        sep  = "&" if "?" in path else "?"
        data = api_request("GET", f"{path}{sep}page={page}&per_page=50")
        results.extend(data.get(key, []))
        meta = data.get("meta", {}).get("pagination", {})
        if page >= meta.get("last_page", 1):
            break
        page += 1
    return results


# ─── Server resolution ────────────────────────────────────────────────────────

def _resolve_server(name_or_id: str) -> dict:
    """
    Resolve a server by name or numeric ID.
    Exits with a helpful error if not found.
    """
    # Numeric ID → direct lookup
    if name_or_id.isdigit():
        data = api_request("GET", f"/servers/{name_or_id}")
        if "server" in data:
            return data["server"]
        print(f"{RED}Error: server with ID {name_or_id} not found.{RESET}", file=sys.stderr)
        sys.exit(1)

    # Name → search
    data = api_request("GET", f"/servers?name={urllib.parse.quote(name_or_id)}")
    servers = data.get("servers", [])
    if not servers:
        print(
            f"{RED}Error: server '{name_or_id}' not found.{RESET}\n"
            f"Run 'hetzner.py list-servers' to see available servers.",
            file=sys.stderr,
        )
        sys.exit(1)
    return servers[0]


def _server_ip(server: dict, prefer_ipv4: bool = True) -> str:
    """Get the public IP of a server (IPv4 preferred)."""
    public = server.get("public_net", {})
    ipv4   = public.get("ipv4", {}).get("ip", "")
    ipv6   = public.get("ipv6", {}).get("ip", "").split("/")[0]
    if prefer_ipv4 and ipv4:
        return ipv4
    return ipv6 or ipv4


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_list_servers(args):
    check_config()
    servers = _paginate("/servers", "servers")

    if not servers:
        print(f"{YELLOW}No servers found. Create one with: hetzner.py create-server{RESET}")
        return

    print(f"\n{BOLD}Hetzner Cloud Servers{RESET}")
    print(f"{'ID':<8} {'Name':<24} {'Status':<14} {'Type':<10} {'IPv4':<18} {'Location'}")
    print("─" * 90)
    for s in sorted(servers, key=lambda x: x.get("name", "")):
        status    = s.get("status", "unknown")
        color     = STATUS_COLORS.get(status, RESET)
        srv_type  = s.get("server_type", {}).get("name", "")
        ipv4      = _server_ip(s)
        location  = s.get("datacenter", {}).get("location", {}).get("name", "")
        print(
            f"  {s['id']:<6} {s['name']:<24} {color}{status:<14}{RESET} "
            f"{srv_type:<10} {ipv4:<18} {location}"
        )
    print(f"\nTotal: {len(servers)} server(s)")


def cmd_server_status(args):
    check_config()
    server = _resolve_server(args.name_or_id)

    status   = server.get("status", "unknown")
    color    = STATUS_COLORS.get(status, RESET)
    srv_type = server.get("server_type", {})
    image    = server.get("image", {})
    public   = server.get("public_net", {})
    dc       = server.get("datacenter", {})

    print(f"\n{BOLD}{server['name']}{RESET} (ID: {server['id']})")
    print(f"  Status:   {color}{status}{RESET}")
    print(f"  Type:     {srv_type.get('name', '')} — {srv_type.get('cores', '')} vCPU, {srv_type.get('memory', '')} GB RAM")
    print(f"  Image:    {image.get('description', image.get('name', 'custom'))}")
    print(f"  Location: {dc.get('location', {}).get('description', '')} ({dc.get('location', {}).get('name', '')})")
    print(f"  IPv4:     {public.get('ipv4', {}).get('ip', 'none')}")
    print(f"  IPv6:     {public.get('ipv6', {}).get('ip', 'none')}")
    print(f"  Created:  {server.get('created', '')}")
    labels = server.get("labels", {})
    if labels:
        print(f"  Labels:   {', '.join(f'{k}={v}' for k, v in labels.items())}")


def cmd_start(args):
    check_config()
    server = _resolve_server(args.name_or_id)
    name   = server["name"]
    status = server.get("status", "")

    if status == "running":
        print(f"{YELLOW}Server '{name}' is already running.{RESET}")
        return

    print(f"Starting {YELLOW}{name}{RESET}...")
    api_request("POST", f"/servers/{server['id']}/actions/poweron")
    print(f"{GREEN}Started: {name}{RESET}")


def cmd_stop(args):
    check_config()
    server = _resolve_server(args.name_or_id)
    name   = server["name"]
    status = server.get("status", "")

    if status == "off":
        print(f"{YELLOW}Server '{name}' is already off.{RESET}")
        return

    print(f"Stopping {YELLOW}{name}{RESET}...")
    api_request("POST", f"/servers/{server['id']}/actions/shutdown")
    print(f"{GREEN}Stopped (graceful shutdown sent): {name}{RESET}")
    print(f"{YELLOW}Tip: Use 'poweroff' action for forced stop if shutdown hangs.{RESET}")


def cmd_reboot(args):
    check_config()
    server = _resolve_server(args.name_or_id)
    name   = server["name"]

    print(f"Rebooting {YELLOW}{name}{RESET}...")
    api_request("POST", f"/servers/{server['id']}/actions/reboot")
    print(f"{GREEN}Reboot initiated: {name}{RESET}")


def cmd_create_server(args):
    check_config()

    ssh_key_name = args.ssh_key or DEFAULT_SSH_KEY
    ssh_key_ids  = []

    if ssh_key_name:
        # Resolve SSH key name to ID
        data = api_request("GET", f"/ssh_keys?name={urllib.parse.quote(ssh_key_name)}")
        keys = data.get("ssh_keys", [])
        if not keys:
            print(
                f"{YELLOW}Warning: SSH key '{ssh_key_name}' not found in Hetzner.{RESET}\n"
                f"  Available keys: hetzner.py ssh-keys (not yet implemented)\n"
                f"  Creating server without SSH key.",
                file=sys.stderr,
            )
        else:
            ssh_key_ids = [keys[0]["id"]]

    payload: dict = {
        "name":        args.name,
        "server_type": args.type,
        "image":       args.image,
        "start_after_create": True,
    }
    if ssh_key_ids:
        payload["ssh_keys"] = ssh_key_ids

    print(f"Creating server {YELLOW}{args.name}{RESET} ({args.type}, {args.image})...")
    data   = api_request("POST", "/servers", payload)
    server = data.get("server", {})
    ipv4   = server.get("public_net", {}).get("ipv4", {}).get("ip", "pending")

    print(f"{GREEN}Created: {server['name']} (ID: {server['id']}){RESET}")
    print(f"  IPv4:    {ipv4}")
    print(f"  Type:    {args.type}")
    print(f"  Image:   {args.image}")
    print(f"  Status:  {server.get('status', 'initializing')}")
    if ipv4 != "pending":
        print(f"\n{CYAN}SSH:{RESET} ssh root@{ipv4}")


def cmd_delete_server(args):
    check_config()
    server = _resolve_server(args.name_or_id)
    name   = server["name"]
    ipv4   = _server_ip(server)

    print(f"{RED}Warning: This will permanently delete server '{name}' ({ipv4}).{RESET}")
    print(f"  ID: {server['id']}  Status: {server.get('status', '')}")
    confirm = input("Type the server name to confirm deletion: ").strip()

    if confirm != name:
        print("Aborted — name did not match.")
        sys.exit(0)

    api_request("DELETE", f"/servers/{server['id']}")
    print(f"{GREEN}Deleted: {name}{RESET}")


def cmd_ssh(args):
    check_config()
    server = _resolve_server(args.name_or_id)
    status = server.get("status", "")

    if status != "running":
        color = STATUS_COLORS.get(status, YELLOW)
        print(
            f"{YELLOW}Warning: server '{server['name']}' is {color}{status}{RESET}.\n"
            f"SSH may fail. Start it first: hetzner.py start {args.name_or_id}",
            file=sys.stderr,
        )

    ip   = _server_ip(server)
    user = args.user or "root"

    if not ip:
        print(f"{RED}Error: No public IP found for server '{server['name']}'.{RESET}", file=sys.stderr)
        sys.exit(1)

    ssh_cmd = ["ssh", f"{user}@{ip}"]
    if args.cmd:
        ssh_cmd += [args.cmd]

    print(f"Connecting to {CYAN}{user}@{ip}{RESET} ({server['name']})...")
    os.execvp("ssh", ssh_cmd)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Dexter — Hetzner Cloud client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hetzner.py list-servers
  hetzner.py server-status web-01
  hetzner.py start web-01
  hetzner.py create-server app-prod --type cx22 --image ubuntu-24.04
  hetzner.py ssh web-01 --cmd "systemctl status nginx"
  hetzner.py delete-server test-server
""",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list-servers
    sub.add_parser("list-servers", help="List all servers")

    # server-status
    p_status = sub.add_parser("server-status", help="Show detailed status of a server")
    p_status.add_argument("name_or_id", help="Server name or numeric ID")

    # start
    p_start = sub.add_parser("start", help="Power on a server")
    p_start.add_argument("name_or_id", help="Server name or numeric ID")

    # stop
    p_stop = sub.add_parser("stop", help="Gracefully shut down a server")
    p_stop.add_argument("name_or_id", help="Server name or numeric ID")

    # reboot
    p_reboot = sub.add_parser("reboot", help="Reboot a server")
    p_reboot.add_argument("name_or_id", help="Server name or numeric ID")

    # create-server
    p_create = sub.add_parser("create-server", help="Create a new server")
    p_create.add_argument("name", help="Server name")
    p_create.add_argument("--type", required=True, help="Server type (e.g. cx22, cx32)")
    p_create.add_argument("--image", required=True, help="OS image (e.g. ubuntu-24.04)")
    p_create.add_argument("--ssh-key", default="", help="SSH key name (overrides HETZNER_DEFAULT_SSH_KEY)")

    # delete-server
    p_delete = sub.add_parser("delete-server", help="Permanently delete a server")
    p_delete.add_argument("name_or_id", help="Server name or numeric ID")

    # ssh
    p_ssh = sub.add_parser("ssh", help="SSH into a server")
    p_ssh.add_argument("name_or_id", help="Server name or numeric ID")
    p_ssh.add_argument("--cmd", default="", help="Command to run via SSH (non-interactive)")
    p_ssh.add_argument("--user", default="root", help="SSH user (default: root)")

    args = parser.parse_args()

    dispatch = {
        "list-servers":   cmd_list_servers,
        "server-status":  cmd_server_status,
        "start":          cmd_start,
        "stop":           cmd_stop,
        "reboot":         cmd_reboot,
        "create-server":  cmd_create_server,
        "delete-server":  cmd_delete_server,
        "ssh":            cmd_ssh,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
