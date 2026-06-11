"""
scraper.py — fetch a car listing URL and extract its text.

Supported sites:
  - sahibinden.com  (best-effort, bot protection may block)
  - arabam.com      (reliable)
  - araba.com       (reliable)
  - otosor.com.tr   (reliable)
  - otoplus.com.tr  (reliable)
  - fordikinciel.com (reliable)

Primary user flow: paste a listing URL → server fetches & extracts text → analyzer.
"""

from __future__ import annotations

import re
import warnings
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SUPPORTED_DOMAINS = {
    "sahibinden.com",
    "arabam.com",
    "araba.com",
    "otosor.com.tr",
    "otoplus.com.tr",
    "fordikinciel.com",
    "otoshops.com",
}


class ScrapeError(Exception):
    """Raised when we cannot retrieve usable listing text."""


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower().lstrip("www.")
    return host


def _is_supported(url: str) -> bool:
    d = _domain(url)
    return any(d == s or d.endswith("." + s) for s in SUPPORTED_DOMAINS)


def _fetch(url: str, verify: bool = True) -> requests.Response:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15, verify=verify)
    except requests.RequestException as exc:
        raise ScrapeError(f"Bağlantı hatası: {exc}") from exc
    return resp


def _extract_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    """Try CSS selectors in order, fall back to body."""
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            for tag in el(["script", "style", "noscript"]):
                tag.decompose()
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 200:
                return text
    # full body fallback
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    return (soup.body or soup).get_text(separator="\n", strip=True)


# Footer/stop markers — everything from here on is noise
_STOP_MARKERS = [
    "sahibinden.com, tüm kullanıcılar",
    "vasıta alırken/kiralarken bunlara dikkat",
    "copyright ©",
    "7/24 müşteri hizmetleri",
    "yardım merkezi",
    "güvenli alışverişin ipuçları",
    "hakkımızda\nsürdürülebilirlik",
    "kurumsal",
    "site haritası",
    "bizi takip edin",
    "güven damgası",
    "etbis",
    "arabam.com güvencesi ve tecrübeli",
    "galeriden skoda", "galeriden hyundai", "galeriden audi",
    "galeriden volkswagen", "galeriden bmw", "galeriden mercedes",
    "galeriden renault", "galeriden fiat", "galeriden toyota",
    "plaka\n",  # "Plaka\n230 TL" section at bottom
]

# Line-level noise substrings
_NOISE_CONTAINS = [
    "uygulamada aç", "favori ilanlar", "favori aramalar", "ilanları karşılaştır",
    "size özel ilanlar", "karşılaştır\n",
    "sponsorlu", "kredi teklifi al", "kredi hesapla", "ekspertiz teklif", "kopyalandı",
    "paketleri ve şubeleri", "created by arabam", "arabam-plus", "trink sat",
    "eids bilgileri", "eids araç", "eids (elektronik",
    "güvenliğiniz için kapora", "hasar sorgula", "ekspertiz yaptır",
    "sıfır araçları incele",
    "bireysel kullanıcılar için ücret", "sbm üzerinden",
    "telefonu göster", "mesaj gönder", "tüm ilanlarını gör",
    "favori satıcılarıma", "ilan ile ilgili şikayetim",
    "platinum üye", "gold üye", "bronze üye", "silver üye",
    "fill 1", "{{errormessage}}",
    "lokal boyalı", "tramer tutarı",
    "yetki belge numarası", "yetki belge no:",
    "şubeleri gör", "büyük fotoğraf", "ilan klibi", "sanal tur",
    "facebook ile paylaş", "x ile paylaş", "e-posta ile gönder",
    "favorilerime ekle", "yazdırfacebook",
    "kelime, ilan no veya mağaza", "detaylı arama",
    "ücretsiz* ilan ver", "sahibinden.com anasayfasına",
    "neden mağaza", "mağaza açmak",
    "size özel ilanlar", "ilan ile ilgili şikayetim",
    "irtibat numar", "iletişim numar",
    "araçsız kalmayin", "araçsız kalmayın",
    "detayli bilgi için", "detaylı bilgi için",
    "aracimiz km-ekspertiz", "araçlarımızda km",
    "plaka\n230", "plaka:\n",
]

# Exact lines that are pure UI chrome
_NOISE_EXACT = {
    "otomobil", "vasıta", "anasayfa", "geri", "ileri", "-", ".",
    "orijinal", "boyalı", "değişmiş", "belirtilmemiş",
    "ön tampon", "arka tampon", "motor kaputu", "arka kaput", "tavan",
    "sağ ön kapı", "sol ön kapı", "sağ arka kapı", "sol arka kapı",
    "sağ ön çamurluk", "sol ön çamurluk", "sağ arka çamurluk", "sol arka çamurluk",
    "aracın ilk sahibiyim", "i̇lk sahibi değilim",
    "boya, değişen ve tramer", "araç bilgileri",
    "genel bakış", "ilan detayları", "konumu", "teknik özellikler",
    "açıklama", "donanım", "özellikler",
    "boyalı veya değişen parça",
    "güvenlik", "i̇ç donanım", "dış donanım", "multimedya",
}

# Phone number pattern — also removes "Cep", "Ofis", "Tel" prefixes
_PHONE_RE = re.compile(
    r"(?:cep|ofis|tel|gsm|telefon)?\s*:?\s*"
    r"(0\s*[(\s]?\d{3}[)\s]*\s*\d{3}\s*\d{2}\s*\d{2}|\+90\s*\d{3}[\s\d]{8,})",
    re.IGNORECASE,
)


def _is_noise(line: str) -> bool:
    low = line.lower()
    if low in _NOISE_EXACT:
        return True
    if any(n in low for n in _NOISE_CONTAINS):
        return True
    # Bare panel names like "Sağ Arka Çamurluk" standing alone
    if re.match(r"^(sağ|sol|ön|arka)\s+\w+(\s+\w+)?$", low):
        return True
    # "3. YIL", "13. YIL" dealer badge
    if re.match(r"^\d+\.\s*yıl$", low):
        return True
    # Navigation breadcrumb: "Vasıta / Otomobil / Audi / ..."
    if re.match(r"^vasıta\s*/", low) or low.count(" / ") >= 2:
        return True
    # Related search tag spam: "Galeriden Audi A5", "2025 Audi A5", "Siyah Audi..."
    if re.match(r"^(galeriden|satılık|i̇kinci el|siyah|beyaz|gri|kırmızı|mavi)\s+\w+", low):
        return True
    return False


def _find_stop(lines: list[str]) -> int:
    """Return index where footer noise begins."""
    joined = "\n".join(l.lower() for l in lines)
    for marker in _STOP_MARKERS:
        idx = joined.find(marker.lower())
        if idx >= 0:
            # Convert char offset to line index
            char_count = 0
            for i, l in enumerate(lines):
                char_count += len(l) + 1
                if char_count >= idx:
                    return i
    return len(lines)


def _clean(raw: str) -> str:
    lines = [l.strip() for l in raw.splitlines() if l.strip()]

    # Cut footer
    lines = lines[:_find_stop(lines)]

    # Remove phone numbers from lines (but keep the line if other content remains)
    lines = [_PHONE_RE.sub("", l).strip() for l in lines]
    lines = [l for l in lines if l]

    # Remove noise lines
    lines = [l for l in lines if not _is_noise(l)]

    # Global deduplication (same line appearing twice anywhere)
    seen: set[str] = set()
    deduped: list[str] = []
    for l in lines:
        key = l.lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(l)

    # Drop single-char lines
    deduped = [l for l in deduped if len(l) > 1]

    return "\n".join(deduped)


# ---------------------------------------------------------------------------
# Per-site scrapers
# ---------------------------------------------------------------------------

def _scrape_sahibinden(url: str) -> str:
    resp = _fetch(url)
    if resp.status_code in (403, 429) or "tloading" in resp.url:
        raise ScrapeError(
            "SAHIBINDEN_BLOCKED"
        )
    if resp.status_code != 200:
        raise ScrapeError(f"Beklenmeyen durum kodu: {resp.status_code}")
    soup = BeautifulSoup(resp.text, "lxml")
    return _clean(_extract_text(soup, ["#classifiedDetail", ".classifiedDetail"]))


def _scrape_arabam(url: str) -> str:
    resp = _fetch(url)
    if resp.status_code != 200:
        raise ScrapeError(f"arabam.com yanıt vermedi: {resp.status_code}")
    soup = BeautifulSoup(resp.text, "lxml")

    # Remove known noise containers before extracting text
    for sel in [
        ".breadcrumb", "nav", "header", "footer",
        ".similar-listings", ".dealer-info", ".contact-box",
        ".financing", ".share-buttons", ".ad-banner",
        "[class*='sponsor']", "[class*='banner']", "[class*='social']",
        ".body-parts-table", "[class*='bodyParts']",
        ".eids", "[class*='eids']",
    ]:
        for el in soup.select(sel):
            el.decompose()

    return _clean(_extract_text(soup, [
        ".classified-detail",
        "[class*='classifiedDetail']",
        "[class*='listing-detail']",
        "[class*='detail-page']",
        "main",
    ]))


def _scrape_generic(url: str, verify: bool = True) -> str:
    resp = _fetch(url, verify=verify)
    if resp.status_code != 200:
        raise ScrapeError(f"Site yanıt vermedi: {resp.status_code}")
    soup = BeautifulSoup(resp.text, "lxml")
    return _clean(_extract_text(soup, ["main", "article", ".detail", ".listing"]))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _resolve_short_link(url: str) -> str:
    """Follow redirects on short links (e.g. shbd.io) to get the real URL."""
    try:
        resp = requests.head(url, headers=_HEADERS, timeout=10, allow_redirects=True)
        return resp.url
    except requests.RequestException:
        return url


def scrape_listing(url: str) -> str:
    """Fetch a listing URL and return cleaned text ready for the AI analyzer.

    Raises ScrapeError with a user-friendly Turkish message on failure.
    """
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    # Resolve known short-link domains before domain validation
    if "shbd.io" in url:
        url = _resolve_short_link(url)

    if not _is_supported(url):
        supported = ", ".join(sorted(SUPPORTED_DOMAINS))
        raise ScrapeError(
            f"Bu site desteklenmiyor. Desteklenen siteler: {supported}"
        )

    d = _domain(url)

    if "sahibinden.com" in d:
        text = _scrape_sahibinden(url)
    elif "arabam.com" in d:
        text = _scrape_arabam(url)
    elif "araba.com" in d:
        text = _scrape_generic(url, verify=False)
    else:
        text = _scrape_generic(url)

    if len(text) < 150:
        raise ScrapeError(
            "İlan içeriği çıkarılamadı. Lütfen ilan metnini kopyalayıp yapıştırın."
        )

    return text
