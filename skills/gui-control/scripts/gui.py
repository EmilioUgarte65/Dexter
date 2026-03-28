#!/usr/bin/env python3
"""
Dexter — GUI automation via computer-use vision loop.
Drives the desktop with pyautogui, guided by Claude --image feedback.
Completed step sequences are saved as macros for instant replay.

Usage:
  gui.py run "<task>" [--max-steps N] [--no-macro]
  gui.py status
  gui.py macro list
  gui.py macro replay <slug>
  gui.py macro delete <slug>
"""

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─── Local imports ─────────────────────────────────────────────────────────────

_SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPTS_DIR))
import macro_store

# ─── ANSI colors ───────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

# ─── Constants ─────────────────────────────────────────────────────────────────

PREFIX       = "[Dexter GUI]"
MAX_STEPS    = 25
VERIFY_RATE  = 0.25   # probability of a random spot-check after each action (0.0–1.0)
DEXTER_ROOT  = Path(__file__).resolve().parents[3]   # skills/gui-control/scripts/ → Dexter/

# ─── Platform detection ────────────────────────────────────────────────────────

def detect_platform() -> dict:
    """
    Probe the runtime environment for GUI automation capabilities.

    Returns a dict with keys:
      os, display_server, has_display, wayland, pyautogui_ok, xdotool_ok,
      screenshot_tool, accessibility_ok, automation_ok
    """
    import platform as _platform

    info: dict = {
        "os":               _platform.system(),   # "Linux", "Darwin", "Windows"
        "display_server":   None,
        "has_display":      False,
        "wayland":          False,
        "pyautogui_ok":     False,
        "xdotool_ok":       False,
        "screenshot_tool":  None,
        "accessibility_ok": False,
        "automation_ok":    False,
    }

    system = info["os"]

    if system == "Linux":
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        wayland_disp = os.environ.get("WAYLAND_DISPLAY", "")
        x_disp       = os.environ.get("DISPLAY", "")

        if session_type == "wayland" or wayland_disp:
            info["display_server"] = "wayland"
            info["has_display"]    = True
            info["wayland"]        = True
            info["automation_ok"]  = False
        elif x_disp:
            info["display_server"] = "x11"
            info["has_display"]    = True
            info["wayland"]        = False
            info["automation_ok"]  = True
        else:
            info["display_server"] = None
            info["has_display"]    = False
            info["automation_ok"]  = False

        # xdotool
        info["xdotool_ok"] = shutil.which("xdotool") is not None

        # screenshot tool
        if shutil.which("scrot"):
            info["screenshot_tool"] = "scrot"
        elif shutil.which("import"):    # imagemagick
            info["screenshot_tool"] = "import"
        else:
            info["screenshot_tool"] = None

    elif system == "Darwin":
        info["display_server"]  = "quartz"
        info["has_display"]     = True
        info["wayland"]         = False
        info["automation_ok"]   = True
        info["screenshot_tool"] = "screencapture" if shutil.which("screencapture") else None

    elif system == "Windows":
        info["display_server"] = "win32"
        info["has_display"]    = True
        info["wayland"]        = False
        info["automation_ok"]  = True
        try:
            from PIL import ImageGrab  # noqa: F401
            info["screenshot_tool"] = "PIL.ImageGrab"
        except ImportError:
            try:
                import pyautogui as _pag  # noqa: F401
                info["screenshot_tool"] = "pyautogui"
            except ImportError:
                info["screenshot_tool"] = None

    # pyautogui probe (all platforms)
    try:
        import pyautogui  # noqa: F401
        info["pyautogui_ok"] = True
    except ImportError:
        info["pyautogui_ok"] = False

    # macOS: rough accessibility check
    if system == "Darwin":
        result = subprocess.run(
            ["osascript", "-e", "tell application \"System Events\" to get name of first process"],
            capture_output=True, text=True, timeout=5
        )
        info["accessibility_ok"] = result.returncode == 0

    return info


# ─── gui status ───────────────────────────────────────────────────────────────

def cmd_status():
    """Print platform capability table and exit non-zero on FAIL."""
    info = detect_platform()
    system = info["os"]

    checks = []

    # Display check
    if not info["has_display"]:
        checks.append(("Display", "FAIL", "No display found — set $DISPLAY or use Xvfb"))
    elif info["wayland"]:
        checks.append(("Display", "WARN",
                        "Wayland detected — automation not supported. "
                        "Set QT_QPA_PLATFORM=xcb or use ydotool"))
    else:
        checks.append(("Display", "PASS", f"{info['display_server']} @ {os.environ.get('DISPLAY', 'N/A')}"))

    # pyautogui
    if info["pyautogui_ok"]:
        checks.append(("pyautogui", "PASS", "installed"))
    else:
        checks.append(("pyautogui", "FAIL", "not installed — run: pip install pyautogui"))

    # screenshot tool
    if info["screenshot_tool"]:
        checks.append(("Screenshot", "PASS", info["screenshot_tool"]))
    else:
        if system == "Linux":
            checks.append(("Screenshot", "FAIL",
                            "no screenshot tool — run: sudo apt install scrot"))
        elif system == "Darwin":
            checks.append(("Screenshot", "FAIL", "screencapture not found (unexpected on macOS)"))
        elif system == "Windows":
            checks.append(("Screenshot", "FAIL", "Pillow not installed — run: pip install Pillow"))

    # xdotool (Linux only)
    if system == "Linux":
        if info["xdotool_ok"]:
            checks.append(("xdotool", "PASS", "installed"))
        else:
            checks.append(("xdotool", "WARN",
                            "not installed (optional) — run: sudo apt install xdotool"))

    # macOS accessibility
    if system == "Darwin":
        if info["accessibility_ok"]:
            checks.append(("Accessibility", "PASS", "osascript OK"))
        else:
            checks.append(("Accessibility", "WARN",
                            "osascript failed — grant Accessibility in System Settings → Privacy"))

    # claude CLI
    claude_ok = shutil.which("claude") is not None
    if claude_ok:
        checks.append(("claude CLI", "PASS", shutil.which("claude")))
    else:
        checks.append(("claude CLI", "FAIL", "not found — install Claude Code CLI"))

    # Print table
    col_label = max(len(c[0]) for c in checks) + 2
    col_status = 6
    print(f"\n{BOLD}{PREFIX} Platform status — {system}{RESET}\n")
    print(f"  {'Check':<{col_label}} {'Status':<{col_status}} Details")
    print(f"  {'-' * col_label} {'-' * col_status} -------")

    has_fail = False
    for label, status, detail in checks:
        if status == "PASS":
            color = GREEN
        elif status == "WARN":
            color = YELLOW
        else:
            color = RED
            has_fail = True
        print(f"  {label:<{col_label}} {color}{status:<{col_status}}{RESET} {detail}")

    print()
    if has_fail:
        sys.exit(1)


# ─── Screenshot helper ────────────────────────────────────────────────────────

def take_screenshot(path: str) -> None:
    """
    Capture the current screen to `path` (PNG).
    Platform-aware: scrot (Linux X11), screencapture (macOS), PIL (Windows).
    Raises RuntimeError if no screenshot method is available.
    """
    import platform as _platform
    system = _platform.system()

    if system == "Linux":
        if shutil.which("scrot"):
            result = subprocess.run(["scrot", path], capture_output=True)
            if result.returncode == 0:
                return
        if shutil.which("import"):
            result = subprocess.run(["import", "-window", "root", path], capture_output=True)
            if result.returncode == 0:
                return
        raise RuntimeError(
            "No screenshot tool available on Linux. "
            "Install scrot: sudo apt install scrot"
        )

    elif system == "Darwin":
        if shutil.which("screencapture"):
            result = subprocess.run(["screencapture", "-x", path], capture_output=True)
            if result.returncode == 0:
                return
        raise RuntimeError("screencapture failed on macOS.")

    elif system == "Windows":
        try:
            from PIL import ImageGrab
            ImageGrab.grab().save(path)
            return
        except ImportError:
            pass
        try:
            import pyautogui
            pyautogui.screenshot().save(path)
            return
        except (ImportError, Exception) as e:
            raise RuntimeError(f"Cannot take screenshot on Windows: {e}") from e

    else:
        raise RuntimeError(f"Unsupported platform for screenshot: {system}")


# ─── Action dispatcher ────────────────────────────────────────────────────────

def execute_action(action: dict) -> bool:
    """
    Dispatch a parsed action dict to pyautogui.
    Returns True on success, False on unknown action (warning logged).
    Raises on pyautogui errors or import failure.
    'done' action returns True but the CALLER is responsible for breaking the loop.
    """
    act = action.get("action", "")

    if act == "done":
        return True

    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE    = 0.1
    except ImportError:
        raise RuntimeError(
            "pyautogui is not installed. Run: pip install pyautogui"
        )

    if act == "click":
        pyautogui.click(int(action["x"]), int(action["y"]))

    elif act == "right_click":
        pyautogui.rightClick(int(action["x"]), int(action["y"]))

    elif act == "double_click":
        pyautogui.doubleClick(int(action["x"]), int(action["y"]))

    elif act == "type":
        pyautogui.typewrite(str(action["text"]), interval=0.05)

    elif act == "key":
        keys_str = str(action["keys"])
        keys     = [k.strip() for k in keys_str.split("+")]
        pyautogui.hotkey(*keys)

    elif act == "scroll":
        amount = int(action.get("amount", 3))
        pyautogui.scroll(amount)

    elif act == "move":
        pyautogui.moveTo(int(action["x"]), int(action["y"]), duration=0.3)

    elif act == "navigate":
        url    = str(action["url"])
        import platform as _platform
        system = _platform.system()
        if system == "Linux":
            opener = "xdg-open"
        elif system == "Darwin":
            opener = "open"
        else:
            opener = "start"
        subprocess.run([opener, url], check=False)

    elif act == "wait":
        ms = float(action.get("ms", 500))
        time.sleep(ms / 1000.0)

    else:
        print(f"{YELLOW}{PREFIX} Unknown action '{act}' — skipping{RESET}", file=sys.stderr)
        return False

    return True


# ─── Claude response parser ───────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """Extract the first JSON object from a text string. Raises ValueError if none found."""
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in response:\n{text[:300]}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}\nRaw: {match.group(0)[:200]}") from e


def parse_claude_response(text: str) -> dict:
    """
    Extract the first JSON object from Claude's stdout.
    Validates that 'action' key is present.
    Raises ValueError if no valid JSON action found.
    """
    obj = _extract_json(text)
    if "action" not in obj:
        raise ValueError(f"JSON missing 'action' key: {obj}")
    return obj


def parse_verify_response(text: str) -> dict:
    """
    Extract a verify-style {ok, note} response from Claude's stdout.
    Falls back to {"ok": False, "note": raw_text} if no JSON found.
    """
    try:
        obj = _extract_json(text)
        return {"ok": bool(obj.get("ok", False)), "note": str(obj.get("note", ""))}
    except ValueError:
        return {"ok": False, "note": text.strip()[:200]}


# ─── Vision loop ──────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a desktop automation agent. You observe screenshots and emit a single JSON action to
make progress toward completing the user's task. Each response MUST be exactly one JSON object
— no prose, no explanation. Use {"action": "done"} when the task is complete.

Available actions:
{"action":"click","x":N,"y":N}
{"action":"right_click","x":N,"y":N}
{"action":"double_click","x":N,"y":N}
{"action":"type","text":"TEXT"}
{"action":"key","keys":"ctrl+t"}
{"action":"scroll","amount":3}
{"action":"move","x":N,"y":N}
{"action":"navigate","url":"https://..."}
{"action":"wait","ms":500}
{"action":"done"}
"""


def run_vision_loop(task: str, max_steps: int, system_prompt: str, verify_rate: float = VERIFY_RATE) -> list:
    """
    Execute the computer-use vision loop.
    Returns the list of executed step dicts.
    If max_steps is reached without 'done', returns partial list (caller checks len vs done).
    """
    ts    = int(datetime.now(timezone.utc).timestamp())
    steps = []

    claude_cmd = shutil.which("claude")
    if not claude_cmd:
        print(f"{RED}{PREFIX} 'claude' CLI not found in PATH.{RESET}", file=sys.stderr)
        sys.exit(1)

    for i in range(1, max_steps + 1):
        screenshot_path = f"/tmp/dexter_gui_{ts}_{i}.png"

        # 1. Take screenshot
        try:
            take_screenshot(screenshot_path)
        except RuntimeError as e:
            print(f"{RED}{PREFIX} Screenshot failed: {e}{RESET}", file=sys.stderr)
            sys.exit(1)

        # 2. Build prompt
        history_summary = ""
        if steps:
            history_lines = [f"  step {j+1}: {json.dumps(s)}" for j, s in enumerate(steps)]
            history_summary = "\n\nHistory so far:\n" + "\n".join(history_lines)

        prompt = (
            f"{system_prompt}"
            f"\n\nTask: {task}"
            f"{history_summary}"
            f"\n\nStep {i}/{max_steps}. What is the next action?"
        )

        # 3. Spawn claude (unset CLAUDECODE to avoid nested-session error)
        env = dict(os.environ)
        env.pop("CLAUDECODE", None)

        try:
            result = subprocess.run(
                [claude_cmd, "-p", prompt,
                 "--image", screenshot_path,
                 "--dangerously-skip-permissions"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(DEXTER_ROOT),
                env=env,
            )
        except subprocess.TimeoutExpired:
            print(f"{YELLOW}{PREFIX} Claude timed out on step {i} — aborting.{RESET}", file=sys.stderr)
            break
        finally:
            # 7. Cleanup temp screenshot
            try:
                Path(screenshot_path).unlink(missing_ok=True)
            except OSError:
                pass

        if result.returncode != 0:
            print(
                f"{YELLOW}{PREFIX} Claude exited {result.returncode} on step {i}: "
                f"{result.stderr[:200]}{RESET}",
                file=sys.stderr,
            )
            break

        # 4. Parse response
        try:
            action = parse_claude_response(result.stdout)
        except ValueError as e:
            print(f"{YELLOW}{PREFIX} Parse error on step {i}: {e}{RESET}", file=sys.stderr)
            break

        # 5. Check for done
        if action.get("action") == "done":
            steps.append(action)
            break

        # 6. Execute action, append to steps
        execute_action(action)
        steps.append(action)

        # 7. Random spot-check verification
        if verify_rate > 0 and random.random() < verify_rate:
            action_desc = json.dumps(action)
            spot_prompt = _SPOT_CHECK_PROMPT.format(action=action_desc)
            print(f"  {YELLOW}[spot-check]{RESET}", end=" ")
            verdict = verify_screenshot(spot_prompt)
            if not verdict.get("ok"):
                print(
                    f"{YELLOW}{PREFIX} Spot-check failed on step {i}: {verdict.get('note', '')}{RESET}\n"
                    f"  Continuing — Claude will adapt on the next step.",
                    file=sys.stderr,
                )

    return steps


def replay_macro(steps: list) -> None:
    """Execute a saved macro step list via execute_action."""
    for i, step in enumerate(steps, 1):
        act = step.get("action", "")
        if act == "done":
            break
        print(f"  {BLUE}step {i}{RESET}: {json.dumps(step)}")
        execute_action(step)


# ─── Subcommand handlers ──────────────────────────────────────────────────────

def cmd_run(task: str, max_steps: int, no_macro: bool, verify_rate: float = VERIFY_RATE) -> None:
    """
    Run a GUI task — macro replay on cache hit, vision loop on miss.
    """
    info = detect_platform()

    # Platform gate
    if info["wayland"]:
        print(
            f"{RED}{PREFIX} Wayland is not supported by pyautogui (requires X11).{RESET}\n"
            f"  Workaround: set QT_QPA_PLATFORM=xcb to force X11 mode, or use ydotool.\n"
            f"  Then re-run with DISPLAY=:0 gui.py run ...",
            file=sys.stderr,
        )
        sys.exit(1)

    if not info["has_display"]:
        print(
            f"{RED}{PREFIX} No display detected ($DISPLAY not set).{RESET}\n"
            f"  For headless servers: Xvfb :99 -screen 0 1920x1080x24 &\n"
            f"                        DISPLAY=:99 gui.py run ...",
            file=sys.stderr,
        )
        sys.exit(1)

    # Macro cache lookup
    if not no_macro:
        cached = macro_store.find(task)
        if cached:
            slug = macro_store.slugify(task)
            print(f"{GREEN}{PREFIX} Macro cache hit: {slug}{RESET}")
            print(f"  Replaying {len(cached)} step(s) without vision loop...\n")
            replay_macro(cached)
            print(f"\n{GREEN}{PREFIX} Macro replay complete.{RESET}")
            return

    # Vision loop
    print(f"{BLUE}{PREFIX} Starting vision loop for: {task!r}{RESET}")
    print(f"  Max steps: {max_steps} | Platform: {info['os']} / {info['display_server']}\n")

    steps = run_vision_loop(task, max_steps, _SYSTEM_PROMPT, verify_rate=verify_rate)

    # Check if loop ended with done
    if steps and steps[-1].get("action") == "done":
        action_steps = [s for s in steps if s.get("action") != "done"]
        slug = macro_store.slugify(task)

        if not no_macro:
            key = macro_store.save(task, action_steps, info["os"])
            print(
                f"\n{GREEN}{PREFIX} Task complete. "
                f"{len(action_steps)} step(s). "
                f"Macro saved as {slug}.{RESET}"
            )
            print(f"  Topic key: {key}")
        else:
            print(
                f"\n{GREEN}{PREFIX} Task complete. "
                f"{len(action_steps)} step(s). "
                f"(--no-macro: not saved){RESET}"
            )
    else:
        print(
            f"\n{RED}{PREFIX} Task did not complete within {max_steps} step(s).{RESET}\n"
            f"  The incomplete sequence was NOT saved as a macro.",
            file=sys.stderr,
        )
        sys.exit(1)


def cmd_macro_list() -> None:
    """Print all saved macros in a table."""
    macros = macro_store.list_all()

    if not macros:
        print(f"{YELLOW}{PREFIX} No macros saved yet.{RESET}")
        print(f"  Run 'gui.py run \"<task>\"' to create one.")
        return

    print(f"\n{BOLD}{PREFIX} Saved macros ({len(macros)}){RESET}\n")
    col_slug    = max(len(m["slug"]) for m in macros) + 2
    col_steps   = 7
    col_plat    = max(len(m.get("platform", "")) for m in macros) + 2

    print(f"  {'Slug':<{col_slug}} {'Steps':<{col_steps}} {'Platform':<{col_plat}} Saved at")
    print(f"  {'-' * col_slug} {'-' * col_steps} {'-' * col_plat} --------")

    for m in macros:
        saved = m.get("saved_at", "")[:19].replace("T", " ")  # trim microseconds/tz
        print(
            f"  {m['slug']:<{col_slug}} "
            f"{m['step_count']:<{col_steps}} "
            f"{m.get('platform', 'unknown'):<{col_plat}} "
            f"{saved}"
        )
    print()


def cmd_macro_replay(slug: str) -> None:
    """Replay a macro by slug."""
    steps = macro_store.find(slug)

    if steps is None:
        available = [m["slug"] for m in macro_store.list_all()]
        print(
            f"{RED}{PREFIX} Macro not found: {slug!r}{RESET}",
            file=sys.stderr,
        )
        if available:
            print(f"  Available: {', '.join(available)}", file=sys.stderr)
        else:
            print("  No macros saved yet.", file=sys.stderr)
        sys.exit(1)

    info = detect_platform()
    if info["wayland"] or not info["has_display"]:
        print(f"{RED}{PREFIX} Cannot replay macro: no X11 display.{RESET}", file=sys.stderr)
        sys.exit(1)

    print(f"{BLUE}{PREFIX} Replaying macro: {slug}{RESET}")
    print(f"  {len(steps)} step(s)\n")
    replay_macro(steps)
    print(f"\n{GREEN}{PREFIX} Replay complete.{RESET}")


def cmd_macro_delete(slug: str) -> None:
    """Delete a macro by slug."""
    deleted = macro_store.delete(slug)

    if not deleted:
        available = [m["slug"] for m in macro_store.list_all()]
        print(f"{RED}{PREFIX} Macro not found: {slug!r}{RESET}", file=sys.stderr)
        if available:
            print(f"  Available: {', '.join(available)}", file=sys.stderr)
        sys.exit(1)

    print(f"{GREEN}{PREFIX} Macro deleted: {slug}{RESET}")


# ─── Verify screenshot ────────────────────────────────────────────────────────

_VERIFY_SYSTEM_PROMPT = """\
You are a GUI verification agent. Look at the screenshot and answer whether the
described situation is correct or if something went wrong. Reply with exactly one
JSON object — no prose. Format:
{"ok": true, "note": "brief description of what you see"}
{"ok": false, "note": "what went wrong or what is missing"}
"""

_SPOT_CHECK_PROMPT = """\
You are a GUI verification agent. Look at the screenshot taken immediately after
executing this action: {action}

Did the action have the expected effect on the screen?
Reply with exactly one JSON object:
{"ok": true, "note": "brief description of the current screen state"}
{"ok": false, "note": "what seems wrong or did not change as expected"}
"""


def verify_screenshot(prompt: str, context: str = "") -> dict:
    """
    Take a screenshot and ask Claude whether everything looks OK.
    Returns: {"ok": bool, "note": str}
    Prints the result to stdout with color coding.
    """
    ts   = int(datetime.now(timezone.utc).timestamp())
    path = f"/tmp/dexter_verify_{ts}.png"

    try:
        take_screenshot(path)
    except RuntimeError as e:
        print(f"{RED}{PREFIX} Verify screenshot failed: {e}{RESET}", file=sys.stderr)
        return {"ok": False, "note": str(e)}

    claude_cmd = shutil.which("claude")
    if not claude_cmd:
        print(f"{RED}{PREFIX} 'claude' CLI not found — cannot verify.{RESET}", file=sys.stderr)
        return {"ok": False, "note": "claude CLI not found"}

    full_prompt = _VERIFY_SYSTEM_PROMPT
    if context:
        full_prompt += f"\n\nContext: {context}"
    full_prompt += f"\n\nQuestion: {prompt}"

    env = dict(os.environ)
    env.pop("CLAUDECODE", None)

    try:
        result = subprocess.run(
            [claude_cmd, "-p", full_prompt,
             "--image", path,
             "--dangerously-skip-permissions"],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
    except subprocess.TimeoutExpired:
        print(f"{YELLOW}{PREFIX} Verify timed out.{RESET}", file=sys.stderr)
        return {"ok": False, "note": "timeout"}
    finally:
        Path(path).unlink(missing_ok=True)

    verdict = parse_verify_response(result.stdout)

    ok   = verdict.get("ok", False)
    note = verdict.get("note", "")
    color = GREEN if ok else RED
    icon  = "✓" if ok else "✗"
    print(f"  {color}{icon} {note}{RESET}")

    return verdict


def cmd_verify(prompt: str, context: str) -> None:
    """
    gui verify — take a screenshot and let Claude assess what's on screen.
    Triggered by: 'no se envió', 'no funcionó', 'qué pasó', or manually.
    """
    info = detect_platform()
    if not info["has_display"] or info["wayland"]:
        print(f"{RED}{PREFIX} No display available for verification.{RESET}", file=sys.stderr)
        sys.exit(1)

    print(f"{BLUE}{PREFIX} Taking verification screenshot...{RESET}")
    verdict = verify_screenshot(prompt or "Is everything on screen OK? Did the last action work?", context)

    if not verdict.get("ok"):
        sys.exit(1)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Dexter GUI automation — computer-use vision loop + macro replay",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  gui.py run "open a new terminal tab"\n'
            '  gui.py run "click the send button" --max-steps 10\n'
            '  gui.py run "open Firefox" --no-macro\n'
            "  gui.py status\n"
            "  gui.py macro list\n"
            "  gui.py macro replay open-a-new-terminal-tab\n"
            "  gui.py macro delete open-a-new-terminal-tab\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── run ───────────────────────────────────────────────────────────────────
    p_run = sub.add_parser("run", help="Run a GUI task via vision loop or macro replay")
    p_run.add_argument("task", help="Natural language task description")
    p_run.add_argument(
        "--max-steps", type=int, default=MAX_STEPS,
        metavar="N",
        help=f"Maximum vision loop iterations (default: {MAX_STEPS})",
    )
    p_run.add_argument(
        "--no-macro", action="store_true",
        help="Skip macro lookup and do not save after completion",
    )
    p_run.add_argument(
        "--verify-rate", type=float, default=VERIFY_RATE, metavar="0.0-1.0",
        help=f"Probability of a random spot-check screenshot after each action (default: {VERIFY_RATE}). 0 disables.",
    )

    # ── verify ────────────────────────────────────────────────────────────────
    p_verify = sub.add_parser(
        "verify",
        help="Take a screenshot and ask Claude if everything looks OK",
    )
    p_verify.add_argument(
        "prompt", nargs="?", default="",
        help="What to check (e.g. 'did the email send?'). Defaults to a general OK check.",
    )
    p_verify.add_argument(
        "--context", default="",
        help="Extra context for Claude (e.g. the task that was just run)",
    )

    # ── status ────────────────────────────────────────────────────────────────
    sub.add_parser("status", help="Show platform capability checks")

    # ── macro ─────────────────────────────────────────────────────────────────
    p_macro = sub.add_parser("macro", help="Manage saved macros")
    macro_sub = p_macro.add_subparsers(dest="macro_command", required=True)

    macro_sub.add_parser("list", help="List all saved macros")

    p_replay = macro_sub.add_parser("replay", help="Replay a saved macro by slug")
    p_replay.add_argument("slug", help="Macro slug (from 'macro list')")

    p_delete = macro_sub.add_parser("delete", help="Delete a saved macro by slug")
    p_delete.add_argument("slug", help="Macro slug (from 'macro list')")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args.task, args.max_steps, args.no_macro, args.verify_rate)

    elif args.command == "verify":
        cmd_verify(args.prompt, args.context)

    elif args.command == "status":
        cmd_status()

    elif args.command == "macro":
        if args.macro_command == "list":
            cmd_macro_list()
        elif args.macro_command == "replay":
            cmd_macro_replay(args.slug)
        elif args.macro_command == "delete":
            cmd_macro_delete(args.slug)


if __name__ == "__main__":
    main()
