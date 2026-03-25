---
name: instagram
description: >
  Post photos, stories, and view profile info via instagrapi (unofficial Instagram API).
  WARNING: Uses unofficial API — account ban risk. Use a secondary account only.
  Trigger: "instagram", "ig", "foto instagram", "story instagram".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Instagram

Posts photos and stories via `instagrapi` (unofficial Instagram private API).

## CRITICAL WARNING

> **Instagram WILL ban accounts that use unofficial APIs.**
>
> - Use a **secondary/test account only** — NEVER your main account
> - This may stop working at any time without notice
> - Instagram actively detects and blocks automation
> - This tool is provided for educational and testing purposes

If you need reliable Instagram posting for business, use the official [Instagram Graph API](https://developers.facebook.com/docs/instagram-api) (requires Facebook Business account).

## Setup

```bash
pip install instagrapi

export INSTAGRAM_USERNAME="your_test_account"
export INSTAGRAM_PASSWORD="your_password"
```

## Usage

```bash
# Post a photo with caption
python3 skills/social/instagram/scripts/post.py post-photo /path/to/image.jpg --caption "Hello from Dexter!"

# Post a story
python3 skills/social/instagram/scripts/post.py stories /path/to/image.jpg

# View your own profile info
python3 skills/social/instagram/scripts/post.py profile
```

## Supported Image Formats

- JPEG/JPG (recommended)
- PNG (auto-converted)
- Square or 4:5 ratio recommended for feed posts

## Notes

- Session is cached after first login to reduce ban risk
- `instagrapi` must be installed: `pip install instagrapi`
- If login fails, Instagram may require 2FA or challenge verification
- Do NOT run this tool too frequently — it mimics human behavior but isn't perfect
