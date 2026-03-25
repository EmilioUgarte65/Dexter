#!/usr/bin/env python3
"""
Dexter LLM Router — check provider availability and pick the best one.

Reads ~/.dexter/llm-router.json for provider configuration.

Usage:
    python3 check_providers.py --check-all   # check all providers, print table
    python3 check_providers.py --best        # print only the best provider name
    python3 check_providers.py --json        # machine-readable JSON output
    python3 check_providers.py --help        # show this help
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

DEXTER_DIR = Path.home() / ".dexter"
CONFIG_FILE = DEXTER_DIR / "llm-router.json"

SUPPORTED_PROVIDERS = {"anthropic", "openai", "google", "ollama"}


# ── Config loading ────────────────────────────────────────────────────────────

def load_config() -> dict | None:
    if not CONFIG_FILE.exists():
        print(f"[Dexter] Warning: no config at {CONFIG_FILE}", file=sys.stderr)
        print(f"[Dexter] Copy notifications/llm-router.template.json to {CONFIG_FILE}", file=sys.stderr)
        return None
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[Dexter] Error reading config: {e}", file=sys.stderr)
        return None


# ── Provider checks ───────────────────────────────────────────────────────────

def check_anthropic(model: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"status": "no-key", "latency_ms": None}

    payload = json.dumps({
        "model": model,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    return _do_request(req)


def check_openai(model: str) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return {"status": "no-key", "latency_ms": None}

    payload = json.dumps({
        "model": model,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }).encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    return _do_request(req)


def check_google(model: str) -> dict:
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return {"status": "no-key", "latency_ms": None}

    payload = json.dumps({
        "contents": [{"parts": [{"text": "hi"}]}],
    }).encode()

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _do_request(req)


def check_ollama(provider_cfg: dict) -> dict:
    base_url = provider_cfg.get("base_url", "http://localhost:11434")
    req = urllib.request.Request(
        f"{base_url}/api/tags",
        method="GET",
    )
    return _do_request(req)


def _do_request(req: urllib.request.Request, timeout: int = 8) -> dict:
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"status": "available", "latency_ms": latency_ms}
    except urllib.error.HTTPError as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        # 4xx with a response still means the server is reachable
        if e.code in (400, 401, 422, 429):
            return {"status": "available", "latency_ms": latency_ms}
        return {"status": "unavailable", "latency_ms": latency_ms, "error": f"HTTP {e.code}"}
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return {"status": "unavailable", "latency_ms": None, "error": str(e)}


# ── Check dispatcher ──────────────────────────────────────────────────────────

def check_provider(p: dict) -> dict:
    name = p.get("name", "")
    model = p.get("model", "")

    if name == "anthropic":
        result = check_anthropic(model)
    elif name == "openai":
        result = check_openai(model)
    elif name == "google":
        result = check_google(model)
    elif name == "ollama":
        result = check_ollama(p)
    else:
        result = {"status": "unavailable", "latency_ms": None, "error": "unknown provider"}

    return {
        "name": name,
        "model": model,
        "priority": p.get("priority", 99),
        **result,
    }


def check_all_providers(providers: list[dict]) -> list[dict]:
    """Check all providers, sorted by priority."""
    sorted_providers = sorted(providers, key=lambda p: p.get("priority", 99))
    return [check_provider(p) for p in sorted_providers]


def pick_best(results: list[dict]) -> dict | None:
    """Return the available provider with the lowest priority number."""
    available = [r for r in results if r["status"] == "available"]
    if not available:
        return None
    return min(available, key=lambda r: r["priority"])


# ── Output formatters ─────────────────────────────────────────────────────────

def print_table(results: list[dict]):
    header = f"{'Provider':<14} {'Model':<30} {'Status':<14} {'Latency':>10}"
    print(header)
    print("-" * len(header))
    for r in results:
        latency = f"{r['latency_ms']} ms" if r["latency_ms"] is not None else "-"
        status = r["status"]
        print(f"{r['name']:<14} {r['model']:<30} {status:<14} {latency:>10}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dexter LLM Router — check provider availability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--check-all",
        action="store_true",
        help="Check all providers and print a status table",
    )
    group.add_argument(
        "--best",
        action="store_true",
        help="Print only the name of the best available provider",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (works with --check-all or --best)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    cfg = load_config()
    if cfg is None:
        sys.exit(0)

    providers = cfg.get("providers", [])
    if not providers:
        print("[Dexter] No providers configured in llm-router.json", file=sys.stderr)
        sys.exit(0)

    results = check_all_providers(providers)

    if args.best:
        best = pick_best(results)
        if best is None:
            if args.json:
                print(json.dumps({"best": None, "error": "no providers available"}))
            else:
                print("none")
            sys.exit(1)
        if args.json:
            print(json.dumps({"best": best["name"], "model": best["model"], "latency_ms": best["latency_ms"]}))
        else:
            print(best["name"])
        return

    # Default: --check-all (or bare invocation)
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_table(results)
        best = pick_best(results)
        if best:
            print(f"\nBest: {best['name']} ({best['model']}) — {best['latency_ms']} ms")
        else:
            print("\nNo providers available.")


if __name__ == "__main__":
    main()
