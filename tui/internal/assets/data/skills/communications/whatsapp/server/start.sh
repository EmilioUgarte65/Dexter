#!/usr/bin/env bash
# Dexter WhatsApp Server — install deps + start
# Usage: bash start.sh [--port 3001] [--background]
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PORT=3000
BACKGROUND=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --background) BACKGROUND=true; shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# Install deps if needed
if [[ ! -d node_modules ]]; then
  echo "[Dexter] Installing WhatsApp server dependencies..."
  npm install --silent
  echo "[Dexter] Done."
fi

if [[ "$BACKGROUND" == true ]]; then
  WA_PORT="$PORT" nohup node server.js > "$HOME/.dexter/whatsapp-server.log" 2>&1 &
  echo "[Dexter] WhatsApp server started in background (PID $!)"
  echo "[Dexter] Logs: ~/.dexter/whatsapp-server.log"
  echo "[Dexter] Check pairing code: tail -f ~/.dexter/whatsapp-server.log"
else
  echo "[Dexter] Starting WhatsApp server on port $PORT..."
  echo "[Dexter] First time? Enter the pairing code in WhatsApp → ⋮ → Linked Devices → Link with phone number."
  echo ""
  WA_PORT="$PORT" exec node server.js
fi
