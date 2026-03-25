package installer

import (
	"bufio"
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

const dexterTOMLMarker = "# Dexter MCP servers"

// dexterTOMLBlock is the TOML block appended for MCP servers.
const dexterTOMLBlock = `
# Dexter MCP servers
[mcp.engram]
command = "engram"
args = ["mcp", "--tools=agent"]

[mcp.context7]
command = "npx"
args = ["-y", "@upstash/context7-mcp"]
`

// AppendTOMLBlock appends the Dexter MCP TOML block to targetFile if not already present.
//
// Detection: performs a string scan for the marker comment; no TOML parse/re-emit.
// This is an append-only operation — existing content is never modified.
// dryRun=true reports what would happen without writing.
func AppendTOMLBlock(targetFile string, dryRun bool) error {
	existing, err := os.ReadFile(targetFile)
	if err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("toml: read %q: %w", targetFile, err)
	}

	// Idempotency: check if marker already present via line scan.
	if containsTOMLMarker(existing) {
		if dryRun {
			fmt.Printf("[dry-run] toml: %s already has Dexter block — skip\n", targetFile)
		}
		return nil
	}

	if dryRun {
		fmt.Printf("[dry-run] toml: would append Dexter MCP block to %s\n", targetFile)
		return nil
	}

	if err := os.MkdirAll(filepath.Dir(targetFile), 0o755); err != nil {
		return fmt.Errorf("toml: mkdir %q: %w", filepath.Dir(targetFile), err)
	}

	f, err := os.OpenFile(targetFile, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return fmt.Errorf("toml: open %q: %w", targetFile, err)
	}
	defer f.Close()

	if _, err := f.WriteString(dexterTOMLBlock); err != nil {
		return fmt.Errorf("toml: write %q: %w", targetFile, err)
	}
	return nil
}

// containsTOMLMarker checks whether data contains the Dexter TOML marker line.
func containsTOMLMarker(data []byte) bool {
	scanner := bufio.NewScanner(bytes.NewReader(data))
	for scanner.Scan() {
		if strings.TrimSpace(scanner.Text()) == dexterTOMLMarker {
			return true
		}
	}
	return false
}
