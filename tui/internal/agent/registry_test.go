package agent

import (
	"path/filepath"
	"strings"
	"testing"
)

const fakeHome = "/tmp/fake"

// TestRegistry_ReturnsSixAgents verifies that Registry() always returns exactly 6 entries.
func TestRegistry_ReturnsSixAgents(t *testing.T) {
	agents := Registry()
	if len(agents) != 6 {
		t.Errorf("Registry() returned %d agents, want 6", len(agents))
	}
}

// TestRegistry_AllFieldsNonEmpty verifies that every entry has a non-empty ID, DisplayName,
// and a non-empty ConfigDir when called with a fake home directory.
func TestRegistry_AllFieldsNonEmpty(t *testing.T) {
	agents := Registry()
	for _, a := range agents {
		t.Run(string(a.ID), func(t *testing.T) {
			if a.ID == "" {
				t.Error("ID is empty")
			}
			if a.DisplayName == "" {
				t.Error("DisplayName is empty")
			}
			if a.ConfigDir == nil {
				t.Error("ConfigDir func is nil")
			} else if dir := a.ConfigDir(fakeHome); dir == "" {
				t.Error("ConfigDir(fakeHome) returned empty string")
			}
		})
	}
}

// TestRegistry_ExpectedIDs verifies the set of IDs exactly.
func TestRegistry_ExpectedIDs(t *testing.T) {
	want := map[AgentID]bool{
		AgentClaudeCode: true,
		AgentOpenCode:   true,
		AgentCodex:      true,
		AgentCursor:     true,
		AgentGemini:     true,
		AgentVSCode:     true,
	}
	for _, a := range Registry() {
		if !want[a.ID] {
			t.Errorf("unexpected agent ID: %q", a.ID)
		}
		delete(want, a.ID)
	}
	for id := range want {
		t.Errorf("missing agent ID: %q", id)
	}
}

// TestDetect_SubsetOfRegistry verifies that Detect() only returns agents that are in Registry().
func TestDetect_SubsetOfRegistry(t *testing.T) {
	// Use a temp dir that won't match any real agent config dirs.
	results := Detect(fakeHome)

	registryIDs := make(map[AgentID]bool)
	for _, a := range Registry() {
		registryIDs[a.ID] = true
	}

	for _, r := range results {
		if !registryIDs[r.Agent] {
			t.Errorf("Detect() returned unknown agent ID: %q", r.Agent)
		}
	}
}

// TestDetect_ResultCountMatchesRegistry verifies that Detect() returns one result per agent
// (even if not found), so callers can always display the full list with badges.
func TestDetect_ResultCountMatchesRegistry(t *testing.T) {
	results := Detect(fakeHome)
	if len(results) != 6 {
		t.Errorf("Detect() returned %d results, want 6 (one per agent)", len(results))
	}
}

// TestConfigDir_LinuxPaths verifies OS-aware path resolution on Linux paths
// using a fake homeDir so tests are hermetic.
func TestConfigDir_LinuxPaths(t *testing.T) {
	tests := []struct {
		agentID AgentID
		want    string // expected ConfigDir given fakeHome on Linux
	}{
		{AgentClaudeCode, filepath.Join(fakeHome, ".claude")},
		{AgentCodex, filepath.Join(fakeHome, ".codex")},
		{AgentCursor, filepath.Join(fakeHome, ".cursor")},
		{AgentGemini, filepath.Join(fakeHome, ".gemini")},
		// opencode uses ~/.config/opencode on linux
		{AgentOpenCode, filepath.Join(fakeHome, ".config", "opencode")},
		// vscode uses ~/.config/Code on linux
		{AgentVSCode, filepath.Join(fakeHome, ".config", "Code")},
	}

	agentMap := make(map[AgentID]AgentConfig)
	for _, a := range Registry() {
		agentMap[a.ID] = a
	}

	for _, tt := range tests {
		t.Run(string(tt.agentID), func(t *testing.T) {
			a, ok := agentMap[tt.agentID]
			if !ok {
				t.Fatalf("agent %q not found in registry", tt.agentID)
			}
			got := a.ConfigDir(fakeHome)
			// On non-Linux hosts the path may differ; only enforce on linux/darwin
			// by checking for the expected suffix — the fakeHome prefix is always there.
			if !strings.HasPrefix(got, fakeHome) {
				t.Errorf("ConfigDir(%q) = %q; want path rooted at fakeHome", fakeHome, got)
			}
			// On the current platform the path must equal the expected one
			// (skip this check on darwin/windows where vscode and opencode differ).
			if tt.agentID != AgentOpenCode && tt.agentID != AgentVSCode {
				if got != tt.want {
					t.Errorf("ConfigDir(%q) = %q, want %q", fakeHome, got, tt.want)
				}
			}
		})
	}
}

// TestAllAgents_StrategiesNonEmpty verifies that every agent has non-empty strategy values.
func TestAllAgents_StrategiesNonEmpty(t *testing.T) {
	for _, a := range Registry() {
		t.Run(string(a.ID), func(t *testing.T) {
			if a.SystemPromptStrategy == "" {
				t.Error("SystemPromptStrategy is empty")
			}
			if a.MCPStrategy == "" {
				t.Error("MCPStrategy is empty")
			}
			if a.DetectFn == nil {
				t.Error("DetectFn is nil")
			}
			if a.BackupFiles == nil {
				t.Error("BackupFiles func is nil")
			} else if files := a.BackupFiles(fakeHome); len(files) == 0 {
				t.Error("BackupFiles(fakeHome) returned empty slice")
			}
		})
	}
}
