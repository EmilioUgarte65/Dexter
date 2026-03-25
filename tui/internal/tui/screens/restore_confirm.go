package screens

import (
	"fmt"
	"strings"

	"github.com/gentleman-programming/dexter/internal/tui/styles"
	"github.com/gentleman-programming/dexter/internal/tui/types"
)

// RenderRestoreConfirm renders the restore confirmation screen.
func RenderRestoreConfirm(m types.Model) string {
	var sb strings.Builder

	sb.WriteString(styles.Title.Render("Confirm Restore") + "\n\n")

	if m.RestoreCursor >= 0 && m.RestoreCursor < len(m.Manifests) {
		manifest := m.Manifests[m.RestoreCursor]
		ts := manifest.CreatedAt.Format("2006-01-02 15:04:05 UTC")
		sb.WriteString(fmt.Sprintf("  Restoring backup from: %s\n", styles.Focused.Render(ts)))
		sb.WriteString(fmt.Sprintf("  Files to restore: %d\n", len(manifest.Entries)))
	} else {
		sb.WriteString(styles.Error.Render("  No backup selected.") + "\n")
	}

	sb.WriteString("\n")
	sb.WriteString(styles.Muted.Render("Enter to confirm, Esc to cancel"))

	return sb.String()
}
