"""
scraper_araba.py — Araba.com ilan scraper
https://www.araba.com/satilik-araba?page=N
~11 sayfa, ~129 ilan, SSL verify=False
"""
from __future__ import annotations
import logging, re, time, warnings
from typing import Any
import requests
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore", message="Unverified HTTPS request")
logger = logging.getLogger(__name__)
BASE_URL = "https://www.araba.com/satilik-araba"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "Accept-Language": "tr-TR,tr;q=0.9"}

AUTO_KW = ["otomatik", "dsg", "edc", "eat", "cvt", "x-tronic", "steptronic", "auto"]
DIESEL_KW = ["dci", "tdi", "crdi", "tdci", "multijet", "hdi", "cdti", "d-4d", "ecoblue", "dizel"]
ELECTRIC_KW = ["elektrik", "electric", "bev"]
HYBRID_KW = ["hibrit", "hybrid", "phev"]

def _fuel(t: str) -> str:
    t = t.lower()
    if any(k in t for k in ELECTRIC_KW): return "Elektrik"
    if any(k in t for k in HYBRID_KW): return "Hibrit"
    if any(k in t for k in DIESEL_KW): return "Dizel"
    return "Benzin"

def _trans(t: str) -> str:
    return "Otomatik" if any(k in t.lower() for k in AUTO_KW) else "Manuel"

def _int(t: str) -> int | None:
    try: return int(re.sub(r"[^\d]", "", t))
    except: return None

_DETAIL_RE = re.compile(
    r'^(19[9]\d|20[012]\d)\s*\|\s*(\w+)\s*\|\s*([\w/üşöçğı ]+?)\s*\|\s*([\d.,]+)\s*Km$',
    re.I | re.UNICODE,
)
_PRICE_RE = re.compile(r'^([\d.,]+)\s*TL$')


def _parse_lines(lines: list[str], results: list[dict]) -> None:
    i = 0
    while i < len(lines) - 1:
        detail_m = _DETAIL_RE.match(lines[i])
        if detail_m:
            year = int(detail_m.group(1))
            transmission_raw = detail_m.group(2)
            fuel_raw = detail_m.group(3)
            km = _int(detail_m.group(4).replace(".", "").replace(",", ""))

            price_m = None
            for offset in [1, 2]:
                if i + offset < len(lines):
                    price_m = _PRICE_RE.match(lines[i + offset])
                    if price_m:
                        break

            price = _int(price_m.group(1).replace(".", "").replace(",", "")) if price_m else None
            title = lines[i - 1] if i > 0 else ""

            if year and km and price and price > 50_000 and title:
                parts = title.split()
                brand = parts[0] if parts else "Bilinmiyor"
                results.append({
                    "brand": brand,
                    "model": " ".join(parts[:4]),
                    "year": year,
                    "km": km,
                    "fuel_type": _fuel(fuel_raw),
                    "transmission": _trans(transmission_raw),
                    "listed_price": price,
                    "city": None,
                    "body_type": None,
                    "has_damage": 0,
                })
            i += 2
        else:
            i += 1


def _scrape_page(page: int) -> list[dict[str, Any]]:
    try:
        r = requests.get(BASE_URL, params={"page": page}, headers=HEADERS, timeout=15, verify=False)
        r.raise_for_status()
    except Exception as e:
        logger.warning(f"[araba] page {page}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    cards = soup.select("div.listing-card, article.car-card, div.car-listing-item, div[class*='card']")
    if cards:
        for card in cards:
            try:
                lines = [l.strip() for l in card.get_text(separator="\n", strip=True).split("\n") if l.strip()]
                _parse_lines(lines, results)
            except Exception as e:
                logger.debug(f"[araba] card parse: {e}")
    else:
        lines = [l.strip() for l in soup.get_text(separator="\n", strip=True).split("\n") if l.strip()]
        _parse_lines(lines, results)

    return results


def scrape_araba_listings(max_pages: int = 15) -> list[dict[str, Any]]:
    all_results, seen = [], set()
    for page in range(1, max_pages + 1):
        logger.info(f"[araba] page {page} …")
        rows = _scrape_page(page)
        if not rows:
            logger.info(f"[araba] empty at page {page}, stopping")
            break
        added = 0
        for r in rows:
            k = (r["brand"], r["model"], r["year"], r["km"], r["listed_price"])
            if k not in seen:
                seen.add(k); all_results.append(r); added += 1
        logger.info(f"[araba] page {page}: +{added} (total {len(all_results)})")
        time.sleep(0.4)
    logger.info(f"[araba] Total: {len(all_results)}")
    return all_results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = scrape_araba_listings(max_pages=3)
    print(f"Scraped {len(data)}")
    for d in data[:3]: print(d)
