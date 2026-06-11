"""
scraper_otoshops.py — Otoshops.com ilan scraper
https://www.otoshops.com/tum-arabalar?page=N
~403 ilan, ~20/sayfa
"""
from __future__ import annotations
import logging, re, time
from typing import Any
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
BASE_URL = "https://www.otoshops.com/tum-arabalar"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "Accept-Language": "tr-TR,tr;q=0.9"}

AUTO_KW = ["otomatik", "dsg", "edc", "eat", "cvt", "x-tronic", "steptronic"]
DIESEL_KW = ["dizel", "dci", "tdi", "crdi", "tdci", "multijet", "hdi", "cdti", "d-4d", "ecoblue"]
ELECTRIC_KW = ["elektrik", "electric", "bev"]
HYBRID_KW = ["hibrit", "hybrid", "phev"]

def _fuel(t):
    t = t.lower()
    if any(k in t for k in ELECTRIC_KW): return "Elektrik"
    if any(k in t for k in HYBRID_KW): return "Hibrit"
    if any(k in t for k in DIESEL_KW): return "Dizel"
    return "Benzin"

def _trans(t):
    return "Otomatik" if any(k in t.lower() for k in AUTO_KW) else "Manuel"

def _int(t):
    try: return int(re.sub(r"[^\d]", "", str(t)))
    except: return None

def _scrape_page(page: int) -> list[dict[str, Any]]:
    params = {"page": page} if page > 1 else {}
    try:
        r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        logger.warning(f"[otoshops] page {page}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    # CarItem class ile kart bul
    cards = soup.select(".CarItem")
    for card in cards:
        try:
            full = card.get_text(separator="|", strip=True)
            parts = [p.strip() for p in full.split("|") if p.strip()]

            # Fiyat: .Price class
            price_el = card.select_one(".Price")
            price = _int(price_el.get_text(strip=True)) if price_el else None
            if not price or price < 50_000: continue

            # Başlık: ilk anlamlı metin (araç adı)
            # Format: "Mercedes-Benz E 200 D 75HP | 1995 | Manuel | Dizel | 306.500 Km | OTOSHOPS... | KOKAELI"
            title = ""
            year = None; km = None; fuel = "Benzin"; trans = "Manuel"; city = None

            for j, p in enumerate(parts):
                # Yıl
                if re.match(r'^(19[9]\d|20[012]\d)$', p):
                    year = int(p)
                    if not title and j > 0:
                        title = " ".join(parts[:j])
                # KM
                elif re.search(r'km', p, re.I) and re.search(r'\d', p):
                    km = _int(p)
                # Şehir: tek kelime ve büyük harf
                elif re.match(r'^[A-ZÇĞİÖŞÜ][a-zçğışöüñA-ZÇĞİÖŞÜ]+$', p) and len(p) > 2 and j > 2:
                    city = p

            if not title:
                title = parts[0] if parts else ""
            title_parts = title.split()
            brand = title_parts[0] if title_parts else "Bilinmiyor"
            model = " ".join(title_parts[:4]) if len(title_parts) >= 2 else title

            if not year or not km or not brand: continue

            results.append({
                "brand": brand, "model": model, "year": year, "km": km,
                "fuel_type": _fuel(full), "transmission": _trans(full),
                "listed_price": price, "city": city, "body_type": None, "has_damage": 0,
            })
        except Exception as e:
            logger.debug(f"[otoshops] {e}")

    return results

def scrape_otoshops_listings(max_pages: int = 25) -> list[dict[str, Any]]:
    all_results, seen = [], set()
    consecutive_empty = 0
    for page in range(1, max_pages + 1):
        logger.info(f"[otoshops] page {page}/{max_pages} …")
        rows = _scrape_page(page)
        if not rows:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                break
            continue
        consecutive_empty = 0
        added = 0
        for r in rows:
            k = (r["brand"], r["model"], r["year"], r["km"], r["listed_price"])
            if k not in seen:
                seen.add(k); all_results.append(r); added += 1
        logger.info(f"[otoshops] page {page}: +{added} (total {len(all_results)})")
        time.sleep(0.3)
    logger.info(f"[otoshops] Total: {len(all_results)}")
    return all_results

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = scrape_otoshops_listings(max_pages=3)
    print(f"Scraped {len(data)}")
    for d in data[:3]: print(d)
