---
name: todoist
description: >
  List, add, complete, and delete Todoist tasks via the Todoist REST API v2.
  Trigger: "todoist", "tarea", "todo", "task", "pendiente".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
allowed-tools: Read, Bash
---

# Todoist

Manages Todoist tasks via the REST API v2: list active tasks, add new ones, mark as complete, or delete.

## Setup

1. Go to [Todoist Settings → Integrations → API token](https://app.todoist.com/app/settings/integrations/developer)
2. Copy your personal API token

```bash
export TODOIST_API_TOKEN="your_api_token_here"
```

**Install dependencies:**
```bash
pip install requests
```

## Usage

```bash
# List all active tasks
python3 skills/productivity/todoist/scripts/manage.py --action list

# Add a new task
python3 skills/productivity/todoist/scripts/manage.py --action add --content "Buy groceries"

# Add a task with due date and project
python3 skills/productivity/todoist/scripts/manage.py --action add \
  --content "Review PR" \
  --due-string "tomorrow" \
  --project-id "2345678901"

# Mark a task as complete
python3 skills/productivity/todoist/scripts/manage.py --action complete --task-id "1234567890"

# Delete a task
python3 skills/productivity/todoist/scripts/manage.py --action delete --task-id "1234567890"
```

## Requirements

- `TODOIST_API_TOKEN` — personal API token from Todoist Settings → Integrations
- pip: `requests`

## How to use

"Agregar una tarea para revisar el PR de Juan para mañana"
"Mostrar todas las tareas pendientes en Todoist"
"Marcar como completada la tarea 1234567890"

## Script

Run `scripts/manage.py --action {list,add,complete,delete} [options]`

| Action     | Required args | Optional args                  |
|------------|---------------|--------------------------------|
| `list`     | —             | —                              |
| `add`      | `--content`   | `--project-id`, `--due-string` |
| `complete` | `--task-id`   | —                              |
| `delete`   | `--task-id`   | —                              |
