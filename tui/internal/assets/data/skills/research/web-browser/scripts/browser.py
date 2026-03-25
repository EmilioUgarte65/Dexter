#!/usr/bin/env python3
"""
Dexter — Web browser automation via Playwright.
Falls back to urllib for plain HTML when Playwright is unavailable.

Usage:
  browser.py fetch <url> [--output file.md]
  browser.py screenshot <url> [--output file.png]
  browser.py click <url> <selector>
  browser.py fill <url> <selector> <value>
  browser.py search <query> [--limit N]
"""

import sys
import os
import argparse
import urllib.request
import urllib.error
import urllib.parse
import html.parser
import re
from pathlib import Path
from typing import Optional

# ─── ANSI colors ──────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

# ─── Config ───────────────────────────────────────────────────────────────────

HEADLESS = os.environ.get("BROWSER_HEADLESS", "true").lower() != "false"
TIMEOUT  = int(os.environ.get("BROWSER_TIMEOUT", "30000"))

# ─── Playwright availability ──────────────────────────────────────────────────

def check_playwright() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def require_playwright():
    if not check_playwright():
        print(f"{RED}Playwright is not installed.{RESET}", file=sys.stderr)
        print(f"{YELLOW}Install with:{RESET}", file=sys.stderr)
        print("  pip install playwright && python -m playwright install chromium", file=sys.stderr)
        sys.exit(1)


# ─── HTML → Markdown converter (stdlib) ───────────────────────────────────────

class HTMLToMarkdown(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.result      = []
        self._skip_tags  = {"script", "style", "noscript", "head"}
        self._block_tags = {"p", "div", "article", "section", "main"}
        self._current_tag = []
        self._in_skip    = 0

    def handle_starttag(self, tag, attrs):
        self._current_tag.append(tag)
        if tag in self._skip_tags:
            self._in_skip += 1
            return
        if self._in_skip:
            return
        attrs_dict = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self.result.append(f"\n{'#' * level} ")
        elif tag == "a":
            href = attrs_dict.get("href", "")
            self.result.append(f"[")
            self._pending_href = href
        elif tag == "br":
            self.result.append("\n")
        elif tag in ("ul", "ol"):
            self.result.append("\n")
        elif tag == "li":
            self.result.append("\n- ")
        elif tag in self._block_tags:
            self.result.append("\n")
        elif tag == "strong" or tag == "b":
            self.result.append("**")
        elif tag == "em" or tag == "i":
            self.result.append("_")
        elif tag == "code":
            self.result.append("`")
        elif tag == "pre":
            self.result.append("\n```\n")

    def handle_endtag(self, tag):
        if self._current_tag and self._current_tag[-1] == tag:
            self._current_tag.pop()
        if tag in self._skip_tags:
            self._in_skip = max(0, self._in_skip - 1)
            return
        if self._in_skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.result.append("\n")
        elif tag == "a":
            href = getattr(self, "_pending_href", "")
            self.result.append(f"]({href})")
        elif tag in self._block_tags:
            self.result.append("\n")
        elif tag == "strong" or tag == "b":
            self.result.append("**")
        elif tag == "em" or tag == "i":
            self.result.append("_")
        elif tag == "code":
            self.result.append("`")
        elif tag == "pre":
            self.result.append("\n```\n")

    def handle_data(self, data):
        if self._in_skip:
            return
        self.result.append(data)

    def get_markdown(self) -> str:
        text = "".join(self.result)
        # Clean up excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def html_to_markdown(html_content: str) -> str:
    parser = HTMLToMarkdown()
    try:
        parser.feed(html_content)
        return parser.get_markdown()
    except Exception:
        # Fallback: strip all tags
        return re.sub(r"<[^>]+>", "", html_content).strip()


# ─── urllib fallback fetcher ──────────────────────────────────────────────────

def fetch_urllib(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Dexter/1.0)"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            encoding = resp.headers.get_content_charset("utf-8")
            return resp.read().decode(encoding, errors="replace")
    except urllib.error.HTTPError as e:
        print(f"{RED}HTTP error {e.code}: {url}{RESET}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"{RED}Cannot reach {url}: {e.reason}{RESET}", file=sys.stderr)
        sys.exit(1)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_fetch(url: str, output: Optional[str] = None):
    if check_playwright():
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            page    = browser.new_page()
            page.goto(url, timeout=TIMEOUT, wait_until="networkidle")
            content = page.content()
            browser.close()
        markdown = html_to_markdown(content)
    else:
        print(f"{YELLOW}Playwright not available — using urllib (no JS support){RESET}", file=sys.stderr)
        print(f"Install: pip install playwright && python -m playwright install chromium", file=sys.stderr)
        content  = fetch_urllib(url)
        markdown = html_to_markdown(content)

    if output:
        Path(output).write_text(markdown, encoding="utf-8")
        print(f"{GREEN}Saved to: {output}{RESET}")
        print(f"  Characters: {len(markdown):,}")
    else:
        print(markdown)


def cmd_screenshot(url: str, output: Optional[str] = None):
    require_playwright()

    out_path = output or "screenshot.png"
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page    = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url, timeout=TIMEOUT, wait_until="networkidle")
        page.screenshot(path=out_path, full_page=True)
        browser.close()

    print(f"{GREEN}Screenshot saved: {out_path}{RESET}")
    size = Path(out_path).stat().st_size
    print(f"  Size: {size / 1024:.1f} KB")


def cmd_click(url: str, selector: str):
    require_playwright()

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page    = browser.new_page()
        page.goto(url, timeout=TIMEOUT, wait_until="networkidle")

        try:
            page.click(selector, timeout=10000)
            page.wait_for_load_state("networkidle", timeout=TIMEOUT)
        except Exception as e:
            print(f"{RED}Click failed on selector '{selector}': {e}{RESET}", file=sys.stderr)
            browser.close()
            sys.exit(1)

        content  = page.content()
        browser.close()

    markdown = html_to_markdown(content)
    print(f"{GREEN}Clicked '{selector}' — page content:{RESET}\n")
    print(markdown[:3000])
    if len(markdown) > 3000:
        print(f"\n{YELLOW}... (truncated, {len(markdown):,} total chars){RESET}")


def cmd_fill(url: str, selector: str, value: str):
    require_playwright()

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page    = browser.new_page()
        page.goto(url, timeout=TIMEOUT, wait_until="networkidle")

        try:
            page.fill(selector, value, timeout=10000)
            print(f"{GREEN}Filled '{selector}' with: {value}{RESET}")
            content = page.content()
        except Exception as e:
            print(f"{RED}Fill failed on selector '{selector}': {e}{RESET}", file=sys.stderr)
            browser.close()
            sys.exit(1)

        browser.close()

    markdown = html_to_markdown(content)
    print(f"\nPage content after fill:\n")
    print(markdown[:2000])


def cmd_search(query: str, limit: int = 5):
    encoded  = urllib.parse.quote_plus(query)
    ddg_url  = f"https://html.duckduckgo.com/html/?q={encoded}"

    if check_playwright():
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            page    = browser.new_page()
            page.goto(ddg_url, timeout=TIMEOUT, wait_until="networkidle")
            content = page.content()
            browser.close()
    else:
        print(f"{YELLOW}Using urllib fallback (no JS){RESET}")
        content = fetch_urllib(ddg_url)

    # Parse DuckDuckGo results
    results = []
    # DDG HTML uses class="result__title" and "result__snippet"
    title_re   = re.compile(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL)
    snippet_re = re.compile(r'class="result__snippet"[^>]*>(.*?)</span>', re.DOTALL)

    titles   = title_re.findall(content)
    snippets = [re.sub(r"<[^>]+>", "", s).strip() for s in snippet_re.findall(content)]

    print(f"\n{BLUE}DuckDuckGo results for: {query}{RESET}\n")
    for i, (href, title) in enumerate(titles[:limit]):
        title_clean = re.sub(r"<[^>]+>", "", title).strip()
        snippet     = snippets[i] if i < len(snippets) else ""
        print(f"  {i+1}. {title_clean}")
        print(f"     {BLUE}{href}{RESET}")
        if snippet:
            print(f"     {snippet[:120]}")
        print()

    if not titles:
        print(f"{YELLOW}No results parsed. DuckDuckGo may have changed its HTML structure.{RESET}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter Web Browser CLI")
    sub    = parser.add_subparsers(dest="command", required=True)

    # fetch
    p_fetch = sub.add_parser("fetch", help="Fetch URL and extract as markdown")
    p_fetch.add_argument("url")
    p_fetch.add_argument("--output", help="Save to file instead of stdout")

    # screenshot
    p_ss = sub.add_parser("screenshot", help="Take a screenshot of a URL")
    p_ss.add_argument("url")
    p_ss.add_argument("--output", default="screenshot.png")

    # click
    p_click = sub.add_parser("click", help="Click an element then extract content")
    p_click.add_argument("url")
    p_click.add_argument("selector", help="CSS selector (e.g. 'button#load-more')")

    # fill
    p_fill = sub.add_parser("fill", help="Fill a form field")
    p_fill.add_argument("url")
    p_fill.add_argument("selector", help="CSS selector (e.g. 'input[name=q]')")
    p_fill.add_argument("value")

    # search
    p_search = sub.add_parser("search", help="DuckDuckGo search")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=5, help="Max results (default: 5)")

    args = parser.parse_args()

    if args.command == "fetch":
        cmd_fetch(args.url, args.output)
    elif args.command == "screenshot":
        cmd_screenshot(args.url, args.output)
    elif args.command == "click":
        cmd_click(args.url, args.selector)
    elif args.command == "fill":
        cmd_fill(args.url, args.selector, args.value)
    elif args.command == "search":
        cmd_search(args.query, args.limit)


if __name__ == "__main__":
    main()
