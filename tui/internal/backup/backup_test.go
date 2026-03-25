package backup

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// helpers ----------------------------------------------------------------

func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("writeFile: mkdir %s: %v", path, err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("writeFile: %s: %v", path, err)
	}
}

func readFile(t *testing.T, path string) []byte {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("readFile: %s: %v", path, err)
	}
	return data
}

// tests ------------------------------------------------------------------

func TestSnapshot(t *testing.T) {
	home := t.TempDir()

	// Create 3 source files under home.
	src1 := filepath.Join(home, ".config", "agent", "config.json")
	src2 := filepath.Join(home, ".config", "agent", "settings.toml")
	src3 := filepath.Join(home, ".local", "share", "agent", "data.txt")

	writeFile(t, src1, `{"key":"value"}`)
	writeFile(t, src2, `[section]\nfoo = "bar"`)
	writeFile(t, src3, "some data")

	files := []string{src1, src2, src3}

	m, err := Snapshot(home, files)
	if err != nil {
		t.Fatalf("Snapshot returned error: %v", err)
	}

	if got, want := len(m.Entries), 3; got != want {
		t.Fatalf("manifest entries: got %d, want %d", got, want)
	}

	for _, entry := range m.Entries {
		if _, err := os.Stat(entry.BackupPath); err != nil {
			t.Errorf("backup file missing: %s: %v", entry.BackupPath, err)
		}
		// Content must match.
		orig := readFile(t, entry.OriginalPath)
		bkup := readFile(t, entry.BackupPath)
		if !bytes.Equal(orig, bkup) {
			t.Errorf("content mismatch for %s", entry.OriginalPath)
		}
	}
}

func TestSnapshot_SkipsMissing(t *testing.T) {
	home := t.TempDir()

	missing := filepath.Join(home, "does-not-exist.txt")

	m, err := Snapshot(home, []string{missing})
	if err != nil {
		t.Fatalf("Snapshot should not fail for missing files, got: %v", err)
	}

	if got := len(m.Entries); got != 0 {
		t.Fatalf("expected 0 entries, got %d", got)
	}
}

func TestWriteReadManifest(t *testing.T) {
	dir := t.TempDir()

	ts := time.Date(2026, 3, 24, 12, 0, 0, 0, time.UTC)
	original := Manifest{
		CreatedAt: ts,
		Entries: []ManifestEntry{
			{OriginalPath: "/home/user/.config/a.json", BackupPath: "/home/user/.dexter/backups/ts/a.json"},
			{OriginalPath: "/home/user/.config/b.toml", BackupPath: "/home/user/.dexter/backups/ts/b.toml"},
		},
	}

	if err := WriteManifest(dir, original); err != nil {
		t.Fatalf("WriteManifest: %v", err)
	}

	got, err := ReadManifest(dir)
	if err != nil {
		t.Fatalf("ReadManifest: %v", err)
	}

	if !got.CreatedAt.Equal(original.CreatedAt) {
		t.Errorf("CreatedAt: got %v, want %v", got.CreatedAt, original.CreatedAt)
	}
	if len(got.Entries) != len(original.Entries) {
		t.Fatalf("Entries len: got %d, want %d", len(got.Entries), len(original.Entries))
	}
	for i, e := range original.Entries {
		g := got.Entries[i]
		if g.OriginalPath != e.OriginalPath || g.BackupPath != e.BackupPath {
			t.Errorf("entry[%d] mismatch: got %+v, want %+v", i, g, e)
		}
	}
}

func TestRestore(t *testing.T) {
	home := t.TempDir()

	src1 := filepath.Join(home, "a.txt")
	src2 := filepath.Join(home, "sub", "b.txt")
	src3 := filepath.Join(home, "sub", "nested", "c.txt")

	writeFile(t, src1, "content-a")
	writeFile(t, src2, "content-b")
	writeFile(t, src3, "content-c")

	m, err := Snapshot(home, []string{src1, src2, src3})
	if err != nil {
		t.Fatalf("Snapshot: %v", err)
	}
	if len(m.Entries) != 3 {
		t.Fatalf("expected 3 entries, got %d", len(m.Entries))
	}

	// Delete originals.
	for _, p := range []string{src1, src2, src3} {
		if err := os.Remove(p); err != nil {
			t.Fatalf("remove %s: %v", p, err)
		}
	}

	// Restore.
	if err := Restore(m); err != nil {
		t.Fatalf("Restore: %v", err)
	}

	// Verify byte-for-byte.
	expected := map[string]string{
		src1: "content-a",
		src2: "content-b",
		src3: "content-c",
	}
	for path, want := range expected {
		got := string(readFile(t, path))
		if got != want {
			t.Errorf("restored %s: got %q, want %q", path, got, want)
		}
	}
}

func TestRestore_PartialFailure(t *testing.T) {
	home := t.TempDir()

	// Build a manifest that references a backup file that does NOT exist.
	m := Manifest{
		CreatedAt: time.Now().UTC(),
		Entries: []ManifestEntry{
			{
				BackupPath:   filepath.Join(home, "nonexistent-backup.txt"),
				OriginalPath: filepath.Join(home, "target.txt"),
			},
		},
	}

	err := Restore(m)
	if err == nil {
		t.Fatal("expected error for missing backup file, got nil")
	}
	// Must not panic — reaching here means it returned gracefully.
	t.Logf("Restore correctly returned error: %v", err)
}
