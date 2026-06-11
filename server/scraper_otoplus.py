"""
scraper_otoplus.py — OtoPlus.com ilan scraper
https://www.otoplus.com/al?ln=1&sayfa=N
~168 ilan, JSON-LD schema.org/Vehicle structured data
"""
from __future__ import annotations
import json, logging, re, time
from typing import Any
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
BASE_URL = "https://www.otoplus.com/al"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "Accept-Language": "tr-TR,tr;q=0.9"}

def _int(t):
    try: return int(re.sub(r"[^\d]", "", str(t)))
    except: return None

def _scrape_page(page: int) -> list[dict[str, Any]]:
    try:
        r = requests.get(BASE_URL, params={"ln": 1, "sayfa": page}, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        logger.warning(f"[otoplus] page {page}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    # JSON-LD schema.org/Vehicle objelerini çek
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            graph = data.get("@graph", [data]) if isinstance(data, dict) else data
            for item in graph:
                if not isinstance(item, dict): continue
                if item.get("@type") != "Vehicle": continue

                name = item.get("name", "")
                # name: "2024 Ford PUMA PUMA STYLE 1.0 ECOBOOST 125 7AT"
                name_parts = name.split()

                # Yıl
                year = None
                if name_parts and re.match(r'^(19[9]\d|20[012]\d)$', name_parts[0]):
                    year = int(name_parts[0])
                    name_parts = name_parts[1:]  # yılı çıkar

                brand_obj = item.get("brand", {})
                brand = brand_obj.get("name", "") if isinstance(brand_obj, dict) else str(brand_obj)
                if not brand and name_parts:
                    brand = name_parts[0]

                model = " ".join(name_parts[:4]) if name_parts else name

                # KM
                mileage = item.get("mileageFromOdometer", {})
                if isinstance(mileage, dict):
                    km = _int(mileage.get("value", 0))
                else:
                    km = _int(str(mileage))

                # Fiyat — URL'den çek: "...1360000tl..."
                url = item.get("url", "")
                price_m = re.search(r'(\d+)tl', url, re.I)
                price = int(price_m.group(1)) if price_m else None

                # Yakıt
                fuel_raw = item.get("fuelType", "")
                if "elektrik" in fuel_raw.lower() or "electric" in fuel_raw.lower():
                    fuel = "Elektrik"
                elif "hibrit" in fuel_raw.lower() or "hybrid" in fuel_raw.lower():
                    fuel = "Hibrit"
                elif "dizel" in fuel_raw.lower() or "diesel" in fuel_raw.lower():
                    fuel = "Dizel"
                else:
                    fuel = "Benzin"

                # Şanzıman
                trans_raw = item.get("vehicleTransmission", "")
                trans = "Otomatik" if "auto" in trans_raw.lower() or "otomatik" in trans_raw.lower() else "Manuel"

                # Şehir — URL'den çek
                city_m = re.search(r'(\w+)-\d+tl', url, re.I)
                city = city_m.group(1).capitalize() if city_m else None

                if not (year and km and price and brand): continue
                if price < 50_000: continue

                results.append({
                    "brand": brand, "model": model, "year": year, "km": km,
                    "fuel_type": fuel, "transmission": trans,
                    "listed_price": price, "city": city, "body_type": None, "has_damage": 0,
                })
        except Exception as e:
            logger.debug(f"[otoplus] JSON-LD parse: {e}")

    return results

def scrape_otoplus_listings(max_pages: int = 15) -> list[dict[str, Any]]:
    all_results, seen = [], set()
    for page in range(1, max_pages + 1):
        logger.info(f"[otoplus] page {page} …")
        rows = _scrape_page(page)
        if not rows:
            logger.info(f"[otoplus] empty at page {page}, stopping")
            break
        added = 0
        for r in rows:
            k = (r["brand"], r["model"], r["year"], r["km"], r["listed_price"])
            if k not in seen:
                seen.add(k); all_results.append(r); added += 1
        logger.info(f"[otoplus] page {page}: +{added} (total {len(all_results)})")
        time.sleep(0.4)
    logger.info(f"[otoplus] Total: {len(all_results)}")
    return all_results

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = scrape_otoplus_listings(max_pages=3)
    print(f"Scraped {len(data)}")
    for d in data[:3]: print(d)
