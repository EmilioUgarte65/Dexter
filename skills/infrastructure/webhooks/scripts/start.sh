#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$HOME/.dexter/webhook-server.pid"
LOG_FILE="$HOME/.dexter/webhook-server.log"
PORT="${WH_PORT:-4242}"
BACKGROUND=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --background) BACKGROUND=true; shift ;;
    --port) PORT="$2"; shift 2 ;;
    --stop) [[ -f "$PID_FILE" ]] && kill "$(cat "$PID_FILE")" && rm "$PID_FILE" && echo "Stopped"; exit 0 ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "[Dexter] Webhook server already running (PID $(cat $PID_FILE))"
  exit 0
fi

mkdir -p "$HOME/.dexter"
[[ ! -f "$HOME/.dexter/webhooks.json" ]] && echo "[]" > "$HOME/.dexter/webhooks.json"

if [[ "$BACKGROUND" == true ]]; then
  WH_PORT="$PORT" nohup python3 "$SCRIPT_DIR/webhook_server.py" > "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  echo "[Dexter] Webhook server started (PID $!, port $PORT)"
  echo "[Dexter] Logs: $LOG_FILE"
else
  WH_PORT="$PORT" exec python3 "$SCRIPT_DIR/webhook_server.py"
fi
