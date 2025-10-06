import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st

# ----------------------------------------
# PlayStation Pricing Scraper (v1.4)
# ----------------------------------------
# Key improvements:
# - Any input URL is first resolved to a canonical product ID.
#   * Accepts: www.playstation.com/games/...   -> finds product link -> ID
#             store.playstation.com/.../concept/... -> finds linked product -> ID
#             store.playstation.com/.../product/{ID} or raw ID -> uses ID
# - For each region, builds: https://store.playstation.com/{locale}/product/{ID}
# - Structured parsing only (Next.js JSON -> JSON-LD -> meta).

TARGET_LOCALES: Dict[str, Dict[str, str]] = {
    "USD": {"locale": "en-us", "country": "US"},
    "GBP": {"locale": "en-gb", "country": "GB"},
    "EUR": {"locale": "de-de", "country": "DE"},
    "JPY": {"locale": "ja-jp", "country": "JP"},
    "BRL": {"locale": "pt-br", "country": "BR"},
    "CAD": {"locale": "en-ca", "country": "CA"},
}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
}

PRODUCT_ID_RE = re.compile(r"/product/([^/?#]+)")

@dataclass
class PriceInfo:
    region_code: str
    msrp: Optional[float]
    current: Optional[float]
    discount_pct: Optional[float]
    locale: str
    country: str
    currency_code: Optional[str]
    title: Optional[str] = None
    product_id: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None  # which parser produced the value

# ------------------------
# HTTP + Helpers
# ------------------------

def build_headers(locale: Optional[str] = None) -> Dict[str, str]:
    h = dict(DEFAULT_HEADERS)
    if locale:
        # Map Accept-Language to the requested locale for better localization
        # e.g., "en-us" -> "en-US,en;q=0.9"
        lang = locale.replace("-", "_").split("_")[0]
        h["Accept-Language"] = f"{lang}-{locale.split('-')[-1].upper()},{lang};q=0.8"
    else:
        h["Accept-Language"] = "en-US,en;q=0.9"
    return h

def fetch_html(url: str, locale: Optional[str] = None, timeout: int = 25) -> Optional[str]:
    try:
        r = requests.get(url, headers=build_headers(locale), timeout=timeout)
        if r.status_code == 200:
            return r.text
        return None
    except requests.RequestException:
        return None

def parse_next_json(html: str) -> Optional[dict]:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except Exception:
        return None

def _num(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        s = str(x).strip().replace(",", "")
        return float(s)
    except Exception:
        return None

# ------------------------
# Product ID Resolution
# ------------------------

def extract_product_id_from_href(href: str) -> Optional[str]:
    if not href:
        return None
    m = PRODUCT_ID_RE.search(href)
    if m:
        return m.group(1)
    return None

def extract_title_from_html(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    # og:title first
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og.get("content").strip()
    # h1 fallback
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    # title tag
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None

def resolve_to_product_id(input_ref: str, locale: str, title_hint: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (product_id, possibly_better_title).
    Strategy:
      - If input already contains /product/{ID}, extract ID.
      - If input is a raw ID, return it.
      - If input is www.playstation.com page -> fetch, find any store.playstation.com/product link.
      - If input is store.playstation.com/.../concept/... -> fetch, find product link in page or Next.js.
      - If still missing, try search with title_hint (or derived title from page).
    """
    # Raw product ID?
    if not input_ref.startswith("http"):
        return input_ref.strip(), None

    # Already a product URL?
    pid = extract_product_id_from_href(input_ref)
    if pid:
        return pid, None

    # Fetch page and scan for product links
    html = fetch_html(input_ref, locale=None)  # locale-less: initial discovery
    if html:
        # Look for any anchor linking to /product/{ID}
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            pid = extract_product_id_from_href(a["href"])
            if pid:
                return pid, extract_title_from_html(html)

        # Try __NEXT_DATA__ for product references
        nxt = parse_next_json(html)
        if nxt:
            # Heuristic walk to find product IDs nested in arrays
            try:
                def find_ids(obj):
                    found = set()
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if k in ("id", "productId") and isinstance(v, str) and ("PPSA" in v or "-" in v):
                                found.add(v)
                            else:
                                found |= find_ids(v)
                    elif isinstance(obj, list):
                        for it in obj:
                            found |= find_ids(it)
                    return found
                ids = list(find_ids(nxt))
                # Prefer IDs that look like full "UPxxxx-PPSA..." codes
                ids.sort(key=lambda s: (("PPSA" in s) * 2 + ("-" in s)), reverse=True)
                if ids:
                    return ids[0], extract_title_from_html(html)
            except Exception:
                pass

        # Derive a title if none
        derived_title = extract_title_from_html(html)
    else:
        derived_title = None

    # Last resort: search by title
    t = title_hint or derived_title
    if t:
        url = f"https://store.playstation.com/{locale}/search/{requests.utils.quote(t)}"
        s_html = fetch_html(url, locale=locale)
        if s_html:
            soup2 = BeautifulSoup(s_html, "html.parser")
            for a in soup2.find_all("a", href=True):
                pid = extract_product_id_from_href(a["href"])
                if pid:
                    return pid, t

            # Try Next.js
            nxt2 = parse_next_json(s_html)
            if nxt2:
                try:
                    props = nxt2.get("props", {})
                    page_props = props.get("pageProps", {})
                    for key in ["results", "searchResults", "items"]:
                        arr = page_props.get(key)
                        if isinstance(arr, list):
                            for item in arr:
                                if isinstance(item, dict):
                                    pid = item.get("id") or item.get("productId")
                                    if pid:
                                        return pid, t
                except Exception:
                    pass

    return None, None

def build_product_url(locale: str, product_id: str) -> str:
    return f"https://store.playstation.com/{locale}/product/{product_id}"

# ------------------------
# Price extraction
# ------------------------

def from_next_json(next_json: dict) -> Tuple[Optional[str], Optional[str], Optional[float], Optional[float], Optional[str]]:
    """Return (title, product_id, msrp, current, currency) from Next.js payload."""
    try:
        props = next_json.get("props", {})
        page_props = props.get("pageProps", {})
        product = page_props.get("product") or page_props.get("pageData") or page_props.get("telemetryData") or {}

        title = product.get("name") or product.get("title") or page_props.get("title")
        product_id = product.get("id") or product.get("productId") or product.get("slug") or page_props.get("productId")

        msrp = None
        current = None
        currency = None

        # 1) product.price
        p = product.get("price") if isinstance(product, dict) else None
        if isinstance(p, dict):
            msrp = _num(p.get("basePrice")) or msrp
            current = _num(p.get("discountedPrice") or p.get("finalPrice") or p.get("current") or p.get("value")) or current
            currency = p.get("currency") or currency

        # 2) defaultSku.price
        if current is None:
            default_sku = product.get("defaultSku") if isinstance(product, dict) else None
            if isinstance(default_sku, dict):
                p2 = default_sku.get("price") if isinstance(default_sku.get("price"), dict) else None
                if p2:
                    msrp = _num(p2.get("basePrice")) or msrp
                    current = _num(p2.get("discountedPrice") or p2.get("finalPrice") or p2.get("current") or p2.get("value")) or current
                    currency = p2.get("currency") or currency

        # 3) skus[].price
        if current is None:
            skus = product.get("skus") if isinstance(product, dict) else None
            if isinstance(skus, list):
                for sku in skus:
                    p3 = sku.get("price") if isinstance(sku.get("price"), dict) else None
                    if p3:
                        msrp = _num(p3.get("basePrice")) or msrp
                        current = _num(p3.get("discountedPrice") or p3.get("finalPrice") or p3.get("current") or p3.get("value")) or current
                        currency = p3.get("currency") or currency
                        if current is not None:
                            break

        # 4) pageProps.price
        if current is None:
            pp = page_props.get("price") or page_props.get("store", {}).get("price")
            if isinstance(pp, dict):
                msrp = _num(pp.get("basePrice")) or msrp
                current = _num(pp.get("discountedPrice") or pp.get("finalPrice") or pp.get("current")) or current
                currency = pp.get("currency") or currency

        return title, product_id, msrp, current, currency
    except Exception:
        return None, None, None, None, None

def parse_json_ld(html: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
    """Parse <script type="application/ld+json"> blocks (Product/Offer)."""
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")
    for s in scripts:
        try:
            data = json.loads(s.string) if s.string else None
        except Exception:
            continue
        candidates: List[dict] = []
        if isinstance(data, dict):
            candidates = [data]
        elif isinstance(data, list):
            candidates = [x for x in data if isinstance(x, dict)]
        for obj in candidates:
            t = obj.get("@type")
            if isinstance(t, list):
                types = set([str(x).lower() for x in t])
            else:
                types = {str(t).lower()} if t else set()
            if {"product", "videogame", "offer"} & types or "offers" in obj:
                title = obj.get("name")
                offers = obj.get("offers")
                if isinstance(offers, dict):
                    price = _num(offers.get("price"))
                    currency = offers.get("priceCurrency")
                    if price is not None:
                        return title, price, currency
                elif isinstance(offers, list):
                    for off in offers:
                        if isinstance(off, dict):
                            price = _num(off.get("price"))
                            currency = off.get("priceCurrency")
                            if price is not None:
                                return title, price, currency
    return None, None, None

def parse_meta_tags(html: str) -> Tuple[Optional[float], Optional[str]]:
    """Check og:price:amount / itemprop=price as last resort for CURRENT price."""
    soup = BeautifulSoup(html, "html.parser")
    meta_amt = soup.find("meta", property="og:price:amount")
    meta_cur = soup.find("meta", property="og:price:currency")
    if meta_amt and meta_amt.get("content"):
        price = _num(meta_amt.get("content"))
        currency = meta_cur.get("content") if meta_cur and meta_cur.get("content") else None
        if price is not None:
            return price, currency
    ip = soup.find(attrs={"itemprop": "price"})
    ipcur = soup.find(attrs={"itemprop": "priceCurrency"})
    if ip and ip.get("content"):
        price = _num(ip.get("content"))
        currency = ipcur.get("content") if ipcur and ipcur.get("content") else None
        if price is not None:
            return price, currency
    return None, None

def compute_discount(msrp: Optional[float], current: Optional[float]) -> Optional[float]:
    if msrp is None or current is None or msrp <= 0:
        return None
    return round(100 * (1 - (current / msrp)), 2)

# ------------------------
# Orchestration
# ------------------------

def fetch_region_price(product_id: str, region_code: str, locale: str, country: str) -> PriceInfo:
    url = build_product_url(locale, product_id)
    html = fetch_html(url, locale=locale)

    title = None
    pid = None
    msrp = None
    current = None
    currency = None
    source = None

    if html:
        nxt = parse_next_json(html)
        if nxt:
            t, p, m, c, cur = from_next_json(nxt)
            title = t or title
            pid = p or pid
            msrp = m if (m is not None and m > 0) else msrp
            current = c if (c is not None and c > 0) else current
            currency = cur or currency
            if current is not None:
                source = "next_json"

        if current is None:
            t2, c2, cur2 = parse_json_ld(html)
            title = t2 or title
            if c2 is not None and c2 > 0:
                current = c2
                currency = cur2 or currency
                source = "json_ld"

        if current is None:
            c3, cur3 = parse_meta_tags(html)
            if c3 is not None and c3 > 0:
                current = c3
                currency = cur3 or currency
                source = "meta"

        if msrp is None and current is not None:
            msrp = current

    discount = compute_discount(msrp, current)

    return PriceInfo(
        region_code=region_code,
        msrp=msrp,
        current=current,
        discount_pct=discount,
        locale=locale,
        country=country,
        currency_code=currency,
        title=title,
        product_id=pid or product_id,
        url=url,
        source=source
    )

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="PlayStation Pricing (Regions)", page_icon="🎮", layout="centered")
st.title("🎮 PlayStation Store — Regional Pricing Pull (MVP v1.4)")
st.caption("Resolves any PlayStation URL to a Product ID, then pulls regional prices from store.playstation.com. Structured parsing only (Next.js JSON, JSON-LD, meta).")

st.markdown("**Input a PlayStation product:** paste a Store URL or a Product ID. Works with `www.playstation.com/games/...`, `store.playstation.com/.../concept/...`, or `.../product/{ID}`.")
product_ref = st.text_input("Product URL or Product ID", value="", placeholder="https://www.playstation.com/en-us/games/helldivers-2/ or UP0006-PPSA02145_00-RESIDENTEVIL8000")

title_hint = st.text_input("Optional: Title hint (used only if we need to search)", value="", placeholder="e.g., Helldivers 2")

region_keys = ["USD", "GBP", "EUR", "JPY", "BRL", "CAD"]
picked = st.multiselect("Regions to pull", region_keys, default=region_keys)

if st.button("Pull Prices"):
    if not product_ref.strip() and not title_hint.strip():
        st.error("Please enter a Product URL/ID or at least a Title hint.")
    else:
        # 1) Resolve to product ID (use US locale for search normalization)
        resolved_id, derived_title = resolve_to_product_id(product_ref.strip(), locale="en-us", title_hint=title_hint.strip() or None)
        if not resolved_id:
            st.error("Couldn't resolve a Product ID from the input. Try pasting a product page URL or provide a Title hint.")
        else:
            st.caption(f"Resolved Product ID: `{resolved_id}`")
            use_title = derived_title or title_hint.strip() or None

            # 2) Pull each region using the product ID
            results: List[PriceInfo] = []
            with st.spinner("Fetching regional prices..."):
                for rk in picked:
                    meta = TARGET_LOCALES[rk]
                    pi = fetch_region_price(
                        product_id=resolved_id,
                        region_code=rk,
                        locale=meta["locale"],
                        country=meta["country"],
                    )
                    results.append(pi)

            rows = []
            main_title = None
            for r in results:
                if r.title and not main_title:
                    main_title = r.title
                rows.append({
                    "Region": f"{r.region_code} ({r.locale.upper()})",
                    "Country": r.country,
                    "Currency": r.currency_code or r.region_code,
                    "MSRP": r.msrp,
                    "Current Price": r.current,
                    "Discount %": r.discount_pct,
                    "Source": r.source,
                    "Product URL": r.url
                })
            df = pd.DataFrame(rows)

            if main_title:
                st.subheader(main_title)

            st.dataframe(df, use_container_width=True)

            st.download_button(
                "Download CSV",
                df.to_csv(index=False).encode("utf-8"),
                file_name="ps_prices.csv",
                mime="text/csv"
            )

            st.markdown("**Notes**")
            st.markdown(
                "- The app resolves any URL to a Product ID, then queries `store.playstation.com/{locale}/product/{ID}` per region.\n"
                "- If a region shows `None`, the SKU may be unavailable there or the page withheld price without the right cookie/headers."
            )
