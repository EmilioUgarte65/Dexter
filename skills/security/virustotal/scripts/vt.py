#!/usr/bin/env python3
"""
Dexter VirusTotal Scanner — scan files and URLs via VT API v3.
Usage:
  python3 vt.py --file /path/to/file
  python3 vt.py --url https://example.com
  python3 vt.py --hash <sha256>
"""

import sys
import os
import hashlib
import argparse
import json
import time
from pathlib import Path

try:
    import urllib.request
    import urllib.error
except ImportError:
    pass


API_KEY = os.environ.get("VIRUSTOTAL_API_KEY", "")
BASE_URL = "https://www.virustotal.com/api/v3"
MAX_FILE_SIZE = 32 * 1024 * 1024  # 32 MB


def vt_request(method: str, endpoint: str, data=None, files=None) -> dict:
    if not API_KEY:
        print("Error: VIRUSTOTAL_API_KEY environment variable not set.", file=sys.stderr)
        print("Get a free key at https://www.virustotal.com/gui/sign-in", file=sys.stderr)
        sys.exit(1)

    url = f"{BASE_URL}{endpoint}"
    headers = {"x-apikey": API_KEY}

    if method == "GET":
        req = urllib.request.Request(url, headers=headers)
    elif method == "POST" and data:
        import urllib.parse
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    else:
        req = urllib.request.Request(url, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"VT API error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr)
        sys.exit(1)


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def print_report(name: str, report: dict, kind: str = "file"):
    stats = report.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
    results = report.get("data", {}).get("attributes", {}).get("last_analysis_results", {})

    malicious = stats.get("malicious", 0)
    suspicious = stats.get("suspicious", 0)
    total = sum(stats.values())
    detections = malicious + suspicious

    if detections == 0:
        verdict = "\033[92mCLEAN\033[0m"
    elif detections <= 2:
        verdict = "\033[93mSUSPICIOUS\033[0m"
    else:
        verdict = "\033[91mMALICIOUS\033[0m"

    print(f"\n{'File' if kind == 'file' else 'URL'}: {name}")
    print(f"Result: {detections}/{total} engines detected")
    print(f"Verdict: {verdict}")

    if detections > 0:
        print("\nDetections:")
        for engine, res in results.items():
            if res.get("category") in ("malicious", "suspicious"):
                cat = res.get("category", "")
                result_name = res.get("result", "—")
                color = "\033[91m" if cat == "malicious" else "\033[93m"
                print(f"  {color}─ {engine}: {result_name}\033[0m")

    print()
    return detections


def scan_file(filepath_str: str):
    filepath = Path(filepath_str).resolve()
    if not filepath.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    file_hash = sha256_file(filepath)
    print(f"SHA256: {file_hash}")

    # Check existing report first (avoid re-upload)
    report = vt_request("GET", f"/files/{file_hash}")
    if "data" in report:
        print(f"(Using cached report)")
        print_report(filepath.name, report, "file")
        return

    # Upload if under size limit
    if filepath.stat().st_size > MAX_FILE_SIZE:
        print(f"File too large for upload (>{MAX_FILE_SIZE // 1024 // 1024} MB) — reporting hash only")
        print("No existing VT report found for this hash.")
        return

    print("Uploading to VirusTotal...")
    # Note: multipart upload requires more complex handling
    # For simplicity, report that upload is not implemented in this version
    # and instruct user to use the web UI for new files
    print("Upload via API requires multipart form data — use virustotal.com for new file submissions.")
    print(f"Or check hash directly: vt.py --hash {file_hash}")


def scan_url(url: str):
    data = {"url": url}
    submit = vt_request("POST", "/urls", data=data)
    analysis_id = submit.get("data", {}).get("id", "")
    if not analysis_id:
        print("Failed to submit URL", file=sys.stderr)
        sys.exit(1)

    print(f"Submitted. Waiting for analysis...")
    time.sleep(15)  # VT needs time to analyze

    report = vt_request("GET", f"/analyses/{analysis_id}")
    print_report(url, report, "url")


def scan_hash(file_hash: str):
    report = vt_request("GET", f"/files/{file_hash}")
    if "data" not in report:
        print(f"No report found for hash: {file_hash}")
        return
    print_report(file_hash[:16] + "...", report, "file")


def main():
    parser = argparse.ArgumentParser(description="Dexter VirusTotal Scanner")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to file to scan")
    group.add_argument("--url", help="URL to scan")
    group.add_argument("--hash", help="SHA256 hash to look up")
    args = parser.parse_args()

    if args.file:
        scan_file(args.file)
    elif args.url:
        scan_url(args.url)
    elif args.hash:
        scan_hash(args.hash)


if __name__ == "__main__":
    main()
