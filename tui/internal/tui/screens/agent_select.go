package screens

import (
	"fmt"
	"strings"

	"github.com/gentleman-programming/dexter/internal/agent"
	"github.com/gentleman-programming/dexter/internal/tui/styles"
	"github.com/gentleman-programming/dexter/internal/tui/types"
)

// RenderAgentSelect renders the multi-select agent selection screen.
func RenderAgentSelect(m types.Model) string {
	var sb strings.Builder

	sb.WriteString(styles.Title.Render("Select agents to install") + "\n\n")

	// Build detection lookup.
	detected := make(map[agent.AgentID]bool)
	for _, r := range m.DetectionResults {
		detected[r.Agent] = r.Found
	}

	registry := agent.Registry()
	for i, cfg := range registry {
		cursor := "  "
		if i == m.AgentCursor {
			cursor = "> "
		}

		checkbox := "[ ]"
		if m.SelectedAgents[cfg.ID] {
			checkbox = "[x]"
		}

		detectedBadge := ""
		if detected[cfg.ID] {
			detectedBadge = "  " + styles.Success.Render("detected")
		}

		line := fmt.Sprintf("%s%s %s%s", cursor, checkbox, cfg.DisplayName, detectedBadge)

		if i == m.AgentCursor {
			sb.WriteString(styles.Focused.Render(line) + "\n")
		} else {
			sb.WriteString(styles.Unfocused.Render(line) + "\n")
		}
	}

	sb.WriteString("\n")
	sb.WriteString(styles.Muted.Render("Space to toggle, Enter to confirm, Esc to go back"))

	return sb.String()
}
