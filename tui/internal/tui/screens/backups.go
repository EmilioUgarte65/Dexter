package screens

import (
	"fmt"
	"strings"

	"github.com/gentleman-programming/dexter/internal/tui/styles"
	"github.com/gentleman-programming/dexter/internal/tui/types"
)

// RenderBackupList renders the backup list selection screen.
func RenderBackupList(m types.Model) string {
	var sb strings.Builder

	sb.WriteString(styles.Title.Render("Backups") + "\n\n")

	if len(m.Manifests) == 0 {
		sb.WriteString(styles.Muted.Render("No backups found.") + "\n")
	} else {
		for i, manifest := range m.Manifests {
			ts := manifest.CreatedAt.Format("2006-01-02 15:04:05 UTC")
			line := fmt.Sprintf("%s  (%d files)", ts, len(manifest.Entries))

			if i == m.RestoreCursor {
				sb.WriteString(styles.Focused.Render("> "+line) + "\n")
			} else {
				sb.WriteString(styles.Unfocused.Render("  "+line) + "\n")
			}
		}
	}

	sb.WriteString("\n")
	sb.WriteString(styles.Muted.Render("Enter to restore, Esc to go back"))

	return sb.String()
}
