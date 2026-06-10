"""
scraper_sahibinden.py — nodriver-based scraper for sahibinden.com

Navigates the main second-hand car listing page and paginates through results.
Returns data in the same format as scraper_arabam.scrape_arabam_listings().

Uses nodriver (undetected Chrome) because sahibinden.com has bot protection
that blocks plain requests/BeautifulSoup.

Usage:
    python scraper_sahibinden.py          # test run, prints first 20 rows
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BASE_URL = "https://www.sahibinden.com/ikinci-el-otomobil"

DIESEL_KEYWORDS = [
    "dci", "tdi", "crdi", "tdci", "multijet", "bluehdi", "hdi",
    "d-4d", "cdti", "1.3 m", "1.5 d", "1.6 d", " d ", "dizel",
]
AUTO_KEYWORDS = [
    "dsg", "edc", "eat6", "eat8", "steptronic", "tiptronic",
    "x-tronic", "cvt", "otomatik", "auto",
]


def _infer_fuel(text: str) -> str:
    lower = text.lower()
    for kw in DIESEL_KEYWORDS:
        if kw in lower:
            return "Dizel"
    return "Benzin"


def _infer_transmission(text: str) -> str:
    lower = text.lower()
    for kw in AUTO_KEYWORDS:
        if kw in lower:
            return "Otomatik"
    return "Manuel"


def _clean_int(text: str) -> int | None:
    try:
        return int(text.strip().replace(".", "").replace(",", "").replace("\xa0", ""))
    except (ValueError, AttributeError):
        return None


def _parse_listings(html: str) -> list[dict[str, Any]]:
    """Parse one page of sahibinden.com listing HTML into structured rows."""
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr.searchResultsItem[data-id]")
    results: list[dict[str, Any]] = []

    for row in rows:
        try:
            # Brand / model / engine — the three tag attribute cells
            tag_attrs = row.select("td.searchResultsTagAttributeValue")
            brand  = tag_attrs[0].text.strip() if len(tag_attrs) > 0 else None
            model  = tag_attrs[1].text.strip() if len(tag_attrs) > 1 else None
            engine = tag_attrs[2].text.strip() if len(tag_attrs) > 2 else ""

            # Title (used for fuel/transmission inference)
            title_tag = row.select_one("td.searchResultsTitleValue a.classifiedTitle")
            title = title_tag.text.strip() if title_tag else ""

            # Year / km
            attr_vals = row.select("td.searchResultsAttributeValue")
            year_str = attr_vals[0].text.strip() if len(attr_vals) > 0 else ""
            km_str   = attr_vals[1].text.strip() if len(attr_vals) > 1 else ""

            # Price
            price_tag = row.select_one(
                "td.searchResultsPriceValue div.classified-price-container span"
            )
            price_str = price_tag.text.strip().split()[0] if price_tag else ""

            year  = _clean_int(year_str)
            km    = _clean_int(km_str)
            price = _clean_int(price_str)

            if not (brand and year and km and price):
                continue

            # City — "İstanbul/Kadıköy" → keep full string, city column is free-text
            city_tag = row.select_one("td.searchResultsLocationValue")
            city = city_tag.text.strip().split()[0] if city_tag else None

            # Fuel & transmission inference from engine + title
            combined = f"{engine} {title}"
            fuel_type    = _infer_fuel(combined)
            transmission = _infer_transmission(combined)

            full_model = f"{brand} {model} {engine}".strip() if model else brand

            results.append({
                "brand":        brand,
                "model":        full_model,
                "year":         year,
                "km":           km,
                "fuel_type":    fuel_type,
                "transmission": transmission,
                "listed_price": price,
                "city":         city,
                "body_type":    None,
                "has_damage":   0,
            })
        except Exception as e:
            logger.debug(f"Row parse error: {e}")

    return results


async def _scrape_async(max_pages: int = 20) -> list[dict[str, Any]]:
    """Async core: open sahibinden.com with nodriver and paginate."""
    import nodriver as uc

    driver = await uc.start(headless=True)
    all_results: list[dict[str, Any]] = []
    seen: set[tuple] = set()

    try:
        tab = await driver.get(BASE_URL)

        # Wait for the actual listing table to appear (page has JS-driven loading)
        try:
            await tab.wait_for("tr.searchResultsItem", timeout=20)
        except Exception:
            pass
        await tab.sleep(3)

        # Accept cookies if banner appears
        try:
            accept = await tab.find("Tüm Çerezleri Kabul Et", best_match=True)
            if accept:
                await accept.click()
                await tab.sleep(2)
        except Exception:
            pass

        # Set results-per-page to 50
        try:
            limit50 = await tab.select('a.paging-size.Limit50Passive[title="50"]')
            if limit50:
                await limit50.click()
                await tab.wait_for("tr.searchResultsItem", timeout=10)
                await tab.sleep(2)
        except Exception:
            pass

        for page_num in range(1, max_pages + 1):
            logger.info(f"[sahibinden] page {page_num}/{max_pages} …")
            try:
                # Ensure content is loaded before parsing
                try:
                    await tab.wait_for("tr.searchResultsItem", timeout=10)
                except Exception:
                    pass
                await tab.sleep(1)
                html = await tab.get_content()
                rows = _parse_listings(html)

                added = 0
                for r in rows:
                    key = (r["brand"], r["model"], r["year"], r["km"], r["listed_price"])
                    if key not in seen:
                        seen.add(key)
                        all_results.append(r)
                        added += 1

                logger.info(f"[sahibinden] page {page_num}: +{added} unique rows (total {len(all_results)})")

                # Next page
                next_btn = await tab.select('.prevNextBut[title="Sonraki"]')
                if not next_btn:
                    logger.info("[sahibinden] Last page reached.")
                    break
                await next_btn.click()
                await tab.sleep(2)

            except Exception as e:
                logger.warning(f"[sahibinden] page {page_num} error: {e}")
                break

    finally:
        driver.stop()

    logger.info(f"[sahibinden] Total unique listings: {len(all_results)}")
    return all_results


def scrape_sahibinden_listings(max_pages: int = 20) -> list[dict[str, Any]]:
    """Sync wrapper — can be called from ml.py like scrape_arabam_listings()."""
    try:
        return asyncio.run(_scrape_async(max_pages=max_pages))
    except Exception as e:
        logger.error(f"[sahibinden] Scraper failed: {e}")
        return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = scrape_sahibinden_listings(max_pages=3)
    print(f"\nScraped {len(data)} unique listings.")
    for row in data[:5]:
        print(row)
