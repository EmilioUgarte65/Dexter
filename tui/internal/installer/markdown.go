package installer

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
)

const (
	markerOpen  = "<!-- dexter:core -->"
	markerClose = "<!-- /dexter:core -->"
)

// InjectPrompt inserts or updates the Dexter block in systemFile.
//
// Behaviour:
//   - If systemFile does not contain markerOpen, the block is appended at the end.
//   - If systemFile already contains markerOpen, the content between the markers is replaced.
//   - Idempotent: calling with identical content leaves the file byte-for-byte identical.
//   - If systemFile does not exist, it is created (including parent directories).
//   - dryRun=true validates the operation but does not write any files.
//
// configDir is used only to ensure the parent directory exists; pass the agent
// config dir (e.g. ~/.claude) so that mkdir -p is done correctly.
func InjectPrompt(configDir, systemFile string, content []byte, dryRun bool) error {
	if dryRun {
		return validateInjectPrompt(systemFile, content)
	}

	// Ensure parent directory exists.
	if err := os.MkdirAll(filepath.Dir(systemFile), 0o755); err != nil {
		return fmt.Errorf("inject_prompt: mkdir %q: %w", filepath.Dir(systemFile), err)
	}

	existing, err := os.ReadFile(systemFile)
	if err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("inject_prompt: read %q: %w", systemFile, err)
	}

	var newContent []byte
	if bytes.Contains(existing, []byte(markerOpen)) {
		newContent = replaceBlock(existing, content)
	} else {
		newContent = appendBlock(existing, content)
	}

	// Idempotency check: skip write if identical.
	if bytes.Equal(existing, newContent) {
		return nil
	}

	if err := os.WriteFile(systemFile, newContent, 0o644); err != nil {
		return fmt.Errorf("inject_prompt: write %q: %w", systemFile, err)
	}
	return nil
}

// validateInjectPrompt checks that the operation is logically valid without writing.
func validateInjectPrompt(systemFile string, content []byte) error {
	if len(content) == 0 {
		return fmt.Errorf("inject_prompt: content is empty")
	}
	_ = systemFile // path existence is not checked in dry-run
	return nil
}

// replaceBlock replaces the content between the Dexter markers, preserving
// the markers themselves and all content outside the block.
func replaceBlock(existing, newContent []byte) []byte {
	openIdx := bytes.Index(existing, []byte(markerOpen))
	closeIdx := bytes.Index(existing, []byte(markerClose))

	if openIdx < 0 || closeIdx < 0 || closeIdx <= openIdx {
		// Markers malformed — fall back to append.
		return appendBlock(existing, newContent)
	}

	// Include the open marker line (up to and including its newline).
	beforeBlock := existing[:openIdx+len(markerOpen)]
	// Find the newline after the open marker.
	nlAfterOpen := bytes.IndexByte(existing[openIdx+len(markerOpen):], '\n')
	if nlAfterOpen >= 0 {
		beforeBlock = existing[:openIdx+len(markerOpen)+nlAfterOpen+1]
	}

	// afterBlock starts at the close marker.
	afterBlock := existing[closeIdx:]

	var buf bytes.Buffer
	buf.Write(beforeBlock)
	buf.Write(bytes.TrimRight(newContent, "\n"))
	buf.WriteByte('\n')
	buf.Write(afterBlock)
	return buf.Bytes()
}

// appendBlock appends the Dexter block (with markers) at the end of existing.
func appendBlock(existing, newContent []byte) []byte {
	var buf bytes.Buffer
	if len(existing) > 0 {
		buf.Write(bytes.TrimRight(existing, "\n"))
		buf.WriteString("\n\n")
	}
	buf.WriteString(markerOpen)
	buf.WriteByte('\n')
	buf.Write(bytes.TrimRight(newContent, "\n"))
	buf.WriteByte('\n')
	buf.WriteString(markerClose)
	buf.WriteByte('\n')
	return buf.Bytes()
}
