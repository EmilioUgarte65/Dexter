---
name: google-cloud
description: >
  Manage Google Cloud Platform resources: Compute Engine VMs, Cloud Storage buckets,
  SSH access. Wraps gcloud CLI when available, falls back to GCP REST API via stdlib urllib.
  Trigger: "gcloud", "google cloud", "GCP", "compute engine", "cloud storage", "bucket",
  "VM en GCP", "instancia GCP", "subir a GCS", "listar VMs", "start VM"
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Google Cloud

Manages GCP Compute Engine VMs and Cloud Storage buckets.
Wraps the `gcloud` CLI when installed; falls back to direct GCP REST API calls
via Python stdlib (`urllib`) — no extra dependencies required.

## Setup

```bash
export GOOGLE_CLOUD_PROJECT="my-project-id"
export GOOGLE_CLOUD_ZONE="us-central1-a"           # optional, default: us-central1-a
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

### Getting credentials

**Option A — gcloud CLI (recommended)**:
```bash
gcloud auth login
gcloud config set project my-project-id
```

**Option B — Service account (for automation)**:
1. Go to [GCP Console → IAM → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Create account → Grant roles: `Compute Admin`, `Storage Admin`
3. Create JSON key → Download → set `GOOGLE_APPLICATION_CREDENTIALS`

## Usage

### Virtual Machines (Compute Engine)

```bash
# List all VMs in project
python3 skills/productivity/google-cloud/scripts/gcloud.py list-vms

# Start / stop a VM
python3 skills/productivity/google-cloud/scripts/gcloud.py start-vm my-instance
python3 skills/productivity/google-cloud/scripts/gcloud.py stop-vm my-instance --zone us-east1-b

# SSH into a VM
python3 skills/productivity/google-cloud/scripts/gcloud.py ssh-vm my-instance

# Run a command via SSH
python3 skills/productivity/google-cloud/scripts/gcloud.py ssh-vm my-instance --cmd "df -h"
```

### Cloud Storage

```bash
# List buckets
python3 skills/productivity/google-cloud/scripts/gcloud.py list-buckets

# Upload a file
python3 skills/productivity/google-cloud/scripts/gcloud.py upload my-bucket ./local-file.txt

# Download a file
python3 skills/productivity/google-cloud/scripts/gcloud.py download my-bucket/remote-file.txt ./local-dest.txt
```

## Agent Instructions

When the user mentions "gcloud", "GCP", "google cloud", "compute engine", "cloud storage", or "bucket":

1. **Detect intent**:
   - VM operations → `list-vms`, `start-vm`, `stop-vm`, `ssh-vm`
   - Storage operations → `list-buckets`, `upload`, `download`
2. **Extract parameters** — VM name, zone, bucket name, file path from user message
3. **Check config** — `check_config()` validates env vars and prints setup instructions
4. **Run command** — prefer `gcloud` CLI if available, REST API as fallback
5. **Report result** — summarize VM states or storage operation outcome

### Common patterns

| User says | Command |
|-----------|---------|
| "list my VMs" | `gcloud.py list-vms` |
| "start instance my-vm" | `gcloud.py start-vm my-vm` |
| "SSH into my-server and check disk" | `gcloud.py ssh-vm my-server --cmd "df -h"` |
| "list my GCS buckets" | `gcloud.py list-buckets` |
| "upload file.zip to my-bucket" | `gcloud.py upload my-bucket file.zip` |

### Zone resolution

- If the user specifies a zone → use `--zone` flag
- If not specified → use `GOOGLE_CLOUD_ZONE` env var (default: `us-central1-a`)
- VM operations are zone-specific in GCP

## Error Handling

- Missing `GOOGLE_CLOUD_PROJECT` → `check_config()` prints instructions and exits 1
- VM not found → list available VMs with `list-vms`
- `gcloud` not installed → falls back to REST API automatically (no action needed)
- OAuth2 expired → re-run `gcloud auth login` or refresh service account key
- Storage 403 → account lacks `Storage Admin` role
