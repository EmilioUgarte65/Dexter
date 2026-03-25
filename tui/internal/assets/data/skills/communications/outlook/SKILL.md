---
name: outlook
description: >
  Send and read Outlook email via Microsoft Graph API. Supports sending messages,
  listing inbox, and reading individual messages.
  Trigger: "outlook", "email", "send email", "inbox", "read email", "Office 365 mail".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Outlook

Sends and reads Outlook/Office 365 email via the Microsoft Graph API. Uses OAuth2 device flow
for authentication. Pure Python, no external dependencies.

## Setup

1. Register an app in Azure Portal: Azure Active Directory → App registrations → New registration
2. Add API permissions: `Microsoft Graph` → `Mail.Read`, `Mail.Send` (Delegated)
3. Note the Client ID, Client Secret, and Tenant ID

```bash
export OUTLOOK_CLIENT_ID="your-client-id"
export OUTLOOK_CLIENT_SECRET="your-client-secret"
export OUTLOOK_TENANT_ID="your-tenant-id"
```

A token cache file is stored at `~/.dexter/outlook_token.json` to avoid re-authenticating each run.

## Usage

```bash
# Send an email
python3 skills/communications/outlook/scripts/send.py send \
  --to "recipient@example.com" \
  --subject "Hello from Dexter" \
  --body "Message body here."

# List inbox (default: 10 messages)
python3 skills/communications/outlook/scripts/send.py list-inbox
python3 skills/communications/outlook/scripts/send.py list-inbox --limit 20

# Read a specific message by ID
python3 skills/communications/outlook/scripts/send.py read AAMkAGI...
```

## Notes

- On first run, the script starts an **OAuth2 device flow**: it prints a URL and a code. Open the URL in a browser, enter the code, and sign in. The token is then cached locally.
- All credentials (`OUTLOOK_CLIENT_ID`, `OUTLOOK_CLIENT_SECRET`) are masked in logs.
- **External recipient warning**: if the `--to` address is outside the authenticated tenant domain, a confirmation prompt is shown before sending.
- Graph API base: `https://graph.microsoft.com/v1.0/me/`
