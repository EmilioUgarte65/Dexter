#!/usr/bin/env bash
# Dexter Uninstaller — Unix (Linux / macOS)
# Usage: bash uninstall.sh [--backup-dir <path>] [--dry-run]
set -euo pipefail

BACKUP_BASE="$HOME/.dexter-backup"
DRY_RUN=false
SPECIFIC_BACKUP=""

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${BLUE}[Dexter]${RESET} $*"; }
success() { echo -e "${GREEN}[Dexter]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[Dexter]${RESET} $*"; }
error()   { echo -e "${RED}[Dexter]${RESET} $*" >&2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup-dir) SPECIFIC_BACKUP="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    *) error "Unknown argument: $1"; exit 1 ;;
  esac
done

# Find most recent backup
find_backup() {
  if [[ -n "$SPECIFIC_BACKUP" ]]; then
    echo "$SPECIFIC_BACKUP"
    return
  fi

  if [[ ! -d "$BACKUP_BASE" ]]; then
    error "No backup directory found at $BACKUP_BASE"
    echo "If you installed Dexter without backups, manually remove <!-- dexter:core --> blocks from your agent config."
    exit 1
  fi

  # Find latest backup by timestamp
  local latest
  latest=$(ls -1t "$BACKUP_BASE" 2>/dev/null | head -1)
  if [[ -z "$latest" ]]; then
    error "No backups found in $BACKUP_BASE"
    exit 1
  fi

  echo "$BACKUP_BASE/$latest"
}

# Remove Dexter markers from a file
strip_markers() {
  local file="$1"
  local marker_start="<!-- dexter:core -->"
  local marker_end="<!-- /dexter:core -->"

  if [[ ! -f "$file" ]]; then return; fi
  if ! grep -q "$marker_start" "$file"; then return; fi

  info "Stripping Dexter markers from $file ..."
  [[ "$DRY_RUN" == true ]] && { info "[dry-run] Would strip markers from $file"; return; }

  local tmp
  tmp=$(mktemp)
  local in_block=false

  while IFS= read -r line; do
    if [[ "$line" == *"$marker_start"* ]]; then
      in_block=true
    elif [[ "$line" == *"$marker_end"* ]]; then
      in_block=false
    elif [[ "$in_block" == false ]]; then
      echo "$line" >> "$tmp"
    fi
  done < "$file"

  mv "$tmp" "$file"
  success "Stripped Dexter markers from $file"
}

# Restore files from backup manifest
restore_from_backup() {
  local backup_dir="$1"
  local manifest="$backup_dir/manifest.json"

  if [[ ! -f "$manifest" ]]; then
    warn "No manifest found in $backup_dir — will only strip markers"
    return
  fi

  info "Restoring from backup: $backup_dir"

  if command -v node &>/dev/null; then
    node -e "
      const fs = require('fs');
      const path = require('path');
      const home = process.env.HOME;
      const manifest = JSON.parse(fs.readFileSync('$manifest', 'utf8'));

      manifest.files.forEach(entry => {
        const origPath = entry.path.replace('~', home);
        const backupPath = path.join('$backup_dir', origPath.replace(home, ''));

        if (fs.existsSync(backupPath)) {
          fs.mkdirSync(path.dirname(origPath), { recursive: true });
          fs.copyFileSync(backupPath, origPath);
          console.log('  Restored: ' + entry.path);
        } else {
          console.log('  Warning: backup file not found: ' + entry.path);
        }
      });
    "
  else
    warn "Node.js not found — manually restore files from $backup_dir"
  fi
}

# Remove Dexter skills from agent skills dir (keep user's own skills)
remove_dexter_skills() {
  # The source dir is needed to know which bundles are Dexter's
  local dexter_source
  dexter_source="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

  # Detect skills dir from agent config
  local agent_skills_dirs=(
    "$HOME/.claude/skills"
    "$HOME/.config/opencode/skills"
    "$HOME/.codex/skills"
    "$HOME/.cursor/skills"
    "$HOME/.gemini/skills"
  )

  for skills_dir in "${agent_skills_dirs[@]}"; do
    if [[ ! -d "$skills_dir" ]]; then continue; fi

    for bundle in "$dexter_source/skills"/*/; do
      local bundle_name
      bundle_name=$(basename "$bundle")
      [[ "$bundle_name" == "sonoscli" ]] && continue  # don't touch ClawHub fixture

      local installed="$skills_dir/$bundle_name"
      if [[ -d "$installed" ]]; then
        info "Removing bundle: $installed"
        [[ "$DRY_RUN" == true ]] && { info "[dry-run] Would remove $installed"; continue; }
        rm -rf "$installed"
        success "  Removed: $bundle_name"
      fi
    done

    # Remove CAPABILITIES.md and bundle-loader
    for f in CAPABILITIES.md _shared/bundle-loader.md; do
      [[ -f "$skills_dir/$f" ]] && rm -f "$skills_dir/$f" && success "  Removed: $f"
    done
  done
}

main() {
  echo -e "\n${BOLD}${RED}Dexter Uninstaller${RESET}\n"

  local backup_dir
  backup_dir=$(find_backup)
  info "Using backup: $backup_dir"

  if [[ "$DRY_RUN" == true ]]; then
    warn "DRY RUN MODE — no files will be modified"
  fi

  echo ""
  info "Step 1: Restoring original files..."
  restore_from_backup "$backup_dir"

  echo ""
  info "Step 2: Stripping Dexter markers (for AppendToFile agents)..."
  # Strip markers from common system prompt locations
  for f in "$HOME/.cursorrules" "$HOME/.gemini/GEMINI.md" "$HOME/.codex/instructions.md" "$HOME/.github/copilot-instructions.md"; do
    strip_markers "$f"
  done

  echo ""
  info "Step 3: Removing Dexter skills..."
  remove_dexter_skills

  echo ""
  success "Dexter uninstalled. Your original config has been restored."
  info "Restart your agent to complete the removal."
}

main "$@"
