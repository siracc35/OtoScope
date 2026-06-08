"""
scraper.py — fetch a sahibinden.com listing and extract its text.

sahibinden.com blocks all automated HTTP requests and headless browsers via a
JS challenge page (/cs/tloading). Scraping is therefore best-effort only.

The primary user flow is copy-paste; this endpoint is a convenience shortcut.
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
        raise ScrapeError(f"Network error: {exc}") from exc

    if resp.status_code in (403, 429) or "tloading" in resp.url:
        raise ScrapeError(
            "sahibinden.com blocked the request (bot protection). "
            "Please copy the listing text and paste it instead."
        )
    if resp.status_code != 200:
        raise ScrapeError(f"Unexpected status: {resp.status_code}")

    soup = BeautifulSoup(resp.text, "lxml")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()

    main = soup.select_one("#classifiedDetail") or soup.body or soup
    text = main.get_text(separator="\n", strip=True)
    lines = [ln for ln in (l.strip() for l in text.splitlines()) if ln]
    cleaned = "\n".join(lines)

    if len(cleaned) < 200:
        raise ScrapeError(
            "Could not extract meaningful listing text. "
            "Please paste the listing text instead."
        )
    return cleaned
