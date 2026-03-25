package screens

import (
	"fmt"
	"strings"

	"github.com/gentleman-programming/dexter/internal/tui/styles"
	"github.com/gentleman-programming/dexter/internal/tui/types"
)

// RenderOptions renders the options configuration screen.
func RenderOptions(m types.Model) string {
	var sb strings.Builder

	sb.WriteString(styles.Title.Render("Options") + "\n\n")

	options := []struct {
		label  string
		toggle bool
	}{
		{"Dry run", m.DryRun},
		{"Backup", m.BackupEnabled},
	}

	for i, opt := range options {
		state := "off"
		if opt.toggle {
			state = "on"
		}

		line := fmt.Sprintf("%s [%s]", opt.label, state)

		if i == m.OptionCursor {
			sb.WriteString(styles.Focused.Render("> "+line) + "\n")
		} else {
			sb.WriteString(styles.Unfocused.Render("  "+line) + "\n")
		}
	}

	sb.WriteString("\n")
	sb.WriteString(styles.Muted.Render("Space to toggle, Enter to confirm, Esc to go back"))

	return sb.String()
}
