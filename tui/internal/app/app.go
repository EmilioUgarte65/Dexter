package app

import (
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/gentleman-programming/dexter/internal/tui"
)

// Version is set by main.go via GoReleaser ldflags.
var Version = "dev"

// Run is the main entry point. It parses os.Args and routes to the
// appropriate mode: TUI (no args), headless install, or restore.
func Run(args []string) error {
	// Scan all args for global flags before routing subcommands.
	dryRun := false
	filtered := args[:1] // keep program name
	for _, a := range args[1:] {
		switch a {
		case "--dry-run":
			dryRun = true
		default:
			filtered = append(filtered, a)
		}
	}

	if len(filtered) < 2 {
		return runTUI(dryRun)
	}

	switch filtered[1] {
	case "install":
		return runHeadlessInstall(filtered[2:])
	case "restore":
		return runRestore(filtered[2:])
	case "--version", "-version", "version":
		fmt.Printf("dexter version %s\n", Version)
		return nil
	default:
		fmt.Fprintf(os.Stderr, "unknown command: %s\n", filtered[1])
		fmt.Fprintf(os.Stderr, "usage: dexter [install|restore|--version|--dry-run]\n")
		os.Exit(1)
	}

	return nil
}

func runTUI(dryRun bool) error {
	m := tui.New(Version)
	m.DryRun = dryRun
	p := tea.NewProgram(tui.Wrap(m), tea.WithAltScreen())
	_, err := p.Run()
	return err
}

func runHeadlessInstall(_ []string) error {
	// TODO: Phase 3+ — headless executor
	fmt.Println("headless install: not yet implemented")
	return nil
}

func runRestore(_ []string) error {
	// TODO: Phase 6 — backup.Restore
	fmt.Println("restore: not yet implemented")
	return nil
}
