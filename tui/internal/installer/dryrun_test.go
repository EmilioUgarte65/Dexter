package installer

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/gentleman-programming/dexter/internal/assets"
)

// TestDryRunWritesNoFiles verifies that running all installer functions with
// dryRun=true leaves the filesystem byte-for-byte identical to its state
// before the call — no files created, no files modified.
func TestDryRunWritesNoFiles(t *testing.T) {
	homeDir := t.TempDir()

	// Pre-create the claude-code config dir (simulating existing install).
	configDir := filepath.Join(homeDir, ".claude")
	if err := os.MkdirAll(configDir, 0o755); err != nil {
		t.Fatalf("setup: mkdir configDir: %v", err)
	}

	// Snapshot the directory tree before dry-run calls.
	before := collectFiles(t, homeDir)

	// --- InjectPrompt dry-run ---
	systemFile := filepath.Join(configDir, "CLAUDE.md")
	content := assets.MustRead("DEXTER.md")
	if err := InjectPrompt(configDir, systemFile, content, true); err != nil {
		t.Fatalf("InjectPrompt dry-run: %v", err)
	}

	// --- CopySkills dry-run ---
	skillsFS, err := assets.ReadSkillsFS()
	if err != nil {
		t.Fatalf("ReadSkillsFS: %v", err)
	}
	skillsDir := filepath.Join(configDir, "skills")
	if err := CopySkills(skillsDir, skillsFS, true); err != nil {
		t.Fatalf("CopySkills dry-run: %v", err)
	}

	// --- CopySeparateMCPFiles dry-run (claude-code uses MCPSeparateFiles) ---
	mcpFS, err := assets.ReadMCPFS()
	if err != nil {
		t.Fatalf("ReadMCPFS: %v", err)
	}
	mcpDir := filepath.Join(configDir, "mcp")
	if err := CopySeparateMCPFiles(mcpDir, mcpFS, true); err != nil {
		t.Fatalf("CopySeparateMCPFiles dry-run: %v", err)
	}

	// --- Snapshot the directory tree after dry-run calls ---
	after := collectFiles(t, homeDir)

	// Assert: no new files appeared and no existing files changed.
	for path, afterContent := range after {
		beforeContent, existed := before[path]
		if !existed {
			t.Errorf("dry-run created new file: %s", path)
			continue
		}
		if string(beforeContent) != string(afterContent) {
			t.Errorf("dry-run modified file: %s", path)
		}
	}
	for path := range before {
		if _, ok := after[path]; !ok {
			t.Errorf("dry-run deleted file: %s", path)
		}
	}
}

// collectFiles walks root and returns a map of relative path → content.
func collectFiles(t *testing.T, root string) map[string][]byte {
	t.Helper()
	result := make(map[string][]byte)
	err := filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(root, path)
		result[rel] = data
		return nil
	})
	if err != nil {
		t.Fatalf("collectFiles: %v", err)
	}
	return result
}
