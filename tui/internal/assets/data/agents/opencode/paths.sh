#!/usr/bin/env bash
# Dexter — OpenCode path definitions

AGENT_NAME="opencode"

# Config root
AGENT_CONFIG_DIR="$HOME/.config/opencode"

# SystemPrompt injection target (FileReplace — AGENTS.md)
SYSTEM_PROMPT_FILE="$AGENT_CONFIG_DIR/AGENTS.md"
SYSTEM_PROMPT_STRATEGY="FileReplace"   # SOUL.md replaces/creates AGENTS.md

# Skills directory (opencode uses instructions dir)
SKILLS_DIR="$AGENT_CONFIG_DIR/skills"

# MCP strategy: MergeIntoSettings
MCP_DIR=""
SETTINGS_FILE="$AGENT_CONFIG_DIR/config.json"
SETTINGS_STRATEGY="JSONMerge"   # MCPs merged into config.json

# Backup target
BACKUP_FILES=(
  "$SYSTEM_PROMPT_FILE"
  "$SETTINGS_FILE"
)
