package screens

import (
	"fmt"

	"github.com/gentleman-programming/dexter/internal/tui/styles"
	"github.com/gentleman-programming/dexter/internal/tui/types"
)

// RenderWelcome renders the welcome screen.
func RenderWelcome(m types.Model) string {
	return fmt.Sprintf(
		"%s\n\n%s\n\n%s",
		styles.Logo,
		styles.Muted.Render("version "+m.Version),
		styles.Muted.Render("Press Enter to install, r to restore backups, q to quit"),
	)
}
