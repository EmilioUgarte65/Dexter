# GGA — Gentleman's Code Review Rules

> GGA (Gentleman Code Analyzer) is Dexter's built-in code quality gate.
> It runs on ALL code changes made by Dexter or its sub-agents.
> These rules complement the security-auditor — GGA focuses on code quality,
> security-auditor focuses on runtime behavior.

## Rules

### BLOCK: Hardcoded Secrets

Any hardcoded credential, API key, password, or token in source code MUST be blocked.

**Patterns that trigger BLOCK:**

```
# Hardcoded API keys
api_key = "sk-..."
API_KEY = "AIza..."
SECRET = "ghp_..."
token = "xoxb-..."
password = "hunter2"

# Connection strings with credentials
mongodb://user:password@host
postgresql://user:pass@host
mysql://root:secret@host

# Private keys inline
-----BEGIN RSA PRIVATE KEY-----
-----BEGIN OPENSSH PRIVATE KEY-----
```

**Required fix**: Move to environment variable or secrets manager.
```python
# WRONG
client = OpenAI(api_key="sk-abc123")

# RIGHT
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
```

---

### BLOCK: `any` Types in TypeScript

Using `any` bypasses TypeScript's type system and hides bugs. Every `any` must be justified.

**Patterns that trigger BLOCK:**

```typescript
// Untyped parameters
function process(data: any) { ... }

// Untyped variables
const result: any = fetchData();

// Type assertions to any
const x = value as any;
```

**Exceptions** (add comment to bypass):
```typescript
// gga-ignore: any — third-party lib has no types
const lib = require("untyped-lib") as any;
```

**Required fix**: Use proper types, `unknown` with type guards, or generics.
```typescript
// WRONG
function process(data: any): any { ... }

// RIGHT
function process<T extends Record<string, unknown>>(data: T): ProcessedResult { ... }
```

---

### BLOCK: Empty Catch Blocks

Silent error swallowing makes debugging impossible and can hide security issues.

**Patterns that trigger BLOCK:**

```python
# Python — empty except
try:
    risky_operation()
except Exception:
    pass    # ← BLOCKED

# Python — except with only comment
try:
    risky_operation()
except Exception:
    # TODO: handle this later    # ← BLOCKED
```

```typescript
// TypeScript/JavaScript — empty catch
try {
    riskyOperation();
} catch (e) {}    // ← BLOCKED

// Catch that only logs but doesn't re-raise in critical paths
try {
    riskyOperation();
} catch (e) {
    console.log(e);    // ← WARN (not BLOCK, but flagged)
}
```

**Required fix**: Handle the error or explicitly propagate it.
```python
# RIGHT
try:
    risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    raise  # or handle appropriately
```

---

## Severity

| Rule | Default action | Override |
|------|---------------|---------|
| Hardcoded secret | BLOCK | Never |
| `any` type | BLOCK | `gga-ignore: any — <reason>` comment |
| Empty catch | BLOCK | `gga-ignore: empty-catch — <reason>` comment |

---

## Integration

GGA runs automatically via Dexter's security layer before:
- Committing code changes
- Applying self-generated skill scripts
- Deploying any skill with `scripts/` directory

To run manually:
```bash
python3 skills/security/security-auditor/scripts/audit.py <skill-dir>
```

GGA rules are enforced by the security-auditor's code quality checks embedded in `audit.py`.
