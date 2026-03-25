# Dexter — Test Suite

Two test layers cover the project:

| Layer | Tool | Location | What it tests |
|-------|------|----------|---------------|
| Installer | bats-core | `tests/installer/install.bats` | `install.sh` + `uninstall.sh` behaviour |
| Python scripts | pytest | `tests/scripts/test_scripts.py` | Syntax, `--help` smoke, security-auditor logic |

---

## Prerequisites

### bats-core (installer tests)

```bash
# macOS
brew install bats-core

# Ubuntu / Debian
apt-get install bats

# Any platform via npm
npm install -g bats
```

### pytest (script tests)

```bash
pip install pytest          # system / venv pip
# or
pip3 install pytest
```

---

## Running the tests

### All tests (requires both tools)

```bash
make test
```

### Installer tests only

```bash
bats tests/installer/install.bats

# With verbose output
bats --verbose-run tests/installer/install.bats
```

### Python script tests only

```bash
python3 -m pytest tests/scripts/ -v

# Stop on first failure
python3 -m pytest tests/scripts/ -v -x

# Run only security-auditor unit tests
python3 -m pytest tests/scripts/ -v -k "auditor or overall_result or scan"
```

---

## What is tested

### Installer (`tests/installer/install.bats`)

| # | Test |
|---|------|
| 1 | `install.sh` passes `bash -n` syntax check |
| 2 | `uninstall.sh` passes `bash -n` syntax check |
| 3–4 | Unknown argument exits non-zero and prints an error |
| 5–9 | `--dry-run` creates zero files in `$HOME` |
| 10–15 | `--dry-run` output includes DRY RUN notice and expected target paths |
| 16–18 | No backup dir: exits non-zero with a descriptive error |
| 19–20 | Edge cases: unknown arg and `--dry-run` without backup |
| 21–22 | Empty backup dir: warns about missing manifest, exits 0 |

Each test runs in an isolated `$HOME` (`mktemp -d`). Your real home directory is never touched.

### Python scripts (`tests/scripts/test_scripts.py`)

**Group 1 — Syntax check** (41 scripts)
Every `.py` script under `skills/` is compiled with `py_compile`. A broken file fails immediately.

**Group 2 — `--help` smoke test** (26 scripts)
Scripts are invoked with `--help` in a subprocess. They must exit 0 and produce output.
Scripts that validate required API env vars before argparse are excluded from this group
(see `_HELP_SKIP` in the test file) — they are still covered by the syntax check.

**Group 3 — security-auditor unit tests** (9 tests)
`audit.py` is imported directly (no subprocess) and its core functions are exercised:

- `scan_file()` detects curl exfiltration (HIGH) — query string to external URL
- `scan_file()` does NOT flag plain curl GETs
- `scan_file()` detects `eval()` (MEDIUM or higher)
- `overall_result([])` returns PASS
- `overall_result([HIGH finding])` returns BLOCK
- `overall_result([MEDIUM finding])` returns WARN
- `scan_skill_dir()` returns no HIGH/CRITICAL for a clean skill

**Group 4 — openclaw-adapter**
`convert.py --help` exits 0 and mentions `skill` in its output.

---

## Known limitations

- Scripts that check required env vars before argparse (e.g. `discord/send.py`, `slack/send.py`)
  cannot be smoke-tested with `--help` without the real credentials. They are listed in
  `_HELP_SKIP` inside `test_scripts.py` with comments explaining the root cause.
- Installer tests require bash 4+. macOS ships bash 3 — install `bash` via Homebrew if bats
  reports syntax errors on macOS.
- The bats test file cannot be syntax-checked with `bash -n` — this is expected. bats
  preprocesses `@test` blocks before handing them to bash; the scripts under test
  (`install.sh`, `uninstall.sh`) do pass `bash -n` cleanly.
