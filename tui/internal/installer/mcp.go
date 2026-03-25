package installer

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
)

// ConfigureMCP reads the embedded MCP configuration for agentID and deep-merges
// it into mcpFile on the filesystem.
//
// Behaviour:
//   - Reads embedded mcp/{agentID}.json from fsys.
//   - If mcpFile does not exist, the embedded content is written as-is.
//   - If mcpFile exists, deep-merges the embedded content into the existing JSON.
//   - dryRun=true prints the merged result without writing.
//
// fsys should be the sub-filesystem rooted at the embedded mcp/ directory
// (i.e. from assets.ReadMCPFS()).
func ConfigureMCP(mcpFile string, fsys fs.FS, agentID string, dryRun bool) error {
	embeddedPath := agentID + ".json"
	embeddedData, err := fs.ReadFile(fsys, embeddedPath)
	if err != nil {
		return fmt.Errorf("configure_mcp: read embedded mcp/%s: %w", embeddedPath, err)
	}

	// Read existing file (may not exist).
	var existing []byte
	existing, err = os.ReadFile(mcpFile)
	if err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("configure_mcp: read %q: %w", mcpFile, err)
	}

	result, err := ApplyOverlay(existing, embeddedData)
	if err != nil {
		return fmt.Errorf("configure_mcp: merge: %w", err)
	}

	if dryRun {
		fmt.Printf("[dry-run] configure_mcp: merged result for %s:\n%s\n", mcpFile, string(result.Merged))
		return nil
	}

	if !result.Changed {
		return nil
	}

	if err := os.MkdirAll(filepath.Dir(mcpFile), 0o755); err != nil {
		return fmt.Errorf("configure_mcp: mkdir %q: %w", filepath.Dir(mcpFile), err)
	}

	if err := os.WriteFile(mcpFile, result.Merged, 0o644); err != nil {
		return fmt.Errorf("configure_mcp: write %q: %w", mcpFile, err)
	}
	return nil
}
