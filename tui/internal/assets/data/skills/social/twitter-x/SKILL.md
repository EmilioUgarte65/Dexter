---
name: twitter-x
description: >
  Post tweets, create threads, search tweets, and read your timeline via X API v2.
  Uses tweepy if installed, falls back to direct urllib calls. Cost warning shown on startup.
  Trigger: "twitter", "tweet", "X", "hilo twitter", "post twitter".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Twitter / X

Post and read tweets via the X API v2. Uses `tweepy` when available, falls back to pure stdlib urllib.

## IMPORTANT: Cost Warning

X API v2 pricing:
- **Free tier**: Post-only, 1,500 tweets/month. No read access.
- **Basic tier**: ~$100/month. Read access included.
- **Pro tier**: ~$5,000/month.

Reading timeline, search, and likes require **Basic tier or higher**.

## Setup

```bash
export TWITTER_API_KEY="your_api_key"
export TWITTER_API_SECRET="your_api_secret"
export TWITTER_ACCESS_TOKEN="your_access_token"
export TWITTER_ACCESS_TOKEN_SECRET="your_access_token_secret"
```

Get credentials at: https://developer.twitter.com/en/portal/dashboard

## Install tweepy (optional but recommended)

```bash
pip install tweepy
```

## Usage

```bash
# Post a tweet
python3 skills/social/twitter-x/scripts/post.py post "Hello from Dexter!"

# Post a thread (multiple connected tweets)
python3 skills/social/twitter-x/scripts/post.py thread "First tweet" "Second tweet" "Third tweet"

# Search tweets (requires Basic tier)
python3 skills/social/twitter-x/scripts/post.py search "python ai" --limit 10

# Read your timeline (requires Basic tier)
python3 skills/social/twitter-x/scripts/post.py timeline --limit 20

# Get likes on a tweet (requires Basic tier)
python3 skills/social/twitter-x/scripts/post.py likes --tweet-id 1234567890
```

## Notes

- Free tier only allows posting. Searching/reading requires paid access.
- Rate limits: Free = 17 posts/day, Basic = 100 posts/day.
- `tweepy` provides cleaner error messages; urllib fallback is functional but minimal.
