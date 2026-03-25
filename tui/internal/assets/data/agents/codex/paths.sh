#!/usr/bin/env bash
# Dexter — Codex (OpenAI CLI) path definitions

AGENT_NAME="codex"

# Config root
AGENT_CONFIG_DIR="$HOME/.codex"

# SystemPrompt injection target (AppendToFile)
SYSTEM_PROMPT_FILE="$AGENT_CONFIG_DIR/instructions.md"
SYSTEM_PROMPT_STRATEGY="AppendToFile"

# Skills directory
SKILLS_DIR="$AGENT_CONFIG_DIR/skills"

# MCP strategy: TOMLFile
MCP_DIR=""
SETTINGS_FILE="$AGENT_CONFIG_DIR/config.toml"
SETTINGS_STRATEGY="TOMLFile"

# Backup target
BACKUP_FILES=(
  "$SYSTEM_PROMPT_FILE"
  "$SETTINGS_FILE"
)
