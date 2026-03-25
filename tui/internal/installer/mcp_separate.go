package installer

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
)

// CopySeparateMCPFiles copies all MCP JSON files from the embedded mcp/ directory
// to mcpDir on the filesystem.
//
// Each embedded file is written to mcpDir/{filename}. Existing files are overwritten.
// dryRun=true reports what would change without writing.
//
// fsys should be the sub-filesystem rooted at the embedded mcp/ directory.
func CopySeparateMCPFiles(mcpDir string, fsys fs.FS, dryRun bool) error {
	var errs []error

	entries, err := fs.ReadDir(fsys, ".")
	if err != nil {
		return fmt.Errorf("mcp_separate: read embedded mcp dir: %w", err)
	}

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		data, err := fs.ReadFile(fsys, entry.Name())
		if err != nil {
			errs = append(errs, fmt.Errorf("mcp_separate: read %q: %w", entry.Name(), err))
			continue
		}

		target := filepath.Join(mcpDir, entry.Name())

		if dryRun {
			fmt.Printf("[dry-run] mcp_separate: would write %s\n", target)
			continue
		}

		if mkErr := os.MkdirAll(mcpDir, 0o755); mkErr != nil {
			errs = append(errs, fmt.Errorf("mcp_separate: mkdir %q: %w", mcpDir, mkErr))
			continue
		}

		if writeErr := os.WriteFile(target, data, 0o644); writeErr != nil {
			errs = append(errs, fmt.Errorf("mcp_separate: write %q: %w", target, writeErr))
		}
	}

	return joinErrors(errs)
}
