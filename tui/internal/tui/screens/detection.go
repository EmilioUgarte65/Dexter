package screens

import (
	"fmt"
	"strings"

	"github.com/gentleman-programming/dexter/internal/agent"
	"github.com/gentleman-programming/dexter/internal/tui/styles"
	"github.com/gentleman-programming/dexter/internal/tui/types"
)

// spinnerFrames are the characters used to animate the spinner.
var spinnerFrames = []string{"⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"}

// RenderDetection renders the agent detection screen.
func RenderDetection(m types.Model) string {
	var sb strings.Builder

	sb.WriteString(styles.Title.Render("Detecting agents") + "\n\n")

	// Build a lookup map from detection results.
	detected := make(map[agent.AgentID]bool)
	for _, r := range m.DetectionResults {
		detected[r.Agent] = r.Found
	}

	for _, cfg := range agent.Registry() {
		var badge string
		if detected[cfg.ID] {
			badge = styles.Success.Render("✓ detected")
		} else {
			badge = styles.Muted.Render("· not found")
		}
		sb.WriteString(fmt.Sprintf("  %-20s %s\n", cfg.DisplayName, badge))
	}

	sb.WriteString("\n")

	if m.Detecting {
		frame := spinnerFrames[m.SpinnerFrame%len(spinnerFrames)]
		sb.WriteString(styles.Spinner.Render(frame+" Detecting agents..."))
	} else {
		sb.WriteString(styles.Muted.Render("Press Enter to continue"))
	}

	return sb.String()
}
