package installer

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/gentleman-programming/dexter/internal/backup"
)

// TestRollbackOnMCPFailure verifies that when MCP configuration fails, a
// backup.Restore call correctly returns all files to their pre-install state,
// and that the backup directory is preserved after restore.
func TestRollbackOnMCPFailure(t *testing.T) {
	homeDir := t.TempDir()
	configDir := filepath.Join(homeDir, ".claude")

	if err := os.MkdirAll(configDir, 0o755); err != nil {
		t.Fatalf("setup: mkdir: %v", err)
	}

	// Write original files that will be backed up.
	systemFile := filepath.Join(configDir, "CLAUDE.md")
	originalContent := "# Original Config\n"
	if err := os.WriteFile(systemFile, []byte(originalContent), 0o644); err != nil {
		t.Fatalf("setup: write CLAUDE.md: %v", err)
	}

	settingsFile := filepath.Join(configDir, "settings.json")
	originalSettings := `{"theme":"dark"}`
	if err := os.WriteFile(settingsFile, []byte(originalSettings), 0o644); err != nil {
		t.Fatalf("setup: write settings.json: %v", err)
	}

	// Snapshot before install.
	backupFiles := []string{systemFile, settingsFile}
	manifest, err := backup.Snapshot(homeDir, backupFiles)
	if err != nil {
		t.Fatalf("Snapshot: %v", err)
	}
	if len(manifest.Entries) != 2 {
		t.Fatalf("expected 2 manifest entries, got %d", len(manifest.Entries))
	}

	// Record the backup directory so we can verify it survives restore.
	backupDir := filepath.Dir(manifest.Entries[0].BackupPath)

	// Simulate partial install: modify CLAUDE.md (step succeeds).
	if err := os.WriteFile(systemFile, []byte("# Modified by install\n"), 0o644); err != nil {
		t.Fatalf("simulate install: write CLAUDE.md: %v", err)
	}

	// Simulate MCP step failure: pass a malformed overlay JSON.
	malformedJSON := []byte(`{"mcpServers": INVALID}`)
	_, mcpErr := ApplyOverlay(nil, malformedJSON)
	if mcpErr == nil {
		t.Fatal("expected ApplyOverlay to fail on malformed JSON, but it succeeded")
	}

	// Verify: because mcpErr != nil we trigger rollback via backup.Restore.
	if err := backup.Restore(manifest); err != nil {
		t.Fatalf("Restore: %v", err)
	}

	// CLAUDE.md must be back to original content.
	restored, err := os.ReadFile(systemFile)
	if err != nil {
		t.Fatalf("read restored CLAUDE.md: %v", err)
	}
	if string(restored) != originalContent {
		t.Errorf("CLAUDE.md after restore: got %q, want %q", string(restored), originalContent)
	}

	// settings.json must also be restored.
	restoredSettings, err := os.ReadFile(settingsFile)
	if err != nil {
		t.Fatalf("read restored settings.json: %v", err)
	}
	if string(restoredSettings) != originalSettings {
		t.Errorf("settings.json after restore: got %q, want %q", string(restoredSettings), originalSettings)
	}

	// Backup directory must NOT be deleted after restore.
	if _, err := os.Stat(backupDir); os.IsNotExist(err) {
		t.Errorf("backup dir was deleted after restore: %s", backupDir)
	}
}
