---
name: self-correct-loop
description: >
  Meta-skill: instructs the agent to iterate on code writing in a self-correction
  loop — write, run, read errors, fix, repeat — until tests pass or a max iteration
  limit is reached.
  Trigger: "self-correct", "auto-correct", "fix until it works", "loop until passing",
  "iterate until green", "fix this until all tests pass", "iterate on this code until it compiles",
  "keep fixing", "retry until it works"
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
allowed-tools: Read, Edit, Write, Bash
---

# Self-Correct Loop

A meta-skill that puts the agent into an iterative fix loop. Instead of writing code
once and stopping, the agent runs the tests or build, reads the failures, and keeps
fixing until everything passes — or until `MAX_ITERATIONS` is reached.

## When to Activate

Activate this skill whenever the user says something like:

- "fix this until all tests pass"
- "iterate on this code until it compiles"
- "keep fixing until it works"
- "loop until passing" / "loop until green"
- "auto-correct this", "self-correct"
- "retry until it works"

## Protocol

Follow these steps exactly:

### Step 1 — Write the code

Implement the change or fix as requested. Apply it to the relevant files.

### Step 2 — Run the tests / build

Execute the verification command. Common examples:
- `python -m pytest tests/`
- `go test ./...`
- `npm test`
- `python -m py_compile file.py`
- `cargo build`
- `tsc --noEmit`

If the user specified a command, use that. Otherwise infer from the project context.

### Step 3 — Evaluate the result

- **All passing** → STOP. Report success and what was changed.
- **Still failing** → read the full error output carefully. Identify the root cause.

### Step 4 — Fix

Apply the targeted fix to the failing code. Do NOT rewrite unrelated parts.

### Step 5 — Loop

Go back to Step 2. Increment the iteration counter.

### Step 6 — Hard stop at MAX_ITERATIONS

**Default MAX_ITERATIONS: 5**

If the loop reaches MAX_ITERATIONS without passing, STOP immediately and report:

```
Self-correct loop exhausted after {N} iterations.

Tried:
- Iteration 1: [what was changed] → [error summary]
- Iteration 2: [what was changed] → [error summary]
...

Current state: [describe what's still failing and why]

Recommendation: [what the agent thinks is needed — human review, missing context, etc.]
```

Do NOT continue iterating beyond MAX_ITERATIONS. This prevents infinite loops and
protects against cases where the agent is stuck in a wrong direction.

## Rules

1. **Read errors completely** — do not skim. The root cause is often in the last line.
2. **Fix surgically** — change only what the error indicates. Avoid speculative rewrites.
3. **One fix per iteration** — if there are multiple failures, fix the first blocking one.
4. **Track what you tried** — keep a mental log of each iteration's change + outcome.
5. **Stop at MAX_ITERATIONS** — never bypass this limit, even if close to passing.
6. **Report clearly at the end** — whether success or exhaustion, always summarize.

## Examples

### Natural language triggers

```
"Fix this until all tests pass"
→ Activates self-correct loop with: python -m pytest

"Iterate on this code until it compiles"
→ Activates self-correct loop with: detected build command

"Keep fixing the TypeScript errors"
→ Activates self-correct loop with: tsc --noEmit

"Loop until green"
→ Activates self-correct loop with: inferred test command
```

### Success report format

```
Self-correct loop: PASSED in {N} iteration(s).

Changes made:
- {file}: {what changed}
- {file}: {what changed}

Final run: all {N} tests passing.
```

### Exhaustion report format

```
Self-correct loop: EXHAUSTED after 5 iterations.

Iterations:
1. Fixed import path in foo.py → TypeError still on line 42
2. Added missing return type → AssertionError in test_bar
3. Corrected assertion logic → AttributeError in test_baz
4. Added missing attribute → 2 tests still failing
5. Adjusted constructor args → 1 test still failing

Remaining failure:
  test_qux: expected 3, got 4 — likely a logic error in the algorithm itself.

Recommendation: The algorithm logic needs human review. The fix requires
understanding the business rule behind the expected value.
```

## Notes

- This skill has no scripts — it is pure agent protocol.
- MAX_ITERATIONS can be adjusted by the user: "iterate up to 10 times".
- If the user says "stop" or "that's enough", exit the loop immediately.
- If the test command is unclear, ask the user ONCE before starting the loop.
