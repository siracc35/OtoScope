"""
scraper_carvak.py — Carvak.com ilan scraper
https://www.carvak.com/tr/satilik-arac?page=N
~129 ilan, 0-indexed pagination
"""
from __future__ import annotations
import logging, re, time
from typing import Any
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
BASE_URL = "https://www.carvak.com/tr/satilik-arac"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "Accept-Language": "tr-TR,tr;q=0.9"}

AUTO_KW = ["otomatik", "dsg", "edc", "eat", "cvt", "x-tronic", "steptronic", "auto"]
DIESEL_KW = ["dci", "tdi", "crdi", "tdci", "multijet", "hdi", "cdti", "d-4d", "ecoblue", "dizel"]
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
    try: return int(re.sub(r"[^\d]", "", t))
    except: return None

def _scrape_page(page: int) -> list[dict[str, Any]]:
    try:
        r = requests.get(BASE_URL, params={"page": page}, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        logger.warning(f"[carvak] page {page}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    # İki tip kart var: card-product (yeni stil) ve text listeleri
    # Önce card-product dene
    cards = soup.select("div.card-product, div.card-wrapper")

    for card in cards:
        try:
            text = card.get_text(separator="|", strip=True)
            # Format: "Fiat|•|Egea|2024|•|11.624 km|•|1.4 Fire Easy|•|Manuel|₺ 958.000"
            parts = [p.strip() for p in re.split(r'[|•]', text) if p.strip()]

            # Brand/model
            price_el = card.select_one(".card-pricing, .price-item-main, .price")
            price_text = price_el.get_text(strip=True) if price_el else ""
            price = _int(price_text.replace("₺", "").replace("TL", "").replace(".", ""))
            if not price or price < 50_000: continue

            # Model: ilk 2 kelime
            brand = parts[0] if parts else ""
            model = " ".join(parts[:3]) if len(parts) >= 2 else brand

            # Yıl: 4 haneli sayı
            year = None
            for p in parts:
                m = re.match(r'^(19[9]\d|20[012]\d)$', p.replace(".", ""))
                if m: year = int(m.group()); break

            # KM
            km = None
            for p in parts:
                if "km" in p.lower():
                    km = _int(p); break

            if not year or not km or not brand: continue

            full = " ".join(parts)
            results.append({
                "brand": brand, "model": model, "year": year, "km": km,
                "fuel_type": _fuel(full), "transmission": _trans(full),
                "listed_price": price, "city": None, "body_type": None, "has_damage": 0,
            })
        except Exception as e:
            logger.debug(f"[carvak] {e}")

    # Fallback: düz text listesi ("Renault Megane 1.5 DCI TOUCH 2017 • Istanbul • 102.106 km")
    if not results:
        raw = soup.get_text(separator="\n", strip=True)
        # "Brand Model ... Year • City • KM km" + satır sonraki satırda fiyat yok, price-item'dan al
        price_items = [_int(el.get_text(strip=True)) for el in soup.select(".price-item, .card-pricing") if _int(re.sub(r"[^\d]", "", el.get_text(strip=True)))]
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        for i, line in enumerate(lines):
            m = re.search(r'^(.+?)\s+(19[9]\d|20[012]\d)\s*[•|]\s*(\S+)\s*[•|]\s*([\d.,]+)\s*km', line, re.I)
            if m:
                title, year_s, city, km_s = m.groups()
                year = int(year_s); km = _int(km_s)
                if year and km and i < len(price_items) and price_items[i] and price_items[i] > 50_000:
                    parts = title.split()
                    results.append({
                        "brand": parts[0], "model": " ".join(parts[:4]), "year": year, "km": km,
                        "fuel_type": _fuel(title), "transmission": _trans(title),
                        "listed_price": price_items[i], "city": city, "body_type": None, "has_damage": 0,
                    })
    return results

def scrape_carvak_listings(max_pages: int = 25) -> list[dict[str, Any]]:
    all_results, seen = [], set()
    for page in range(0, max_pages):
        logger.info(f"[carvak] page {page} …")
        rows = _scrape_page(page)
        if not rows:
            logger.info(f"[carvak] empty at page {page}, stopping")
            break
        added = 0
        for r in rows:
            k = (r["brand"], r["model"], r["year"], r["km"], r["listed_price"])
            if k not in seen:
                seen.add(k); all_results.append(r); added += 1
        logger.info(f"[carvak] page {page}: +{added} (total {len(all_results)})")
        time.sleep(0.4)
    logger.info(f"[carvak] Total: {len(all_results)}")
    return all_results

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = scrape_carvak_listings(max_pages=3)
    print(f"Scraped {len(data)}")
    for d in data[:3]: print(d)
