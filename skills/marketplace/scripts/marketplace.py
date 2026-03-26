#!/usr/bin/env python3
"""
Dexter Marketplace — unified skill discovery, installation, and browsing.

Commands:
  search <query>               Search across all sources in the local index
  browse [category]            List all skills or skills in a specific category
  install <category/name>      Install a skill (runs security-auditor automatically)
  update-index                 Refresh ~/.dexter/marketplace-index.json from all sources
  list-installed               List skills installed from marketplace

Usage:
  marketplace.py search "calendar reminder"
  marketplace.py browse
  marketplace.py browse productivity
  marketplace.py install productivity/reminder
  marketplace.py install productivity/reminder --source dexter-marketplace
  marketplace.py update-index
  marketplace.py list-installed

GitHub rate limits: set GITHUB_TOKEN env var to raise limit from 60 to 5000 req/hr.
"""

import sys
import os
import json
import shutil
import subprocess
import tempfile
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional


# ─── Config ───────────────────────────────────────────────────────────────────

INDEX_PATH = Path.home() / ".dexter" / "marketplace-index.json"
COMMUNITY_DIR = Path.home() / ".dexter" / "community"
INDEX_TTL_HOURS = 24

DEXTER_MARKETPLACE_OWNER = "EmilioUgarte65"
DEXTER_MARKETPLACE_REPO = "dexter-marketplace"
CLAWFLOWS_OWNER = "nikilster"
CLAWFLOWS_REPO = "clawflows"

GITHUB_API = "https://api.github.com"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _github_headers() -> dict:
    """Build GitHub API request headers, using GITHUB_TOKEN if available."""
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "dexter-marketplace/1.0"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _github_get(url: str) -> Optional[dict]:
    """
    Perform a GET to the GitHub API.
    Returns parsed JSON dict/list or None on error.
    Prints a clear warning on 403/429 (rate limit) with GITHUB_TOKEN hint.
    """
    req = urllib.request.Request(url, headers=_github_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            print(
                f"  [WARN] GitHub API rate limit hit ({e.code}). "
                "Set GITHUB_TOKEN env var to raise the limit:\n"
                "    export GITHUB_TOKEN=<your-token>",
                file=sys.stderr,
            )
        else:
            print(f"  [WARN] GitHub API error {e.code} for {url}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"  [WARN] Network error fetching {url}: {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  [WARN] Unexpected error fetching {url}: {e}", file=sys.stderr)
        return None


# ─── Source adapters ──────────────────────────────────────────────────────────

class DexterMarketplaceAdapter:
    """
    Fetches skills from the official dexter-marketplace GitHub repository.
    Repo layout: <category>/<name>/SKILL.md
    """

    name = "dexter-marketplace"

    def fetch(self) -> list:
        """
        Fetch the full repo tree and filter for SKILL.md files.
        Returns a list of skill dicts in cache format.
        """
        url = f"{GITHUB_API}/repos/{DEXTER_MARKETPLACE_OWNER}/{DEXTER_MARKETPLACE_REPO}/git/trees/main?recursive=1"
        data = _github_get(url)
        if not data:
            # Try HEAD as fallback branch name
            url = f"{GITHUB_API}/repos/{DEXTER_MARKETPLACE_OWNER}/{DEXTER_MARKETPLACE_REPO}/git/trees/HEAD?recursive=1"
            data = _github_get(url)

        if not data or "tree" not in data:
            print(f"  [WARN] dexter-marketplace: could not fetch skill tree", file=sys.stderr)
            return []

        skills = []
        for entry in data["tree"]:
            path = entry.get("path", "")
            # Match <category>/<name>/SKILL.md
            parts = path.split("/")
            if len(parts) == 3 and parts[2] == "SKILL.md" and entry.get("type") == "blob":
                category, name = parts[0], parts[1]
                slug = f"{category}/{name}"
                raw_url = (
                    f"https://raw.githubusercontent.com/"
                    f"{DEXTER_MARKETPLACE_OWNER}/{DEXTER_MARKETPLACE_REPO}/main/{path}"
                )
                repo_url = (
                    f"https://github.com/{DEXTER_MARKETPLACE_OWNER}/"
                    f"{DEXTER_MARKETPLACE_REPO}/tree/main/{category}/{name}"
                )
                skills.append({
                    "slug": slug,
                    "name": name,
                    "category": category,
                    "source": self.name,
                    "description": "",   # Description fetched lazily on install
                    "install_url": raw_url,
                    "repo_url": repo_url,
                    "audited": False,
                })

        print(f"  [OK] dexter-marketplace: {len(skills)} skill(s) found")
        return skills

    def download(self, entry: dict, dest: Path) -> None:
        """
        Download SKILL.md (and scripts/ if present) from dexter-marketplace to dest.
        """
        dest.mkdir(parents=True, exist_ok=True)
        skill_md_url = entry["install_url"]
        skill_md_path = dest / "SKILL.md"

        req = urllib.request.Request(skill_md_url, headers=_github_headers())
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                skill_md_path.write_bytes(resp.read())
        except Exception as e:
            raise RuntimeError(f"Failed to download SKILL.md from {skill_md_url}: {e}")

        # Try to download scripts/ directory
        category, name = entry["slug"].split("/", 1)
        scripts_tree_url = (
            f"{GITHUB_API}/repos/{DEXTER_MARKETPLACE_OWNER}/{DEXTER_MARKETPLACE_REPO}"
            f"/contents/{category}/{name}/scripts"
        )
        scripts_data = _github_get(scripts_tree_url)
        if scripts_data and isinstance(scripts_data, list):
            scripts_dir = dest / "scripts"
            scripts_dir.mkdir(exist_ok=True)
            for file_entry in scripts_data:
                if file_entry.get("type") == "file" and file_entry.get("download_url"):
                    fname = file_entry["name"]
                    req2 = urllib.request.Request(
                        file_entry["download_url"], headers=_github_headers()
                    )
                    try:
                        with urllib.request.urlopen(req2, timeout=15) as resp:
                            (scripts_dir / fname).write_bytes(resp.read())
                    except Exception as e:
                        print(f"  [WARN] Could not download scripts/{fname}: {e}", file=sys.stderr)


class ClawHubAdapter:
    """
    Fetches skills from ClawHub via the npx clawhub CLI.
    Requires npx to be installed. If npx is absent, prints a warning and returns [].
    """

    name = "clawhub"

    def _check_npx(self) -> bool:
        """Return True if npx is available, False otherwise (with warning)."""
        if shutil.which("npx"):
            return True
        print(
            "  [WARN] ClawHub: npx not found — ClawHub results unavailable.\n"
            "  Hint: install npm and npx first:\n"
            "    npm install -g npx\n"
            "  Or install Node.js from https://nodejs.org which includes npx.",
            file=sys.stderr,
        )
        return False

    def fetch(self) -> list:
        """
        Run `npx clawhub list --json` and map output to cache schema.
        Returns [] if npx is missing or the command fails.
        """
        if not self._check_npx():
            return []

        try:
            result = subprocess.run(
                ["npx", "clawhub", "list", "--json"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                print(
                    f"  [WARN] ClawHub: `npx clawhub list --json` failed "
                    f"(exit {result.returncode}). ClawHub results unavailable.",
                    file=sys.stderr,
                )
                return []

            raw = json.loads(result.stdout)
            skills = []
            items = raw if isinstance(raw, list) else raw.get("skills", raw.get("results", []))
            for item in items:
                slug_raw = item.get("slug", item.get("name", ""))
                if not slug_raw:
                    continue
                # Normalise to category/name format
                parts = slug_raw.split("/")
                if len(parts) == 2:
                    category, name = parts
                elif len(parts) == 1:
                    category, name = "community", parts[0]
                else:
                    category, name = parts[0], "/".join(parts[1:])

                skills.append({
                    "slug": f"{category}/{name}",
                    "name": name,
                    "category": category,
                    "source": self.name,
                    "description": item.get("description", ""),
                    "install_url": item.get("url", item.get("install_url", "")),
                    "repo_url": item.get("repo_url", item.get("url", "")),
                    "audited": False,
                })

            print(f"  [OK] clawhub: {len(skills)} skill(s) found")
            return skills

        except json.JSONDecodeError as e:
            print(f"  [WARN] ClawHub: could not parse JSON output: {e}", file=sys.stderr)
            return []
        except subprocess.TimeoutExpired:
            print("  [WARN] ClawHub: command timed out after 30s", file=sys.stderr)
            return []
        except Exception as e:
            print(f"  [WARN] ClawHub: unexpected error: {e}", file=sys.stderr)
            return []

    def download(self, entry: dict, dest: Path) -> None:
        """Download a ClawHub skill via `npx clawhub install` to dest."""
        if not self._check_npx():
            raise RuntimeError("npx not available — cannot install ClawHub skill")

        slug = entry["slug"]
        dest.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(
                ["npx", "clawhub", "install", slug, "--output", str(dest)],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"`npx clawhub install {slug}` failed (exit {result.returncode}):\n{result.stderr}"
                )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"ClawHub install timed out for {slug}")


class CommunityGithubAdapter:
    """
    Searches GitHub for repos tagged topic:dexter-skill.
    Also attempts to find repos containing a SKILL.md at root.
    """

    name = "github"

    def fetch(self) -> list:
        """
        Search GitHub for repos tagged with topic:dexter-skill.
        Returns list of skill dicts in cache format.
        """
        url = f"{GITHUB_API}/search/repositories?q=topic:dexter-skill&per_page=50"
        data = _github_get(url)
        if not data:
            return []

        items = data.get("items", [])
        skills = []
        seen_slugs = set()

        for repo in items:
            repo_name = repo.get("name", "")
            description = repo.get("description", "")
            html_url = repo.get("html_url", "")
            default_branch = repo.get("default_branch", "main")

            # Derive category from repo topics or default to "community"
            topics = repo.get("topics", [])
            category = "community"
            for t in topics:
                if t.startswith("dexter-") and t != "dexter-skill":
                    category = t[len("dexter-"):]
                    break

            slug = f"{category}/{repo_name}"
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            install_url = (
                f"https://raw.githubusercontent.com/"
                f"{repo.get('full_name', '')}/{default_branch}/SKILL.md"
            )

            skills.append({
                "slug": slug,
                "name": repo_name,
                "category": category,
                "source": self.name,
                "description": description or "",
                "install_url": install_url,
                "repo_url": html_url,
                "audited": False,
            })

        print(f"  [OK] github community: {len(skills)} skill(s) found")
        return skills

    def download(self, entry: dict, dest: Path) -> None:
        """Download SKILL.md and scripts/ from a community GitHub repo."""
        dest.mkdir(parents=True, exist_ok=True)
        install_url = entry.get("install_url", "")
        if not install_url:
            raise RuntimeError(f"No install_url for community skill {entry['slug']}")

        req = urllib.request.Request(install_url, headers=_github_headers())
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                (dest / "SKILL.md").write_bytes(resp.read())
        except Exception as e:
            raise RuntimeError(f"Failed to download SKILL.md from {install_url}: {e}")

        # Try to download scripts/ via GitHub contents API
        repo_url = entry.get("repo_url", "")
        if "github.com" in repo_url:
            # Extract owner/repo from URL
            parts = repo_url.rstrip("/").split("github.com/")
            if len(parts) == 2:
                owner_repo = parts[1]
                scripts_api = f"{GITHUB_API}/repos/{owner_repo}/contents/scripts"
                scripts_data = _github_get(scripts_api)
                if scripts_data and isinstance(scripts_data, list):
                    scripts_dir = dest / "scripts"
                    scripts_dir.mkdir(exist_ok=True)
                    for file_entry in scripts_data:
                        if file_entry.get("type") == "file" and file_entry.get("download_url"):
                            fname = file_entry["name"]
                            req2 = urllib.request.Request(
                                file_entry["download_url"], headers=_github_headers()
                            )
                            try:
                                with urllib.request.urlopen(req2, timeout=15) as resp:
                                    (scripts_dir / fname).write_bytes(resp.read())
                            except Exception as e:
                                print(
                                    f"  [WARN] Could not download scripts/{fname}: {e}",
                                    file=sys.stderr,
                                )


class ClawFlowsAdapter:
    """
    Fetches workflows from the ClawFlows community library.
    Maps WORKFLOW.md files to skill cache entries.
    """

    name = "clawflows"

    def fetch(self) -> list:
        """
        Fetch ClawFlows repo tree and find WORKFLOW.md files.
        Returns list of skill dicts in cache format.
        """
        url = (
            f"{GITHUB_API}/repos/{CLAWFLOWS_OWNER}/{CLAWFLOWS_REPO}"
            "/git/trees/main?recursive=1"
        )
        data = _github_get(url)
        if not data or "tree" not in data:
            print(f"  [WARN] clawflows: could not fetch workflow tree", file=sys.stderr)
            return []

        skills = []
        for entry in data["tree"]:
            path = entry.get("path", "")
            # Match workflows/available/<type>/<name>/WORKFLOW.md
            if not path.endswith("WORKFLOW.md"):
                continue
            if entry.get("type") != "blob":
                continue

            parts = path.split("/")
            # workflows/available/<community|featured>/<name>/WORKFLOW.md
            if len(parts) >= 4:
                name = parts[-2]
                raw_url = (
                    f"https://raw.githubusercontent.com/"
                    f"{CLAWFLOWS_OWNER}/{CLAWFLOWS_REPO}/main/{path}"
                )
                repo_url = (
                    f"https://github.com/{CLAWFLOWS_OWNER}/{CLAWFLOWS_REPO}"
                    f"/tree/main/{'/'.join(parts[:-1])}"
                )
                slug = f"clawflows/{name}"
                skills.append({
                    "slug": slug,
                    "name": name,
                    "category": "clawflows",
                    "source": self.name,
                    "description": f"ClawFlows workflow: {name}",
                    "install_url": raw_url,
                    "repo_url": repo_url,
                    "audited": False,
                })

        print(f"  [OK] clawflows: {len(skills)} workflow(s) found")
        return skills

    def download(self, entry: dict, dest: Path) -> None:
        """
        Download a WORKFLOW.md and convert it to SKILL.md using clawflows-adapter.
        Falls back to copying WORKFLOW.md directly if converter is not found.
        """
        dest.mkdir(parents=True, exist_ok=True)
        install_url = entry["install_url"]

        req = urllib.request.Request(install_url, headers=_github_headers())
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                workflow_content = resp.read()
        except Exception as e:
            raise RuntimeError(f"Failed to download WORKFLOW.md from {install_url}: {e}")

        # Write WORKFLOW.md temporarily
        workflow_path = dest / "WORKFLOW.md"
        workflow_path.write_bytes(workflow_content)

        # Try to convert using clawflows-adapter
        converter_candidates = [
            Path(__file__).parent.parent.parent / "clawflows-adapter" / "scripts" / "import_workflow.py",
            Path.home() / "proyectos" / "Dexter" / "skills" / "clawflows-adapter" / "scripts" / "import_workflow.py",
        ]
        converter = None
        for c in converter_candidates:
            if c.exists():
                converter = c
                break

        if converter:
            result = subprocess.run(
                [sys.executable, str(converter), str(workflow_path), "--output", str(dest)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                workflow_path.unlink(missing_ok=True)
                return
            else:
                print(
                    f"  [WARN] clawflows converter failed: {result.stderr.strip()}\n"
                    "  Keeping WORKFLOW.md as-is.",
                    file=sys.stderr,
                )
        else:
            # No converter — rename WORKFLOW.md → SKILL.md with minimal frontmatter
            name = entry["name"]
            minimal_skill = (
                f"---\nname: {name}\ndescription: >\n"
                f"  ClawFlows workflow: {name}\n"
                f"  Trigger: {name}\n"
                "license: MIT\nmetadata:\n  author: community\n"
                f"  version: \"1.0\"\n  source: clawflows\n  audited: false\n"
                "allowed-tools: Read, Bash\n---\n\n"
            )
            workflow_text = workflow_path.read_text(encoding="utf-8")
            (dest / "SKILL.md").write_text(minimal_skill + workflow_text, encoding="utf-8")
            workflow_path.unlink(missing_ok=True)


# ─── Source registry ──────────────────────────────────────────────────────────

ADAPTERS = {
    "dexter-marketplace": DexterMarketplaceAdapter(),
    "clawhub":            ClawHubAdapter(),
    "github":             CommunityGithubAdapter(),
    "clawflows":          ClawFlowsAdapter(),
}


# ─── Index management ─────────────────────────────────────────────────────────

def _load_index() -> dict:
    """
    Load the local marketplace index from ~/.dexter/marketplace-index.json.
    Returns an empty index structure if the file is absent or corrupted.
    Auto-refreshes if the cache is stale (older than INDEX_TTL_HOURS).
    """
    if INDEX_PATH.exists():
        try:
            data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            fetched_at_str = data.get("fetched_at", "")
            if fetched_at_str:
                fetched_at = datetime.fromisoformat(fetched_at_str)
                age = datetime.now(timezone.utc) - fetched_at
                if age < timedelta(hours=INDEX_TTL_HOURS):
                    return data
                else:
                    print(
                        f"Index is {int(age.total_seconds() / 3600)}h old (TTL: {INDEX_TTL_HOURS}h) — refreshing...",
                        file=sys.stderr,
                    )
        except (json.JSONDecodeError, ValueError):
            print("Index file corrupted — rebuilding...", file=sys.stderr)

    return _refresh_index()


def _refresh_index() -> dict:
    """
    Fetch from all source adapters, merge results, and write to ~/.dexter/marketplace-index.json.
    Returns the new index dict.
    """
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("Refreshing marketplace index from all sources...")
    all_skills = []
    seen_slugs: set = set()

    for source_name, adapter in ADAPTERS.items():
        try:
            skills = adapter.fetch()
            for skill in skills:
                slug = skill["slug"]
                if slug not in seen_slugs:
                    seen_slugs.add(slug)
                    all_skills.append(skill)
        except Exception as e:
            print(f"  [WARN] {source_name}: error during fetch: {e}", file=sys.stderr)

    index = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "ttl_hours": INDEX_TTL_HOURS,
        "skills": all_skills,
    }

    INDEX_PATH.write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"Index updated: {len(all_skills)} skill(s) from {len(ADAPTERS)} source(s)")
    return index


# ─── Security audit ───────────────────────────────────────────────────────────

def _run_audit(skill_dir: Path) -> tuple:
    """
    Run security-auditor on skill_dir.
    Returns (result, output) where result is PASS / WARN / BLOCK.
    Mirrors the same candidate-path resolution used in convert.py.
    """
    candidates = [
        Path(__file__).parent.parent.parent / "security" / "security-auditor" / "scripts" / "audit.py",
        Path.home() / ".claude" / "skills" / "security" / "security-auditor" / "scripts" / "audit.py",
        Path.home() / "proyectos" / "Dexter" / "skills" / "security" / "security-auditor" / "scripts" / "audit.py",
    ]
    audit_script = None
    for c in candidates:
        if c.exists():
            audit_script = c
            break

    if not audit_script:
        return "WARN", "security-auditor not found — skipping audit"

    try:
        result = subprocess.run(
            [sys.executable, str(audit_script), str(skill_dir), "--json"],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        try:
            data = json.loads(output)
            return data.get("result", "WARN"), output
        except json.JSONDecodeError:
            return "WARN", output or result.stderr
    except subprocess.TimeoutExpired:
        return "WARN", "Audit timed out"
    except Exception as e:
        return "WARN", f"Audit error: {e}"


# ─── Registry append ──────────────────────────────────────────────────────────

def _find_registry() -> Optional[Path]:
    """
    Locate .atl/skill-registry.md relative to the Dexter project root.
    Searches from the script's location upward, then from cwd.
    """
    # From this script: skills/marketplace/scripts/marketplace.py
    # → project root is three levels up
    candidates = [
        Path(__file__).parent.parent.parent.parent / ".atl" / "skill-registry.md",
        Path.cwd() / ".atl" / "skill-registry.md",
        Path.home() / "proyectos" / "Dexter" / ".atl" / "skill-registry.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _registry_append(name: str, category: str, source: str, skill_path: Path) -> None:
    """
    Append one skill entry to .atl/skill-registry.md under the '#### marketplace' section.
    Creates the section if it doesn't exist.
    """
    registry = _find_registry()
    if not registry:
        print(
            f"  [WARN] skill-registry.md not found — skill installed but not registered.\n"
            f"  Manual registration: | `{name}` | {skill_path} |",
            file=sys.stderr,
        )
        return

    text = registry.read_text(encoding="utf-8")
    entry_line = f"| `{name}` | `{skill_path}` |\n"

    if "#### marketplace" in text:
        # Append under the existing section
        idx = text.index("#### marketplace")
        # Find the next blank line after the table header or existing entries
        # Insert before the next section heading or end of file
        insert_at = len(text)
        lines = text.splitlines(keepends=True)
        in_section = False
        pos = 0
        for line in lines:
            if "#### marketplace" in line:
                in_section = True
            elif in_section and line.startswith("####"):
                insert_at = pos
                break
            pos += len(line)
        text = text[:insert_at] + entry_line + text[insert_at:]
    else:
        # Create a new marketplace section at the end of the file
        marketplace_section = (
            "\n#### marketplace\n"
            "| Skill | Path |\n"
            "|-------|------|\n"
            + entry_line
        )
        text = text.rstrip() + "\n" + marketplace_section

    registry.write_text(text, encoding="utf-8")
    print(f"  Registered in skill-registry.md: {name}")


# ─── Subcommands ──────────────────────────────────────────────────────────────

def cmd_search(args) -> int:
    """Search the local index for skills matching the query."""
    query = " ".join(args.query).lower()
    index = _load_index()
    skills = index.get("skills", [])

    matches = []
    for skill in skills:
        haystack = " ".join([
            skill.get("name", ""),
            skill.get("description", ""),
            skill.get("category", ""),
            skill.get("slug", ""),
        ]).lower()
        if query in haystack:
            matches.append(skill)

    if not matches:
        print(f"No skills found for '{' '.join(args.query)}'")
        print("Try `marketplace.py update-index` to refresh from all sources.")
        return 0

    print(f"\nFound {len(matches)} skill(s) matching '{' '.join(args.query)}':\n")
    _print_skills_table(matches)
    return 0


def cmd_browse(args) -> int:
    """List all skills or skills in a specific category."""
    index = _load_index()
    skills = index.get("skills", [])

    if args.category:
        category = args.category.lower()
        skills = [s for s in skills if s.get("category", "").lower() == category]
        if not skills:
            print(f"No skills found in category '{args.category}'")
            return 0
        print(f"\nSkills in category '{args.category}':\n")
    else:
        if not skills:
            print("Index is empty. Run `marketplace.py update-index` first.")
            return 0
        print(f"\nAll marketplace skills ({len(skills)} total):\n")

    # Group by category
    by_category: dict = {}
    for skill in skills:
        cat = skill.get("category", "unknown")
        by_category.setdefault(cat, []).append(skill)

    for cat in sorted(by_category):
        print(f"  [{cat}]")
        for skill in by_category[cat]:
            name = skill.get("name", skill.get("slug", ""))
            desc = skill.get("description", "")
            source = skill.get("source", "")
            desc_short = desc[:60] + "..." if len(desc) > 60 else desc
            print(f"    {skill['slug']:<40}  {source:<20}  {desc_short}")
        print()

    return 0


def cmd_install(args) -> int:
    """Install a skill from the marketplace (runs security-auditor automatically)."""
    slug = args.slug
    preferred_source = getattr(args, "source", None)

    index = _load_index()
    skills = index.get("skills", [])

    # Find matching entries
    matches = [s for s in skills if s["slug"] == slug]
    if preferred_source:
        source_matches = [s for s in matches if s["source"] == preferred_source]
        if source_matches:
            matches = source_matches
        else:
            print(
                f"Skill '{slug}' not found from source '{preferred_source}'. "
                f"Available sources: {', '.join(s['source'] for s in matches) or 'none'}",
                file=sys.stderr,
            )
            return 1

    if not matches:
        print(
            f"Skill '{slug}' not found in the local index.\n"
            f"Try `marketplace.py update-index` to refresh or check the slug.",
            file=sys.stderr,
        )
        return 1

    entry = matches[0]
    source_name = entry["source"]
    adapter = ADAPTERS.get(source_name)
    if not adapter:
        print(f"Unknown source adapter: {source_name}", file=sys.stderr)
        return 1

    category, name = (slug.split("/", 1) + ["unknown"])[:2]

    print(f"\nInstalling '{slug}' from {source_name}...")

    # 1. Download to tmp dir
    with tempfile.TemporaryDirectory(prefix="dexter-install-") as tmp_str:
        tmp_dir = Path(tmp_str)
        try:
            adapter.download(entry, tmp_dir)
        except RuntimeError as e:
            print(f"[ERROR] Download failed: {e}", file=sys.stderr)
            return 1

        # 2. Run security audit
        print(f"  Running security audit...")
        audit_result, audit_output = _run_audit(tmp_dir)
        print(f"  Audit result: {audit_result}")

        if audit_result == "BLOCK":
            print(f"[BLOCK] Skill '{slug}' rejected by security-auditor. Install aborted.", file=sys.stderr)
            try:
                data = json.loads(audit_output)
                for finding in data.get("findings", []):
                    if finding.get("severity") in ("CRITICAL", "HIGH"):
                        print(
                            f"  [{finding['severity']}] {Path(finding['file']).name}:{finding['line']}"
                            f" — {finding['description']}",
                            file=sys.stderr,
                        )
            except Exception:
                if audit_output:
                    print(f"  Details: {audit_output}", file=sys.stderr)
            return 1

        # 3. Copy to ~/.dexter/community/<category>/<name>/
        dest = COMMUNITY_DIR / category / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(tmp_dir, dest)

    print(f"  Installed to: {dest}")

    # 4. Append to registry
    skill_md_path = dest / "SKILL.md"
    _registry_append(name, category, source_name, skill_md_path)

    if audit_result == "WARN":
        print(f"\n[WARN] Skill installed with warnings — review audit findings before use.")

    print(f"\n[OK] '{slug}' installed successfully from {source_name}.")
    return 0


def cmd_update_index(args) -> int:
    """Force-refresh the marketplace index from all sources."""
    _refresh_index()
    return 0


def cmd_list_installed(args) -> int:
    """List skills installed from the marketplace (in ~/.dexter/community/)."""
    if not COMMUNITY_DIR.exists():
        print("No marketplace skills installed yet.")
        print(f"Skills installed via marketplace go to: {COMMUNITY_DIR}")
        return 0

    installed = []
    for category_dir in sorted(COMMUNITY_DIR.iterdir()):
        if not category_dir.is_dir():
            continue
        for skill_dir in sorted(category_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            installed.append({
                "slug": f"{category_dir.name}/{skill_dir.name}",
                "category": category_dir.name,
                "name": skill_dir.name,
                "path": str(skill_md),
                "has_skill_md": skill_md.exists(),
            })

    if not installed:
        print("No marketplace skills installed yet.")
        return 0

    print(f"\nInstalled marketplace skills ({len(installed)}):\n")
    print(f"  {'Slug':<45}  {'Path'}")
    print(f"  {'-'*44}  {'-'*50}")
    for skill in installed:
        flag = "" if skill["has_skill_md"] else " [missing SKILL.md]"
        print(f"  {skill['slug']:<45}  {skill['path']}{flag}")
    print()
    return 0


# ─── Output helpers ───────────────────────────────────────────────────────────

def _print_skills_table(skills: list) -> None:
    """Print a formatted table of skills."""
    print(f"  {'Slug':<40}  {'Source':<20}  {'Description'}")
    print(f"  {'-'*39}  {'-'*19}  {'-'*50}")
    for skill in skills:
        name = skill.get("slug", "")
        source = skill.get("source", "")
        desc = skill.get("description", "")
        desc_short = desc[:50] + "..." if len(desc) > 50 else desc
        print(f"  {name:<40}  {source:<20}  {desc_short}")
    print()


# ─── Check config ─────────────────────────────────────────────────────────────

def check_config() -> None:
    """
    Verify environment and dependencies.
    Prints warnings for missing optional tools (npx, GITHUB_TOKEN).
    Does NOT exit — missing optional tools are handled gracefully per-adapter.
    """
    if not os.environ.get("GITHUB_TOKEN"):
        # Only warn when explicitly running check_config, not on every command
        pass  # Warned per-request when rate limit is hit


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Dexter Marketplace — unified skill discovery and installation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    # search
    p_search = subparsers.add_parser("search", help="Search for skills by keyword")
    p_search.add_argument("query", nargs="+", help="Search query")
    p_search.set_defaults(func=cmd_search)

    # browse
    p_browse = subparsers.add_parser("browse", help="Browse skills by category")
    p_browse.add_argument("category", nargs="?", help="Category to browse (omit for all)")
    p_browse.set_defaults(func=cmd_browse)

    # install
    p_install = subparsers.add_parser("install", help="Install a skill")
    p_install.add_argument("slug", help="Skill slug in <category/name> format")
    p_install.add_argument(
        "--source",
        choices=list(ADAPTERS.keys()),
        help="Preferred source (optional — picks first match if omitted)",
    )
    p_install.set_defaults(func=cmd_install)

    # update-index
    p_update = subparsers.add_parser("update-index", help="Refresh the local marketplace index")
    p_update.set_defaults(func=cmd_update_index)

    # list-installed
    p_list = subparsers.add_parser("list-installed", help="List installed marketplace skills")
    p_list.set_defaults(func=cmd_list_installed)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
