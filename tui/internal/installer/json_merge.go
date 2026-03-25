package installer

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// JSONMerge reads an existing target JSON file (or uses {} if absent), deep-merges
// overlayJSON into it, and writes the result back to targetFile.
//
// Fails if the resulting JSON is invalid.
// dryRun=true prints the merged result without writing.
func JSONMerge(targetFile string, overlayJSON []byte, dryRun bool) error {
	var existingJSON []byte
	existing, err := os.ReadFile(targetFile)
	if err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("json_merge: read %q: %w", targetFile, err)
	}
	if err == nil {
		existingJSON = existing
	}

	result, err := ApplyOverlay(existingJSON, overlayJSON)
	if err != nil {
		return fmt.Errorf("json_merge: merge: %w", err)
	}

	// Validate: re-parse the output.
	var validate map[string]any
	if err := json.Unmarshal(result.Merged, &validate); err != nil {
		return fmt.Errorf("json_merge: merged result is invalid JSON: %w", err)
	}

	if dryRun {
		fmt.Printf("[dry-run] json_merge: merged result for %s:\n%s\n", targetFile, string(result.Merged))
		return nil
	}

	if !result.Changed {
		return nil
	}

	if err := os.MkdirAll(filepath.Dir(targetFile), 0o755); err != nil {
		return fmt.Errorf("json_merge: mkdir %q: %w", filepath.Dir(targetFile), err)
	}

	if err := os.WriteFile(targetFile, result.Merged, 0o644); err != nil {
		return fmt.Errorf("json_merge: write %q: %w", targetFile, err)
	}
	return nil
}
