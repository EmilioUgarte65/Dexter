---
name: gmail
description: >
  Send, read, list, and search Gmail messages via the Gmail REST API with OAuth2.
  Uses google-auth-oauthlib when available, falls back to raw OAuth2 flow.
  Trigger: "gmail", "email", "send email", "correo", "mandar mail", "leer mail", "inbox".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Gmail

Sends and reads email via the Gmail API. First run requires OAuth2 browser authorization.

## Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable Gmail API
3. Create OAuth2 credentials → Desktop app → Download as `credentials.json`
4. First run will open browser for authorization

```bash
export GMAIL_CREDENTIALS_FILE="$HOME/.config/dexter/gmail_credentials.json"
export GMAIL_TOKEN_FILE="$HOME/.config/dexter/gmail_token.json"   # auto-created on first auth
```

**Optional: Install google-auth-oauthlib for smoother OAuth flow:**
```bash
pip install google-auth-oauthlib google-auth-httplib2
```

## Usage

```bash
# Send an email
python3 skills/productivity/gmail/scripts/gmail.py send "recipient@example.com" "Subject here" "Body of the email"

# List recent inbox messages
python3 skills/productivity/gmail/scripts/gmail.py list
python3 skills/productivity/gmail/scripts/gmail.py list --limit 20

# List with a Gmail query filter
python3 skills/productivity/gmail/scripts/gmail.py list --query "is:unread"

# Search emails
python3 skills/productivity/gmail/scripts/gmail.py search "from:boss@company.com subject:urgent"

# Read a specific message
python3 skills/productivity/gmail/scripts/gmail.py read <message_id>
```

## Notes

- `GMAIL_CREDENTIALS_FILE` — required. OAuth2 client credentials JSON from Google Cloud Console
- `GMAIL_TOKEN_FILE` — where the access token is cached after first login (auto-created)
- Scopes used: `gmail.send`, `gmail.readonly`
- First run opens a browser window for Google sign-in — authorize and close
- Token is cached and auto-refreshed; re-auth only needed if token is deleted or expires
