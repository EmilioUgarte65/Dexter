package installer

import (
	"fmt"
	"os"
	"path/filepath"
)

// AppendToFile appends content to targetPath.
// The file and any parent directories are created if absent.
// dryRun=true validates without writing.
func AppendToFile(targetPath string, content []byte, dryRun bool) error {
	if dryRun {
		fmt.Printf("[dry-run] append_to_file: would append %d bytes to %s\n", len(content), targetPath)
		return nil
	}

	if err := os.MkdirAll(filepath.Dir(targetPath), 0o755); err != nil {
		return fmt.Errorf("append_to_file: mkdir %q: %w", filepath.Dir(targetPath), err)
	}

	f, err := os.OpenFile(targetPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return fmt.Errorf("append_to_file: open %q: %w", targetPath, err)
	}
	defer f.Close()

	if _, err := f.Write(content); err != nil {
		return fmt.Errorf("append_to_file: write %q: %w", targetPath, err)
	}
	return nil
}
