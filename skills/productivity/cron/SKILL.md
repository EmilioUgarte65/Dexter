---
name: cron
description: >
  Manage cron jobs: list, add, remove, and run tasks on schedule.
  Converts human-readable schedules to cron expressions automatically.
  Trigger: "cron", "schedule", "scheduled task", "crontab", "every 5 minutes", "programar tarea", "tarea programada".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Cron Manager

Manages cron jobs via the `crontab` CLI. Supports human-readable schedule input.

## Usage

```bash
# List current cron jobs
python3 skills/productivity/cron/scripts/cron_manager.py list

# Add a new cron job (with cron expression)
python3 skills/productivity/cron/scripts/cron_manager.py add "*/5 * * * *" "/usr/bin/python3 /home/user/script.py"

# Add with human-readable schedule
python3 skills/productivity/cron/scripts/cron_manager.py add "every 5 minutes" "/usr/bin/python3 /home/user/script.py"
python3 skills/productivity/cron/scripts/cron_manager.py add "every hour" "/usr/bin/backup.sh"
python3 skills/productivity/cron/scripts/cron_manager.py add "every day" "/usr/bin/cleanup.sh" --comment "daily cleanup"

# Remove jobs matching a pattern
python3 skills/productivity/cron/scripts/cron_manager.py remove "script.py"

# Run a command immediately (outside cron)
python3 skills/productivity/cron/scripts/cron_manager.py run-now "/usr/bin/python3 /home/user/script.py"

# View recent cron logs
python3 skills/productivity/cron/scripts/cron_manager.py logs
python3 skills/productivity/cron/scripts/cron_manager.py logs --tail 50
```

## Human → Cron Schedule Conversion

| Human phrase              | Cron expression  |
|---------------------------|------------------|
| every minute              | `* * * * *`      |
| every 5 minutes           | `*/5 * * * *`    |
| every 15 minutes          | `*/15 * * * *`   |
| every 30 minutes          | `*/30 * * * *`   |
| every hour                | `0 * * * *`      |
| every 2 hours             | `0 */2 * * *`    |
| every day / daily         | `0 0 * * *`      |
| every week / weekly       | `0 0 * * 0`      |
| every month / monthly     | `0 0 1 * *`      |
| at midnight               | `0 0 * * *`      |
| at noon                   | `0 12 * * *`     |

## Notes

- Requires `crontab` CLI to be installed (standard on Linux/macOS)
- `remove` removes ALL jobs that contain the given pattern — review with `list` first
- `logs` reads from `/var/log/syslog` or `/var/log/cron` depending on the OS
