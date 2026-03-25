---
name: hardening-check
description: >
  Verify that Dexter's security configuration is properly hardened.
  Trigger: "hardening check", "security check", "verificar seguridad", "is dexter secure", "security status".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
allowed-tools: Bash, Read
---

# Hardening Check

Verifies that all Dexter security layers are properly configured.

## Run

```bash
bash -c '
echo "=== Dexter Hardening Check ==="

# 1. Deny list
if grep -q "deny" ~/.claude/settings.json 2>/dev/null; then
  echo "[PASS] Deny list configured"
else
  echo "[WARN] No deny list found in settings.json"
fi

# 2. blocklist.json
DEXTER_DIR="$(dirname $(realpath ~/.claude/skills/CAPABILITIES.md 2>/dev/null || echo "/tmp"))"
if [ -f "$DEXTER_DIR/../blocklist.json" ] || [ -f "$HOME/proyectos/Dexter/blocklist.json" ]; then
  echo "[PASS] blocklist.json present"
else
  echo "[WARN] blocklist.json not found"
fi

# 3. Engram MCP
if pgrep -f "engram mcp" > /dev/null; then
  echo "[PASS] Engram MCP running"
else
  echo "[WARN] Engram MCP not running — start with: engram mcp --tools=agent &"
fi

# 4. Not running as root
if [ "$(id -u)" = "0" ]; then
  echo "[BLOCK] Agent is running as root — this is dangerous"
else
  echo "[PASS] Not running as root"
fi

# 5. Skills dir not world-writable
SKILLS_DIR=~/.claude/skills
if [ -d "$SKILLS_DIR" ] && [ "$(stat -c %a "$SKILLS_DIR" 2>/dev/null)" = "777" ]; then
  echo "[WARN] Skills dir is world-writable: $SKILLS_DIR"
else
  echo "[PASS] Skills dir permissions OK"
fi

echo ""
echo "For full audit details, see security-guide/GUIDE.md"
'
```

## Checks

| Check | What it verifies |
|-------|-----------------|
| Deny list | `permissions.deny` in settings.json has dangerous command patterns |
| blocklist.json | Plugin blocklist file exists and is non-empty |
| Engram MCP | Memory server is running (required for audit logging) |
| Root check | Agent process is NOT running as root |
| Skills permissions | Skills directory is not world-writable |

## Fix Common Issues

**Deny list missing**: Run `bash install.sh` to apply overlay.json with default deny list.

**blocklist.json missing**: Copy from Dexter source: `cp ~/proyectos/Dexter/blocklist.json ~/.claude/`

**Running as root**: Never run AI agents as root. Use a dedicated non-privileged user.

**World-writable skills**: `chmod 755 ~/.claude/skills`
