#!/usr/bin/env bash
# Dexter — Cursor path definitions

AGENT_NAME="cursor"

# Config root
AGENT_CONFIG_DIR="$HOME/.cursor"

# SystemPrompt injection target (AppendToFile — .cursorrules or rules)
SYSTEM_PROMPT_FILE="$HOME/.cursorrules"
SYSTEM_PROMPT_STRATEGY="AppendToFile"

# Skills directory
SKILLS_DIR="$AGENT_CONFIG_DIR/skills"

# MCP strategy: MCPConfigFile
MCP_DIR=""
SETTINGS_FILE="$AGENT_CONFIG_DIR/mcp.json"
SETTINGS_STRATEGY="MCPConfigFile"

# Backup target
BACKUP_FILES=(
  "$SYSTEM_PROMPT_FILE"
  "$SETTINGS_FILE"
)
