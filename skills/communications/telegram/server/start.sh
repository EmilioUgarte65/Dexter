#!/usr/bin/env bash
# Dexter Telegram Server — install deps + start
# Usage: bash start.sh [--port 3002] [--background] [--install-service]
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PORT=3001
BACKGROUND=false
INSTALL_SERVICE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --background) BACKGROUND=true; shift ;;
    --install-service) INSTALL_SERVICE=true; shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# Install deps if needed
if [[ ! -d node_modules ]]; then
  echo "[Dexter] Installing Telegram server dependencies..."
  npm install --silent
  echo "[Dexter] Done."
fi

# ─── Service registration ──────────────────────────────────────────────────────
# Supports systemd (Linux) and launchd (macOS).
install_service() {
  local os
  os="$(uname -s)"

  if [[ "$os" == "Linux" ]] && command -v systemctl &>/dev/null; then
    local unit_dir="$HOME/.config/systemd/user"
    local unit_file="$unit_dir/dexter-telegram.service"
    mkdir -p "$unit_dir"
    cat > "$unit_file" <<EOF
[Unit]
Description=Dexter Telegram Server
After=network.target

[Service]
Type=simple
WorkingDirectory=$DIR
ExecStart=$(command -v node) $DIR/server.js
Environment=TELEGRAM_PORT=$PORT
Restart=on-failure
RestartSec=5
StandardOutput=append:$HOME/.dexter/telegram-server.log
StandardError=append:$HOME/.dexter/telegram-server.log

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable dexter-telegram
    systemctl --user start dexter-telegram
    echo "[Dexter] systemd service registered and started."
    echo "[Dexter] Manage with: systemctl --user {start|stop|status|restart} dexter-telegram"
    echo "[Dexter] Logs: journalctl --user -u dexter-telegram -f"

  elif [[ "$os" == "Darwin" ]]; then
    local plist_dir="$HOME/Library/LaunchAgents"
    local plist_file="$plist_dir/sh.dexter.telegram.plist"
    mkdir -p "$plist_dir"
    cat > "$plist_file" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>sh.dexter.telegram</string>
  <key>ProgramArguments</key>
  <array>
    <string>$(command -v node)</string>
    <string>$DIR/server.js</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$DIR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>TELEGRAM_PORT</key>
    <string>$PORT</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$HOME/.dexter/telegram-server.log</string>
  <key>StandardErrorPath</key>
  <string>$HOME/.dexter/telegram-server.log</string>
</dict>
</plist>
EOF
    launchctl load "$plist_file"
    echo "[Dexter] launchd agent registered and started."
    echo "[Dexter] Manage with: launchctl {start|stop} sh.dexter.telegram"
    echo "[Dexter] Logs: tail -f ~/.dexter/telegram-server.log"

  else
    echo "[Dexter] Auto-service not supported on this OS."
    echo "[Dexter] Start manually: bash $DIR/start.sh --background"
  fi
}

if [[ "$INSTALL_SERVICE" == true ]]; then
  install_service
  exit 0
fi

if [[ "$BACKGROUND" == true ]]; then
  TELEGRAM_PORT="$PORT" nohup node server.js > "$HOME/.dexter/telegram-server.log" 2>&1 &
  echo "[Dexter] Telegram server started in background (PID $!)"
  echo "[Dexter] Logs: ~/.dexter/telegram-server.log"
else
  echo "[Dexter] Starting Telegram server on port $PORT..."
  echo "[Dexter] Bot token needed: set TELEGRAM_BOT_TOKEN or add bot_token to ~/.dexter/telegram-persona.json"
  echo ""
  TELEGRAM_PORT="$PORT" exec node server.js
fi
