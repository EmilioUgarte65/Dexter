package screens

import (
	"strings"

	"github.com/gentleman-programming/dexter/internal/agent"
	"github.com/gentleman-programming/dexter/internal/tui/styles"
	"github.com/gentleman-programming/dexter/internal/tui/types"
)

// RenderReview renders the installation review screen.
func RenderReview(m types.Model) string {
	var sb strings.Builder

	sb.WriteString(styles.Title.Render("Review") + "\n\n")

	// Build name lookup.
	nameFor := make(map[agent.AgentID]string)
	for _, cfg := range agent.Registry() {
		nameFor[cfg.ID] = cfg.DisplayName
	}

	sb.WriteString(styles.Focused.Render("Agents to install:") + "\n")
	for id, selected := range m.SelectedAgents {
		if !selected {
			continue
		}
		name := nameFor[id]
		if name == "" {
			name = string(id)
		}
		sb.WriteString("  • " + name + "\n")
	}

	sb.WriteString("\n")
	sb.WriteString(styles.Focused.Render("Options:") + "\n")

	dryRunState := "off"
	if m.DryRun {
		dryRunState = "on"
	}
	backupState := "off"
	if m.BackupEnabled {
		backupState = "on"
	}

	sb.WriteString("  Dry run: " + dryRunState + "\n")
	sb.WriteString("  Backup:  " + backupState + "\n")

	sb.WriteString("\n")
	sb.WriteString(styles.Muted.Render("Press Enter to install, Esc to go back"))

	return sb.String()
}
