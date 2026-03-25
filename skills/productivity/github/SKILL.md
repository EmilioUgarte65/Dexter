---
name: github
description: >
  Interact with GitHub repositories via REST API v3. List issues, create issues,
  view pull requests, merge PRs, and list releases — no gh CLI required.
  Trigger: "github", "gh", "issue", "pull request", "PR", "release", "repo".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# GitHub

Manages GitHub repositories via the REST API v3. Pure Python, no external dependencies.

## Setup

1. Create a Personal Access Token: GitHub → Settings → Developer Settings → PAT → Generate new token
2. Required scopes: `repo` (full control of private repos) or `public_repo` (public only)

```bash
export GITHUB_TOKEN="ghp_..."
export GITHUB_DEFAULT_REPO="owner/repo"   # optional default repository
```

## Usage

```bash
# List issues
python3 skills/productivity/github/scripts/gh_client.py issues owner/repo
python3 skills/productivity/github/scripts/gh_client.py issues owner/repo --state closed

# Create an issue
python3 skills/productivity/github/scripts/gh_client.py create-issue owner/repo "Bug: login fails" "Steps to reproduce..."

# List pull requests
python3 skills/productivity/github/scripts/gh_client.py pr-list owner/repo
python3 skills/productivity/github/scripts/gh_client.py pr-list owner/repo --state closed

# Merge a pull request
python3 skills/productivity/github/scripts/gh_client.py pr-merge owner/repo 42

# List releases
python3 skills/productivity/github/scripts/gh_client.py release owner/repo
```

## Notes

- `GITHUB_TOKEN` — required for private repos. Public API works without token but is rate-limited (60 req/hr)
- `GITHUB_DEFAULT_REPO` — if set, `owner/repo` argument can be omitted (pass `""` to use it)
- Rate limit with token: 5,000 requests/hour
- `pr-merge` uses squash merge by default
