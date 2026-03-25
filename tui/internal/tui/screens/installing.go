package screens

import (
	"strings"

	"github.com/gentleman-programming/dexter/internal/pipeline"
	"github.com/gentleman-programming/dexter/internal/tui/styles"
	"github.com/gentleman-programming/dexter/internal/tui/types"
)

// RenderInstalling renders the live installation progress screen.
func RenderInstalling(m types.Model) string {
	var sb strings.Builder

	sb.WriteString(styles.Title.Render("Installing") + "\n\n")

	for _, step := range m.Progress.Steps {
		icon := stepIcon(step.Status, m.SpinnerFrame)
		line := icon + " " + step.Label
		switch step.Status {
		case pipeline.StepStatusSucceeded:
			sb.WriteString(styles.Success.Render(line) + "\n")
		case pipeline.StepStatusFailed, pipeline.StepStatusRolledBack:
			sb.WriteString(styles.Error.Render(line) + "\n")
		case pipeline.StepStatusRunning:
			sb.WriteString(styles.Spinner.Render(line) + "\n")
		default:
			sb.WriteString(styles.Muted.Render(line) + "\n")
		}
	}

	return sb.String()
}

func stepIcon(status pipeline.StepStatus, frame int) string {
	switch status {
	case pipeline.StepStatusPending:
		return "·"
	case pipeline.StepStatusRunning:
		return spinnerFrames[frame%len(spinnerFrames)]
	case pipeline.StepStatusSucceeded:
		return "✓"
	case pipeline.StepStatusFailed:
		return "✗"
	case pipeline.StepStatusRolledBack:
		return "↩"
	}
	return "·"
}
