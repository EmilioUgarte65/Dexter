package installer

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// MCPConfigFile writes a single MCP config JSON to settingsFile, deep-merging
// if the file already exists.
//
// mcpJSON is the MCP configuration to write/merge (typically from embedded assets).
// dryRun=true prints the result without writing.
func MCPConfigFile(settingsFile string, mcpJSON []byte, dryRun bool) error {
	var existingJSON []byte
	existing, err := os.ReadFile(settingsFile)
	if err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("mcp_config: read %q: %w", settingsFile, err)
	}
	if err == nil {
		existingJSON = existing
	}

	result, err := ApplyOverlay(existingJSON, mcpJSON)
	if err != nil {
		return fmt.Errorf("mcp_config: merge: %w", err)
	}

	// Validate output is parseable JSON.
	var validate map[string]any
	if err := json.Unmarshal(result.Merged, &validate); err != nil {
		return fmt.Errorf("mcp_config: merged result is invalid JSON: %w", err)
	}

	if dryRun {
		fmt.Printf("[dry-run] mcp_config: would write to %s:\n%s\n", settingsFile, string(result.Merged))
		return nil
	}

	if !result.Changed {
		return nil
	}

	if err := os.MkdirAll(filepath.Dir(settingsFile), 0o755); err != nil {
		return fmt.Errorf("mcp_config: mkdir %q: %w", filepath.Dir(settingsFile), err)
	}

	if err := os.WriteFile(settingsFile, result.Merged, 0o644); err != nil {
		return fmt.Errorf("mcp_config: write %q: %w", settingsFile, err)
	}
	return nil
}
