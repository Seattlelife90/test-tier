
from __future__ import annotations
import re, time, json, logging, requests
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
from .ps_market_silo_v1 import PS_SUPPORTED, ps_locale, ps_currency

log = logging.getLogger("ps_fetcher")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# --- Helpers -----------------------------------------------------------------
def _normalize_ps_url(url: str) -> str:
    """Ensure the URL looks like a PlayStation Store product or concept URL."""
    if not url.startswith("http"):
        # treat as bare product id, e.g. UP0006-PPSA26127_00-...
        return f"https://store.playstation.com/en-us/product/{url}"
    # If no locale path present, inject /en-us/
    if re.match(r"^https?://store\.playstation\.com/(?:[a-z]{2}-[a-z]{2})/", url) is None:
        url = url.replace("store.playstation.com/", "store.playstation.com/en-us/")
    return url

def _localize(url: str, locale: str) -> str:
    """Swap locale segment in a PS URL to the requested locale (e.g., fr-fr)."""
    return re.sub(r"(store\.playstation\.com/)([a-z]{2}-[a-z]{2})/",
                  rf"\1{locale}/", url, flags=re.IGNORECASE)

def _fetch(url: str, timeout: float = 12.0) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return r.text

def _parse_baseprice_from_html(html: str) -> Optional[Tuple[float,str]]:
    """
    Try multiple strategies to extract MSRP (basePrice) and currency:
    1) Next.js data blob (look for "basePrice": {"value": ..., "currency": "..."}
    2) Any "basePrice" pair elsewhere
    3) JSON-LD offers with "priceCurrency" and "price"
    """
    # Strategy 1/2: find basePrice value + currency
    m = re.search(r'"basePrice"\s*:\s*{[^}]*"value"\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*"currency"\s*:\s*"([A-Z]{3})"', html)
    if m:
        try:
            return float(m.group(1)), m.group(2)
        except:  # noqa: E722
            pass

    # Strategy 3: JSON-LD
    # Pull first <script type="application/ld+json"> and try to read offers
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("script", {"type": "application/ld+json"}):
            text = tag.string or ""
            data = json.loads(text)
            offers = data.get("offers")
            if isinstance(offers, dict):
                cur = offers.get("priceCurrency")
                price = offers.get("price")
                if price and cur:
                    return float(str(price).replace(",", "")), cur
            if isinstance(offers, list):
                for off in offers:
                    cur = off.get("priceCurrency")
                    price = off.get("price")
                    if price and cur:
                        return float(str(price).replace(",", "")), cur
    except Exception:
        pass

    return None

# --- Public API ---------------------------------------------------------------
def fetch_ps_prices(
    base_url_or_id: str,
    countries: List[str],
    prefer_msrp: bool = True,
    edition_hint: str = "standard",
    sleep_between: float = 0.3,
) -> List[Dict]:
    """
    Fetch PlayStation prices across PS-supported countries.
    - base_url_or_id: product URL/ID (prefer product URL). Concept URLs may return bundle editions.
    - countries: ISO2 codes to attempt (will be filtered to PS_SUPPORTED).
    - prefer_msrp: if True, prefer MSRP (basePrice) over discounted/current.
    - edition_hint: reserved for future edition filtering (standard/cross-gen).

    Returns list of dict rows: {country, currency, price, source_url, platform="PlayStation"}
    """
    rows: List[Dict] = []
    base = _normalize_ps_url(base_url_or_id)
    for cc in countries:
        cc = cc.upper()
        if cc not in PS_SUPPORTED:
            continue
        loc = ps_locale(cc)
        url = _localize(base, loc)
        try:
            html = _fetch(url)
            parsed = _parse_baseprice_from_html(html) if prefer_msrp else None
            if parsed:
                price, cur = parsed
            else:
                # fallback: try to find any "currentPrice" if MSRP missing
                m = re.search(r'"currentPrice"\s*:\s*{[^}]*"value"\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*"currency"\s*:\s*"([A-Z]{3})"', html)
                if m:
                    price, cur = float(m.group(1)), m.group(2)
                else:
                    # last resort: pick a number near a currency code
                    m2 = re.search(r'([A-Z]{3})\s*([0-9]+(?:\.[0-9]+)?)', html)
                    if not m2:
                        rows.append({"platform": "PlayStation", "country": cc, "currency": None, "price": None, "source_url": url, "reason": "no_price_found"})
                        time.sleep(sleep_between)
                        continue
                    cur, price = m2.group(1), float(m2.group(2))

            rows.append({
                "platform": "PlayStation",
                "country": cc,
                "currency": cur,
                "price": price,
                "source_url": url,
            })
        except Exception as e:
            rows.append({"platform": "PlayStation", "country": cc, "currency": None, "price": None, "source_url": url, "reason": f"error:{e.__class__.__name__}"})
        time.sleep(sleep_between)
    return rows
