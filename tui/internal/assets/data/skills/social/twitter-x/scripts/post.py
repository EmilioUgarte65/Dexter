#!/usr/bin/env python3
"""
Dexter — X (Twitter) API v2 client.
Uses tweepy if available, falls back to urllib + OAuth 1.0a.

Usage:
  post.py post <text>
  post.py thread <text1> [text2 ...]
  post.py search <query> [--limit N]
  post.py timeline [--limit N]
  post.py likes --tweet-id ID
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
import hmac
import hashlib
import base64
import time
import uuid
from typing import Optional

# ─── ANSI colors ──────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

# ─── Cost warning ─────────────────────────────────────────────────────────────

COST_WARNING = f"""{YELLOW}
⚠  X API v2 — Cost Warning:
   Free tier : post-only, 1,500 tweets/month
   Basic tier: ~$100/month (required for search/timeline/likes)
   Pro tier  : ~$5,000/month
{RESET}"""

# ─── Config ───────────────────────────────────────────────────────────────────

API_KEY             = os.environ.get("TWITTER_API_KEY", "")
API_SECRET          = os.environ.get("TWITTER_API_SECRET", "")
ACCESS_TOKEN        = os.environ.get("TWITTER_ACCESS_TOKEN", "")
ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")

BASE_URL = "https://api.twitter.com/2"


def check_config():
    missing = []
    if not API_KEY:             missing.append("TWITTER_API_KEY")
    if not API_SECRET:          missing.append("TWITTER_API_SECRET")
    if not ACCESS_TOKEN:        missing.append("TWITTER_ACCESS_TOKEN")
    if not ACCESS_TOKEN_SECRET: missing.append("TWITTER_ACCESS_TOKEN_SECRET")
    if missing:
        print(f"{RED}Error: Missing env vars: {', '.join(missing)}{RESET}", file=sys.stderr)
        print("Get credentials at: https://developer.twitter.com/en/portal/dashboard", file=sys.stderr)
        sys.exit(1)


# ─── OAuth 1.0a (stdlib fallback) ─────────────────────────────────────────────

def _oauth_header(method: str, url: str, params: dict = None) -> str:
    """Build OAuth 1.0a Authorization header."""
    oauth_params = {
        "oauth_consumer_key":     API_KEY,
        "oauth_nonce":            uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp":        str(int(time.time())),
        "oauth_token":            ACCESS_TOKEN,
        "oauth_version":          "1.0",
    }

    # Merge params for signature base string
    all_params = dict(oauth_params)
    if params:
        all_params.update(params)

    sorted_params = sorted(all_params.items())
    param_string  = "&".join(f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
                             for k, v in sorted_params)

    base_string = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(param_string, safe=""),
    ])

    signing_key = f"{urllib.parse.quote(API_SECRET, safe='')}&{urllib.parse.quote(ACCESS_TOKEN_SECRET, safe='')}"
    signature   = base64.b64encode(
        hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    ).decode()

    oauth_params["oauth_signature"] = signature
    header_parts = [f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
                    for k, v in sorted(oauth_params.items())]
    return "OAuth " + ", ".join(header_parts)


def _request(method: str, endpoint: str, payload: dict = None, params: dict = None) -> dict:
    """Make an authenticated X API v2 request via urllib."""
    url = f"{BASE_URL}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    body = json.dumps(payload).encode() if payload else None
    headers = {
        "Authorization":  _oauth_header(method, f"{BASE_URL}{endpoint}", params),
        "Content-Type":   "application/json",
        "Accept":         "application/json",
    }

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
        except Exception:
            err = {"detail": body}
        title  = err.get("title", "API Error")
        detail = err.get("detail", body)
        print(f"{RED}X API error {e.code} — {title}: {detail}{RESET}", file=sys.stderr)
        if e.code == 403:
            print(f"{YELLOW}Hint: This endpoint may require a paid tier (Basic ~$100/mo){RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Network error: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Tweepy wrapper ───────────────────────────────────────────────────────────

def _get_tweepy_client():
    try:
        import tweepy
        return tweepy.Client(
            consumer_key=API_KEY,
            consumer_secret=API_SECRET,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_TOKEN_SECRET,
        )
    except ImportError:
        return None


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_post(text: str):
    if len(text) > 280:
        print(f"{RED}Error: Tweet exceeds 280 characters ({len(text)} chars){RESET}", file=sys.stderr)
        sys.exit(1)

    client = _get_tweepy_client()
    if client:
        try:
            resp = client.create_tweet(text=text)
            tweet_id = resp.data["id"]
        except Exception as e:
            print(f"{RED}tweepy error: {e}{RESET}", file=sys.stderr)
            sys.exit(1)
    else:
        resp = _request("POST", "/tweets", payload={"text": text})
        tweet_id = resp["data"]["id"]

    print(f"{GREEN}Tweet posted!{RESET}")
    print(f"  ID : {tweet_id}")
    print(f"  URL: https://x.com/i/web/status/{tweet_id}")


def cmd_thread(texts: list[str]):
    if not texts:
        print(f"{RED}Error: Provide at least one tweet text{RESET}", file=sys.stderr)
        sys.exit(1)

    for i, text in enumerate(texts):
        if len(text) > 280:
            print(f"{RED}Error: Tweet {i+1} exceeds 280 chars ({len(text)}){RESET}", file=sys.stderr)
            sys.exit(1)

    client  = _get_tweepy_client()
    prev_id = None
    ids     = []

    print(f"{BLUE}Posting thread ({len(texts)} tweets)...{RESET}")
    for i, text in enumerate(texts):
        if client:
            try:
                kwargs = {"text": text}
                if prev_id:
                    kwargs["in_reply_to_tweet_id"] = prev_id
                resp    = client.create_tweet(**kwargs)
                tweet_id = resp.data["id"]
            except Exception as e:
                print(f"{RED}tweepy error on tweet {i+1}: {e}{RESET}", file=sys.stderr)
                sys.exit(1)
        else:
            payload = {"text": text}
            if prev_id:
                payload["reply"] = {"in_reply_to_tweet_id": prev_id}
            resp     = _request("POST", "/tweets", payload=payload)
            tweet_id = resp["data"]["id"]

        ids.append(tweet_id)
        prev_id = tweet_id
        print(f"  {GREEN}[{i+1}/{len(texts)}]{RESET} Posted: https://x.com/i/web/status/{tweet_id}")

    print(f"\n{GREEN}Thread complete! First tweet: https://x.com/i/web/status/{ids[0]}{RESET}")


def cmd_search(query: str, limit: int = 10):
    client = _get_tweepy_client()
    if client:
        try:
            resp  = client.search_recent_tweets(query=query, max_results=min(limit, 100))
            tweets = resp.data or []
        except Exception as e:
            print(f"{RED}tweepy error: {e}{RESET}", file=sys.stderr)
            sys.exit(1)
        print(f"\n{BLUE}Search results for: {query}{RESET}\n")
        for t in tweets:
            print(f"  [{t.id}] {t.text[:100]}{'...' if len(t.text) > 100 else ''}")
    else:
        params = {"query": query, "max_results": min(limit, 100)}
        resp   = _request("GET", "/tweets/search/recent", params=params)
        tweets = resp.get("data", [])
        print(f"\n{BLUE}Search results for: {query}{RESET}\n")
        for t in tweets:
            text = t["text"]
            print(f"  [{t['id']}] {text[:100]}{'...' if len(text) > 100 else ''}")

    print(f"\n  {len(tweets)} results returned.")


def cmd_timeline(limit: int = 20):
    client = _get_tweepy_client()
    if client:
        try:
            me   = client.get_me()
            uid  = me.data.id
            resp = client.get_home_timeline(max_results=min(limit, 100))
            tweets = resp.data or []
        except Exception as e:
            print(f"{RED}tweepy error: {e}{RESET}", file=sys.stderr)
            sys.exit(1)
    else:
        me_resp = _request("GET", "/users/me")
        uid     = me_resp["data"]["id"]
        params  = {"max_results": min(limit, 100)}
        resp    = _request("GET", f"/users/{uid}/timelines/reverse_chronological", params=params)
        tweets  = resp.get("data", [])

    print(f"\n{BLUE}Timeline (last {len(tweets)} tweets):{RESET}\n")
    for t in tweets:
        text = getattr(t, "text", t.get("text", "")) if not hasattr(t, "text") else t.text
        tid  = getattr(t, "id", t.get("id", ""))
        print(f"  [{tid}] {str(text)[:100]}")


def cmd_likes(tweet_id: str):
    client = _get_tweepy_client()
    if client:
        try:
            resp  = client.get_liking_users(tweet_id)
            users = resp.data or []
        except Exception as e:
            print(f"{RED}tweepy error: {e}{RESET}", file=sys.stderr)
            sys.exit(1)
        print(f"\n{BLUE}Users who liked tweet {tweet_id}:{RESET}\n")
        for u in users:
            print(f"  @{u.username} ({u.name})")
    else:
        resp  = _request("GET", f"/tweets/{tweet_id}/liking_users")
        users = resp.get("data", [])
        print(f"\n{BLUE}Users who liked tweet {tweet_id}:{RESET}\n")
        for u in users:
            print(f"  @{u.get('username', '?')} ({u.get('name', '?')})")

    print(f"\n  {len(users)} users found.")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    print(COST_WARNING)
    check_config()

    parser = argparse.ArgumentParser(description="Dexter X (Twitter) CLI")
    sub    = parser.add_subparsers(dest="command", required=True)

    # post
    p_post = sub.add_parser("post", help="Post a single tweet")
    p_post.add_argument("text", help="Tweet text (max 280 chars)")

    # thread
    p_thread = sub.add_parser("thread", help="Post a thread of tweets")
    p_thread.add_argument("texts", nargs="+", help="One or more tweet texts")

    # search
    p_search = sub.add_parser("search", help="Search recent tweets (Basic tier required)")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")

    # timeline
    p_tl = sub.add_parser("timeline", help="Show home timeline (Basic tier required)")
    p_tl.add_argument("--limit", type=int, default=20, help="Max tweets (default: 20)")

    # likes
    p_likes = sub.add_parser("likes", help="Get users who liked a tweet (Basic tier required)")
    p_likes.add_argument("--tweet-id", required=True, help="Tweet ID")

    args = parser.parse_args()

    if args.command == "post":
        cmd_post(args.text)
    elif args.command == "thread":
        cmd_thread(args.texts)
    elif args.command == "search":
        cmd_search(args.query, args.limit)
    elif args.command == "timeline":
        cmd_timeline(args.limit)
    elif args.command == "likes":
        cmd_likes(args.tweet_id)


if __name__ == "__main__":
    main()
