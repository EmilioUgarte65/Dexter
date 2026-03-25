package pipeline

import "errors"

// FailurePolicy controls how the Runner behaves when a step fails.
type FailurePolicy int

const (
	// StopOnError stops execution at the first failed step (default).
	StopOnError FailurePolicy = iota
	// ContinueOnError continues executing remaining steps, collecting all errors.
	ContinueOnError
)

// Runner executes a list of steps for a given stage, calling OnProgress before
// and after each step and respecting FailurePolicy.
type Runner struct {
	FailurePolicy FailurePolicy
	OnProgress    ProgressFunc
}

// Run executes steps sequentially. It emits a Running event before each step
// and a Succeeded or Failed event after. On failure with StopOnError it
// returns immediately; with ContinueOnError it collects all errors.
func (r Runner) Run(stage Stage, steps []Step) StageResult {
	result := StageResult{Stage: stage, Success: true, Steps: make([]StepResult, 0, len(steps))}
	var errs []error

	for _, step := range steps {
		r.emit(ProgressEvent{StepID: step.ID(), Status: StepStatusRunning})

		err := step.Run()

		sr := StepResult{StepID: step.ID()}
		if err != nil {
			sr.Status = StepStatusFailed
			sr.Err = err
			result.Steps = append(result.Steps, sr)
			r.emit(ProgressEvent{StepID: step.ID(), Status: StepStatusFailed, Err: err})
			errs = append(errs, err)
			result.Success = false

			if r.FailurePolicy == StopOnError {
				result.Err = err
				return result
			}
			continue
		}

		sr.Status = StepStatusSucceeded
		result.Steps = append(result.Steps, sr)
		r.emit(ProgressEvent{StepID: step.ID(), Status: StepStatusSucceeded})
	}

	if len(errs) > 0 {
		result.Err = errors.Join(errs...)
	}

	return result
}

func (r Runner) emit(event ProgressEvent) {
	if r.OnProgress != nil {
		r.OnProgress(event)
	}
}
