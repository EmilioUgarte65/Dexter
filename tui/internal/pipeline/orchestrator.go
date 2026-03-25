package pipeline

import "fmt"

// RollbackPolicy controls whether a rollback is attempted after apply failure.
type RollbackPolicy struct {
	OnApplyFailure bool
}

// DefaultRollbackPolicy returns a policy that rolls back on any apply failure.
func DefaultRollbackPolicy() RollbackPolicy {
	return RollbackPolicy{OnApplyFailure: true}
}

func (p RollbackPolicy) shouldRollback(stage Stage, err error) bool {
	return err != nil && stage == StageApply && p.OnApplyFailure
}

// OrchestratorOption configures an Orchestrator.
type OrchestratorOption func(*Orchestrator)

// WithFailurePolicy sets the failure policy for the apply-stage runner.
func WithFailurePolicy(policy FailurePolicy) OrchestratorOption {
	return func(o *Orchestrator) {
		o.runner.FailurePolicy = policy
	}
}

// WithProgressFunc sets a callback that receives every step lifecycle event.
func WithProgressFunc(fn ProgressFunc) OrchestratorOption {
	return func(o *Orchestrator) {
		o.runner.OnProgress = fn
	}
}

// Orchestrator runs a StagePlan through prepare → apply, triggering rollback
// on apply failure according to the RollbackPolicy.
type Orchestrator struct {
	runner   Runner
	policy   RollbackPolicy
	stepByID map[string]Step
}

// NewOrchestrator creates a new Orchestrator with the given policy and options.
func NewOrchestrator(policy RollbackPolicy, opts ...OrchestratorOption) *Orchestrator {
	o := &Orchestrator{
		runner:   Runner{},
		policy:   policy,
		stepByID: make(map[string]Step),
	}
	for _, opt := range opts {
		opt(o)
	}
	return o
}

// Execute runs plan.Prepare then plan.Apply. On apply failure it triggers
// rollback (reverse order) for steps that implement RollbackStep.
func (o *Orchestrator) Execute(plan StagePlan) ExecutionResult {
	o.indexSteps(plan.Prepare)
	o.indexSteps(plan.Apply)

	prepareResult := o.runner.Run(StagePrepare, plan.Prepare)
	if !prepareResult.Success {
		return ExecutionResult{Prepare: prepareResult, Err: prepareResult.Err}
	}

	applyResult := o.runner.Run(StageApply, plan.Apply)
	result := ExecutionResult{Prepare: prepareResult, Apply: applyResult}
	if applyResult.Success {
		return result
	}

	result.Err = applyResult.Err
	if o.policy.shouldRollback(StageApply, applyResult.Err) {
		result.Rollback = executeRollback(applyResult.Steps, o.stepByID)
		if !result.Rollback.Success {
			result.Err = result.Rollback.Err
		}
	}

	return result
}

func (o *Orchestrator) indexSteps(steps []Step) {
	for _, s := range steps {
		o.stepByID[s.ID()] = s
	}
}

// executeRollback calls Rollback() in reverse order on all succeeded steps
// that implement RollbackStep. Rollback failures do not mask the original
// apply error but do mark the rollback stage as failed.
func executeRollback(steps []StepResult, index map[string]Step) StageResult {
	result := StageResult{Stage: StageRollback, Success: true}

	for i := len(steps) - 1; i >= 0; i-- {
		sr := steps[i]
		if sr.Status != StepStatusSucceeded {
			continue
		}

		step, ok := index[sr.StepID]
		if !ok {
			continue
		}

		rb, ok := step.(RollbackStep)
		if !ok {
			continue
		}

		err := rb.Rollback()
		item := StepResult{StepID: rb.ID(), Status: StepStatusRolledBack}
		if err != nil {
			item.Status = StepStatusFailed
			item.Err = err
			result.Steps = append(result.Steps, item)
			result.Success = false
			result.Err = fmt.Errorf("rollback step %q: %w", rb.ID(), err)
			return result
		}
		result.Steps = append(result.Steps, item)
	}

	return result
}
