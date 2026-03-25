package backup

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Snapshot creates a timestamped backup of the given files under ~/.dexter/backups/{timestamp}/.
// Files that do not exist on disk are silently skipped — they are not treated as errors.
// Returns a Manifest describing every file that was actually copied.
func Snapshot(homeDir string, files []string) (Manifest, error) {
	ts := time.Now().UTC()
	backupDir := filepath.Join(homeDir, ".dexter", "backups", ts.Format("20060102T150405Z"))

	if err := os.MkdirAll(backupDir, 0o755); err != nil {
		return Manifest{}, fmt.Errorf("backup: create backup dir: %w", err)
	}

	var entries []ManifestEntry
	for _, src := range files {
		if _, err := os.Stat(src); os.IsNotExist(err) {
			// File not created yet — skip silently.
			continue
		}

		// Strip homeDir prefix to reconstruct relative path inside the backup dir.
		rel, err := relativeToHome(homeDir, src)
		if err != nil {
			return Manifest{}, fmt.Errorf("backup: resolve relative path for %q: %w", src, err)
		}

		dst := filepath.Join(backupDir, rel)
		if err := copyFile(src, dst); err != nil {
			return Manifest{}, fmt.Errorf("backup: copy %q: %w", src, err)
		}

		entries = append(entries, ManifestEntry{
			OriginalPath: src,
			BackupPath:   dst,
		})
	}

	m := Manifest{
		CreatedAt: ts,
		Entries:   entries,
	}
	return m, nil
}

// relativeToHome returns the portion of absPath after homeDir.
// If absPath is not under homeDir the full path is used as-is (leading slash stripped).
func relativeToHome(homeDir, absPath string) (string, error) {
	rel, err := filepath.Rel(homeDir, absPath)
	if err != nil {
		return "", err
	}
	// filepath.Rel may return paths starting with ".." when absPath is outside homeDir.
	if strings.HasPrefix(rel, "..") {
		// Fall back to using the absolute path stripped of its leading slash.
		rel = strings.TrimPrefix(absPath, string(os.PathSeparator))
	}
	return rel, nil
}

// copyFile copies src to dst, creating any intermediate directories required.
func copyFile(src, dst string) error {
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return err
	}

	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()

	if _, err := io.Copy(out, in); err != nil {
		return err
	}
	return out.Close()
}
