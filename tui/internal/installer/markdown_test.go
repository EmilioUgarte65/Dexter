package installer

import (
	"os"
	"path/filepath"
	"testing"
)

func TestInjectPrompt_FirstInjection(t *testing.T) {
	dir := t.TempDir()
	systemFile := filepath.Join(dir, "CLAUDE.md")
	original := "# My existing content\n\nSome text here.\n"

	if err := os.WriteFile(systemFile, []byte(original), 0o644); err != nil {
		t.Fatal(err)
	}

	content := []byte("# Dexter Config\nThis is the dexter block.\n")
	if err := InjectPrompt(dir, systemFile, content, false); err != nil {
		t.Fatalf("InjectPrompt() error = %v", err)
	}

	result, err := os.ReadFile(systemFile)
	if err != nil {
		t.Fatal(err)
	}

	resultStr := string(result)

	// Original content preserved.
	if !containsStr(resultStr, "My existing content") {
		t.Error("original content not preserved")
	}
	// Open marker present exactly once.
	if count := countOccurrences(resultStr, markerOpen); count != 1 {
		t.Errorf("markerOpen count = %d, want 1", count)
	}
	// Close marker present exactly once.
	if count := countOccurrences(resultStr, markerClose); count != 1 {
		t.Errorf("markerClose count = %d, want 1", count)
	}
	// Content appears between markers.
	if !containsStr(resultStr, "Dexter Config") {
		t.Error("injected content not found")
	}
	// Block is appended (open marker appears after original content).
	origIdx := indexStr(resultStr, "My existing content")
	markerIdx := indexStr(resultStr, markerOpen)
	if markerIdx < origIdx {
		t.Error("Dexter block should be appended after original content")
	}
}

func TestInjectPrompt_FileCreated(t *testing.T) {
	dir := t.TempDir()
	systemFile := filepath.Join(dir, "CLAUDE.md")
	// File does not exist yet.

	content := []byte("# Dexter\n")
	if err := InjectPrompt(dir, systemFile, content, false); err != nil {
		t.Fatalf("InjectPrompt() error = %v", err)
	}

	result, err := os.ReadFile(systemFile)
	if err != nil {
		t.Fatal(err)
	}
	if !containsStr(string(result), markerOpen) {
		t.Error("file should contain open marker")
	}
}

func TestInjectPrompt_UpdateInjection(t *testing.T) {
	dir := t.TempDir()
	systemFile := filepath.Join(dir, "CLAUDE.md")

	// First write with old content.
	initial := "# Preamble\n\n" + markerOpen + "\n# Old Content\n" + markerClose + "\n"
	if err := os.WriteFile(systemFile, []byte(initial), 0o644); err != nil {
		t.Fatal(err)
	}

	newContent := []byte("# New Dexter Content\nUpdated.\n")
	if err := InjectPrompt(dir, systemFile, newContent, false); err != nil {
		t.Fatalf("InjectPrompt() error = %v", err)
	}

	result, err := os.ReadFile(systemFile)
	if err != nil {
		t.Fatal(err)
	}
	resultStr := string(result)

	// Old content gone.
	if containsStr(resultStr, "Old Content") {
		t.Error("old content should be replaced")
	}
	// New content present.
	if !containsStr(resultStr, "New Dexter Content") {
		t.Error("new content should be present")
	}
	// Preamble preserved.
	if !containsStr(resultStr, "Preamble") {
		t.Error("preamble should be preserved")
	}
	// Markers not duplicated.
	if count := countOccurrences(resultStr, markerOpen); count != 1 {
		t.Errorf("markerOpen count = %d, want 1", count)
	}
	if count := countOccurrences(resultStr, markerClose); count != 1 {
		t.Errorf("markerClose count = %d, want 1", count)
	}
}

func TestInjectPrompt_Idempotent(t *testing.T) {
	dir := t.TempDir()
	systemFile := filepath.Join(dir, "CLAUDE.md")
	content := []byte("# Dexter Block\nSome content.\n")

	// First injection.
	if err := InjectPrompt(dir, systemFile, content, false); err != nil {
		t.Fatalf("first inject error: %v", err)
	}
	after1, _ := os.ReadFile(systemFile)

	// Second injection with same content.
	if err := InjectPrompt(dir, systemFile, content, false); err != nil {
		t.Fatalf("second inject error: %v", err)
	}
	after2, _ := os.ReadFile(systemFile)

	if string(after1) != string(after2) {
		t.Errorf("idempotency violated:\nafter1:\n%s\nafter2:\n%s", after1, after2)
	}
}

func TestInjectPrompt_OriginalContentPreserved(t *testing.T) {
	dir := t.TempDir()
	systemFile := filepath.Join(dir, "CLAUDE.md")

	// Initial file with specific content above and below where block will go.
	original := "# My Rules\n\nDo this. Do that.\n"
	if err := os.WriteFile(systemFile, []byte(original), 0o644); err != nil {
		t.Fatal(err)
	}

	content := []byte("# Dexter\n")
	if err := InjectPrompt(dir, systemFile, content, false); err != nil {
		t.Fatalf("InjectPrompt() error = %v", err)
	}

	result, _ := os.ReadFile(systemFile)
	resultStr := string(result)

	if !containsStr(resultStr, "My Rules") {
		t.Error("heading not preserved")
	}
	if !containsStr(resultStr, "Do this. Do that.") {
		t.Error("body not preserved")
	}
}

func TestInjectPrompt_DryRun(t *testing.T) {
	dir := t.TempDir()
	systemFile := filepath.Join(dir, "CLAUDE.md")
	original := "# Original\n"
	if err := os.WriteFile(systemFile, []byte(original), 0o644); err != nil {
		t.Fatal(err)
	}

	content := []byte("# Dexter\n")
	if err := InjectPrompt(dir, systemFile, content, true); err != nil {
		t.Fatalf("dry-run InjectPrompt() error = %v", err)
	}

	// File should be untouched.
	result, _ := os.ReadFile(systemFile)
	if string(result) != original {
		t.Error("dry-run must not modify the file")
	}
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func containsStr(s, substr string) bool {
	return indexStr(s, substr) >= 0
}

func indexStr(s, substr string) int {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return i
		}
	}
	return -1
}

func countOccurrences(s, substr string) int {
	count := 0
	start := 0
	for {
		idx := indexStr(s[start:], substr)
		if idx < 0 {
			break
		}
		count++
		start += idx + len(substr)
	}
	return count
}
