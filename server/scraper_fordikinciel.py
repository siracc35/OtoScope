"""
scraper_fordikinciel.py — Ford İkinci El ilan scraper
https://www.fordikinciel.com/araba-fiyatlari?p=N
~1.400 ilan, 71 sayfa, ~20 ilan/sayfa
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.fordikinciel.com/araba-fiyatlari"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}

AUTO_KEYWORDS = ["otomatik", "dsg", "edc", "eat", "cvt", "tiptronic", "steptronic", "x-tronic"]
DIESEL_KEYWORDS = ["ecoblue", "tdci", "tdi", "dci", "crdi", "dizel", "hdi", "cdti", "d-4d", "multijet"]
ELECTRIC_KEYWORDS = ["elektrik", "electric", "ev", "bev"]
HYBRID_KEYWORDS = ["hibrit", "hybrid", "phev", "mhev"]


def _infer_fuel(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ELECTRIC_KEYWORDS):
        return "Elektrik"
    if any(k in lower for k in HYBRID_KEYWORDS):
        return "Hibrit"
    if any(k in lower for k in DIESEL_KEYWORDS):
        return "Dizel"
    return "Benzin"


def _infer_transmission(text: str) -> str:
    return "Otomatik" if any(k in text.lower() for k in AUTO_KEYWORDS) else "Manuel"


def _clean_int(text: str) -> int | None:
    try:
        cleaned = text.strip().replace(".", "").replace(",", "").replace("\xa0", "").replace(" ", "")
        cleaned = "".join(c for c in cleaned if c.isdigit())
        return int(cleaned) if cleaned else None
    except (ValueError, AttributeError):
        return None


def _scrape_page(page: int) -> list[dict[str, Any]]:
    url = f"{BASE_URL}?p={page}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"[fordikinciel] page {page} failed: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    results = []

    # Kart container'larını bul
    cards = soup.select("div.listing-item, article.listing-item, div.car-card, div[class*='listing'], div[class*='card']")

    # Fallback: her linkin içindeki fiyat + başlık kombinasyonu
    if not cards:
        cards = soup.select("a[href*='/detay/'], a[href*='/ilan/']")

    for card in cards:
        try:
            # Başlık / marka+model
            title_el = card.select_one("h3, h4, h2, .title, .car-title, .name")
            if not title_el:
                title_el = card
            title = title_el.get_text(separator=" ", strip=True)
            if not title or len(title) < 4:
                continue

            parts = title.split()
            brand = parts[0] if parts else "Ford"
            model = " ".join(parts[:4]) if len(parts) >= 2 else title

            # Fiyat
            price_el = card.select_one(".price, .fiyat, [class*='price'], [class*='fiyat'], span[class*='tl']")
            if not price_el:
                # TL içeren herhangi bir text
                price_el = card.find(string=lambda t: t and ("TL" in t or "₺" in t))
            price_text = price_el.get_text(strip=True) if hasattr(price_el, "get_text") else str(price_el)
            price = _clean_int(price_text.replace("TL", "").replace("₺", ""))
            if not price or price < 50_000:
                continue

            # Yıl, km, yakıt, şanzıman — li veya span listeleri
            specs_text = card.get_text(separator=" ", strip=True)
            specs_els = card.select("li, span.spec, td, div.spec-item")

            year = None
            km = None
            for el in specs_els:
                txt = el.get_text(strip=True).replace(".", "").replace(",", "")
                if txt.isdigit():
                    num = int(txt)
                    if 1990 <= num <= 2026 and year is None:
                        year = num
                    elif num > 1000 and km is None:
                        km = num

            # Yıl bulunamadıysa text'ten çek
            if not year:
                import re
                m = re.search(r'\b(19[9]\d|20[012]\d)\b', specs_text)
                if m:
                    year = int(m.group())

            # KM bulunamadıysa text'ten çek
            if not km:
                import re
                m = re.search(r'(\d[\d.]{2,})\s*[Kk][Mm]', specs_text)
                if m:
                    km = _clean_int(m.group(1))

            if not year or not km:
                continue

            results.append({
                "brand":        brand,
                "model":        model,
                "year":         year,
                "km":           km,
                "fuel_type":    _infer_fuel(specs_text),
                "transmission": _infer_transmission(specs_text),
                "listed_price": price,
                "city":         None,
                "body_type":    None,
                "has_damage":   0,
            })
        except Exception as e:
            logger.debug(f"[fordikinciel] card parse error: {e}")

    return results


def scrape_fordikinciel_listings(max_pages: int = 80) -> list[dict[str, Any]]:
    all_results: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    consecutive_empty = 0

    for page in range(1, max_pages + 1):
        logger.info(f"[fordikinciel] page {page}/{max_pages} …")
        rows = _scrape_page(page)

        if not rows:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                logger.info(f"[fordikinciel] no more listings after page {page - 1}")
                break
            continue
        consecutive_empty = 0

        added = 0
        for r in rows:
            key = (r["brand"], r["model"], r["year"], r["km"], r["listed_price"])
            if key not in seen:
                seen.add(key)
                all_results.append(r)
                added += 1

        logger.info(f"[fordikinciel] page {page}: +{added} (total {len(all_results)})")
        time.sleep(0.4)

    logger.info(f"[fordikinciel] Total: {len(all_results)}")
    return all_results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = scrape_fordikinciel_listings(max_pages=3)
    print(f"\nScraped {len(data)} listings.")
    for d in data[:5]:
        print(d)
