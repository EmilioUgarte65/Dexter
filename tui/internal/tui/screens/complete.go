package screens

import (
	"fmt"
	"strings"

	"github.com/gentleman-programming/dexter/internal/pipeline"
	"github.com/gentleman-programming/dexter/internal/tui/styles"
	"github.com/gentleman-programming/dexter/internal/tui/types"
)

// RenderComplete renders the installation complete screen.
func RenderComplete(m types.Model) string {
	var sb strings.Builder

	sb.WriteString(styles.Title.Render("Complete") + "\n\n")

	succeeded, failed := 0, 0
	var failedSteps []types.StepView

	for _, step := range m.Progress.Steps {
		switch step.Status {
		case pipeline.StepStatusSucceeded:
			succeeded++
		case pipeline.StepStatusFailed:
			failed++
			failedSteps = append(failedSteps, step)
		}
	}

	sb.WriteString(fmt.Sprintf("  %s  %s\n",
		styles.Success.Render(fmt.Sprintf("%d succeeded", succeeded)),
		styles.Error.Render(fmt.Sprintf("%d failed", failed)),
	))

	if len(failedSteps) > 0 {
		sb.WriteString("\n")
		sb.WriteString(styles.Error.Render("Failures:") + "\n")
		for _, step := range failedSteps {
			errMsg := ""
			if step.Err != nil {
				errMsg = ": " + step.Err.Error()
			}
			sb.WriteString(styles.Error.Render("  ✗ "+step.Label+errMsg) + "\n")
		}
		sb.WriteString("\n")
		sb.WriteString(styles.Muted.Render("Rollback completed") + "\n")
	}

	sb.WriteString("\n")
	sb.WriteString(styles.Muted.Render("Press q to quit"))

	return sb.String()
}
