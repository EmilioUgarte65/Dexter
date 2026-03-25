#!/usr/bin/env python3
"""
Dexter — Google Cloud Platform client.
Wraps gcloud CLI when available; falls back to GCP REST API via stdlib urllib.

Usage:
  gcloud.py list-vms
  gcloud.py start-vm <name> [--zone ZONE]
  gcloud.py stop-vm  <name> [--zone ZONE]
  gcloud.py ssh-vm   <name> [--zone ZONE] [--cmd CMD]
  gcloud.py list-buckets
  gcloud.py upload   <bucket> <file>
  gcloud.py download <bucket/path> <dest>

Environment:
  GOOGLE_CLOUD_PROJECT            GCP project ID (required)
  GOOGLE_CLOUD_ZONE               Default zone (default: us-central1-a)
  GOOGLE_APPLICATION_CREDENTIALS  Path to service account JSON (for REST fallback)
"""

import sys
import os
import json
import argparse
import subprocess
import urllib.request
import urllib.error
import urllib.parse
import shutil
from pathlib import Path
from typing import Any, Optional

# ─── Config from env ──────────────────────────────────────────────────────────

PROJECT     = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
DEFAULT_ZONE = os.environ.get("GOOGLE_CLOUD_ZONE", "us-central1-a")
CREDENTIALS  = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

COMPUTE_BASE = "https://compute.googleapis.com/compute/v1"
STORAGE_BASE = "https://storage.googleapis.com/storage/v1"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

_access_token_cache: Optional[str] = None


# ─── Config check ─────────────────────────────────────────────────────────────

def check_config():
    """Validate required env vars. Exits 1 with instructions if missing."""
    if not PROJECT:
        print(
            f"{RED}Error: GOOGLE_CLOUD_PROJECT is not set.{RESET}\n"
            "\nSet it with:\n"
            "  export GOOGLE_CLOUD_PROJECT=my-project-id\n"
            "\nOr configure gcloud CLI:\n"
            "  gcloud config set project my-project-id",
            file=sys.stderr,
        )
        sys.exit(1)


# ─── gcloud CLI helpers ───────────────────────────────────────────────────────

def _gcloud_available() -> bool:
    return shutil.which("gcloud") is not None


def _run_gcloud(*args: str) -> str:
    """Run a gcloud command and return stdout. Exits on error."""
    cmd = ["gcloud", *args, "--format=json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"{RED}gcloud error:{RESET} {e.stderr.strip()}", file=sys.stderr)
        sys.exit(1)


# ─── REST API helpers ─────────────────────────────────────────────────────────

def _get_access_token() -> str:
    """Get OAuth2 access token from service account or metadata server."""
    global _access_token_cache

    if _access_token_cache:
        return _access_token_cache

    # Try gcloud token first (if CLI is available)
    if _gcloud_available():
        try:
            result = subprocess.run(
                ["gcloud", "auth", "print-access-token"],
                capture_output=True, text=True, check=True,
            )
            _access_token_cache = result.stdout.strip()
            return _access_token_cache
        except subprocess.CalledProcessError:
            pass

    # Try metadata server (for GCE instances)
    try:
        req = urllib.request.Request(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            token_data = json.loads(resp.read())
            _access_token_cache = token_data["access_token"]
            return _access_token_cache
    except Exception:
        pass

    # Try service account JWT flow
    if CREDENTIALS and Path(CREDENTIALS).exists():
        return _service_account_token()

    print(
        f"{RED}Error: Could not obtain GCP access token.{RESET}\n"
        "Options:\n"
        "  1. Install gcloud CLI: https://cloud.google.com/sdk/docs/install\n"
        "     Then run: gcloud auth login\n"
        "  2. Set GOOGLE_APPLICATION_CREDENTIALS to a service account JSON file\n"
        "  3. Run this on a GCE instance with a service account attached",
        file=sys.stderr,
    )
    sys.exit(1)


def _service_account_token() -> str:
    """Exchange service account JSON key for an access token."""
    import base64
    import time
    import hmac
    import hashlib

    with open(CREDENTIALS) as f:
        sa = json.load(f)

    if sa.get("type") != "service_account":
        print(f"{RED}Error: GOOGLE_APPLICATION_CREDENTIALS is not a service account key.{RESET}", file=sys.stderr)
        sys.exit(1)

    now = int(time.time())
    header  = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "iss": sa["client_email"],
        "scope": "https://www.googleapis.com/auth/cloud-platform",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }

    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header_b64  = b64url(json.dumps(header).encode())
    payload_b64 = b64url(json.dumps(payload).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()

    # Use cryptography library if available for RS256
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        private_key = serialization.load_pem_private_key(
            sa["private_key"].encode(), password=None
        )
        signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        jwt = f"{header_b64}.{payload_b64}.{b64url(signature)}"
    except ImportError:
        print(
            f"{YELLOW}Warning: 'cryptography' package not installed — cannot sign JWT.{RESET}\n"
            "Install it: pip install cryptography\n"
            "Or use: gcloud auth login",
            file=sys.stderr,
        )
        sys.exit(1)

    # Exchange JWT for access token
    data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt,
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        token_data = json.loads(resp.read())
        return token_data["access_token"]


def _api_request(method: str, url: str, data: dict | None = None) -> Any:
    """Make an authenticated GCP API request."""
    token = _get_access_token()
    body  = json.dumps(data).encode() if data else None
    req   = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"{RED}API error {e.code}: {error_body}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── VM commands ──────────────────────────────────────────────────────────────

def cmd_list_vms(args):
    check_config()

    if _gcloud_available():
        output = _run_gcloud("compute", "instances", "list", "--project", PROJECT)
        instances = json.loads(output)
    else:
        url = f"{COMPUTE_BASE}/projects/{PROJECT}/aggregated/instances"
        data = _api_request("GET", url)
        instances = []
        for zone_data in data.get("items", {}).values():
            instances.extend(zone_data.get("instances", []))

    if not instances:
        print(f"{YELLOW}No VM instances found in project {PROJECT}.{RESET}")
        return

    print(f"\n{BOLD}VM Instances — {PROJECT}{RESET}")
    print(f"{'Name':<30} {'Zone':<25} {'Status':<12} {'Machine Type'}")
    print("─" * 85)
    for inst in sorted(instances, key=lambda x: x.get("name", "")):
        status = inst.get("status", "UNKNOWN")
        color  = GREEN if status == "RUNNING" else (RED if status == "TERMINATED" else YELLOW)
        zone   = inst.get("zone", "").split("/")[-1]
        mtype  = inst.get("machineType", "").split("/")[-1]
        print(f"  {inst['name']:<28} {zone:<25} {color}{status:<12}{RESET} {mtype}")
    print(f"\nTotal: {len(instances)} instance(s)")


def cmd_start_vm(args):
    check_config()
    zone = args.zone or DEFAULT_ZONE
    name = args.name

    print(f"Starting VM {YELLOW}{name}{RESET} in zone {zone}...")

    if _gcloud_available():
        _run_gcloud("compute", "instances", "start", name, "--zone", zone, "--project", PROJECT)
    else:
        url = f"{COMPUTE_BASE}/projects/{PROJECT}/zones/{zone}/instances/{name}/start"
        _api_request("POST", url)

    print(f"{GREEN}Started: {name}{RESET}")


def cmd_stop_vm(args):
    check_config()
    zone = args.zone or DEFAULT_ZONE
    name = args.name

    print(f"Stopping VM {YELLOW}{name}{RESET} in zone {zone}...")

    if _gcloud_available():
        _run_gcloud("compute", "instances", "stop", name, "--zone", zone, "--project", PROJECT)
    else:
        url = f"{COMPUTE_BASE}/projects/{PROJECT}/zones/{zone}/instances/{name}/stop"
        _api_request("POST", url)

    print(f"{GREEN}Stopped: {name}{RESET}")


def cmd_ssh_vm(args):
    check_config()
    zone = args.zone or DEFAULT_ZONE
    name = args.name

    if _gcloud_available():
        gcloud_args = ["compute", "ssh", name, "--zone", zone, "--project", PROJECT]
        if args.cmd:
            gcloud_args += ["--command", args.cmd]
        subprocess.run(["gcloud"] + gcloud_args)
    else:
        # Get external IP via API then SSH manually
        url  = f"{COMPUTE_BASE}/projects/{PROJECT}/zones/{zone}/instances/{name}"
        inst = _api_request("GET", url)
        interfaces = inst.get("networkInterfaces", [])
        external_ip = None
        for iface in interfaces:
            for ac in iface.get("accessConfigs", []):
                if "natIP" in ac:
                    external_ip = ac["natIP"]
                    break

        if not external_ip:
            print(f"{RED}Error: No external IP for {name}. Use gcloud CLI or VPN.{RESET}", file=sys.stderr)
            sys.exit(1)

        ssh_cmd = ["ssh", f"{external_ip}"]
        if args.cmd:
            ssh_cmd.append(args.cmd)
        print(f"Connecting to {external_ip}...")
        subprocess.run(ssh_cmd)


# ─── Storage commands ─────────────────────────────────────────────────────────

def cmd_list_buckets(args):
    check_config()

    if _gcloud_available():
        output   = _run_gcloud("storage", "buckets", "list", "--project", PROJECT)
        buckets  = json.loads(output)
    else:
        url     = f"{STORAGE_BASE}/b?project={PROJECT}"
        data    = _api_request("GET", url)
        buckets = data.get("items", [])

    if not buckets:
        print(f"{YELLOW}No buckets found in project {PROJECT}.{RESET}")
        return

    print(f"\n{BOLD}Cloud Storage Buckets — {PROJECT}{RESET}")
    for b in sorted(buckets, key=lambda x: x.get("name", "")):
        name     = b.get("name", "")
        location = b.get("location", b.get("storageClass", ""))
        print(f"  {GREEN}gs://{name}{RESET}  {YELLOW}{location}{RESET}")
    print(f"\nTotal: {len(buckets)} bucket(s)")


def cmd_upload(args):
    check_config()
    bucket   = args.bucket
    filepath = Path(args.file)

    if not filepath.exists():
        print(f"{RED}Error: file not found: {filepath}{RESET}", file=sys.stderr)
        sys.exit(1)

    if _gcloud_available():
        subprocess.run(
            ["gcloud", "storage", "cp", str(filepath), f"gs://{bucket}/{filepath.name}"],
            check=True,
        )
    else:
        # Multipart upload via JSON API
        url    = f"https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o?uploadType=media&name={urllib.parse.quote(filepath.name)}"
        token  = _get_access_token()
        data   = filepath.read_bytes()
        req    = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(data)),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read())
                print(f"{GREEN}Uploaded: gs://{bucket}/{result['name']}{RESET}")
        except urllib.error.HTTPError as e:
            print(f"{RED}Upload error {e.code}: {e.read().decode()}{RESET}", file=sys.stderr)
            sys.exit(1)
        return

    print(f"{GREEN}Uploaded: {filepath.name} → gs://{bucket}/{RESET}")


def cmd_download(args):
    check_config()
    # bucket/path format
    source = args.source
    dest   = Path(args.dest)

    if "/" not in source:
        print(f"{RED}Error: source must be 'bucket/object-path', got: {source!r}{RESET}", file=sys.stderr)
        sys.exit(1)

    bucket, object_path = source.split("/", 1)

    if _gcloud_available():
        subprocess.run(
            ["gcloud", "storage", "cp", f"gs://{bucket}/{object_path}", str(dest)],
            check=True,
        )
    else:
        url   = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{urllib.parse.quote(object_path, safe='')}?alt=media"
        token = _get_access_token()
        req   = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req) as resp:
                dest.write_bytes(resp.read())
        except urllib.error.HTTPError as e:
            print(f"{RED}Download error {e.code}: {e.read().decode()}{RESET}", file=sys.stderr)
            sys.exit(1)

    print(f"{GREEN}Downloaded: gs://{bucket}/{object_path} → {dest}{RESET}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Dexter — Google Cloud Platform client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list-vms
    sub.add_parser("list-vms", help="List all Compute Engine VM instances")

    # start-vm
    p_start = sub.add_parser("start-vm", help="Start a VM instance")
    p_start.add_argument("name", help="VM instance name")
    p_start.add_argument("--zone", default="", help=f"Zone (default: {DEFAULT_ZONE})")

    # stop-vm
    p_stop = sub.add_parser("stop-vm", help="Stop a VM instance")
    p_stop.add_argument("name", help="VM instance name")
    p_stop.add_argument("--zone", default="", help=f"Zone (default: {DEFAULT_ZONE})")

    # ssh-vm
    p_ssh = sub.add_parser("ssh-vm", help="SSH into a VM instance")
    p_ssh.add_argument("name", help="VM instance name")
    p_ssh.add_argument("--zone", default="", help=f"Zone (default: {DEFAULT_ZONE})")
    p_ssh.add_argument("--cmd", default="", help="Command to run via SSH instead of interactive shell")

    # list-buckets
    sub.add_parser("list-buckets", help="List Cloud Storage buckets")

    # upload
    p_upload = sub.add_parser("upload", help="Upload a file to Cloud Storage")
    p_upload.add_argument("bucket", help="Destination bucket name")
    p_upload.add_argument("file", help="Local file path to upload")

    # download
    p_download = sub.add_parser("download", help="Download a file from Cloud Storage")
    p_download.add_argument("source", help="Source path: bucket/object-path")
    p_download.add_argument("dest", help="Local destination path")

    args = parser.parse_args()

    dispatch = {
        "list-vms":      cmd_list_vms,
        "start-vm":      cmd_start_vm,
        "stop-vm":       cmd_stop_vm,
        "ssh-vm":        cmd_ssh_vm,
        "list-buckets":  cmd_list_buckets,
        "upload":        cmd_upload,
        "download":      cmd_download,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
