#!/usr/bin/env python3
"""
Dexter Webhook Server — stdlib-only HTTP server for incoming webhooks.

Reads handlers from ~/.dexter/webhooks.json and executes configured actions
when matching POST requests arrive.

Usage:
    python3 webhook_server.py               # start server on default port
    python3 webhook_server.py --port 8080   # custom port
    python3 webhook_server.py --list        # list registered handlers and exit
    python3 webhook_server.py --help        # show this help
"""

import argparse
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ── Config paths ──────────────────────────────────────────────────────────────

DEXTER_DIR = Path.home() / ".dexter"
HANDLERS_FILE = DEXTER_DIR / "webhooks.json"
LOG_FILE = DEXTER_DIR / "webhook-log.jsonl"
DEFAULT_PORT = int(os.environ.get("WH_PORT", "4242"))

SERVER_START_TIME = time.time()


# ── Handler loading ───────────────────────────────────────────────────────────

def load_handlers() -> list[dict]:
    """Load webhook handlers from ~/.dexter/webhooks.json."""
    if not HANDLERS_FILE.exists():
        return []
    try:
        with open(HANDLERS_FILE) as f:
            data = json.load(f)
        if not isinstance(data, list):
            print(f"[Dexter] Warning: {HANDLERS_FILE} must be a JSON array", file=sys.stderr)
            return []
        return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"[Dexter] Error loading handlers: {e}", file=sys.stderr)
        return []


def find_handler(handlers: list[dict], path: str) -> dict | None:
    """Return the first handler whose path matches the request path."""
    for h in handlers:
        if h.get("path") == path:
            return h
    return None


# ── HMAC validation ───────────────────────────────────────────────────────────

def verify_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    """Validate X-Hub-Signature-256 header against body + secret."""
    if not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


# ── Logging ───────────────────────────────────────────────────────────────────

def log_event(path: str, matched_id: str | None, exit_code: int | None, error: str | None = None):
    """Append a JSONL log entry to ~/.dexter/webhook-log.jsonl."""
    DEXTER_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": path,
        "matched_id": matched_id,
        "exit_code": exit_code,
    }
    if error:
        entry["error"] = error
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        print(f"[Dexter] Warning: could not write log: {e}", file=sys.stderr)


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class WebhookHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Suppress default access log; we do our own structured logging
        print(f"[Dexter] {self.address_string()} - {fmt % args}", file=sys.stderr)

    def send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/status":
            handlers = load_handlers()
            uptime = int(time.time() - SERVER_START_TIME)
            self.send_json(200, {
                "ok": True,
                "uptime_seconds": uptime,
                "handlers": [
                    {"id": h.get("id"), "source": h.get("source"), "path": h.get("path")}
                    for h in handlers
                ],
            })
        else:
            self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        handlers = load_handlers()
        handler = find_handler(handlers, self.path)

        if handler is None:
            log_event(self.path, None, None, "no handler matched")
            self.send_json(404, {"ok": False, "error": "no handler for this path"})
            return

        handler_id = handler.get("id", "unknown")
        secret = handler.get("secret", "")

        # HMAC validation if secret is configured
        if secret:
            sig_header = self.headers.get("X-Hub-Signature-256")
            if not verify_signature(secret, body, sig_header):
                log_event(self.path, handler_id, None, "signature mismatch")
                self.send_json(403, {"ok": False, "error": "invalid signature"})
                return

        # Execute action
        action = handler.get("action", "")
        if not action:
            log_event(self.path, handler_id, None, "no action configured")
            self.send_json(200, {"ok": True, "id": handler_id, "action_exit": None})
            return

        try:
            result = subprocess.run(
                action,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            log_event(self.path, handler_id, None, "action timed out")
            self.send_json(200, {"ok": True, "id": handler_id, "action_exit": None, "warning": "action timed out"})
            return
        except OSError as e:
            log_event(self.path, handler_id, None, str(e))
            self.send_json(500, {"ok": False, "id": handler_id, "error": str(e)})
            return

        log_event(self.path, handler_id, exit_code)
        self.send_json(200, {"ok": True, "id": handler_id, "action_exit": exit_code})


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dexter Webhook Server — receive HTTP webhooks and run actions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to listen on (default: {DEFAULT_PORT}, or WH_PORT env var)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print registered handlers and exit",
    )
    return parser.parse_args()


def cmd_list():
    handlers = load_handlers()
    if not handlers:
        print(f"No handlers registered. Edit {HANDLERS_FILE} to add some.")
        return
    print(f"Registered handlers ({len(handlers)}):")
    for h in handlers:
        secret_info = " [secret]" if h.get("secret") else ""
        print(f"  {h.get('id', '?'):20s}  {h.get('source', '?'):12s}  {h.get('path', '?')}{secret_info}")
        print(f"    action: {h.get('action', '(none)')}")


def main():
    args = parse_args()

    if args.list:
        cmd_list()
        return

    port = args.port
    DEXTER_DIR.mkdir(parents=True, exist_ok=True)

    handlers = load_handlers()
    print(f"[Dexter] Webhook server starting on port {port}")
    print(f"[Dexter] Handlers loaded: {len(handlers)}")
    print(f"[Dexter] Config: {HANDLERS_FILE}")
    print(f"[Dexter] Log: {LOG_FILE}")
    print(f"[Dexter] Status: http://localhost:{port}/status")

    server = HTTPServer(("", port), WebhookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Dexter] Webhook server stopped.")


if __name__ == "__main__":
    main()
