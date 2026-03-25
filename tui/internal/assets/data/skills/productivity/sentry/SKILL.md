---
name: sentry
description: >
  Interact with Sentry error tracking via REST API. List issues, inspect issue details,
  and resolve issues — no Sentry CLI required.
  Trigger: "sentry", "error", "exception", "issue", "resolve issue", "sentry issue".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Sentry

Manages Sentry issues via the REST API. Pure Python, no external dependencies.

## Setup

1. Generate an auth token: Sentry → Settings → API → Auth Tokens → Create New Token
2. Required scopes: `event:read`, `event:write`, `project:read`

```bash
export SENTRY_AUTH_TOKEN="your_token_here"
export SENTRY_ORG="your-org-slug"
```

## Usage

```bash
# List open issues for a project (default limit: 25)
python3 skills/productivity/sentry/scripts/sentry.py list-issues my-project
python3 skills/productivity/sentry/scripts/sentry.py list-issues my-project --limit 10

# Get full details of a specific issue by its ID
python3 skills/productivity/sentry/scripts/sentry.py get-issue 1234567890

# Resolve an issue by its ID
python3 skills/productivity/sentry/scripts/sentry.py resolve 1234567890
```

## Notes

- `SENTRY_AUTH_TOKEN` — required. Token is masked in all log output (only first 4 chars shown).
- `SENTRY_ORG` — required. The organization slug (visible in your Sentry URL: `sentry.io/organizations/<slug>/`)
- Issue IDs are numeric strings visible in the Sentry web UI URL
- `resolve` sets the issue status to `resolved` via a PATCH request
- API base: `https://sentry.io/api/0/`
