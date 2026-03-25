---
name: sentry
description: >
  Interact with Sentry error tracking via REST API. List unresolved issues,
  inspect issue details and stacktraces, resolve issues, and list recent events —
  no Sentry CLI required.
  Trigger: "sentry", "error", "issue", "crash", "exception", "bug report"
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
allowed-tools: Read, Edit, Write, Bash
---

# Sentry

Manages Sentry issues via the REST API. Pure Python, no external dependencies.

## Setup

1. Generate an auth token: Sentry → Settings → API → Auth Tokens → Create New Token
2. Required scopes: `event:read`, `event:write`, `project:read`

```bash
export SENTRY_AUTH_TOKEN="your_token_here"
export SENTRY_ORG="your-org-slug"
export SENTRY_PROJECT="your-project-slug"   # optional default project
```

## Usage

```bash
# List unresolved issues for a project (default limit: 10)
python3 skills/dev/sentry/scripts/sentry_client.py --action list-issues
python3 skills/dev/sentry/scripts/sentry_client.py --action list-issues --project my-project

# Get full details and stacktrace of a specific issue
python3 skills/dev/sentry/scripts/sentry_client.py --action get-issue --issue-id 1234567890

# Resolve an issue by its ID
python3 skills/dev/sentry/scripts/sentry_client.py --action resolve-issue --issue-id 1234567890

# List recent events for an issue
python3 skills/dev/sentry/scripts/sentry_client.py --action list-events --issue-id 1234567890
```

## Agent Instructions

When the user mentions sentry, errors, crashes, exceptions, or bug reports:

1. **Detect intent** — list issues / inspect an issue / resolve / view events
2. **Identify project** — use `SENTRY_PROJECT` env var or ask the user for the project slug
3. **Run command** — call the script with `--action` and `--issue-id` as needed
4. **Report result** — summarize findings in plain language, highlight critical errors

### Common patterns

| User says | Command to run |
|-----------|---------------|
| "show sentry errors" | `--action list-issues` |
| "what's wrong with issue 123" | `--action get-issue --issue-id 123` |
| "mark issue 123 as resolved" | `--action resolve-issue --issue-id 123` |
| "show recent crashes for issue 123" | `--action list-events --issue-id 123` |

## Notes

- `SENTRY_AUTH_TOKEN` — required. Masked in all log output (only first 4 chars shown)
- `SENTRY_ORG` — required. The organization slug (visible in Sentry URL: `sentry.io/organizations/<slug>/`)
- `SENTRY_PROJECT` — optional default project slug. Can be overridden with `--project`
- Issue IDs are numeric strings visible in the Sentry web UI URL
- `resolve-issue` sets status to `resolved` via PUT request
- API base: `https://sentry.io/api/0/`
