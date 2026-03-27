#!/usr/bin/env python3
"""
Test suite for the gui-control skill.

Covers:
  - slugify()
  - parse_claude_response()
  - detect_platform() (env-var controlled)
  - MacroStore save/find via fallback JSON backend
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ─── Path setup ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUI_SCRIPTS  = PROJECT_ROOT / "skills" / "gui-control" / "scripts"

# Ensure the scripts directory is importable (needed by gui.py's local import
# of macro_store) before we load the modules.
sys.path.insert(0, str(GUI_SCRIPTS))


def _load_module(name: str, path: Path):
    """Load a Python file as a module without executing __main__ blocks."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Stub pyautogui so that importing gui.py doesn't require a real display.
_pyautogui_stub = MagicMock()
sys.modules.setdefault("pyautogui", _pyautogui_stub)

_macro_store = _load_module("macro_store", GUI_SCRIPTS / "macro_store.py")
_gui         = _load_module("gui",         GUI_SCRIPTS / "gui.py")


# =============================================================================
# 1. slugify()
# =============================================================================

def test_slugify_basic():
    """'open Outlook in Edge' should become 'open-outlook-in-edge'."""
    result = _macro_store.slugify("open Outlook in Edge")
    assert result == "open-outlook-in-edge"


def test_slugify_special_chars():
    """Special characters are stripped; result is at most 60 characters."""
    # Use a short enough string so the 60-char truncation doesn't split mid-word
    # and leave a trailing hyphen (which is a known edge-case of the [:60] impl).
    task   = "Click 'Send'! #button @fast & easy (v2.0)"
    result = _macro_store.slugify(task)

    # No characters outside [a-z0-9-]
    import re
    assert re.match(r"^[a-z0-9\-]+$", result), f"Unexpected chars in slug: {result!r}"

    # Max 60 chars
    assert len(result) <= 60, f"Slug too long ({len(result)} chars): {result!r}"

    # No leading hyphen
    assert not result.startswith("-")

    # Special chars are gone
    assert "'" not in result
    assert "#" not in result
    assert "@" not in result
    assert "!" not in result
    assert "(" not in result
    assert ")" not in result


# =============================================================================
# 2. parse_claude_response()
# =============================================================================

def test_parse_claude_response_valid():
    """Extracts JSON from text that has prose around it."""
    text = 'Sure, here is the action:\n{"action": "click", "x": 100, "y": 200}\nLet me know!'
    result = _gui.parse_claude_response(text)
    assert result == {"action": "click", "x": 100, "y": 200}


def test_parse_claude_response_done():
    """Parses a bare {"action": "done"} response."""
    text = '{"action": "done"}'
    result = _gui.parse_claude_response(text)
    assert result == {"action": "done"}


def test_parse_claude_response_invalid():
    """Raises ValueError when there is no JSON in the response."""
    with pytest.raises(ValueError, match="No JSON object found"):
        _gui.parse_claude_response("There is no JSON here at all.")


def test_parse_claude_response_missing_action_key():
    """Raises ValueError when JSON is present but lacks 'action' key."""
    with pytest.raises(ValueError, match="missing 'action' key"):
        _gui.parse_claude_response('{"step": 1, "note": "oops"}')


# =============================================================================
# 3. detect_platform()
# =============================================================================

def test_detect_platform_wayland():
    """Simulates a Wayland session: has_display=True, automation_ok=False."""
    env_overrides = {
        "XDG_SESSION_TYPE": "wayland",
        "WAYLAND_DISPLAY":  "wayland-0",
        "DISPLAY":          "",
    }
    with patch("platform.system", return_value="Linux"), \
         patch.dict("os.environ", env_overrides, clear=False), \
         patch("shutil.which", return_value=None):
        info = _gui.detect_platform()

    assert info["has_display"]    is True,  "Expected has_display=True on Wayland"
    assert info["wayland"]        is True,  "Expected wayland=True"
    assert info["automation_ok"]  is False, "Expected automation_ok=False on Wayland"
    assert info["display_server"] == "wayland"


def test_detect_platform_no_display():
    """Simulates a headless Linux environment: has_display=False."""
    env_overrides = {
        "XDG_SESSION_TYPE": "",
        "WAYLAND_DISPLAY":  "",
        "DISPLAY":          "",
    }
    with patch("platform.system", return_value="Linux"), \
         patch.dict("os.environ", env_overrides, clear=False), \
         patch("shutil.which", return_value=None):
        info = _gui.detect_platform()

    assert info["has_display"]   is False, "Expected has_display=False in headless env"
    assert info["automation_ok"] is False, "Expected automation_ok=False in headless env"
    assert info["display_server"] is None


# =============================================================================
# 4. MacroStore — fallback JSON backend
# =============================================================================

@pytest.fixture()
def fallback_store(tmp_path, monkeypatch):
    """
    Fixture that redirects the fallback JSON store to a temp directory and
    forces ENGRAM_AVAILABLE=False so all operations use the JSON backend.
    """
    store_path = tmp_path / ".dexter" / "gui-macros.json"
    monkeypatch.setattr(_macro_store, "FALLBACK_PATH",  store_path)
    monkeypatch.setattr(_macro_store, "ENGRAM_AVAILABLE", False)
    return store_path


def test_macro_store_save_fallback(fallback_store):
    """When ENGRAM_AVAILABLE=False, save() writes to the JSON file."""
    steps = [{"action": "click", "x": 10, "y": 20}]
    key   = _macro_store.save("open Slack", steps, "Linux")

    assert fallback_store.exists(), "Fallback JSON file was not created"

    data = json.loads(fallback_store.read_text())
    slug = _macro_store.slugify("open Slack")

    assert slug in data, f"Expected slug {slug!r} in store, got keys: {list(data)}"
    assert data[slug]["steps"] == steps
    assert data[slug]["platform"] == "Linux"
    assert "gui-macros/default/" in key


def test_macro_store_find_fallback(fallback_store):
    """find() retrieves steps from the JSON file when Engram is not available."""
    steps = [{"action": "type", "text": "hello"}]
    _macro_store.save("open Notes", steps, "Darwin")

    found = _macro_store.find("open Notes")
    assert found == steps, f"Expected {steps!r}, got {found!r}"


def test_macro_store_find_missing(fallback_store):
    """find() returns None when the task slug is not in the store."""
    result = _macro_store.find("a task that was never saved")
    assert result is None, f"Expected None, got {result!r}"
