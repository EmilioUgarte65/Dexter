// Package styles defines all lipgloss styles and the Dexter logo used across TUI screens.
package styles

import "github.com/charmbracelet/lipgloss"

var (
	primaryColor = lipgloss.Color("#7C3AED") // violet
	mutedColor   = lipgloss.Color("#6B7280") // gray
	errorColor   = lipgloss.Color("#EF4444") // red
	successColor = lipgloss.Color("#10B981") // green

	// Focused is the style for the currently selected item.
	Focused = lipgloss.NewStyle().Bold(true).Foreground(primaryColor)

	// Unfocused is the style for normal (non-selected) items.
	Unfocused = lipgloss.NewStyle().Foreground(mutedColor)

	// Spinner is the style applied to spinner text.
	Spinner = lipgloss.NewStyle().Foreground(primaryColor)

	// Title is bold + primary color, used for screen headers.
	Title = lipgloss.NewStyle().Bold(true).Foreground(primaryColor)

	// Error renders text in red.
	Error = lipgloss.NewStyle().Foreground(errorColor)

	// Success renders text in green.
	Success = lipgloss.NewStyle().Foreground(successColor)

	// Muted renders text in dim gray.
	Muted = lipgloss.NewStyle().Foreground(mutedColor)

	// Logo is the ASCII art banner for Dexter.
	Logo = Title.Render(`
██████╗ ███████╗██╗  ██╗████████╗███████╗██████╗
██╔══██╗██╔════╝╚██╗██╔╝╚══██╔══╝██╔════╝██╔══██╗
██║  ██║█████╗   ╚███╔╝    ██║   █████╗  ██████╔╝
██║  ██║██╔══╝   ██╔██╗    ██║   ██╔══╝  ██╔══██╗
██████╔╝███████╗██╔╝ ██╗   ██║   ███████╗██║  ██║
╚═════╝ ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝`)
)
