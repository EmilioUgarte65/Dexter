package installer

import (
	"fmt"
	"os"
	"path/filepath"
)

// FileReplace writes content directly to targetPath, replacing any existing file.
// Parent directories are created as needed.
// dryRun=true validates without writing.
func FileReplace(targetPath string, content []byte, dryRun bool) error {
	if dryRun {
		fmt.Printf("[dry-run] file_replace: would write %d bytes to %s\n", len(content), targetPath)
		return nil
	}

	if err := os.MkdirAll(filepath.Dir(targetPath), 0o755); err != nil {
		return fmt.Errorf("file_replace: mkdir %q: %w", filepath.Dir(targetPath), err)
	}

	if err := os.WriteFile(targetPath, content, 0o644); err != nil {
		return fmt.Errorf("file_replace: write %q: %w", targetPath, err)
	}
	return nil
}
