package pipeline

// Stage labels the phase of execution.
type Stage string

const (
	StagePrepare  Stage = "prepare"
	StageApply    Stage = "apply"
	StageRollback Stage = "rollback"
)

// StagePlan groups steps into a prepare stage and an apply stage.
// Prepare runs first; failure there halts execution before apply begins.
type StagePlan struct {
	Prepare []Step
	Apply   []Step
}

// StepResult records the outcome of a single step execution.
type StepResult struct {
	StepID string
	Status StepStatus
	Err    error
}

// StageResult records the outcome of an entire stage.
type StageResult struct {
	Stage   Stage
	Steps   []StepResult
	Success bool
	Err     error
}

// ExecutionResult is the top-level result returned by Orchestrator.Execute.
type ExecutionResult struct {
	Prepare  StageResult
	Apply    StageResult
	Rollback StageResult
	Err      error
}
