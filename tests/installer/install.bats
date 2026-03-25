#!/usr/bin/env bats
# Dexter installer test suite — requires bats-core
# Run: bats tests/installer/install.bats

# ─── Resolve project root ───────────────────────────────────────────────────
# BATS_TEST_DIRNAME is the directory containing this file
PROJECT_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
INSTALL_SH="$PROJECT_ROOT/install.sh"
UNINSTALL_SH="$PROJECT_ROOT/uninstall.sh"

# ─── Setup / Teardown ───────────────────────────────────────────────────────
setup() {
  # Isolated temp HOME so nothing touches the real environment
  ORIG_HOME="$HOME"
  TEST_TMPDIR="$(mktemp -d)"
  export HOME="$TEST_TMPDIR"
  export DEXTER_BACKUP_BASE="$TEST_TMPDIR/.dexter-backup"
}

teardown() {
  export HOME="$ORIG_HOME"
  rm -rf "$TEST_TMPDIR"
}

# ─── Syntax checks ──────────────────────────────────────────────────────────

@test "install.sh passes bash syntax check" {
  run bash -n "$INSTALL_SH"
  [ "$status" -eq 0 ]
}

@test "uninstall.sh passes bash syntax check" {
  run bash -n "$UNINSTALL_SH"
  [ "$status" -eq 0 ]
}

# ─── install.sh — argument handling ─────────────────────────────────────────

@test "install.sh exits with non-zero status on unknown argument" {
  run bash "$INSTALL_SH" --unknown-flag
  [ "$status" -ne 0 ]
}

@test "install.sh prints error message on unknown argument" {
  run bash "$INSTALL_SH" --unknown-flag
  [[ "$output" == *"Unknown argument"* ]]
}

# ─── install.sh — dry-run creates no files ──────────────────────────────────

@test "install.sh --dry-run with --agent claude-code creates no files in HOME" {
  # Snapshot HOME before
  local before_count
  before_count="$(find "$TEST_TMPDIR" -type f 2>/dev/null | wc -l)"

  run bash "$INSTALL_SH" --agent claude-code --dry-run

  local after_count
  after_count="$(find "$TEST_TMPDIR" -type f 2>/dev/null | wc -l)"

  [ "$before_count" -eq "$after_count" ]
}

@test "install.sh --dry-run does not create ~/.claude/CLAUDE.md" {
  run bash "$INSTALL_SH" --agent claude-code --dry-run
  [ ! -f "$TEST_TMPDIR/.claude/CLAUDE.md" ]
}

@test "install.sh --dry-run does not create ~/.claude/settings.json" {
  run bash "$INSTALL_SH" --agent claude-code --dry-run
  [ ! -f "$TEST_TMPDIR/.claude/settings.json" ]
}

@test "install.sh --dry-run does not create ~/.claude/skills/" {
  run bash "$INSTALL_SH" --agent claude-code --dry-run
  [ ! -d "$TEST_TMPDIR/.claude/skills" ]
}

@test "install.sh --dry-run does not create ~/.dexter-backup/" {
  run bash "$INSTALL_SH" --agent claude-code --dry-run
  [ ! -d "$TEST_TMPDIR/.dexter-backup" ]
}

# ─── install.sh — dry-run output for claude-code ────────────────────────────

@test "install.sh --dry-run outputs DRY RUN MODE notice" {
  run bash "$INSTALL_SH" --agent claude-code --dry-run
  [[ "$output" == *"DRY RUN"* ]]
}

@test "install.sh --dry-run mentions target agent claude-code" {
  run bash "$INSTALL_SH" --agent claude-code --dry-run
  [[ "$output" == *"claude-code"* ]]
}

@test "install.sh --dry-run mentions expected system prompt path" {
  run bash "$INSTALL_SH" --agent claude-code --dry-run
  # Expected: ~/.claude/CLAUDE.md — shown as $HOME/.claude/CLAUDE.md in output
  [[ "$output" == *".claude/CLAUDE.md"* ]]
}

@test "install.sh --dry-run mentions expected skills dir" {
  run bash "$INSTALL_SH" --agent claude-code --dry-run
  [[ "$output" == *".claude/skills"* ]]
}

@test "install.sh --dry-run mentions expected settings file" {
  run bash "$INSTALL_SH" --agent claude-code --dry-run
  [[ "$output" == *".claude/settings.json"* ]]
}

@test "install.sh --dry-run exits with status 0" {
  run bash "$INSTALL_SH" --agent claude-code --dry-run
  [ "$status" -eq 0 ]
}

# ─── uninstall.sh — no backup exists ────────────────────────────────────────

@test "uninstall.sh exits with non-zero when no backup dir exists" {
  # TEST_TMPDIR has no .dexter-backup — uninstall.sh should fail with exit 1
  run bash "$UNINSTALL_SH"
  [ "$status" -ne 0 ]
}

@test "uninstall.sh prints an error (not a silent crash) when no backup exists" {
  run bash "$UNINSTALL_SH"
  # Output must be non-empty — script should explain what's wrong
  [ -n "$output" ]
}

@test "uninstall.sh error message mentions backup directory" {
  run bash "$UNINSTALL_SH"
  [[ "$output" == *"backup"* ]] || [[ "$output" == *"Backup"* ]] || [[ "$output" == *"BACKUP"* ]]
}

@test "uninstall.sh --dry-run exits non-zero when no backup exists" {
  run bash "$UNINSTALL_SH" --dry-run
  [ "$status" -ne 0 ]
}

@test "uninstall.sh exits with non-zero on unknown argument" {
  run bash "$UNINSTALL_SH" --unknown-flag
  [ "$status" -ne 0 ]
}

# ─── uninstall.sh — --backup-dir pointing to empty dir warns, not crashes ───

@test "uninstall.sh --backup-dir with no manifest warns and exits 0" {
  # Provide an existing but empty backup dir — should warn about no manifest
  local fake_backup="$TEST_TMPDIR/fake-backup"
  mkdir -p "$fake_backup"

  run bash "$UNINSTALL_SH" --backup-dir "$fake_backup" --dry-run
  # Should warn about missing manifest but NOT exit with a shell crash (trap or set -e on missing file)
  [ "$status" -eq 0 ]
}

@test "uninstall.sh --backup-dir with no manifest outputs a warning" {
  local fake_backup="$TEST_TMPDIR/fake-backup"
  mkdir -p "$fake_backup"

  run bash "$UNINSTALL_SH" --backup-dir "$fake_backup" --dry-run
  [[ "$output" == *"manifest"* ]] || [[ "$output" == *"Manifest"* ]] || [[ "$output" == *"dry-run"* ]]
}
