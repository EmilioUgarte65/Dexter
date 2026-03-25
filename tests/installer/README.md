# Installer Tests

Unit tests for `install.sh` and `uninstall.sh` using [bats-core](https://github.com/bats-core/bats-core).

## Prerequisites

Install bats-core (pick one):

```bash
# macOS
brew install bats-core

# Ubuntu / Debian
apt-get install bats

# Any platform via npm
npm install -g bats
```

## Running the tests

From the project root:

```bash
bats tests/installer/install.bats
```

Run with verbose output:

```bash
bats --verbose-run tests/installer/install.bats
```

## What is tested

| # | Test | Description |
|---|------|-------------|
| 1 | Syntax — install.sh | `bash -n` must pass with no errors |
| 2 | Syntax — uninstall.sh | `bash -n` must pass with no errors |
| 3 | Unknown argument | `install.sh --unknown-flag` exits non-zero and prints an error |
| 4–8 | Dry-run creates no files | `--agent claude-code --dry-run` must not write anything to `$HOME` |
| 9–14 | Dry-run output | Confirms DRY RUN notice and expected target paths for claude-code |
| 15–17 | No backup — uninstall | Exits non-zero with a descriptive error, never a silent crash |
| 18–19 | No backup — edge cases | Unknown arg and `--dry-run` without backup also fail cleanly |
| 20–21 | Empty backup dir | `--backup-dir` with no manifest warns and exits 0 (no crash) |

## Notes

- Each test runs in an isolated `$HOME` (a `mktemp -d` directory). Your real home directory is never touched.
- Tests that require an actual installed agent environment use `skip` where appropriate. The current suite avoids calling real agent binaries.
- `bash -n install.bats` will fail — this is expected. The `@test "..." {` construct is valid bats-core syntax but not valid raw bash. To syntax-check the test bodies, bats preprocesses the file before passing it to bash. The scripts under test (`install.sh`, `uninstall.sh`) do pass `bash -n` cleanly.
