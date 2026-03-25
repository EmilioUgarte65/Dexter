#!/usr/bin/env python3
"""
Dexter — Skill creator CLI.
Scaffolds new Dexter skills with SKILL.md + scripts/ boilerplate.

Usage:
  create.py new <name> [--category CATEGORY] [--description TEXT] [--interactive]
  create.py validate <skill_path>
  create.py list [--category CAT]

Environment:
  DEXTER_SKILLS_DIR  Base skills directory (default: skills/)
"""

import sys
import os
import re
import argparse
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────────

SKILLS_DIR = Path(os.environ.get("DEXTER_SKILLS_DIR", "skills/"))

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

REQUIRED_FRONTMATTER_FIELDS = [
    "name",
    "description",
    "license",
    "metadata",
]

DEFAULT_CATEGORIES = [
    "communications",
    "productivity",
    "security",
    "domotics",
    "dev",
    "media",
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _import_template():
    """Import template module from same scripts/ directory."""
    scripts_dir = Path(__file__).parent
    sys.path.insert(0, str(scripts_dir))
    import template
    return template


def _validate_name(name: str) -> str:
    """Ensure name is kebab-case."""
    if not re.match(r"^[a-z][a-z0-9-]*$", name):
        print(
            f"{RED}Error: name must be kebab-case (lowercase letters, digits, hyphens).{RESET}\n"
            f"  Got: {name!r}\n"
            f"  OK:  my-skill, deploy-hetzner, gmail-reader",
            file=sys.stderr,
        )
        sys.exit(1)
    return name


def _skill_dir(category: str, name: str) -> Path:
    return SKILLS_DIR / category / name


# ─── Command: new ─────────────────────────────────────────────────────────────

def cmd_new(args):
    name        = _validate_name(args.name)
    category    = args.category
    description = args.description or ""
    interactive = args.interactive

    if interactive:
        name, category, description, triggers, has_script = _interactive_prompt(name)
    else:
        triggers   = [name, name.replace("-", " ")]
        has_script = True

    skill_path = _skill_dir(category, name)

    if skill_path.exists():
        print(f"{YELLOW}Warning: {skill_path} already exists.{RESET}")
        answer = input("Overwrite? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)

    template = _import_template()

    # Generate files
    skill_md_content = template.generate_skill_md(
        name=name,
        category=category,
        description=description or f"{name.replace('-', ' ').title()} integration for Dexter.",
        triggers=triggers,
        has_script=has_script,
    )

    # Write SKILL.md
    skill_path.mkdir(parents=True, exist_ok=True)
    skill_md_path = skill_path / "SKILL.md"
    skill_md_path.write_text(skill_md_content)

    print(f"{GREEN}Created:{RESET} {skill_md_path}")

    if has_script:
        scripts_dir = skill_path / "scripts"
        scripts_dir.mkdir(exist_ok=True)

        script_name   = name.replace("-", "_") + ".py"
        script_path   = scripts_dir / script_name
        script_content = template.generate_script(name=name)
        script_path.write_text(script_content)
        script_path.chmod(0o755)

        print(f"{GREEN}Created:{RESET} {script_path}")

    print(f"\n{BOLD}Skill scaffolded at:{RESET} {skill_path}/")
    print(f"\n{CYAN}Next steps:{RESET}")
    print(f"  1. Edit {skill_md_path} — fill in real trigger keywords and instructions")
    if has_script:
        print(f"  2. Edit {skill_path / 'scripts' / script_name} — implement the commands")
    print(f"  3. python3 skills/skill-creator/scripts/create.py validate {skill_path}/")
    print(f"  4. Test: mention a trigger keyword and see if Dexter activates the skill")


def _interactive_prompt(default_name: str) -> tuple[str, str, str, list[str], bool]:
    """Prompt the user interactively for skill details."""
    print(f"\n{BOLD}{CYAN}=== Dexter Skill Creator ==={RESET}")
    print("Answer a few questions to scaffold your skill.\n")

    name = input(f"Skill name (kebab-case) [{default_name}]: ").strip() or default_name
    name = _validate_name(name)

    print(f"\nAvailable categories: {', '.join(DEFAULT_CATEGORIES)}")
    category = input("Category [productivity]: ").strip() or "productivity"

    description = input(
        "\nDescription (one sentence, what does this skill do?):\n> "
    ).strip()

    print(
        "\nTrigger keywords (comma-separated — what phrases should activate this skill?):"
    )
    print(f"  Example: hetzner, VPS hetzner, servidor hetzner, deploy hetzner")
    triggers_raw = input("> ").strip()
    triggers = [t.strip() for t in triggers_raw.split(",") if t.strip()]
    if not triggers:
        triggers = [name, name.replace("-", " ")]

    has_script_raw = input(
        "\nCreate a scripts/ directory with Python boilerplate? [Y/n]: "
    ).strip().lower()
    has_script = has_script_raw not in ("n", "no")

    print(f"\n{BOLD}Summary:{RESET}")
    print(f"  Name:        {name}")
    print(f"  Category:    {category}")
    print(f"  Description: {description or '(empty)'}")
    print(f"  Triggers:    {', '.join(triggers)}")
    print(f"  Has script:  {has_script}")
    print()

    confirm = input("Create? [Y/n]: ").strip().lower()
    if confirm in ("n", "no"):
        print("Aborted.")
        sys.exit(0)

    return name, category, description, triggers, has_script


# ─── Command: validate ────────────────────────────────────────────────────────

def cmd_validate(args):
    skill_path = Path(args.skill_path)
    skill_md   = skill_path / "SKILL.md"
    errors     = []
    warnings   = []

    if not skill_path.exists():
        print(f"{RED}Error: path does not exist: {skill_path}{RESET}", file=sys.stderr)
        sys.exit(1)

    if not skill_md.exists():
        print(f"{RED}Error: SKILL.md not found in {skill_path}{RESET}", file=sys.stderr)
        sys.exit(1)

    content = skill_md.read_text()

    # Check frontmatter delimiters
    if not content.startswith("---"):
        errors.append("SKILL.md does not start with '---' frontmatter delimiter")

    # Check required frontmatter fields
    for field in REQUIRED_FRONTMATTER_FIELDS:
        if f"\n{field}:" not in content and not content.startswith(f"{field}:"):
            errors.append(f"Missing required frontmatter field: {field}")

    # Check audited field
    if "audited:" not in content:
        warnings.append("Missing 'audited:' field in metadata — set to false if not reviewed")

    # Check trigger keywords in description
    if "Trigger:" not in content and "trigger:" not in content:
        warnings.append("No 'Trigger:' line found in description — trigger keywords help activation")

    # Check scripts/ if referenced
    scripts_dir = skill_path / "scripts"
    if "scripts/" in content and not scripts_dir.exists():
        errors.append("SKILL.md references scripts/ but directory does not exist")

    if scripts_dir.exists():
        py_files = list(scripts_dir.glob("*.py"))
        if not py_files:
            warnings.append("scripts/ directory exists but contains no .py files")
        else:
            # Check shebang in each script
            for py_file in py_files:
                first_line = py_file.read_text().split("\n")[0]
                if not first_line.startswith("#!/usr/bin/env python3"):
                    warnings.append(f"{py_file.name}: missing '#!/usr/bin/env python3' shebang")

    # Check for hardcoded secrets (basic patterns)
    secret_patterns = [
        r'[A-Za-z0-9]{32,}',  # Long opaque strings (possible tokens)
    ]
    # Just warn if we see something that looks like a hardcoded long hex string
    if re.search(r'["\']([0-9a-f]{32,})["\']', content):
        warnings.append("Possible hardcoded secret detected — review SKILL.md for embedded tokens")

    # Print results
    skill_name = skill_path.name
    print(f"\n{BOLD}Validating:{RESET} {skill_path}/")
    print()

    if not errors and not warnings:
        print(f"{GREEN}✓ All checks passed — {skill_name} looks good!{RESET}")
        return

    if errors:
        print(f"{RED}Errors ({len(errors)}):{RESET}")
        for e in errors:
            print(f"  {RED}✗{RESET} {e}")

    if warnings:
        print(f"{YELLOW}Warnings ({len(warnings)}):{RESET}")
        for w in warnings:
            print(f"  {YELLOW}⚠{RESET}  {w}")

    if errors:
        sys.exit(1)
    else:
        print(f"\n{YELLOW}Passed with warnings.{RESET}")


# ─── Command: list ────────────────────────────────────────────────────────────

def cmd_list(args):
    filter_category = args.category

    if not SKILLS_DIR.exists():
        print(f"{RED}Error: DEXTER_SKILLS_DIR not found: {SKILLS_DIR}{RESET}", file=sys.stderr)
        sys.exit(1)

    categories = sorted([
        d for d in SKILLS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    ])

    if filter_category:
        categories = [c for c in categories if c.name == filter_category]
        if not categories:
            print(f"{YELLOW}No category '{filter_category}' found.{RESET}")
            sys.exit(0)

    total = 0
    for cat_dir in categories:
        skills = sorted([
            d for d in cat_dir.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        ])
        if not skills:
            continue

        print(f"\n{BOLD}{CYAN}{cat_dir.name}/{RESET}")

        for skill_dir in skills:
            skill_md = skill_dir / "SKILL.md"
            content  = skill_md.read_text()

            # Extract trigger line from description block
            triggers = _extract_triggers(content)
            has_script = (skill_dir / "scripts").exists()
            script_indicator = f" {YELLOW}[script]{RESET}" if has_script else ""

            print(f"  {GREEN}{skill_dir.name}{RESET}{script_indicator}")
            if triggers:
                print(f"    {YELLOW}triggers:{RESET} {triggers}")

            total += 1

    print(f"\n{BOLD}Total: {total} skill(s){RESET}")
    if filter_category is None:
        print(
            f"\n{CYAN}Tip:{RESET} Filter by category: "
            f"create.py list --category productivity"
        )


def _extract_triggers(content: str) -> str:
    """Extract trigger keywords from SKILL.md content."""
    for line in content.split("\n"):
        if "Trigger:" in line:
            # Strip leading spaces, "Trigger:", and quotes
            triggers = line.split("Trigger:", 1)[-1].strip()
            # Remove surrounding quotes if present
            return triggers.strip('"').strip("'")
    return ""


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Dexter — Skill creator CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  create.py new deploy-hetzner --category productivity --description "Deploy app to Hetzner VPS"
  create.py new my-workflow --interactive
  create.py validate skills/productivity/my-workflow/
  create.py list
  create.py list --category productivity
""",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # new
    p_new = sub.add_parser("new", help="Scaffold a new skill")
    p_new.add_argument("name", help="Skill name (kebab-case)")
    p_new.add_argument("--category", default="productivity", help="Skill category (default: productivity)")
    p_new.add_argument("--description", default="", help="Short description of what the skill does")
    p_new.add_argument("--interactive", "-i", action="store_true", help="Prompt for all fields interactively")

    # validate
    p_val = sub.add_parser("validate", help="Validate an existing skill directory")
    p_val.add_argument("skill_path", help="Path to the skill directory (contains SKILL.md)")

    # list
    p_list = sub.add_parser("list", help="List all installed skills")
    p_list.add_argument("--category", "-c", default="", help="Filter by category name")

    args = parser.parse_args()

    dispatch = {
        "new":      cmd_new,
        "validate": cmd_validate,
        "list":     cmd_list,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
