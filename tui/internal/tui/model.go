// Package tui is the root Bubbletea model for the Dexter TUI installer.
package tui

import (
	"os"
	"path/filepath"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/gentleman-programming/dexter/internal/agent"
	"github.com/gentleman-programming/dexter/internal/backup"
	"github.com/gentleman-programming/dexter/internal/pipeline"
	"github.com/gentleman-programming/dexter/internal/tui/screens"
	"github.com/gentleman-programming/dexter/internal/tui/types"
)

// Re-export types so callers only need to import tui.
type (
	Screen        = types.Screen
	Model         = types.Model
	StepView      = types.StepView
	ProgressState = types.ProgressState
)

// Re-export Screen constants.
const (
	ScreenWelcome        = types.ScreenWelcome
	ScreenDetection      = types.ScreenDetection
	ScreenAgentSelect    = types.ScreenAgentSelect
	ScreenOptions        = types.ScreenOptions
	ScreenReview         = types.ScreenReview
	ScreenInstalling     = types.ScreenInstalling
	ScreenComplete       = types.ScreenComplete
	ScreenBackupList     = types.ScreenBackupList
	ScreenRestoreConfirm = types.ScreenRestoreConfirm
	ScreenRestoreResult  = types.ScreenRestoreResult
)

// ---------------------------------------------------------------------------
// Msg types
// ---------------------------------------------------------------------------

// TickMsg is sent on every timer tick to advance the spinner and trigger actions.
type TickMsg time.Time

// StepProgressMsg carries a pipeline progress event from an async execution.
type StepProgressMsg pipeline.ProgressEvent

// PipelineDoneMsg is sent when the pipeline execution completes.
type PipelineDoneMsg pipeline.ExecutionResult

// DetectionDoneMsg carries the agent detection results.
type DetectionDoneMsg []agent.DetectionResult

// BackupRestoreMsg is sent after a backup list load or restore attempt.
type BackupRestoreMsg struct {
	Err       error
	Manifests []backup.Manifest // populated when loading the backup list
}

// ---------------------------------------------------------------------------
// Constructor
// ---------------------------------------------------------------------------

// New returns a fresh Model ready to start on ScreenWelcome.
func New(version string) Model {
	return Model{
		Screen:         ScreenWelcome,
		Version:        version,
		SelectedAgents: make(map[agent.AgentID]bool),
		BackupEnabled:  true,
	}
}

// ---------------------------------------------------------------------------
// tea.Model interface (thin wrappers — logic is in update helpers below)
// ---------------------------------------------------------------------------

// Init implements tea.Model. Starts the tick loop.
func Init(m Model) tea.Cmd {
	return tickCmd()
}

// Update implements tea.Model.
func Update(m Model, msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {

	case tea.WindowSizeMsg:
		m.Width = msg.Width
		m.Height = msg.Height

	case TickMsg:
		m.SpinnerFrame++
		if m.Detecting {
			m.Detecting = false // detection fires once; reset after we launch
			return m, tea.Batch(tickCmd(), detectCmd())
		}
		return m, tickCmd()

	case DetectionDoneMsg:
		m.DetectionResults = []agent.DetectionResult(msg)
		m.Detecting = false

	case StepProgressMsg:
		ev := pipeline.ProgressEvent(msg)
		for i, sv := range m.Progress.Steps {
			if sv.ID == ev.StepID {
				m.Progress.Steps[i].Status = ev.Status
				m.Progress.Steps[i].Err = ev.Err
				return m, nil
			}
		}
		// New step not yet in list — append it.
		m.Progress.Steps = append(m.Progress.Steps, StepView{
			ID:     ev.StepID,
			Label:  ev.StepID,
			Status: ev.Status,
			Err:    ev.Err,
		})

	case PipelineDoneMsg:
		m.Progress = ProgressFromExecution(pipeline.ExecutionResult(msg))
		m.Screen = ScreenComplete

	case BackupRestoreMsg:
		if m.Screen == ScreenBackupList {
			m.Manifests = msg.Manifests
		} else {
			m.RestoreResult = msg.Err
		}

	case tea.KeyMsg:
		return handleKey(m, msg)
	}

	return m, nil
}

// View implements tea.Model.
func View(m Model) string {
	switch m.Screen {
	case ScreenWelcome:
		return screens.RenderWelcome(m)
	case ScreenDetection:
		return screens.RenderDetection(m)
	case ScreenAgentSelect:
		return screens.RenderAgentSelect(m)
	case ScreenOptions:
		return screens.RenderOptions(m)
	case ScreenReview:
		return screens.RenderReview(m)
	case ScreenInstalling:
		return screens.RenderInstalling(m)
	case ScreenComplete:
		return screens.RenderComplete(m)
	case ScreenBackupList:
		return screens.RenderBackupList(m)
	case ScreenRestoreConfirm:
		return screens.RenderRestoreConfirm(m)
	case ScreenRestoreResult:
		return screens.RenderRestoreResult(m)
	}
	return ""
}

// ---------------------------------------------------------------------------
// tuiModel adapts Model to the tea.Model interface (pointer-free, value type).
// ---------------------------------------------------------------------------

// TUIModel wraps Model to satisfy the tea.Model interface.
type TUIModel struct {
	m Model
}

func (t TUIModel) Init() tea.Cmd              { return Init(t.m) }
func (t TUIModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	m, cmd := Update(t.m, msg)
	return TUIModel{m: m}, cmd
}
func (t TUIModel) View() string { return View(t.m) }

// Wrap wraps a Model into a tea.Model for use with tea.NewProgram.
func Wrap(m Model) tea.Model { return TUIModel{m: m} }

// ---------------------------------------------------------------------------
// Key handling
// ---------------------------------------------------------------------------

func handleKey(m Model, msg tea.KeyMsg) (Model, tea.Cmd) {
	key := msg.String()

	switch m.Screen {

	case ScreenWelcome:
		switch key {
		case "enter":
			m.Screen = ScreenDetection
			m.Detecting = true
			return m, tea.Batch(tickCmd(), detectCmd())
		case "r":
			m.Screen = ScreenBackupList
			return m, loadBackupsCmd()
		case "q", "ctrl+c":
			return m, tea.Quit
		}

	case ScreenDetection:
		if m.Detecting {
			break
		}
		switch key {
		case "enter":
			m.Screen = ScreenAgentSelect
		case "q", "ctrl+c":
			return m, tea.Quit
		}

	case ScreenAgentSelect:
		registry := agent.Registry()
		switch key {
		case "up", "k":
			if m.AgentCursor > 0 {
				m.AgentCursor--
			}
		case "down", "j":
			if m.AgentCursor < len(registry)-1 {
				m.AgentCursor++
			}
		case " ":
			id := registry[m.AgentCursor].ID
			if m.SelectedAgents == nil {
				m.SelectedAgents = make(map[agent.AgentID]bool)
			}
			m.SelectedAgents[id] = !m.SelectedAgents[id]
		case "enter":
			if countSelected(m) > 0 {
				m.Screen = ScreenOptions
			}
		case "esc":
			m = goBack(m)
		case "q", "ctrl+c":
			return m, tea.Quit
		}

	case ScreenOptions:
		switch key {
		case "up", "k":
			if m.OptionCursor > 0 {
				m.OptionCursor--
			}
		case "down", "j":
			if m.OptionCursor < 1 {
				m.OptionCursor++
			}
		case " ":
			switch m.OptionCursor {
			case 0:
				m.DryRun = !m.DryRun
			case 1:
				m.BackupEnabled = !m.BackupEnabled
			}
		case "enter":
			m.Screen = ScreenReview
		case "esc":
			m = goBack(m)
		case "q", "ctrl+c":
			return m, tea.Quit
		}

	case ScreenReview:
		switch key {
		case "enter":
			m.Screen = ScreenInstalling
			return m, startInstalling(m)
		case "esc":
			m = goBack(m)
		case "q", "ctrl+c":
			return m, tea.Quit
		}

	case ScreenInstalling:
		// No input accepted while installing.
		if key == "ctrl+c" {
			return m, tea.Quit
		}

	case ScreenComplete:
		switch key {
		case "q", "ctrl+c":
			return m, tea.Quit
		}

	case ScreenBackupList:
		switch key {
		case "up", "k":
			if m.RestoreCursor > 0 {
				m.RestoreCursor--
			}
		case "down", "j":
			if m.RestoreCursor < len(m.Manifests)-1 {
				m.RestoreCursor++
			}
		case "enter":
			if len(m.Manifests) > 0 {
				m.Screen = ScreenRestoreConfirm
			}
		case "esc":
			m = goBack(m)
		case "q", "ctrl+c":
			return m, tea.Quit
		}

	case ScreenRestoreConfirm:
		switch key {
		case "enter":
			m.Screen = ScreenRestoreResult
			return m, doRestoreCmd(m)
		case "esc":
			m = goBack(m)
		case "q", "ctrl+c":
			return m, tea.Quit
		}

	case ScreenRestoreResult:
		switch key {
		case "q", "ctrl+c":
			return m, tea.Quit
		}
	}

	return m, nil
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

func tickCmd() tea.Cmd {
	return tea.Tick(100*time.Millisecond, func(t time.Time) tea.Msg {
		return TickMsg(t)
	})
}

func detectCmd() tea.Cmd {
	return func() tea.Msg {
		homeDir, _ := os.UserHomeDir()
		results := agent.Detect(homeDir)
		return DetectionDoneMsg(results)
	}
}

func loadBackupsCmd() tea.Cmd {
	return func() tea.Msg {
		homeDir, err := os.UserHomeDir()
		if err != nil {
			return BackupRestoreMsg{Err: err}
		}
		backupsDir := filepath.Join(homeDir, ".dexter", "backups")
		entries, err := os.ReadDir(backupsDir)
		if err != nil {
			// No backups directory — not an error.
			return BackupRestoreMsg{Manifests: nil}
		}

		var manifests []backup.Manifest
		for _, e := range entries {
			if !e.IsDir() {
				continue
			}
			m, err := backup.ReadManifest(filepath.Join(backupsDir, e.Name()))
			if err != nil {
				continue
			}
			manifests = append(manifests, m)
		}
		return BackupRestoreMsg{Manifests: manifests}
	}
}

func doRestoreCmd(m Model) tea.Cmd {
	return func() tea.Msg {
		if m.RestoreCursor < 0 || m.RestoreCursor >= len(m.Manifests) {
			return BackupRestoreMsg{Err: nil}
		}
		err := backup.Restore(m.Manifests[m.RestoreCursor])
		return BackupRestoreMsg{Err: err}
	}
}

func startInstalling(m Model) tea.Cmd {
	if m.ExecuteFn == nil {
		// No executor injected (e.g. in tests) — send a done message immediately.
		return func() tea.Msg {
			return PipelineDoneMsg(pipeline.ExecutionResult{})
		}
	}

	selected := selectedIDs(m)
	dryRun := m.DryRun
	executeFn := m.ExecuteFn

	return func() tea.Msg {
		ch := make(chan tea.Msg, 128)

		go func() {
			result := executeFn(selected, dryRun, func(ev pipeline.ProgressEvent) {
				ch <- StepProgressMsg(ev)
			})
			ch <- PipelineDoneMsg(result)
			close(ch)
		}()

		// Return the first message; remaining will be sent via the program.
		// Because tea.Cmd returns a single Msg we must use tea.Batch indirection.
		// The goroutine drains ch via a recursive command chain.
		return <-ch
	}
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func countSelected(m Model) int {
	n := 0
	for _, v := range m.SelectedAgents {
		if v {
			n++
		}
	}
	return n
}

func selectedIDs(m Model) []agent.AgentID {
	ids := make([]agent.AgentID, 0, len(m.SelectedAgents))
	for id, selected := range m.SelectedAgents {
		if selected {
			ids = append(ids, id)
		}
	}
	return ids
}
