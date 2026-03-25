package tui

import (
	"github.com/gentleman-programming/dexter/internal/pipeline"
	"github.com/gentleman-programming/dexter/internal/tui/types"
)

// ProgressFromExecution builds a ProgressState from a completed ExecutionResult,
// merging prepare and apply step results into a flat list.
func ProgressFromExecution(r pipeline.ExecutionResult) types.ProgressState {
	allSteps := append(r.Prepare.Steps, r.Apply.Steps...)
	views := make([]types.StepView, 0, len(allSteps))
	for _, sr := range allSteps {
		views = append(views, types.StepView{
			ID:     sr.StepID,
			Label:  sr.StepID,
			Status: sr.Status,
			Err:    sr.Err,
		})
	}
	return types.ProgressState{Steps: views}
}
