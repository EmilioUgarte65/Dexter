---
name: hetzner
description: >
  Manage Hetzner Cloud servers via the Hetzner Cloud API v1. List, start, stop, reboot,
  create, delete servers, and SSH into them. Pure stdlib urllib — no extra dependencies.
  Trigger: "hetzner", "VPS hetzner", "servidor hetzner", "cloud hetzner",
  "deploy hetzner", "crear servidor hetzner", "listar servidores hetzner"
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Hetzner Cloud

Manage Hetzner Cloud servers (VPS) via the [Hetzner Cloud API v1](https://docs.hetzner.cloud/).
Pure Python stdlib — no pip dependencies required.

## Setup

```bash
export HETZNER_API_TOKEN="your_hetzner_api_token_here"
export HETZNER_DEFAULT_SSH_KEY="my-ssh-key-name"   # optional, for create-server
```

### Getting your API token

1. Go to [Hetzner Cloud Console](https://console.hetzner.cloud/)
2. Select your project → Security → API Tokens
3. Click "Generate API Token" → Read/Write → Copy the token
4. `export HETZNER_API_TOKEN="<token>"`

## Usage

### Manage servers

```bash
# List all servers
python3 skills/productivity/hetzner/scripts/hetzner.py list-servers

# Get detailed status of one server
python3 skills/productivity/hetzner/scripts/hetzner.py server-status my-server

# Power operations
python3 skills/productivity/hetzner/scripts/hetzner.py start  my-server
python3 skills/productivity/hetzner/scripts/hetzner.py stop   my-server
python3 skills/productivity/hetzner/scripts/hetzner.py reboot my-server

# Create a new server
python3 skills/productivity/hetzner/scripts/hetzner.py create-server my-app \
  --type cx22 \
  --image ubuntu-24.04

# Delete a server (requires confirmation)
python3 skills/productivity/hetzner/scripts/hetzner.py delete-server my-server

# SSH into a server
python3 skills/productivity/hetzner/scripts/hetzner.py ssh my-server

# Run a command via SSH
python3 skills/productivity/hetzner/scripts/hetzner.py ssh my-server --cmd "systemctl status nginx"
```

### Common server types

| Type | vCPU | RAM | Disk | Monthly (approx) |
|------|------|-----|------|-----------------|
| cx22 | 2    | 4 GB | 40 GB SSD | ~€4 |
| cx32 | 4    | 8 GB | 80 GB SSD | ~€8 |
| cx42 | 8    | 16 GB | 160 GB SSD | ~€16 |

### Common images

- `ubuntu-24.04`, `ubuntu-22.04`
- `debian-12`, `debian-11`
- `fedora-40`

## Agent Instructions

When the user mentions "hetzner", "VPS hetzner", "servidor hetzner", or "cloud hetzner":

1. **Detect intent**:
   - Show servers → `list-servers` or `server-status <name>`
   - Power → `start`, `stop`, `reboot`
   - Provision → `create-server`
   - Remove → `delete-server`
   - Connect → `ssh`
2. **Extract parameters** — server name/ID from user message
3. **Check config** — `check_config()` validates `HETZNER_API_TOKEN`
4. **Run command** — accept name OR numeric ID in all commands
5. **Report result** — server state, IP address, creation details

### Common patterns

| User says | Command |
|-----------|---------|
| "list my Hetzner servers" | `hetzner.py list-servers` |
| "start server web-01" | `hetzner.py start web-01` |
| "reboot the DB server" | `hetzner.py reboot <db-server-name>` |
| "create a cx22 Ubuntu server called app-prod" | `hetzner.py create-server app-prod --type cx22 --image ubuntu-24.04` |
| "SSH into my-server and check logs" | `hetzner.py ssh my-server --cmd "journalctl -n 50"` |
| "delete test-server" | `hetzner.py delete-server test-server` |

### Name vs ID

All commands accept either the server **name** (string) or **numeric ID**.
Use `list-servers` to find the name/ID if unsure.

## Error Handling

- Missing `HETZNER_API_TOKEN` → `check_config()` prints export instructions and exits 1
- Server not found → suggest `list-servers`
- API 422 → validation error (e.g., server type not available in datacenter)
- Delete confirmation → script prompts `y/N` before deleting to prevent accidents
- SSH → falls back to IPv4 if IPv6 is not reachable
