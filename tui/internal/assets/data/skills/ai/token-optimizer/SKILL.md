---
name: token-optimizer
description: >
  Tracks token usage patterns across sessions and suggests creating skills when
  the same type of problem is solved repeatedly. Converts repeated reasoning into
  cached skills for compound savings over time.
  Trigger: token optimizer, cuánto gasté, token usage, optimize tokens, ahorro tokens
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Token Optimizer Skill

## Purpose

Every repeated reasoning chain is wasted money. This skill tracks what tasks consume
tokens, finds patterns in repeated work, and tells you exactly when to create a skill
to cache that reasoning permanently.

## Cost Formula (Claude Sonnet pricing)

```
cost_usd = (input_tokens * 0.000003) + (output_tokens * 0.000015)
```

Examples:
- 1000 in + 500 out = $0.0105
- 5000 in + 2000 out = $0.045
- 10 sessions of the same task = 10× that cost → skill saves all of it

## Mandatory Post-Session Protocol

After EVERY session, the AI MUST:

1. Review what task types were solved in this session
2. Log each significant task via the optimizer:
   ```bash
   python3 skills/ai/token-optimizer/scripts/optimizer.py log <task_type> <input_tokens> <output_tokens> [--session SESSION_ID]
   ```
3. Run suggest to check if any pattern has crossed the threshold:
   ```bash
   python3 skills/ai/token-optimizer/scripts/optimizer.py suggest
   ```
4. If suggest outputs skill creation recommendations → **propose them to the user**

## When to Suggest Skill Creation

Trigger suggestion when the SAME task_type appears 3+ times across sessions:
- This means the reasoning was repeated from scratch 3 times
- Estimated wasted cost: 3× the average session cost for that type
- Action: run `python3 skills/skill-creator/scripts/create.py new <name>`

The optimizer does this automatically — trust its output.

## Skill Creation Command

When the optimizer recommends creating a skill:

```bash
# Create the skill scaffold
python3 skills/skill-creator/scripts/create.py new <skill-name>

# Then populate the SKILL.md with the recurring pattern
```

Do NOT skip this step. The compounding savings are real: a skill created after 3
occurrences saves cost on every future occurrence — potentially hundreds of sessions.

## How to Estimate Tokens Before Running

Use these rough estimates when logging tasks:

| Task type | Typical input | Typical output |
|-----------|--------------|----------------|
| Short summary | 500 | 200 |
| Code format | 300 | 300 |
| File operation | 200 | 100 |
| Architecture review | 3000 | 1500 |
| SDD phase | 5000 | 2000 |
| Bug analysis | 2000 | 800 |
| Security audit | 4000 | 1500 |

## Script Reference

```bash
# Log a task after completion
python3 skills/ai/token-optimizer/scripts/optimizer.py log "code-format" 300 300

# View usage report for last 7 days
python3 skills/ai/token-optimizer/scripts/optimizer.py report --days 7

# Get skill creation suggestions (run after every session)
python3 skills/ai/token-optimizer/scripts/optimizer.py suggest

# Clean up old logs (keep last 30 days)
python3 skills/ai/token-optimizer/scripts/optimizer.py reset --days 30
```

## Storage

Logs are stored at `~/.local/share/dexter/token_log.jsonl` — one JSON object per line.
No external dependencies. Safe to inspect, grep, or back up manually.

## When the Optimizer Says "Create a Skill"

This is not a suggestion — it is a directive. The agent MUST:
1. Show the user the recommendation with estimated savings
2. Ask for confirmation
3. Run the skill-creator command
4. Guide the user through populating the new skill

The optimizer exists to pay for itself. Every skill it creates reduces future costs.
