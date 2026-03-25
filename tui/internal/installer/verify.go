package installer

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"

	"github.com/gentleman-programming/dexter/internal/agent"
)

// Verify checks that a completed installation is consistent.
//
// Checks performed:
//   - System prompt file exists and contains both Dexter markers (for MarkdownSections strategy)
//   - Skills directory is non-empty
//   - Settings file exists and contains valid JSON (when SettingsFile is set)
//
// Returns nil if all checks pass. Returns a joined error listing all failures.
func Verify(homeDir string, cfg agent.AgentConfig) error {
	var errs []error

	// 1. System prompt file — marker check (only for MarkdownSections).
	if cfg.SystemPromptStrategy == agent.StrategyMarkdownSections {
		systemFile := cfg.SystemPromptFile(homeDir)
		data, err := os.ReadFile(systemFile)
		if err != nil {
			errs = append(errs, fmt.Errorf("verify: system prompt %q not readable: %w", systemFile, err))
		} else {
			if !bytes.Contains(data, []byte(markerOpen)) {
				errs = append(errs, fmt.Errorf("verify: system prompt %q missing opening marker %q", systemFile, markerOpen))
			}
			if !bytes.Contains(data, []byte(markerClose)) {
				errs = append(errs, fmt.Errorf("verify: system prompt %q missing closing marker %q", systemFile, markerClose))
			}
		}
	} else {
		// For other strategies, just check the file exists.
		systemFile := cfg.SystemPromptFile(homeDir)
		if _, err := os.Stat(systemFile); err != nil {
			errs = append(errs, fmt.Errorf("verify: system prompt %q missing: %w", systemFile, err))
		}
	}

	// 2. Skills directory non-empty.
	skillsDir := cfg.SkillsDir(homeDir)
	entries, err := os.ReadDir(skillsDir)
	if err != nil {
		errs = append(errs, fmt.Errorf("verify: skills dir %q not readable: %w", skillsDir, err))
	} else if len(entries) == 0 {
		errs = append(errs, fmt.Errorf("verify: skills dir %q is empty", skillsDir))
	}

	// 3. Settings file valid JSON (when set).
	if cfg.SettingsFile != nil {
		settingsFile := cfg.SettingsFile(homeDir)
		if settingsFile != "" {
			data, err := os.ReadFile(settingsFile)
			if err != nil {
				// Settings file may not exist for all agents — only error if it should.
				if !os.IsNotExist(err) {
					errs = append(errs, fmt.Errorf("verify: settings file %q not readable: %w", settingsFile, err))
				}
			} else if len(data) > 0 {
				var v any
				if jsonErr := json.Unmarshal(data, &v); jsonErr != nil {
					errs = append(errs, fmt.Errorf("verify: settings file %q is invalid JSON: %w", settingsFile, jsonErr))
				}
			}
		}
	}

	return joinErrors(errs)
}
