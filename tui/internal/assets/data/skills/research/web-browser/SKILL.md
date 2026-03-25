---
name: web-browser
description: >
  Fetch web pages, take screenshots, fill forms, and search DuckDuckGo via Playwright.
  Falls back to urllib for static HTML pages. Full browser automation for JS-heavy sites.
  Trigger: "navegar", "web browser", "screenshot", "scrape", "fetch url", "buscar web".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Web Browser

Full browser automation via Playwright. Falls back to urllib for static pages when Playwright is unavailable.

## Setup

```bash
# Install playwright
pip install playwright
python -m playwright install chromium

# Optional env vars
export BROWSER_HEADLESS=true      # default: true
export BROWSER_TIMEOUT=30000      # default: 30000ms
```

If Playwright is not installed, the tool will show the install command and fall back to urllib for plain HTML.

## Usage

```bash
# Fetch a URL and extract text/markdown
python3 skills/research/web-browser/scripts/browser.py fetch https://example.com
python3 skills/research/web-browser/scripts/browser.py fetch https://example.com --output page.md

# Take a screenshot
python3 skills/research/web-browser/scripts/browser.py screenshot https://example.com
python3 skills/research/web-browser/scripts/browser.py screenshot https://example.com --output capture.png

# Click an element then extract content
python3 skills/research/web-browser/scripts/browser.py click https://example.com "button#load-more"

# Fill a form field
python3 skills/research/web-browser/scripts/browser.py fill https://example.com "input[name=search]" "my query"

# Search DuckDuckGo and get top results
python3 skills/research/web-browser/scripts/browser.py search "python async patterns"
python3 skills/research/web-browser/scripts/browser.py search "climate change 2024" --limit 5
```

## Notes

- `BROWSER_HEADLESS=false` to see the browser window (useful for debugging)
- `BROWSER_TIMEOUT` in milliseconds (default 30s)
- Screenshots saved as PNG
- Fetched content is converted to clean markdown (headers, links, paragraphs)
- DuckDuckGo search returns titles, URLs, and snippets
