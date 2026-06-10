"""
scraper_otosor.py — OtoSOR ilan scraper
https://www.otosor.com.tr/araclar?page=N
~2.900 ilan, ~244 sayfa, ~12 ilan/sayfa

Kart yapısı (Next.js SSR):
  div.relative.flex...  (kart wrapper)
    h4                  → model adı
    div.vehicle-listing-card-footer
      p[1]              → şanzıman (gearshift icon yanı)
      p[2]              → KM (tire icon yanı)
      p[3]              → yıl (car-frame icon yanı)
  div içinde fiyat — "₺X.XXX.XXX" formatında
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.otosor.com.tr/araclar"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}

DIESEL_KEYWORDS = ["dizel", "tdi", "dci", "crdi", "ecoblue", "tdci", "hdi", "cdti", "d-4d", "multijet", "bluehdi", "cdti"]
ELECTRIC_KEYWORDS = ["elektrik", "electric", "ev "]
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


def _clean_int(text: str) -> int | None:
    try:
        cleaned = re.sub(r"[^\d]", "", text.strip())
        return int(cleaned) if cleaned else None
    except (ValueError, AttributeError):
        return None


def _scrape_page(page: int) -> list[dict[str, Any]]:
    url = f"{BASE_URL}?page={page}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"[otosor] page {page} failed: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    results = []

    footers = soup.select(".vehicle-listing-card-footer")
    if not footers:
        return []

    for footer in footers:
        try:
            card = footer.parent.parent  # 2 seviye yukarı — tam kart wrapper

            # Model adı
            title_el = card.select_one("h4")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            parts = title.split()
            brand = parts[0] if parts else "Bilinmiyor"
            model = " ".join(parts[:5]) if len(parts) >= 2 else title

            # Footer'daki 3 <p>: şanzıman, KM, yıl
            specs = footer.select("p")
            if len(specs) < 3:
                continue

            transmission_text = specs[0].get_text(strip=True)
            km_text           = specs[1].get_text(strip=True)
            year_text         = specs[2].get_text(strip=True)

            transmission = "Otomatik" if "otomatik" in transmission_text.lower() else "Manuel"
            km   = _clean_int(km_text.replace("KM", "").replace("Km", ""))
            year = _clean_int(year_text)

            if not year or not km:
                continue
            if not (1990 <= year <= 2026):
                continue

            # Fiyat — card içindeki ₺ içeren text
            full_text = card.get_text(separator=" ", strip=True)
            price_m = re.search(r'₺\s*([\d.,]+)', full_text)
            if not price_m:
                price_m = re.search(r'([\d.]{4,})\s*TL', full_text)
            price = _clean_int(price_m.group(1)) if price_m else None
            if not price or price < 50_000:
                continue

            results.append({
                "brand":        brand,
                "model":        model,
                "year":         year,
                "km":           km,
                "fuel_type":    _infer_fuel(title + " " + full_text),
                "transmission": transmission,
                "listed_price": price,
                "city":         None,
                "body_type":    None,
                "has_damage":   0,
            })
        except Exception as e:
            logger.debug(f"[otosor] card parse error: {e}")

    return results


def scrape_otosor_listings(max_pages: int = 250) -> list[dict[str, Any]]:
    all_results: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    consecutive_empty = 0

    for page in range(1, max_pages + 1):
        logger.info(f"[otosor] page {page}/{max_pages} …")
        rows = _scrape_page(page)

        if not rows:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                logger.info(f"[otosor] no more listings after page {page - 1}")
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

        logger.info(f"[otosor] page {page}: +{added} (total {len(all_results)})")
        time.sleep(0.3)

    logger.info(f"[otosor] Total: {len(all_results)}")
    return all_results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = scrape_otosor_listings(max_pages=3)
    print(f"\nScraped {len(data)} listings.")
    for d in data[:5]:
        print(d)
