#!/usr/bin/env python3
"""
Dexter AI Router — routes tasks to Ollama (local) or cloud models.
Uses Ollama REST API via stdlib urllib only.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Iterator

# ─── Config ──────────────────────────────────────────────────────────────────

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_DEFAULT_MODEL", "llama3.2")

# ─── Colors ──────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

def ok(msg: str) -> None:
    print(f"{GREEN}✓ {msg}{RESET}")

def err(msg: str) -> None:
    print(f"{RED}✗ {msg}{RESET}", file=sys.stderr)

def warn(msg: str) -> None:
    print(f"{YELLOW}⚠ {msg}{RESET}")

def info(msg: str) -> None:
    print(f"{BLUE}ℹ {msg}{RESET}")

# ─── Routing Logic ───────────────────────────────────────────────────────────

SENSITIVE_PATTERNS = [
    "api_key", "apikey", "api key", "secret", "password", "passwd", "token",
    "bearer", "authorization", "credential", "private_key", "ssh-rsa",
    "BEGIN RSA", "BEGIN OPENSSH", "-----BEGIN",
    "ssn", "social security", "credit card", "cvv",
    "192.168.", "10.0.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
    "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
    "jdbc:", "mongodb://", "postgres://", "mysql://", "redis://",
]

CLOUD_PATTERNS = [
    "architecture", "arquitectura", "design", "diseño", "security", "seguridad",
    "audit", "auditoría", "multi-file", "refactor", "vulnerability", "sdd-",
    "sdd propose", "sdd spec", "sdd design", "sdd apply", "sdd verify",
    "analyze", "analizar", "complex", "complejo", "reasoning", "razonamiento",
    "debug", "root cause", "causa raíz", "performance bottleneck",
]

LOCAL_PATTERNS = [
    "format", "formatear", "lint", "summary", "summarize", "resumir",
    "list files", "listar", "rename", "renombrar", "template", "plantilla",
    "short", "corto", "simple", "sencillo", "quick", "rápido",
    "what is", "qué es", "define", "definir", "explain briefly",
]


def is_sensitive(text: str) -> bool:
    lower = text.lower()
    return any(p.lower() in lower for p in SENSITIVE_PATTERNS)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


def recommend_routing(task: str) -> dict:
    """Return routing recommendation with reason."""
    if is_sensitive(task):
        return {
            "route": "local",
            "model": DEFAULT_MODEL,
            "reason": "PRIVACY: task contains sensitive data (keys, PII, or internal hosts). Local-only rule.",
            "privacy": True,
        }

    lower = task.lower()
    estimated_tokens = estimate_tokens(task)

    for pattern in CLOUD_PATTERNS:
        if pattern in lower:
            return {
                "route": "cloud",
                "model": "anthropic/claude-sonnet-4-6",
                "reason": f"Matched cloud pattern: '{pattern}'. Requires judgment or complex reasoning.",
                "privacy": False,
            }

    if estimated_tokens > 500:
        return {
            "route": "cloud",
            "model": "anthropic/claude-sonnet-4-6",
            "reason": f"Task is large (~{estimated_tokens} tokens). Cloud handles long-context better.",
            "privacy": False,
        }

    for pattern in LOCAL_PATTERNS:
        if pattern in lower:
            return {
                "route": "local",
                "model": DEFAULT_MODEL,
                "reason": f"Matched local pattern: '{pattern}'. Simple task, save cost.",
                "privacy": False,
            }

    return {
        "route": "local",
        "model": DEFAULT_MODEL,
        "reason": "No complex indicators found. Defaulting to local model.",
        "privacy": False,
    }

# ─── Ollama API ───────────────────────────────────────────────────────────────

def ollama_request(path: str, payload: dict | None = None, method: str = "GET") -> dict:
    url = f"{OLLAMA_HOST}{path}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        raise ConnectionError(f"Cannot reach Ollama at {OLLAMA_HOST}: {e}") from e


def ollama_stream(prompt: str, model: str) -> Iterator[str]:
    """Stream a generate response, yielding text chunks."""
    url = f"{OLLAMA_HOST}/api/generate"
    payload = json.dumps({"model": model, "prompt": prompt, "stream": True}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw_line in resp:
                line = raw_line.decode().strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    if "response" in chunk:
                        yield chunk["response"]
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    continue
    except urllib.error.URLError as e:
        raise ConnectionError(f"Cannot reach Ollama at {OLLAMA_HOST}: {e}") from e

# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_ask(args: argparse.Namespace) -> int:
    model = args.model or DEFAULT_MODEL
    prompt = args.prompt

    if is_sensitive(prompt):
        warn("Prompt contains sensitive data — routing to local model (privacy rule).")

    info(f"Sending to {model} @ {OLLAMA_HOST}")
    print()

    if args.stream:
        try:
            for chunk in ollama_stream(prompt, model):
                print(chunk, end="", flush=True)
            print()
        except ConnectionError as e:
            err(str(e))
            return 1
    else:
        try:
            result = ollama_request(
                "/api/generate",
                {"model": model, "prompt": prompt, "stream": False},
                method="POST",
            )
            print(result.get("response", ""))
        except ConnectionError as e:
            err(str(e))
            return 1

    return 0


def cmd_models(args: argparse.Namespace) -> int:
    try:
        result = ollama_request("/api/tags")
    except ConnectionError as e:
        err(str(e))
        return 1

    models = result.get("models", [])
    if not models:
        warn("No models found. Pull one with: router.py pull llama3.2")
        return 0

    print(f"\n{BLUE}Available local models:{RESET}")
    print(f"{'Name':<35} {'Size':>10}  Modified")
    print("─" * 65)
    for m in models:
        name = m.get("name", "?")
        size_bytes = m.get("size", 0)
        size_gb = size_bytes / 1_073_741_824
        modified = m.get("modified_at", "?")[:10]
        size_str = f"{size_gb:.1f} GB" if size_bytes else "?"
        print(f"{GREEN}{name:<35}{RESET} {size_str:>10}  {modified}")

    print()
    return 0


def cmd_recommend(args: argparse.Namespace) -> int:
    task = args.task_description
    rec = recommend_routing(task)

    print()
    if rec["route"] == "local":
        route_color = GREEN
        route_label = "LOCAL (Ollama)"
    else:
        route_color = BLUE
        route_label = "CLOUD (Claude/GPT)"

    if rec.get("privacy"):
        print(f"{RED}⚠ PRIVACY RULE TRIGGERED{RESET}")

    print(f"Route:  {route_color}{route_label}{RESET}")
    print(f"Model:  {rec['model']}")
    print(f"Reason: {rec['reason']}")
    print()
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    model = args.model
    info(f"Pulling {model} from Ollama registry...")
    print("(This may take a while — streaming progress)")
    print()

    url = f"{OLLAMA_HOST}/api/pull"
    payload = json.dumps({"name": model, "stream": True}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            last_status = ""
            for raw_line in resp:
                line = raw_line.decode().strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    status = chunk.get("status", "")
                    if status != last_status:
                        if "pulling" in status.lower() or "verifying" in status.lower():
                            completed = chunk.get("completed", 0)
                            total = chunk.get("total", 0)
                            if total > 0:
                                pct = int(completed / total * 100)
                                print(f"\r{YELLOW}{status}: {pct}%{RESET}    ", end="", flush=True)
                            else:
                                print(f"\r{YELLOW}{status}{RESET}    ", end="", flush=True)
                        else:
                            if last_status:
                                print()
                            print(f"{BLUE}{status}{RESET}")
                        last_status = status
                except json.JSONDecodeError:
                    continue
        print()
        ok(f"Model '{model}' pulled successfully.")
    except ConnectionError as e:
        err(str(e))
        return 1
    except urllib.error.URLError as e:
        err(f"Pull failed: {e}")
        return 1

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    print()
    info(f"Checking Ollama at {OLLAMA_HOST}")

    # Check version / health
    try:
        version_result = ollama_request("/api/version")
        version = version_result.get("version", "unknown")
        ok(f"Ollama is running — version {version}")
    except ConnectionError as e:
        err(f"Ollama is NOT running: {e}")
        print(f"\n{YELLOW}Start Ollama with: ollama serve{RESET}")
        return 1

    # List loaded (running) models via /api/ps
    try:
        ps_result = ollama_request("/api/ps")
        running = ps_result.get("models", [])
        if running:
            print(f"\n{BLUE}Loaded in memory:{RESET}")
            for m in running:
                name = m.get("name", "?")
                size_bytes = m.get("size", 0)
                size_gb = size_bytes / 1_073_741_824
                print(f"  {GREEN}{name}{RESET}  ({size_gb:.1f} GB)")
        else:
            warn("No models currently loaded in memory (they load on first use).")
    except ConnectionError:
        warn("Could not retrieve running models (/api/ps unavailable).")

    # List available models
    try:
        tags_result = ollama_request("/api/tags")
        models = tags_result.get("models", [])
        print(f"\n{BLUE}Available models ({len(models)}):{RESET}")
        for m in models:
            print(f"  • {m.get('name', '?')}")
        if not models:
            warn("No models installed. Pull one: router.py pull llama3.2")
    except ConnectionError:
        warn("Could not list models.")

    print()
    return 0

# ─── Main ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="router.py",
        description="Dexter AI Router — Ollama local model interface",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # ask
    p_ask = sub.add_parser("ask", help="Send a prompt to Ollama")
    p_ask.add_argument("prompt", help="The prompt to send")
    p_ask.add_argument("--model", "-m", default=None, help="Model name (default: $OLLAMA_DEFAULT_MODEL)")
    p_ask.add_argument("--stream", "-s", action="store_true", help="Stream output as it arrives")

    # models
    sub.add_parser("models", help="List available local models")

    # recommend
    p_rec = sub.add_parser("recommend", help="Get routing recommendation for a task")
    p_rec.add_argument("task_description", help="Description of the task to route")

    # pull
    p_pull = sub.add_parser("pull", help="Pull a model from Ollama registry")
    p_pull.add_argument("model", help="Model name (e.g. llama3.2, mistral, codellama)")

    # status
    sub.add_parser("status", help="Check Ollama status and loaded models")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "ask": cmd_ask,
        "models": cmd_models,
        "recommend": cmd_recommend,
        "pull": cmd_pull,
        "status": cmd_status,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
