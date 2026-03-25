// Package types holds the shared Model and Screen types used by both the tui
// and tui/screens packages, preventing import cycles.
package types

import (
	"github.com/gentleman-programming/dexter/internal/agent"
	"github.com/gentleman-programming/dexter/internal/backup"
	"github.com/gentleman-programming/dexter/internal/pipeline"
)

// Screen identifies which screen the TUI is currently rendering.
type Screen int

const (
	ScreenWelcome Screen = iota
	ScreenDetection
	ScreenAgentSelect
	ScreenOptions
	ScreenReview
	ScreenInstalling
	ScreenComplete
	ScreenBackupList
	ScreenRestoreConfirm
	ScreenRestoreResult
)

// StepView is the TUI representation of a single pipeline step.
type StepView struct {
	ID     string
	Label  string
	Status pipeline.StepStatus
	Err    error
}

// ProgressState holds all step views for the installing screen.
type ProgressState struct {
	Steps []StepView
}

// Model is the root Bubbletea model for the Dexter TUI.
// All fields are populated progressively as the user navigates screens.
type Model struct {
	Screen        Screen
	Version       string
	Width, Height int

	// Detection
	DetectionResults []agent.DetectionResult
	Detecting        bool

	// Selection
	AgentCursor    int
	SelectedAgents map[agent.AgentID]bool

	// Options
	OptionCursor  int
	DryRun        bool
	BackupEnabled bool

	// Progress
	Progress ProgressState

	// Restore flow
	Manifests     []backup.Manifest
	RestoreCursor int
	RestoreResult error

	// Spinner
	SpinnerFrame int

	// ExecuteFn is injected at runtime; nil in tests.
	ExecuteFn func(selected []agent.AgentID, dryRun bool, onProgress func(pipeline.ProgressEvent)) pipeline.ExecutionResult
}
