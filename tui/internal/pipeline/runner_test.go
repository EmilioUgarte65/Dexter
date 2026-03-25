package pipeline

import (
	"errors"
	"reflect"
	"testing"
)

// ---------------------------------------------------------------------------
// Mock step helpers
// ---------------------------------------------------------------------------

type mockStep struct {
	id      string
	order   *[]string
	runErr  error
	rollErr error
}

func newMockStep(id string, order *[]string) *mockStep {
	return &mockStep{id: id, order: order}
}

func newMockStepWithError(id string, order *[]string, runErr error) *mockStep {
	return &mockStep{id: id, order: order, runErr: runErr}
}

func (s *mockStep) ID() string { return s.id }

func (s *mockStep) Run() error {
	*s.order = append(*s.order, "run:"+s.id)
	return s.runErr
}

func (s *mockStep) Rollback() error {
	*s.order = append(*s.order, "rollback:"+s.id)
	return s.rollErr
}

// ---------------------------------------------------------------------------
// Runner tests
// ---------------------------------------------------------------------------

func TestRunnerAllStepsSucceed(t *testing.T) {
	order := []string{}
	events := []ProgressEvent{}

	runner := Runner{
		FailurePolicy: StopOnError,
		OnProgress: func(e ProgressEvent) {
			events = append(events, e)
		},
	}

	steps := []Step{
		newMockStep("step-a", &order),
		newMockStep("step-b", &order),
	}

	result := runner.Run(StageApply, steps)

	if result.Err != nil {
		t.Fatalf("Run() unexpected error: %v", result.Err)
	}
	if !result.Success {
		t.Fatalf("Run() expected Success=true")
	}

	wantOrder := []string{"run:step-a", "run:step-b"}
	if !reflect.DeepEqual(order, wantOrder) {
		t.Fatalf("execution order = %v, want %v", order, wantOrder)
	}

	// Each step emits running + succeeded = 4 events total.
	if len(events) != 4 {
		t.Fatalf("events = %d, want 4", len(events))
	}
	if events[0].StepID != "step-a" || events[0].Status != StepStatusRunning {
		t.Fatalf("event[0] = %+v", events[0])
	}
	if events[1].StepID != "step-a" || events[1].Status != StepStatusSucceeded {
		t.Fatalf("event[1] = %+v", events[1])
	}
	if events[2].StepID != "step-b" || events[2].Status != StepStatusRunning {
		t.Fatalf("event[2] = %+v", events[2])
	}
	if events[3].StepID != "step-b" || events[3].Status != StepStatusSucceeded {
		t.Fatalf("event[3] = %+v", events[3])
	}
}

func TestRunnerStopOnErrorHaltsAtFailedStep(t *testing.T) {
	order := []string{}
	runner := Runner{FailurePolicy: StopOnError}

	steps := []Step{
		newMockStep("step-1", &order),
		newMockStepWithError("step-2", &order, errors.New("boom")),
		newMockStep("step-3", &order),
	}

	result := runner.Run(StageApply, steps)

	if result.Success {
		t.Fatalf("Run() expected Success=false")
	}
	if result.Err == nil {
		t.Fatalf("Run() expected non-nil error")
	}

	// step-3 must NOT have run.
	wantOrder := []string{"run:step-1", "run:step-2"}
	if !reflect.DeepEqual(order, wantOrder) {
		t.Fatalf("execution order = %v, want %v", order, wantOrder)
	}

	if len(result.Steps) != 2 {
		t.Fatalf("steps = %d, want 2", len(result.Steps))
	}
	if result.Steps[0].Status != StepStatusSucceeded {
		t.Fatalf("step-1 status = %q", result.Steps[0].Status)
	}
	if result.Steps[1].Status != StepStatusFailed {
		t.Fatalf("step-2 status = %q", result.Steps[1].Status)
	}
}

func TestRunnerContinueOnErrorExecutesAllSteps(t *testing.T) {
	order := []string{}
	runner := Runner{FailurePolicy: ContinueOnError}

	steps := []Step{
		newMockStep("step-1", &order),
		newMockStepWithError("step-2", &order, errors.New("fail-2")),
		newMockStep("step-3", &order),
	}

	result := runner.Run(StageApply, steps)

	wantOrder := []string{"run:step-1", "run:step-2", "run:step-3"}
	if !reflect.DeepEqual(order, wantOrder) {
		t.Fatalf("execution order = %v, want %v", order, wantOrder)
	}

	if result.Success {
		t.Fatalf("Run() expected Success=false")
	}
	if result.Err == nil {
		t.Fatalf("Run() expected aggregated error")
	}
	if len(result.Steps) != 3 {
		t.Fatalf("steps = %d, want 3", len(result.Steps))
	}
	if result.Steps[1].Status != StepStatusFailed {
		t.Fatalf("step-2 status = %q", result.Steps[1].Status)
	}
}

func TestRunnerProgressEmitsFailedEvent(t *testing.T) {
	events := []ProgressEvent{}
	order := []string{}

	runner := Runner{
		FailurePolicy: ContinueOnError,
		OnProgress: func(e ProgressEvent) {
			events = append(events, e)
		},
	}

	steps := []Step{
		newMockStep("ok", &order),
		newMockStepWithError("bad", &order, errors.New("oops")),
	}

	result := runner.Run(StageApply, steps)

	if result.Success {
		t.Fatalf("expected failure")
	}

	// ok: running+succeeded; bad: running+failed = 4 events
	if len(events) != 4 {
		t.Fatalf("events = %d, want 4", len(events))
	}
	last := events[3]
	if last.Status != StepStatusFailed || last.Err == nil {
		t.Fatalf("last event expected Failed with error, got %+v", last)
	}
}

// ---------------------------------------------------------------------------
// Orchestrator tests
// ---------------------------------------------------------------------------

func TestOrchestratorRunsPrepareThenApply(t *testing.T) {
	order := []string{}
	o := NewOrchestrator(DefaultRollbackPolicy())

	result := o.Execute(StagePlan{
		Prepare: []Step{newMockStep("prepare-1", &order)},
		Apply:   []Step{newMockStep("apply-1", &order)},
	})

	if result.Err != nil {
		t.Fatalf("Execute() error = %v", result.Err)
	}
	wantOrder := []string{"run:prepare-1", "run:apply-1"}
	if !reflect.DeepEqual(order, wantOrder) {
		t.Fatalf("execution order = %v, want %v", order, wantOrder)
	}
	if !result.Prepare.Success || !result.Apply.Success {
		t.Fatalf("stage result prepare=%v apply=%v", result.Prepare.Success, result.Apply.Success)
	}
}

func TestOrchestratorPrepareFaultHaltsBeforeApply(t *testing.T) {
	order := []string{}
	o := NewOrchestrator(DefaultRollbackPolicy())

	result := o.Execute(StagePlan{
		Prepare: []Step{newMockStepWithError("prepare-fail", &order, errors.New("disk full"))},
		Apply:   []Step{newMockStep("apply-1", &order)},
	})

	if result.Err == nil {
		t.Fatalf("expected error when prepare fails")
	}
	// apply-1 must not have run
	wantOrder := []string{"run:prepare-fail"}
	if !reflect.DeepEqual(order, wantOrder) {
		t.Fatalf("execution order = %v, want %v", order, wantOrder)
	}
}

func TestOrchestratorRollsBackApplyStepsOnFailure(t *testing.T) {
	order := []string{}
	o := NewOrchestrator(DefaultRollbackPolicy())

	result := o.Execute(StagePlan{
		Apply: []Step{
			newMockStep("apply-1", &order),
			newMockStepWithError("apply-2", &order, errors.New("boom")),
		},
	})

	if result.Err == nil {
		t.Fatalf("Execute() expected apply error")
	}

	// apply-1 succeeds, apply-2 fails, rollback of apply-1 fires
	wantOrder := []string{"run:apply-1", "run:apply-2", "rollback:apply-1"}
	if !reflect.DeepEqual(order, wantOrder) {
		t.Fatalf("execution order = %v, want %v", order, wantOrder)
	}

	if result.Rollback.Stage != StageRollback {
		t.Fatalf("rollback stage = %q", result.Rollback.Stage)
	}
	if !result.Rollback.Success {
		t.Fatalf("rollback expected success, got err = %v", result.Rollback.Err)
	}
}

func TestOrchestratorSkipsRollbackWhenPolicyDisabled(t *testing.T) {
	order := []string{}
	o := NewOrchestrator(RollbackPolicy{OnApplyFailure: false})

	result := o.Execute(StagePlan{
		Apply: []Step{
			newMockStepWithError("apply-1", &order, errors.New("boom")),
		},
	})

	if result.Err == nil {
		t.Fatalf("Execute() expected error")
	}
	if len(result.Rollback.Steps) != 0 {
		t.Fatalf("rollback steps = %d, want 0", len(result.Rollback.Steps))
	}
}

func TestOrchestratorWithProgressFunc(t *testing.T) {
	order := []string{}
	events := []ProgressEvent{}

	o := NewOrchestrator(
		RollbackPolicy{OnApplyFailure: false},
		WithProgressFunc(func(e ProgressEvent) {
			events = append(events, e)
		}),
	)

	result := o.Execute(StagePlan{
		Prepare: []Step{newMockStep("prep", &order)},
		Apply:   []Step{newMockStep("act", &order)},
	})

	if result.Err != nil {
		t.Fatalf("unexpected error: %v", result.Err)
	}

	// prep: running+succeeded; act: running+succeeded = 4 events
	if len(events) != 4 {
		t.Fatalf("events = %d, want 4", len(events))
	}
}

func TestOrchestratorRollbackCalledInReverseOrderExactlyOnce(t *testing.T) {
	order := []string{}
	o := NewOrchestrator(DefaultRollbackPolicy())

	result := o.Execute(StagePlan{
		Apply: []Step{
			newMockStep("a", &order),
			newMockStep("b", &order),
			newMockStepWithError("c", &order, errors.New("fail")),
		},
	})

	if result.Err == nil {
		t.Fatalf("expected error")
	}

	// a and b succeed, c fails → rollback b then a (reverse)
	wantOrder := []string{"run:a", "run:b", "run:c", "rollback:b", "rollback:a"}
	if !reflect.DeepEqual(order, wantOrder) {
		t.Fatalf("execution order = %v, want %v", order, wantOrder)
	}
}
