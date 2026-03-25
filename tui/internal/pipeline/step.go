package pipeline

// StepStatus represents the lifecycle state of a single pipeline step.
type StepStatus string

const (
	StepStatusPending    StepStatus = "pending"
	StepStatusRunning    StepStatus = "running"
	StepStatusSucceeded  StepStatus = "succeeded"
	StepStatusFailed     StepStatus = "failed"
	StepStatusRolledBack StepStatus = "rolled-back"
)

// ProgressEvent is emitted by the Runner before and after each step executes.
type ProgressEvent struct {
	StepID string
	Status StepStatus
	Err    error
}

// ProgressFunc is a callback invoked for every step lifecycle event.
type ProgressFunc func(ProgressEvent)

// Step is the unit of work executed by the Runner.
// Implementing Rollback is optional; steps that do not need rollback
// only implement the base Step interface.
type Step interface {
	ID() string
	Run() error
}

// RollbackStep extends Step with a Rollback method.
// The Runner calls Rollback in reverse order when the apply stage fails.
type RollbackStep interface {
	Step
	Rollback() error
}
