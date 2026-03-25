#!/usr/bin/env bash
# Dexter — Claude Code path definitions

AGENT_NAME="claude-code"

# Config root
AGENT_CONFIG_DIR="$HOME/.claude"

# SystemPrompt injection target (marker-based)
SYSTEM_PROMPT_FILE="$AGENT_CONFIG_DIR/CLAUDE.md"
SYSTEM_PROMPT_STRATEGY="MarkdownSections"   # uses <!-- dexter:ID --> markers

# Skills directory
SKILLS_DIR="$AGENT_CONFIG_DIR/skills"

# MCP strategy: SeparateMCPFiles
MCP_DIR="$AGENT_CONFIG_DIR/mcp"

# Settings file (hooks, permissions, outputStyle)
SETTINGS_FILE="$AGENT_CONFIG_DIR/settings.json"
SETTINGS_STRATEGY="JSONMerge"

# Backup target
BACKUP_FILES=(
  "$SYSTEM_PROMPT_FILE"
  "$SETTINGS_FILE"
)
