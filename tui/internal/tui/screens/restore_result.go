package screens

import (
	"fmt"
	"strings"

	"github.com/gentleman-programming/dexter/internal/tui/styles"
	"github.com/gentleman-programming/dexter/internal/tui/types"
)

// RenderRestoreResult renders the restore result screen.
func RenderRestoreResult(m types.Model) string {
	var sb strings.Builder

	sb.WriteString(styles.Title.Render("Restore Result") + "\n\n")

	if m.RestoreResult == nil {
		sb.WriteString(styles.Success.Render("✓ Restore complete") + "\n")
	} else {
		sb.WriteString(styles.Error.Render(fmt.Sprintf("✗ Restore failed: %s", m.RestoreResult.Error())) + "\n")
	}

	sb.WriteString("\n")
	sb.WriteString(styles.Muted.Render("Press q to quit"))

	return sb.String()
}
