#!/usr/bin/env bash
# Dexter — Gemini CLI path definitions

AGENT_NAME="gemini"

# Config root
AGENT_CONFIG_DIR="$HOME/.gemini"

# SystemPrompt injection target (AppendToFile — GEMINI.md)
SYSTEM_PROMPT_FILE="$AGENT_CONFIG_DIR/GEMINI.md"
SYSTEM_PROMPT_STRATEGY="AppendToFile"

# Skills directory
SKILLS_DIR="$AGENT_CONFIG_DIR/skills"

# MCP strategy: MergeIntoSettings
MCP_DIR=""
SETTINGS_FILE="$AGENT_CONFIG_DIR/settings.json"
SETTINGS_STRATEGY="JSONMerge"

# Backup target
BACKUP_FILES=(
  "$SYSTEM_PROMPT_FILE"
  "$SETTINGS_FILE"
)
