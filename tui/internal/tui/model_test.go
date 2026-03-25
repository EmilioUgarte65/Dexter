package tui

import (
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/gentleman-programming/dexter/internal/agent"
)

// helper to send a single key to a model and return the updated model.
func sendKey(m Model, key string) Model {
	updated, _ := Update(m, tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune(key)})
	return updated
}

// helper for special keys (enter, esc, space, up, down).
func sendSpecialKey(m Model, keyType tea.KeyType) Model {
	updated, _ := Update(m, tea.KeyMsg{Type: keyType})
	return updated
}

func TestWelcomeToDetection(t *testing.T) {
	m := New("test")

	if m.Screen != ScreenWelcome {
		t.Fatalf("expected ScreenWelcome, got %v", m.Screen)
	}

	m = sendSpecialKey(m, tea.KeyEnter)

	if m.Screen != ScreenDetection {
		t.Errorf("after Enter on Welcome: expected ScreenDetection, got %v", m.Screen)
	}
}

func TestAgentToggle(t *testing.T) {
	m := New("test")
	m.Screen = ScreenAgentSelect
	m.DetectionResults = agent.Detect("/nonexistent-home")

	registry := agent.Registry()
	if len(registry) == 0 {
		t.Fatal("registry must have agents")
	}

	firstID := registry[0].ID

	// Initially not selected.
	if m.SelectedAgents[firstID] {
		t.Fatal("agent should not be selected initially")
	}

	// Toggle on.
	m = sendSpecialKey(m, tea.KeySpace)
	if !m.SelectedAgents[firstID] {
		t.Error("agent should be selected after Space")
	}

	// Toggle off.
	m = sendSpecialKey(m, tea.KeySpace)
	if m.SelectedAgents[firstID] {
		t.Error("agent should be deselected after second Space")
	}
}

func TestOptionsToggle(t *testing.T) {
	m := New("test")
	m.Screen = ScreenOptions

	// DryRun is false by default, OptionCursor is at 0 (DryRun row).
	if m.DryRun {
		t.Fatal("DryRun should be false initially")
	}

	m = sendSpecialKey(m, tea.KeySpace)

	if !m.DryRun {
		t.Error("DryRun should be true after Space")
	}
}

func TestCannotProceedWithNoAgents(t *testing.T) {
	m := New("test")
	m.Screen = ScreenAgentSelect
	// No agents selected.

	m = sendSpecialKey(m, tea.KeyEnter)

	if m.Screen != ScreenAgentSelect {
		t.Errorf("should stay on AgentSelect with no agents selected, got %v", m.Screen)
	}
}

func TestGoBack(t *testing.T) {
	m := New("test")
	m.Screen = ScreenOptions

	m = sendSpecialKey(m, tea.KeyEsc)

	if m.Screen != ScreenAgentSelect {
		t.Errorf("after Esc on Options: expected ScreenAgentSelect, got %v", m.Screen)
	}
}
