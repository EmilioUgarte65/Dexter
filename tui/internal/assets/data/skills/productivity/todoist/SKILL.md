---
name: todoist
description: >
  Manage Todoist tasks via REST API v2: list tasks by project, add tasks, complete tasks.
  Auth via TODOIST_API_TOKEN env var. Token is never logged.
  Trigger: "todoist", "task", "todo", "add task", "complete task", "list tasks".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Todoist

Manages tasks in Todoist via the [REST API v2](https://developer.todoist.com/rest/v2/). Supports listing tasks by project, adding tasks with due dates and priorities, and marking tasks as complete.

## Setup

1. Get your API token from [Todoist Settings → Integrations → Developer](https://app.todoist.com/app/settings/integrations/developer).
2. Export the token:

```bash
export TODOIST_API_TOKEN="your_token_here"
```

## Usage

```bash
# List all active tasks (across all projects)
python3 skills/productivity/todoist/scripts/todoist.py list

# List tasks in a specific project (by project ID)
python3 skills/productivity/todoist/scripts/todoist.py list --project-id 2203306141

# Add a task with natural language due date (priority 1=normal … 4=urgent)
python3 skills/productivity/todoist/scripts/todoist.py add "Write Q3 report" --due "next Monday" --priority 3

# Add a task with no due date
python3 skills/productivity/todoist/scripts/todoist.py add "Buy coffee"

# Complete (close) a task by ID
python3 skills/productivity/todoist/scripts/todoist.py complete 2995104339
```

## Notes

- `TODOIST_API_TOKEN` — required. Treated as a secret: masked in all log output (shown as `***`).
- Priority mapping: `1` = normal, `2` = medium, `3` = high, `4` = urgent (matches Todoist's internal scale).
- `--due` accepts Todoist natural language strings (e.g. `"tomorrow"`, `"every Monday"`, `"Jun 15"`).
- `--project-id` filters the `list` command. Find project IDs with Todoist's web app URL or the API.
- Task IDs are shown in the `list` output — copy them for use with `complete`.
- The script uses stdlib `urllib` only — no `requests` required.
