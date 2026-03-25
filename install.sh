#!/usr/bin/env bash
# Dexter Installer — Unix (Linux / macOS)
# Usage: bash install.sh [--agent claude-code|opencode|codex|cursor|gemini|vscode] [--dry-run]
set -euo pipefail

DEXTER_VERSION="1.0.0"
DEXTER_SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$HOME/.dexter-backup/$(date +%Y%m%d_%H%M%S)"
DRY_RUN=false
TARGET_AGENT=""

# ─── Colors ────────────────────────────────────────────────────────────────────
RED='\033[91m'; GREEN='\033[92m'; YELLOW='\033[93m'; BLUE='\033[94m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${BLUE}[Dexter]${RESET} $*"; }
success() { echo -e "${GREEN}[Dexter]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[Dexter]${RESET} $*"; }
error()   { echo -e "${RED}[Dexter]${RESET} $*" >&2; }
header()  { echo -e "\n${BOLD}${BLUE}$*${RESET}"; }

# ─── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent) TARGET_AGENT="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    *) error "Unknown argument: $1"; exit 1 ;;
  esac
done

# ─── Dependency check ──────────────────────────────────────────────────────────
NODE_AVAILABLE=false
command -v node &>/dev/null && NODE_AVAILABLE=true

if [[ "$NODE_AVAILABLE" == false ]]; then
  warn "Node.js not found. Steps that require JSON merging will be skipped."
  warn "Install Node.js to enable full installation: https://nodejs.org"
  warn "Affected: JSONMerge and MCPConfigFile strategies (opencode, cursor)"
  echo ""
fi

# ─── OS Detection ──────────────────────────────────────────────────────────────
detect_os() {
  if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "linux"
  elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macos"
  elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    echo "windows"
  else
    echo "unknown"
  fi
}

# ─── Agent Detection ───────────────────────────────────────────────────────────
detect_agent() {
  if [[ -n "$TARGET_AGENT" ]]; then
    echo "$TARGET_AGENT"
    return
  fi

  # Auto-detect by checking config dirs and running processes
  if [[ -d "$HOME/.claude" ]] || command -v claude &>/dev/null; then
    echo "claude-code"
  elif [[ -d "$HOME/.config/opencode" ]] || command -v opencode &>/dev/null; then
    echo "opencode"
  elif [[ -d "$HOME/.codex" ]] || command -v codex &>/dev/null; then
    echo "codex"
  elif [[ -d "$HOME/.cursor" ]]; then
    echo "cursor"
  elif [[ -d "$HOME/.gemini" ]] || command -v gemini &>/dev/null; then
    echo "gemini"
  elif [[ -d "$HOME/.github" ]] || command -v code &>/dev/null; then
    echo "vscode"
  else
    echo ""
  fi
}

# ─── Load agent paths ──────────────────────────────────────────────────────────
load_agent_paths() {
  local agent="$1"
  local paths_file="$DEXTER_SOURCE_DIR/agents/$agent/paths.sh"

  if [[ ! -f "$paths_file" ]]; then
    error "Unknown agent: $agent (no paths.sh found at $paths_file)"
    exit 1
  fi

  source "$paths_file"
}

# ─── Backup ────────────────────────────────────────────────────────────────────
backup_existing() {
  info "Creating backup at $BACKUP_DIR ..."
  [[ "$DRY_RUN" == true ]] && { info "[dry-run] Would backup to $BACKUP_DIR"; return; }

  mkdir -p "$BACKUP_DIR"

  local manifest="$BACKUP_DIR/manifest.json"
  echo '{"version":"1","timestamp":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","files":[' > "$manifest"

  local first=true
  for file in "${BACKUP_FILES[@]}"; do
    if [[ -f "$file" ]]; then
      local rel="${file/$HOME/~}"
      local sha256
      sha256=$(sha256sum "$file" 2>/dev/null | cut -d' ' -f1 || shasum -a 256 "$file" | cut -d' ' -f1)
      local dest="$BACKUP_DIR$(dirname "$file")"
      mkdir -p "$dest"
      cp "$file" "$dest/"

      [[ "$first" == true ]] && first=false || echo "," >> "$manifest"
      echo -n '  {"path":"'"$rel"'","sha256":"'"$sha256"'"}' >> "$manifest"
      success "  Backed up: $rel"
    fi
  done

  echo "" >> "$manifest"
  echo ']}' >> "$manifest"
  success "Backup complete: $BACKUP_DIR"
}

# ─── Inject DEXTER.md content with markers ─────────────────────────────────────
inject_system_prompt() {
  local target="$1"
  local strategy="$2"
  local content_file="$DEXTER_SOURCE_DIR/DEXTER.md"

  info "Injecting Dexter config into: $target ($strategy)"
  [[ "$DRY_RUN" == true ]] && { info "[dry-run] Would inject into $target"; return; }

  mkdir -p "$(dirname "$target")"

  case "$strategy" in
    MarkdownSections)
      # Use <!-- dexter:core --> ... <!-- /dexter:core --> markers
      local start_marker="<!-- dexter:core -->"
      local end_marker="<!-- /dexter:core -->"

      if [[ -f "$target" ]] && grep -q "$start_marker" "$target"; then
        # Update existing block
        local tmp
        tmp=$(mktemp)
        local in_block=false
        while IFS= read -r line; do
          if [[ "$line" == *"$start_marker"* ]]; then
            in_block=true
            # Write new content
            cat "$content_file" >> "$tmp"
            echo "" >> "$tmp"
          elif [[ "$line" == *"$end_marker"* ]]; then
            in_block=false
          elif [[ "$in_block" == false ]]; then
            echo "$line" >> "$tmp"
          fi
        done < "$target"
        mv "$tmp" "$target"
        success "Updated existing Dexter block in $target"
      else
        # Append new block
        echo "" >> "$target"
        cat "$content_file" >> "$target"
        echo "" >> "$target"
        success "Appended Dexter block to $target"
      fi
      ;;

    FileReplace)
      # Replace/create SOUL.md as the agent's system prompt
      cp "$DEXTER_SOURCE_DIR/SOUL.md" "$target"
      success "Installed SOUL.md as $target"
      ;;

    AppendToFile)
      mkdir -p "$(dirname "$target")"
      touch "$target"
      if ! grep -q "<!-- dexter:core -->" "$target" 2>/dev/null; then
        echo "" >> "$target"
        echo "<!-- Dexter v${DEXTER_VERSION} -->" >> "$target"
        cat "$content_file" >> "$target"
        success "Appended Dexter config to $target"
      else
        warn "Dexter already present in $target — skipping"
      fi
      ;;
  esac
}

# ─── Copy skills ───────────────────────────────────────────────────────────────
copy_skills() {
  local skills_dir="$1"

  info "Installing skills to $skills_dir ..."
  [[ "$DRY_RUN" == true ]] && { info "[dry-run] Would copy skills to $skills_dir"; return; }

  mkdir -p "$skills_dir"

  # Copy _shared bundle loader
  mkdir -p "$skills_dir/_shared"
  cp "$DEXTER_SOURCE_DIR/skills/_shared/"*.md "$skills_dir/_shared/" 2>/dev/null || true

  # Copy CAPABILITIES.md
  cp "$DEXTER_SOURCE_DIR/CAPABILITIES.md" "$skills_dir/CAPABILITIES.md"

  # Copy bundles that exist (skip ones not yet implemented)
  for bundle_dir in "$DEXTER_SOURCE_DIR/skills"/*/; do
    local bundle_name
    bundle_name=$(basename "$bundle_dir")
    [[ "$bundle_name" == "_shared" ]] && continue
    [[ "$bundle_name" == "sonoscli" ]] && continue  # ClawHub fixture, don't install

    if [[ -d "$bundle_dir" ]]; then
      cp -r "$bundle_dir" "$skills_dir/$bundle_name/"
      success "  Installed bundle: $bundle_name"
    fi
  done

  success "Skills installed"
}

# ─── Notifications config ──────────────────────────────────────────────────────
setup_notifications() {
  local config_dir="$HOME/.dexter"
  local config_file="$config_dir/notifications.json"
  local template="$DEXTER_SOURCE_DIR/notifications/config.template.json"

  [[ ! -f "$template" ]] && return

  info "Setting up notifications config ..."
  [[ "$DRY_RUN" == true ]] && { info "[dry-run] Would create $config_file if not exists"; return; }

  mkdir -p "$config_dir"

  if [[ -f "$config_file" ]]; then
    info "  Notifications config already exists — skipping ($config_file)"
  else
    cp "$template" "$config_file"
    success "  Created: $config_file"
    info "  Edit $config_file to enable Telegram, WhatsApp, Slack, or Discord notifications."
  fi
}

# ─── WhatsApp server setup ─────────────────────────────────────────────────────
setup_whatsapp() {
  local server_dir="$DEXTER_SOURCE_DIR/skills/communications/whatsapp/server"
  local config_file="$HOME/.dexter/notifications.json"

  [[ ! -f "$server_dir/package.json" ]] && return

  if [[ "$NODE_AVAILABLE" == false ]]; then
    warn "  WhatsApp server requires Node.js — skipped. Install Node.js and run: bash $server_dir/start.sh"
    return
  fi

  [[ "$DRY_RUN" == true ]] && { info "[dry-run] Would set up WhatsApp server at $server_dir"; return; }

  echo ""
  echo -e "${BOLD}Do you want to set up WhatsApp notifications? (any regular WhatsApp number, no Meta account needed)${RESET}"
  read -rp "$(echo -e "${YELLOW}[Dexter]${RESET} Set up WhatsApp? [y/N] ")" answer

  if [[ "${answer,,}" != "y" ]]; then
    info "  Skipping WhatsApp setup. Run later: bash $server_dir/start.sh"
    return
  fi

  info "Installing WhatsApp server dependencies..."
  (cd "$server_dir" && npm install --silent)
  success "  Dependencies installed."

  # Update notifications.json to use whatsapp channel
  read -rp "$(echo -e "${YELLOW}[Dexter]${RESET} Your phone number to receive notifications (e.g. +5491112345678): ")" wa_phone
  if [[ -n "$wa_phone" ]] && [[ -f "$config_file" ]]; then
    if [[ "$NODE_AVAILABLE" == true ]]; then
      node -e "
        const fs = require('fs');
        const cfg = JSON.parse(fs.readFileSync('$config_file','utf8'));
        cfg.channel = 'whatsapp';
        cfg.whatsapp = cfg.whatsapp || {};
        cfg.whatsapp.api_url = 'http://localhost:3000';
        cfg.whatsapp.phone = '$wa_phone';
        fs.writeFileSync('$config_file', JSON.stringify(cfg, null, 2));
      "
      success "  Notifications config updated → channel: whatsapp, phone: $wa_phone"
    fi
  fi

  echo ""
  success "WhatsApp server ready!"
  info "  Start it with: bash $server_dir/start.sh"
  info "  First time: scan the QR code with WhatsApp → Settings → Linked Devices → Link a Device"
  info "  Background: bash $server_dir/start.sh --background"
  echo ""
}

# ─── Configure MCPs ─────────────────────────────────────────────────────────────
configure_mcps() {
  local agent="$1"
  local settings_file="$2"
  local strategy="$3"

  info "Configuring MCPs (strategy: $strategy) ..."
  [[ "$DRY_RUN" == true ]] && { info "[dry-run] Would configure MCPs in $settings_file"; return; }

  case "$strategy" in
    SeparateMCPFiles)
      # Claude Code: copy to ~/.claude/mcp/
      local mcp_dir
      mcp_dir="$(dirname "$settings_file")/../mcp"
      mcp_dir="$(realpath "$mcp_dir" 2>/dev/null || echo "$mcp_dir")"
      mkdir -p "$mcp_dir"
      cp "$DEXTER_SOURCE_DIR/mcp/engram.json" "$mcp_dir/engram.json"
      cp "$DEXTER_SOURCE_DIR/mcp/context7.json" "$mcp_dir/context7.json"
      success "  MCP files installed to $mcp_dir"
      ;;

    JSONMerge)
      # Merge MCPs into existing settings JSON
      if [[ "$NODE_AVAILABLE" == true ]]; then
        node -e "
          const fs = require('fs');
          const settingsPath = '$settings_file';
          const settings = fs.existsSync(settingsPath) ? JSON.parse(fs.readFileSync(settingsPath,'utf8')) : {};
          settings.mcpServers = settings.mcpServers || {};
          settings.mcpServers.engram = { command: 'engram', args: ['mcp','--tools=agent'] };
          settings.mcpServers.context7 = { command: 'npx', args: ['-y','@upstash/context7-mcp'] };
          fs.mkdirSync(require('path').dirname(settingsPath), { recursive: true });
          fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
        "
        success "  MCPs merged into $settings_file"
      else
        warn "  Skipped MCP merge (Node.js required) — add MCPs manually to $settings_file"
      fi
      ;;

    MCPConfigFile)
      # Write/merge dedicated MCP config file
      local overlay="$DEXTER_SOURCE_DIR/agents/$agent/overlay.json"
      if [[ -f "$overlay" ]] && [[ "$NODE_AVAILABLE" == true ]]; then
        node -e "
          const fs = require('fs');
          const overlay = JSON.parse(fs.readFileSync('$overlay','utf8'));
          const target = '$settings_file';
          const existing = fs.existsSync(target) ? JSON.parse(fs.readFileSync(target,'utf8')) : {};
          const merged = Object.assign({}, existing, { mcpServers: overlay.mcpServers });
          fs.mkdirSync(require('path').dirname(target), { recursive: true });
          fs.writeFileSync(target, JSON.stringify(merged, null, 2));
        "
        success "  MCP config written to $settings_file"
      fi
      ;;

    TOMLFile)
      # Append to TOML config
      mkdir -p "$(dirname "$settings_file")"
      cat >> "$settings_file" << 'TOML'

# Dexter MCP servers
[mcp.engram]
command = "engram"
args = ["mcp", "--tools=agent"]

[mcp.context7]
command = "npx"
args = ["-y", "@upstash/context7-mcp"]
TOML
      success "  MCPs appended to $settings_file"
      ;;
  esac
}

# ─── Apply overlay (hooks + permissions) ───────────────────────────────────────
apply_overlay() {
  local agent="$1"
  local settings_file="$2"

  local overlay="$DEXTER_SOURCE_DIR/agents/$agent/overlay.json"
  [[ ! -f "$overlay" ]] && return

  info "Applying overlay to $settings_file ..."
  [[ "$DRY_RUN" == true ]] && { info "[dry-run] Would apply overlay from $overlay"; return; }

  if [[ "$NODE_AVAILABLE" == true ]]; then
    node -e "
      const fs = require('fs');
      const path = require('path');
      const overlay = JSON.parse(fs.readFileSync('$overlay','utf8'));
      const target = '$settings_file';
      const existing = fs.existsSync(target) ? JSON.parse(fs.readFileSync(target,'utf8')) : {};

      // Deep merge: don't overwrite user's existing permissions/hooks, just add Dexter's
      const merged = Object.assign({}, existing);

      if (overlay.outputStyle) merged.outputStyle = overlay.outputStyle;

      if (overlay.permissions) {
        merged.permissions = merged.permissions || {};
        merged.permissions.allow = [...new Set([...(merged.permissions.allow||[]), ...(overlay.permissions.allow||[])])];
        merged.permissions.deny  = [...new Set([...(merged.permissions.deny ||[]), ...(overlay.permissions.deny ||[])])];
      }

      if (overlay.hooks) {
        merged.hooks = Object.assign({}, merged.hooks||{}, overlay.hooks);
      }

      if (overlay.mcpServers) {
        merged.mcpServers = Object.assign({}, merged.mcpServers||{}, overlay.mcpServers);
      }

      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.writeFileSync(target, JSON.stringify(merged, null, 2));
    "
    success "Overlay applied to $settings_file"
  else
    warn "Skipped overlay (Node.js required) — manually apply $overlay to $settings_file"
  fi
}

# ─── Verify install ─────────────────────────────────────────────────────────────
verify_install() {
  local target_prompt="$1"
  local skills_dir="$2"

  header "Verification"
  local ok=true

  [[ -f "$target_prompt" ]] && success "  System prompt: $target_prompt" || { error "  Missing: $target_prompt"; ok=false; }
  [[ -f "$skills_dir/CAPABILITIES.md" ]] && success "  CAPABILITIES.md installed" || { error "  Missing CAPABILITIES.md"; ok=false; }
  [[ -f "$skills_dir/_shared/bundle-loader.md" ]] && success "  Bundle loader installed" || { error "  Missing bundle-loader.md"; ok=false; }

  [[ "$ok" == true ]] && success "Install verification passed" || warn "Some files missing — check errors above"
}

# ─── Main ───────────────────────────────────────────────────────────────────────
main() {
  header "Dexter v${DEXTER_VERSION} Installer"
  echo ""

  local os
  os=$(detect_os)
  info "OS: $os"

  local agent
  agent=$(detect_agent)

  if [[ -z "$agent" ]]; then
    warn "Could not auto-detect agent. Available: claude-code, opencode, codex, cursor, gemini, vscode"
    read -rp "$(echo -e "${YELLOW}[Dexter]${RESET} Enter agent name: ")" agent
  fi

  info "Target agent: $agent"

  if [[ "$DRY_RUN" == true ]]; then
    warn "DRY RUN MODE — no files will be modified"
  fi

  # Load agent-specific paths
  load_agent_paths "$agent"

  header "Step 1: Backup"
  backup_existing

  header "Step 2: System Prompt"
  inject_system_prompt "$SYSTEM_PROMPT_FILE" "$SYSTEM_PROMPT_STRATEGY"

  header "Step 3: Skills"
  copy_skills "$SKILLS_DIR"

  header "Step 3b: Notifications Config"
  setup_notifications

  header "Step 3c: WhatsApp Server (optional)"
  setup_whatsapp

  header "Step 4: MCPs"
  configure_mcps "$agent" "$SETTINGS_FILE" "$SETTINGS_STRATEGY"

  header "Step 5: Overlay (hooks + permissions)"
  apply_overlay "$agent" "$SETTINGS_FILE"

  header "Step 6: Verify"
  verify_install "$SYSTEM_PROMPT_FILE" "$SKILLS_DIR"

  echo ""
  header "Dexter installed successfully!"
  echo -e "  ${BOLD}Agent${RESET}: $agent"
  echo -e "  ${BOLD}Backup${RESET}: $BACKUP_DIR"
  echo -e "  ${BOLD}Config${RESET}: $SYSTEM_PROMPT_FILE"
  echo ""
  info "Restart your agent to activate Dexter."
  info "Run 'dexter uninstall' to revert all changes."
}

main "$@"
