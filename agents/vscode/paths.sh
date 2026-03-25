#!/usr/bin/env bash
# Dexter — VS Code (GitHub Copilot) path definitions

AGENT_NAME="vscode"

# Config root (GitHub Copilot instructions)
AGENT_CONFIG_DIR="$HOME/.github"

# SystemPrompt injection target (AppendToFile — copilot-instructions.md)
SYSTEM_PROMPT_FILE="$AGENT_CONFIG_DIR/copilot-instructions.md"
SYSTEM_PROMPT_STRATEGY="AppendToFile"

# Skills directory
SKILLS_DIR="$HOME/.vscode/extensions/dexter-skills"

# MCP strategy: MCPConfigFile (VS Code settings.json)
MCP_DIR=""
SETTINGS_FILE="$HOME/.config/Code/User/settings.json"
SETTINGS_STRATEGY="MCPConfigFile"

# Backup target
BACKUP_FILES=(
  "$SYSTEM_PROMPT_FILE"
  "$SETTINGS_FILE"
)
