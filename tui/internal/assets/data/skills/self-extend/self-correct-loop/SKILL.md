---
name: self-correct-loop
description: >
  Meta-skill: runs a shell command, captures its output, and attempts self-correction
  if it fails — re-running up to a configurable max number of iterations.
  Trigger: "self-correct", "retry on failure", "fix and rerun", "loop until success", "auto-fix command".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Self-Correct Loop

A meta-skill that runs a shell command and, if it exits with a non-zero code, passes the stderr
output back to the agent for a correction attempt — repeating up to `max_iterations` times.

## Security

Commands are validated against a **denylist** before execution. The following are blocked:

- `rm -rf` (recursive forced removal)
- `curl` or `wget` to external hosts
- `sudo` or `su`
- `mkfs`, `dd`, `> /dev/`
- Pipe chains that write to system paths (`/etc/`, `/usr/`, `/bin/`, `/sbin/`)

If the command matches any denylist rule, execution is refused immediately with exit code 1.

## Usage

```bash
# Run a command with up to 3 self-correction attempts (default)
python3 skills/self-extend/self-correct-loop/scripts/loop.py run "python3 myscript.py"

# Run with a custom iteration limit
python3 skills/self-extend/self-correct-loop/scripts/loop.py run "pytest tests/" --max-iterations 5

# Dry-run: validate command against denylist without executing
python3 skills/self-extend/self-correct-loop/scripts/loop.py check "rm -rf /"
```

## Output

On completion, the script prints a JSON summary:

```json
{
  "exit_code": 0,
  "iterations_used": 2,
  "stdout": "...",
  "stderr": ""
}
```

## Notes

- `max_iterations` defaults to 3. Set `--max-iterations` to override.
- The self-correction message fed back to the agent contains the full stderr from the last failed run.
- If all iterations are exhausted, the final non-zero exit code is returned.
- The denylist is intentionally strict — expand with caution.
