import logging
import time
import requests
from bs4 import BeautifulSoup
from typing import Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# (category_slug, body_type_label, max_pages)
# arabam.com URL: https://www.arabam.com/ikinci-el/<slug>?page=N
# ~20 listings/page. station-wagon and mpv-van return 0 rows (different HTML).
CATEGORIES: list[tuple[str, str | None, int]] = [
    ("sedan",             "Sedan",    100),
    ("hatchback",         "Hatchback", 80),
    ("suv-arazi-araclar", "SUV",       80),
    ("pick-up",           "Pickup",    40),
    ("coupe-cabrio",      "Coupe",     30),
    ("otomobil",          None,        50),  # misc/unlisted body types
]

DIESEL_KEYWORDS = [
    "dci", "tdi", "crdi", "tdci", "multijet", "bluehdi", "hdi",
    "d-4d", "cdti", "1.3 m", "1.5 d", "1.6 d", " d ",
]
AUTO_KEYWORDS = [
    "dsg", "edc", "eat6", "eat8", "steptronic", "tiptronic",
    "x-tronic", "cvt", "otomatik", "auto",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}


def _infer_fuel(model_name: str) -> str:
    lower = model_name.lower()
    for kw in DIESEL_KEYWORDS:
        if kw in lower:
            return "Dizel"
    return "Benzin"


def _infer_transmission(model_name: str) -> str:
    lower = model_name.lower()
    for kw in AUTO_KEYWORDS:
        if kw in lower:
            return "Otomatik"
    return "Manuel"


def _scrape_category(slug: str, body_type: str | None, pages: int) -> list[dict[str, Any]]:
    base = f"https://www.arabam.com/ikinci-el/{slug}"
    results: list[dict[str, Any]] = []
    consecutive_empty = 0

    for page in range(1, pages + 1):
        url = f"{base}?page={page}"
        try:
            logger.info(f"[{slug}] page {page}/{pages} …")
            res = requests.get(url, headers=HEADERS, timeout=12)
            res.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[{slug}] page {page} failed: {e}")
            consecutive_empty += 1
            if consecutive_empty >= 3:
                break
            continue

        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.find_all("tr", class_="listing-list-item")

        if not rows:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                logger.info(f"[{slug}] no more listings after page {page - 1}")
                break
            continue
        consecutive_empty = 0

        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 8:
                continue
            try:
                full_model = tds[1].text.strip()
                brand = full_model.split()[0] if full_model else ""

                year_str  = tds[3].text.strip()
                km_str    = tds[4].text.strip().replace(".", "").replace(",", "")
                price_str = (
                    tds[6].text.strip()
                    .replace(".", "")
                    .replace(",", "")
                    .replace(" TL", "")
                    .replace("\xa0", "")
                    .strip()
                )

                if not (year_str.isdigit() and km_str.isdigit() and price_str.isdigit()):
                    continue

                results.append({
                    "brand":        brand,
                    "model":        full_model,
                    "year":         int(year_str),
                    "km":           int(km_str),
                    "fuel_type":    _infer_fuel(full_model),
                    "transmission": _infer_transmission(full_model),
                    "listed_price": int(price_str),
                    "body_type":    body_type,
                    "city":         None,
                    "has_damage":   0,
                })
            except Exception as e:
                logger.debug(f"[{slug}] row parse error: {e}")

        # Polite delay between pages to avoid rate-limiting
        time.sleep(0.3)

    return results


def scrape_arabam_listings(pages: int = 380) -> list[dict[str, Any]]:
    """Scrape all arabam.com body-type categories up to their max page limits.

    `pages` is the total page budget across all categories. Each category gets
    its configured max pages, but the run stops when the budget is exhausted.
    Returns deduplicated rows (~20 listings/page).
    """
    all_results: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    budget = pages

    for slug, body_type, max_pages in CATEGORIES:
        if budget <= 0:
            break
        n = min(max_pages, budget)
        rows = _scrape_category(slug, body_type, n)
        added = 0
        for r in rows:
            key = (r["brand"], r["model"], r["year"], r["km"], r["listed_price"])
            if key not in seen:
                seen.add(key)
                all_results.append(r)
                added += 1
        budget -= n
        logger.info(f"[{slug}] +{added} unique rows (budget left: {budget})")

    logger.info(f"Total unique listings scraped: {len(all_results)}")
    return all_results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = scrape_arabam_listings(pages=20)
    print(f"\nScraped {len(data)} unique listings.")
    body_counts = {}
    for d in data:
        bt = d.get("body_type") or "unknown"
        body_counts[bt] = body_counts.get(bt, 0) + 1
    print("By body type:", body_counts)
    for d in data[:5]:
        print(d)
