"""
Dexter Marketplace test suite — Phase 4.

Tests:
  marketplace.py (6 tests):
    1. test_index_cache_ttl            — TTL logic: no refresh < 24h, refresh > 24h
    2. test_clawhub_missing_npx_shows_warning — npx absent: warning + empty list
    3. test_install_audit_block        — audit BLOCK: install aborted, message shown
    4. test_install_audit_pass_writes_registry — audit PASS: skill copied + registry entry
    5. test_search_returns_results_from_index  — search filters mock index correctly
    6. test_update_index_writes_fetched_at     — update-index writes fetched_at field

  skill_writer.py (2 tests):
    7. test_detect_llm_cli_prefers_dexter_agent_env — DEXTER_AGENT overrides PATH check
    8. test_dry_run_does_not_write_files            — --dry-run: no files written

Run with:
    pytest tests/scripts/test_marketplace.py -v
"""

import importlib.util
import json
import os
import sys
import textwrap
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Project root ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = PROJECT_ROOT / "skills"

MARKETPLACE_SCRIPT = SKILLS_ROOT / "marketplace" / "scripts" / "marketplace.py"
SKILL_WRITER_SCRIPT = SKILLS_ROOT / "skill-writer" / "scripts" / "skill_writer.py"


# ── Module loaders ────────────────────────────────────────────────────────────

def _load_module(path: Path, name: str):
    """Load a script as a module via importlib (no package required)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def marketplace():
    return _load_module(MARKETPLACE_SCRIPT, "marketplace")


@pytest.fixture(scope="module")
def skill_writer():
    return _load_module(SKILL_WRITER_SCRIPT, "skill_writer")


# =============================================================================
# 1. test_index_cache_ttl
#    Mock filesystem: verify index NOT refreshed when age < 24h,
#    IS refreshed when age > 24h.
# =============================================================================

def test_index_cache_ttl(marketplace, tmp_path):
    """
    _load_index() must:
    - Return cached data without calling _refresh_index when age < 24h.
    - Call _refresh_index when age > 24h.
    """
    from datetime import datetime, timezone, timedelta

    # Build a mock index that looks fresh (1 hour old)
    fresh_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    fresh_index = {
        "fetched_at": fresh_ts,
        "ttl_hours": 24,
        "skills": [{"slug": "test/skill", "name": "skill"}],
    }

    index_file = tmp_path / "marketplace-index.json"
    index_file.write_text(json.dumps(fresh_index), encoding="utf-8")

    refresh_called = []

    def fake_refresh():
        refresh_called.append(True)
        return {"fetched_at": datetime.now(timezone.utc).isoformat(), "ttl_hours": 24, "skills": []}

    with (
        patch.object(marketplace, "INDEX_PATH", index_file),
        patch.object(marketplace, "_refresh_index", side_effect=fake_refresh),
    ):
        result = marketplace._load_index()

    # Fresh cache → _refresh_index must NOT have been called
    assert not refresh_called, "_refresh_index should NOT be called when cache age < 24h"
    assert result["skills"][0]["slug"] == "test/skill", "Should return cached data"

    # Now write a stale index (25 hours old)
    stale_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    stale_index = {
        "fetched_at": stale_ts,
        "ttl_hours": 24,
        "skills": [{"slug": "stale/skill", "name": "stale"}],
    }
    index_file.write_text(json.dumps(stale_index), encoding="utf-8")
    refresh_called.clear()

    with (
        patch.object(marketplace, "INDEX_PATH", index_file),
        patch.object(marketplace, "_refresh_index", side_effect=fake_refresh),
    ):
        marketplace._load_index()

    # Stale cache → _refresh_index MUST have been called
    assert refresh_called, "_refresh_index MUST be called when cache age > 24h"


# =============================================================================
# 2. test_clawhub_missing_npx_shows_warning
#    shutil.which("npx") → None; ClawHubAdapter.fetch() must print warning
#    and return [].
# =============================================================================

def test_clawhub_missing_npx_shows_warning(marketplace, capsys):
    """
    When npx is not in PATH, ClawHubAdapter.fetch() must:
    - Return an empty list (not raise an exception).
    - Print a warning mentioning npm/npx install guidance.
    """
    adapter = marketplace.ClawHubAdapter()

    with patch("shutil.which", return_value=None):
        result = adapter.fetch()

    captured = capsys.readouterr()
    warning_output = captured.err + captured.out

    assert result == [], f"Expected empty list, got: {result}"
    assert (
        "npm" in warning_output.lower()
        or "npx" in warning_output.lower()
        or "install" in warning_output.lower()
    ), (
        "Expected warning mentioning npm/npx install, got:\n" + warning_output
    )


# =============================================================================
# 3. test_install_audit_block
#    _run_audit returns ("BLOCK", ...) → cmd_install must abort and print BLOCK.
# =============================================================================

def test_install_audit_block(marketplace, tmp_path, capsys):
    """
    cmd_install must:
    - Abort the install when _run_audit returns BLOCK.
    - Print a message containing "BLOCK" to indicate the install was rejected.
    """
    # Minimal valid index with one skill
    slug = "test/blocked-skill"
    skill_entry = {
        "slug": slug,
        "name": "blocked-skill",
        "category": "test",
        "source": "dexter-marketplace",
        "description": "A test skill",
        "install_url": "https://example.com/SKILL.md",
        "repo_url": "https://github.com/example/skill",
        "audited": False,
    }
    index_data = {
        "fetched_at": "2099-01-01T00:00:00+00:00",
        "ttl_hours": 24,
        "skills": [skill_entry],
    }

    # Stub the adapter download so it doesn't make real HTTP calls
    mock_adapter = MagicMock()
    mock_adapter.download = MagicMock(return_value=None)

    fake_audit_json = json.dumps({"result": "BLOCK", "findings": []})

    args = MagicMock()
    args.slug = slug
    args.source = None

    with (
        patch.object(marketplace, "_load_index", return_value=index_data),
        patch.object(marketplace, "_run_audit", return_value=("BLOCK", fake_audit_json)),
        patch.dict(marketplace.ADAPTERS, {"dexter-marketplace": mock_adapter}),
    ):
        return_code = marketplace.cmd_install(args)

    captured = capsys.readouterr()
    output = captured.out + captured.err

    assert return_code == 1, f"Expected exit code 1 on BLOCK, got {return_code}"
    assert "BLOCK" in output, (
        "Expected 'BLOCK' in output when install is rejected, got:\n" + output
    )


# =============================================================================
# 4. test_install_audit_pass_writes_registry
#    _run_audit returns ("PASS", ...) → skill copied to community dir + registry.
# =============================================================================

def test_install_audit_pass_writes_registry(marketplace, tmp_path, capsys):
    """
    When _run_audit returns PASS:
    - Skill files must be copied to ~/.dexter/community/<category>/<name>/.
    - _registry_append must be called (registry entry written).
    """
    slug = "productivity/my-skill"
    category, name = "productivity", "my-skill"

    skill_entry = {
        "slug": slug,
        "name": name,
        "category": category,
        "source": "dexter-marketplace",
        "description": "A passing skill",
        "install_url": "https://example.com/SKILL.md",
        "repo_url": "https://github.com/example/my-skill",
        "audited": False,
    }
    index_data = {
        "fetched_at": "2099-01-01T00:00:00+00:00",
        "ttl_hours": 24,
        "skills": [skill_entry],
    }

    # Simulate download: write a SKILL.md into the tmp dir that TemporaryDirectory provides
    community_dir = tmp_path / "community"
    community_dir.mkdir()

    fake_audit_json = json.dumps({"result": "PASS", "findings": []})

    registry_calls = []

    def fake_registry_append(name_, category_, source_, skill_path):
        registry_calls.append({
            "name": name_,
            "category": category_,
            "source": source_,
        })

    # We need to intercept TemporaryDirectory to write a real SKILL.md
    original_td = tempfile.TemporaryDirectory

    class FakeTempDir:
        def __init__(self, **kwargs):
            self._real = original_td(**kwargs)

        def __enter__(self):
            path = self._real.__enter__()
            # Write a minimal SKILL.md so copytree has something
            (Path(path) / "SKILL.md").write_text("---\nname: my-skill\n---\n", encoding="utf-8")
            return path

        def __exit__(self, *args):
            return self._real.__exit__(*args)

    mock_adapter = MagicMock()

    # adapter.download must write files into the tmp_dir passed to it
    def fake_download(entry, dest_path):
        (Path(dest_path) / "SKILL.md").write_text("---\nname: my-skill\n---\n", encoding="utf-8")

    mock_adapter.download = fake_download

    args = MagicMock()
    args.slug = slug
    args.source = None

    with (
        patch.object(marketplace, "_load_index", return_value=index_data),
        patch.object(marketplace, "_run_audit", return_value=("PASS", fake_audit_json)),
        patch.dict(marketplace.ADAPTERS, {"dexter-marketplace": mock_adapter}),
        patch.object(marketplace, "COMMUNITY_DIR", community_dir),
        patch.object(marketplace, "_registry_append", side_effect=fake_registry_append),
        patch("tempfile.TemporaryDirectory", FakeTempDir),
    ):
        return_code = marketplace.cmd_install(args)

    assert return_code == 0, f"Expected exit code 0 on PASS, got {return_code}"

    dest = community_dir / category / name
    assert dest.exists(), f"Skill directory not created at {dest}"
    assert (dest / "SKILL.md").exists(), "SKILL.md not copied to community dir"

    assert registry_calls, "_registry_append was not called"
    assert registry_calls[0]["name"] == name
    assert registry_calls[0]["category"] == category


# =============================================================================
# 5. test_search_returns_results_from_index
#    Mock index with 3 skills; search for keyword; verify correct skill returned.
# =============================================================================

def test_search_returns_results_from_index(marketplace, capsys):
    """
    cmd_search must return only skills whose name/description/category match the query.
    """
    mock_index = {
        "fetched_at": "2099-01-01T00:00:00+00:00",
        "ttl_hours": 24,
        "skills": [
            {
                "slug": "productivity/calendar-reminder",
                "name": "calendar-reminder",
                "category": "productivity",
                "source": "dexter-marketplace",
                "description": "Sends calendar reminders via email",
                "install_url": "",
                "repo_url": "",
                "audited": False,
            },
            {
                "slug": "dev/git-helper",
                "name": "git-helper",
                "category": "dev",
                "source": "github",
                "description": "Automates git workflows",
                "install_url": "",
                "repo_url": "",
                "audited": False,
            },
            {
                "slug": "social/twitter-post",
                "name": "twitter-post",
                "category": "social",
                "source": "clawhub",
                "description": "Post tweets automatically",
                "install_url": "",
                "repo_url": "",
                "audited": False,
            },
        ],
    }

    args = MagicMock()
    args.query = ["calendar"]

    with patch.object(marketplace, "_load_index", return_value=mock_index):
        return_code = marketplace.cmd_search(args)

    captured = capsys.readouterr()
    output = captured.out + captured.err

    assert return_code == 0
    assert "calendar-reminder" in output, (
        "Expected 'calendar-reminder' in search results, got:\n" + output
    )
    assert "git-helper" not in output, (
        "Unexpected 'git-helper' in search results for 'calendar' query"
    )
    assert "twitter-post" not in output, (
        "Unexpected 'twitter-post' in search results for 'calendar' query"
    )


# =============================================================================
# 6. test_update_index_writes_fetched_at
#    Mock all HTTP calls; run cmd_update_index; verify fetched_at in written JSON.
# =============================================================================

def test_update_index_writes_fetched_at(marketplace, tmp_path):
    """
    cmd_update_index must write ~/.dexter/marketplace-index.json with a
    'fetched_at' field present in the JSON output.
    """
    index_file = tmp_path / "marketplace-index.json"

    # All adapters return empty lists (no real HTTP needed)
    def fake_fetch(self):
        return []

    args = MagicMock()

    with (
        patch.object(marketplace, "INDEX_PATH", index_file),
        patch.object(marketplace.DexterMarketplaceAdapter, "fetch", fake_fetch),
        patch.object(marketplace.ClawHubAdapter, "fetch", fake_fetch),
        patch.object(marketplace.CommunityGithubAdapter, "fetch", fake_fetch),
        patch.object(marketplace.ClawFlowsAdapter, "fetch", fake_fetch),
    ):
        marketplace.cmd_update_index(args)

    assert index_file.exists(), "marketplace-index.json was not created"
    data = json.loads(index_file.read_text(encoding="utf-8"))
    assert "fetched_at" in data, (
        f"'fetched_at' not found in written index. Keys: {list(data.keys())}"
    )
    # Validate it's a parseable ISO timestamp
    from datetime import datetime
    ts = datetime.fromisoformat(data["fetched_at"])
    assert ts is not None, "fetched_at is not a valid ISO timestamp"


# =============================================================================
# 7. test_detect_llm_cli_prefers_dexter_agent_env
#    Set DEXTER_AGENT=myagent; detect_llm_cli() must return "myagent" without
#    checking PATH for claude/opencode.
# =============================================================================

def test_detect_llm_cli_prefers_dexter_agent_env(skill_writer):
    """
    detect_llm_cli() must return the value of DEXTER_AGENT env var
    without falling through to shutil.which("claude") or shutil.which("opencode").
    """
    agent_name = "myagent"

    which_calls = []

    def tracking_which(cmd):
        which_calls.append(cmd)
        # Return a path for myagent, None for others
        if cmd == agent_name:
            return f"/usr/local/bin/{agent_name}"
        return None

    with (
        patch.dict(os.environ, {"DEXTER_AGENT": agent_name}),
        patch("shutil.which", side_effect=tracking_which),
    ):
        result = skill_writer.detect_llm_cli()

    assert result == agent_name, (
        f"Expected detect_llm_cli() to return '{agent_name}', got '{result}'"
    )
    # claude and opencode must NOT have been checked
    assert "claude" not in which_calls, (
        "detect_llm_cli() should not check 'claude' when DEXTER_AGENT is set"
    )
    assert "opencode" not in which_calls, (
        "detect_llm_cli() should not check 'opencode' when DEXTER_AGENT is set"
    )


# =============================================================================
# 8. test_dry_run_does_not_write_files
#    Mock LLM CLI to return valid SKILL.md + ---SCRIPT--- + script;
#    run with --dry-run; verify NO files written.
# =============================================================================

def test_dry_run_does_not_write_files(skill_writer, tmp_path, capsys):
    """
    With --dry-run set, cmd_generate must:
    - Print what would be generated.
    - NOT write any files to disk.
    """
    fake_skill_md = textwrap.dedent("""\
        ---
        name: test-skill
        description: >
          A generated test skill. Trigger: test skill
        license: Apache-2.0
        metadata:
          author: dexter
          version: "1.0"
          source: dexter
          audited: false
        allowed-tools: Bash
        ---

        # Test Skill
        Does something useful.

        ## Agent Instructions
        Run the script when the trigger fires.
    """)

    fake_script = textwrap.dedent("""\
        #!/usr/bin/env python3
        \"\"\"Test skill script.\"\"\"
        import argparse

        def main():
            parser = argparse.ArgumentParser()
            parser.parse_args()

        if __name__ == "__main__":
            main()
    """)

    fake_llm_output = fake_skill_md + "\n---SCRIPT---\n" + fake_script

    # Snapshot of files in tmp_path before run
    files_before = set(tmp_path.rglob("*"))

    args = MagicMock()
    args.request = "Create a test skill"
    args.category = "productivity"
    args.name = "test-skill"
    args.dry_run = True

    # Patch check_config so we don't need real paths,
    # detect_llm_cli to return a fake cli name,
    # and _call_llm to return our fake output.
    with (
        patch.object(skill_writer, "check_config", return_value=None),
        patch.object(skill_writer, "detect_llm_cli", return_value="fake-llm"),
        patch.object(skill_writer, "_call_llm", return_value=fake_llm_output),
        patch.object(skill_writer, "find_existing_skills", return_value=[]),
        # Redirect any potential file writes to tmp_path
        patch.object(skill_writer, "COMMUNITY_DIR", tmp_path / "community"),
        patch.object(skill_writer, "REGISTRY_PATH", tmp_path / "registry.md"),
    ):
        skill_writer.cmd_generate(args)

    captured = capsys.readouterr()
    output = captured.out + captured.err

    # Verify the dry run printed something meaningful
    assert "dry" in output.lower() or "test-skill" in output.lower(), (
        "Expected dry-run output, got:\n" + output
    )

    # Verify NO files were written anywhere under tmp_path
    files_after = set(tmp_path.rglob("*"))
    new_files = files_after - files_before
    assert not new_files, (
        f"--dry-run should not write any files, but found new files: {new_files}"
    )
