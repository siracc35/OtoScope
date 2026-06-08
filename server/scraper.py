"""
scraper.py — Phase 3: fetch a sahibinden.com listing and extract its text.

IMPORTANT / RESPONSIBLE USE:
sahibinden.com actively blocks automated traffic (bot protection / WAF). A bare
requests call will very often get a 403 or a CAPTCHA wall instead of the page.
We do NOT try to defeat that protection (rotating proxies, headless evasion,
etc.) — that is against their terms and not something we build here. Instead we:
  - send a normal browser-like User-Agent and a short timeout,
  - if we are blocked, return a clear, honest error so the UI can tell the user
    to fall back to copy-pasting the listing text (our primary flow anyway).

So scraping is a convenience, not the backbone. The paste flow always works.
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}


class ScrapeError(Exception):
    """Raised when we cannot retrieve usable listing text."""


def scrape_listing(url: str) -> str:
    """Fetch a listing URL and return cleaned, human-readable text.

    Raises ScrapeError on network failures, bot-blocks, or empty content.
    """
    if "sahibinden.com" not in url:
        raise ScrapeError("Only sahibinden.com listing URLs are supported.")

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=12)
    except requests.RequestException as exc:
        raise ScrapeError(f"Network error while fetching the page: {exc}") from exc

    if resp.status_code in (403, 429) or "captcha" in resp.text.lower():
        raise ScrapeError(
            "sahibinden.com blocked the automated request (bot protection). "
            "Please copy the listing text and paste it instead."
        )
    if resp.status_code != 200:
        raise ScrapeError(f"Unexpected response status: {resp.status_code}")

    soup = BeautifulSoup(resp.text, "lxml")

    # Strip noise that would pollute the text we send to Gemini.
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()

    # Prefer the main classified container if present; otherwise fall back to body.
    main = soup.select_one("#classifiedDetail") or soup.body or soup
    text = main.get_text(separator="\n", strip=True)

    # Collapse blank lines.
    lines = [ln for ln in (l.strip() for l in text.splitlines()) if ln]
    cleaned = "\n".join(lines)

    if len(cleaned) < 200:
        raise ScrapeError(
            "Could not extract meaningful listing text (page may be JS-rendered "
            "or blocked). Please paste the listing text instead."
        )

    return cleaned
