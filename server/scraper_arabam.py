import re
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# A simple heuristic to guess fuel and transmission from model name
DIESEL_KEYWORDS = ["dci", "tdi", "crdi", "tdci", "multijet", "bluehdi", "hdi", "d-4d", "cdti", "1.3", "1.5", "1.6 d", " d "]
AUTO_KEYWORDS = ["dsg", "edc", "eat6", "eat8", "steptronic", "tiptronic", "x-tronic", "cvt", "otomatik", "auto"]

def infer_fuel_type(model_name: str) -> str:
    lower_name = model_name.lower()
    for kw in DIESEL_KEYWORDS:
        if kw in lower_name:
            return "Dizel"
    # If it contains typical petrol keywords or no diesel keywords, guess Petrol
    return "Benzin"

def infer_transmission(model_name: str) -> str:
    lower_name = model_name.lower()
    for kw in AUTO_KEYWORDS:
        if kw in lower_name:
            return "Otomatik"
    return "Manuel"

def scrape_arabam_listings(pages: int = 1) -> List[Dict[str, Any]]:
    """
    Scrapes listing data from arabam.com.
    Returns a list of dicts: {brand, model, year, km, fuel_type, transmission, price}
    """
    base_url = "https://www.arabam.com/ikinci-el/otomobil"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    results = []
    
    for page in range(1, pages + 1):
        url = f"{base_url}?page={page}"
        try:
            logger.info(f"Fetching arabam.com page {page}...")
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch page {page}: {e}")
            break
            
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.find_all("tr", class_="listing-list-item")
        
        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 8:
                continue
                
            # Column mapping (based on arabam.com layout)
            # 1: Brand / Model / Spec
            # 3: Year
            # 4: KM
            # 6: Price
            
            try:
                full_model = tds[1].text.strip()
                brand = full_model.split()[0] if full_model else ""
                
                year_str = tds[3].text.strip()
                km_str = tds[4].text.strip().replace(".", "")
                price_str = tds[6].text.strip().replace(".", "").replace(" TL", "").strip()
                
                if not (year_str.isdigit() and km_str.isdigit() and price_str.isdigit()):
                    continue
                    
                year = int(year_str)
                km = int(km_str)
                price = int(price_str)
                
                # We infer fuel and transmission for our ML pipeline
                fuel_type = infer_fuel_type(full_model)
                transmission = infer_transmission(full_model)
                
                results.append({
                    "brand": brand,
                    "model": full_model,
                    "year": year,
                    "km": km,
                    "fuel_type": fuel_type,
                    "transmission": transmission,
                    "listed_price": price
                })
            except Exception as e:
                logger.warning(f"Error parsing row: {e}")
                
    return results

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = scrape_arabam_listings(pages=1)
    print(f"Scraped {len(data)} listings.")
    for d in data[:5]:
        print(d)
