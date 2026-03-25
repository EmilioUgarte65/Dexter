package tui

import "github.com/gentleman-programming/dexter/internal/tui/types"

// Route holds the forward and backward screen transitions for a given screen.
type Route struct {
	Forward  types.Screen
	Backward types.Screen
}

var routes = map[types.Screen]Route{
	types.ScreenWelcome:        {Forward: types.ScreenDetection, Backward: types.ScreenWelcome},
	types.ScreenDetection:      {Forward: types.ScreenAgentSelect, Backward: types.ScreenWelcome},
	types.ScreenAgentSelect:    {Forward: types.ScreenOptions, Backward: types.ScreenDetection},
	types.ScreenOptions:        {Forward: types.ScreenReview, Backward: types.ScreenAgentSelect},
	types.ScreenReview:         {Forward: types.ScreenInstalling, Backward: types.ScreenOptions},
	types.ScreenInstalling:     {Forward: types.ScreenComplete, Backward: types.ScreenInstalling},
	types.ScreenComplete:       {Forward: types.ScreenComplete, Backward: types.ScreenComplete},
	types.ScreenBackupList:     {Forward: types.ScreenRestoreConfirm, Backward: types.ScreenWelcome},
	types.ScreenRestoreConfirm: {Forward: types.ScreenRestoreResult, Backward: types.ScreenBackupList},
	types.ScreenRestoreResult:  {Forward: types.ScreenRestoreResult, Backward: types.ScreenRestoreResult},
}

// canGoBack returns false for screens where back navigation is disabled.
func canGoBack(s types.Screen) bool {
	switch s {
	case types.ScreenWelcome, types.ScreenInstalling, types.ScreenComplete, types.ScreenRestoreResult:
		return false
	}
	return true
}

// goBack navigates the model to the previous screen according to the route table.
func goBack(m types.Model) types.Model {
	if !canGoBack(m.Screen) {
		return m
	}
	if r, ok := routes[m.Screen]; ok {
		m.Screen = r.Backward
	}
	return m
}
