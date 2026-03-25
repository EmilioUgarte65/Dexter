package installer

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/gentleman-programming/dexter/internal/assets"
	"github.com/gentleman-programming/dexter/internal/backup"
)

// TestFullClaudeCodeInstall runs the full installation flow for claude-code
// against a temp home directory and verifies all post-conditions.
func TestFullClaudeCodeInstall(t *testing.T) {
	homeDir := t.TempDir()
	configDir := filepath.Join(homeDir, ".claude")

	// Pre-create the config dir and a minimal CLAUDE.md.
	if err := os.MkdirAll(configDir, 0o755); err != nil {
		t.Fatalf("setup: mkdir: %v", err)
	}
	systemFile := filepath.Join(configDir, "CLAUDE.md")
	if err := os.WriteFile(systemFile, []byte("# My Config\n"), 0o644); err != nil {
		t.Fatalf("setup: write CLAUDE.md: %v", err)
	}

	// Files that claude-code backs up.
	backupFiles := []string{
		systemFile,
		filepath.Join(configDir, "settings.json"),
	}

	// 1. Snapshot.
	manifest, err := backup.Snapshot(homeDir, backupFiles)
	if err != nil {
		t.Fatalf("Snapshot: %v", err)
	}

	// Write manifest to disk so ReadManifest can retrieve it.
	backupDir := filepath.Join(homeDir, ".dexter", "backups", "test-install")
	if err := os.MkdirAll(backupDir, 0o755); err != nil {
		t.Fatalf("mkdir backupDir: %v", err)
	}
	if err := backup.WriteManifest(backupDir, manifest); err != nil {
		t.Fatalf("WriteManifest: %v", err)
	}

	// 2. InjectPrompt (non-dry-run).
	content := assets.MustRead("DEXTER.md")
	if err := InjectPrompt(configDir, systemFile, content, false); err != nil {
		t.Fatalf("InjectPrompt: %v", err)
	}

	// 3. CopySkills.
	skillsFS, err := assets.ReadSkillsFS()
	if err != nil {
		t.Fatalf("ReadSkillsFS: %v", err)
	}
	skillsDir := filepath.Join(configDir, "skills")
	if err := CopySkills(skillsDir, skillsFS, false); err != nil {
		t.Fatalf("CopySkills: %v", err)
	}

	// 4. CopySeparateMCPFiles (claude-code MCPStrategy = MCPSeparateFiles).
	mcpFS, err := assets.ReadMCPFS()
	if err != nil {
		t.Fatalf("ReadMCPFS: %v", err)
	}
	mcpDir := filepath.Join(configDir, "mcp")
	if err := CopySeparateMCPFiles(mcpDir, mcpFS, false); err != nil {
		t.Fatalf("CopySeparateMCPFiles: %v", err)
	}

	// --- Assertions ---

	// CLAUDE.md must contain the dexter:core block.
	claudeMD, err := os.ReadFile(systemFile)
	if err != nil {
		t.Fatalf("read CLAUDE.md: %v", err)
	}
	if !bytes.Contains(claudeMD, []byte("<!-- dexter:core -->")) {
		t.Errorf("CLAUDE.md missing <!-- dexter:core --> block")
	}

	// Skills dir must not be empty.
	skillsEntries, err := os.ReadDir(skillsDir)
	if err != nil {
		t.Fatalf("ReadDir skillsDir: %v", err)
	}
	if len(skillsEntries) == 0 {
		t.Errorf("skills dir is empty after install")
	}

	// Backup manifest must be readable and valid.
	readBack, err := backup.ReadManifest(backupDir)
	if err != nil {
		t.Fatalf("ReadManifest: %v", err)
	}
	if readBack.CreatedAt.IsZero() {
		t.Errorf("manifest CreatedAt is zero")
	}

	// MCP dir must contain valid JSON files.
	mcpEntries, err := os.ReadDir(mcpDir)
	if err != nil {
		t.Fatalf("ReadDir mcpDir: %v", err)
	}
	if len(mcpEntries) == 0 {
		t.Errorf("mcp dir is empty after install")
	}
	for _, entry := range mcpEntries {
		if entry.IsDir() {
			continue
		}
		data, err := os.ReadFile(filepath.Join(mcpDir, entry.Name()))
		if err != nil {
			t.Errorf("read mcp file %s: %v", entry.Name(), err)
			continue
		}
		if !json.Valid(data) {
			t.Errorf("mcp file %s is not valid JSON", entry.Name())
		}
	}
}
