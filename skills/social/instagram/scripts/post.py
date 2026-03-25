#!/usr/bin/env python3
"""
Dexter — Instagram posting via instagrapi (unofficial API).
Requires: pip install instagrapi

CRITICAL: Instagram bans accounts that use unofficial APIs.
Use a secondary account. This may stop working at any time.

Usage:
  post.py post-photo <image_path> [--caption TEXT]
  post.py stories <image_path>
  post.py profile
"""

import sys
import os
import argparse
import json
from pathlib import Path

# ─── ANSI colors ──────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

# ─── WARNING banner ───────────────────────────────────────────────────────────

BAN_WARNING = f"""{RED}
╔══════════════════════════════════════════════════════════════╗
║  CRITICAL WARNING: Instagram Unofficial API                  ║
║                                                              ║
║  • Instagram BANS accounts using unofficial automation       ║
║  • Use a SECONDARY/TEST account only — NEVER your main       ║
║  • This may stop working at any time without notice          ║
║  • You accept full responsibility for your account           ║
╚══════════════════════════════════════════════════════════════╝
{RESET}"""

# ─── Config ───────────────────────────────────────────────────────────────────

IG_USERNAME = os.environ.get("INSTAGRAM_USERNAME", "")
IG_PASSWORD = os.environ.get("INSTAGRAM_PASSWORD", "")
SESSION_DIR = Path(os.environ.get("XDG_DATA_HOME",
                   os.path.expanduser("~/.local/share"))) / "dexter" / "instagram"


def check_config():
    missing = []
    if not IG_USERNAME: missing.append("INSTAGRAM_USERNAME")
    if not IG_PASSWORD: missing.append("INSTAGRAM_PASSWORD")
    if missing:
        print(f"{RED}Error: Missing env vars: {', '.join(missing)}{RESET}", file=sys.stderr)
        sys.exit(1)


def check_instagrapi():
    try:
        import instagrapi  # noqa: F401
    except ImportError:
        print(f"{RED}Error: instagrapi not installed.{RESET}", file=sys.stderr)
        print("Install with: pip install instagrapi", file=sys.stderr)
        sys.exit(1)


# ─── Client setup ─────────────────────────────────────────────────────────────

def get_client():
    from instagrapi import Client

    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    session_file = SESSION_DIR / f"{IG_USERNAME}.json"

    cl = Client()
    cl.delay_range = [2, 5]  # Mimic human behavior

    if session_file.exists():
        try:
            cl.load_settings(session_file)
            cl.login(IG_USERNAME, IG_PASSWORD)
            print(f"{GREEN}Logged in (session restored){RESET}")
            return cl
        except Exception:
            print(f"{YELLOW}Session expired, re-logging in...{RESET}")

    try:
        cl.login(IG_USERNAME, IG_PASSWORD)
        cl.dump_settings(session_file)
        print(f"{GREEN}Logged in successfully{RESET}")
    except Exception as e:
        print(f"{RED}Login failed: {e}{RESET}", file=sys.stderr)
        print("Instagram may require 2FA or challenge verification.", file=sys.stderr)
        sys.exit(1)

    return cl


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_post_photo(image_path: str, caption: str = ""):
    path = Path(image_path)
    if not path.exists():
        print(f"{RED}Error: Image not found: {image_path}{RESET}", file=sys.stderr)
        sys.exit(1)

    supported = {".jpg", ".jpeg", ".png", ".webp"}
    if path.suffix.lower() not in supported:
        print(f"{RED}Error: Unsupported format '{path.suffix}'. Use: {', '.join(supported)}{RESET}", file=sys.stderr)
        sys.exit(1)

    cl = get_client()
    print(f"{BLUE}Uploading photo: {path.name}{RESET}")

    try:
        media = cl.photo_upload(path, caption=caption)
        print(f"{GREEN}Photo posted!{RESET}")
        print(f"  Media ID: {media.id}")
        print(f"  URL     : https://www.instagram.com/p/{media.code}/")
    except Exception as e:
        print(f"{RED}Upload failed: {e}{RESET}", file=sys.stderr)
        sys.exit(1)


def cmd_stories(image_path: str):
    path = Path(image_path)
    if not path.exists():
        print(f"{RED}Error: Image not found: {image_path}{RESET}", file=sys.stderr)
        sys.exit(1)

    cl = get_client()
    print(f"{BLUE}Uploading story: {path.name}{RESET}")

    try:
        media = cl.photo_upload_to_story(path)
        print(f"{GREEN}Story posted!{RESET}")
        print(f"  Media ID: {media.id}")
    except Exception as e:
        print(f"{RED}Story upload failed: {e}{RESET}", file=sys.stderr)
        sys.exit(1)


def cmd_profile():
    cl = get_client()
    print(f"\n{BLUE}Fetching profile info...{RESET}\n")

    try:
        user = cl.user_info_by_username(IG_USERNAME)
        print(f"  Username   : @{user.username}")
        print(f"  Full name  : {user.full_name}")
        print(f"  Bio        : {user.biography[:80] + '...' if len(user.biography or '') > 80 else user.biography}")
        print(f"  Followers  : {user.follower_count:,}")
        print(f"  Following  : {user.following_count:,}")
        print(f"  Posts      : {user.media_count:,}")
        print(f"  Verified   : {'Yes' if user.is_verified else 'No'}")
        print(f"  Private    : {'Yes' if user.is_private else 'No'}")
        print(f"  URL        : https://www.instagram.com/{user.username}/")
    except Exception as e:
        print(f"{RED}Failed to fetch profile: {e}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    print(BAN_WARNING)
    check_instagrapi()
    parser = argparse.ArgumentParser(description="Dexter Instagram CLI")
    sub    = parser.add_subparsers(dest="command", required=True)

    # post-photo
    p_photo = sub.add_parser("post-photo", help="Post a photo to feed")
    p_photo.add_argument("image_path", help="Path to image file")
    p_photo.add_argument("--caption", default="", help="Caption text")

    # stories
    p_story = sub.add_parser("stories", help="Post a photo as a story")
    p_story.add_argument("image_path", help="Path to image file")

    # profile
    sub.add_parser("profile", help="Show own profile info")

    args = parser.parse_args()
    check_config()

    if args.command == "post-photo":
        cmd_post_photo(args.image_path, args.caption)
    elif args.command == "stories":
        cmd_stories(args.image_path)
    elif args.command == "profile":
        cmd_profile()


if __name__ == "__main__":
    main()
