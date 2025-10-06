import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st

# ----------------------------------------
# PlayStation Pricing Scraper (Structured)
# ----------------------------------------
# Parsing order:
#   1) __NEXT_DATA__ (Next.js embedded JSON)
#   2) JSON-LD blocks (schema.org Product/Offer/VideoGame)
#   3) Meta tags (og:price:amount, itemprop=price)
# We DO NOT use the old "grab first numbers" heuristic.

TARGET_LOCALES: Dict[str, Dict[str, str]] = {
    "USD": {"locale": "en-us", "country": "US"},
    "GBP": {"locale": "en-gb", "country": "GB"},
    "EUR": {"locale": "de-de", "country": "DE"},
    "JPY": {"locale": "ja-jp", "country": "JP"},
    "BRL": {"locale": "pt-br", "country": "BR"},
    "CAD": {"locale": "en-ca", "country": "CA"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
}

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

def build_product_url(locale: str, product_ref: str) -> str:
    # Accept full URL or product ID; normalize to locale-specific product page.
    if product_ref.startswith("http"):
        try:
            parts = product_ref.split("/")
            if "store.playstation.com" in product_ref and len(parts) > 3:
                parts[3] = locale  # swap locale segment
                return "/".join(parts)
        except Exception:
            pass
        return product_ref
    return f"https://store.playstation.com/{locale}/product/{product_ref}"

def fetch_html(url: str, timeout: int = 25) -> Optional[str]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.text
        return None
    except requests.RequestException:
        return None

# ---------- Parsers ----------

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

def from_next_json(next_json: dict) -> Tuple[Optional[str], Optional[str], Optional[float], Optional[float], Optional[str]]:
    # Return title, product_id, msrp, current, currency from likely keys in Next.js payload.
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
    # Parse <script type="application/ld+json"> blocks for schema.org Product/Offer.
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
    # Check og:price:amount / itemprop=price as last resort for CURRENT price.
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

def resolve_by_search(title_query: str, locale: str) -> Optional[str]:
    # Best-effort search page parse to get the first product URL for a title.
    try:
        url = f"https://store.playstation.com/{locale}/search/{requests.utils.quote(title_query)}"
        html = fetch_html(url)
        if not html:
            return None
        next_json = parse_next_json(html)
        if not next_json:
            return None
        props = next_json.get("props", {})
        page_props = props.get("pageProps", {})
        for key in ["results", "searchResults", "items"]:
            arr = page_props.get(key)
            if isinstance(arr, list):
                for item in arr:
                    if isinstance(item, dict):
                        pid = item.get("id") or item.get("productId")
                        if pid:
                            return f"https://store.playstation.com/{locale}/product/{pid}"
        for v in page_props.values():
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        pid = item.get("id") or item.get("productId")
                        if pid:
                            return f"https://store.playstation.com/{locale}/product/{pid}"
        return None
    except Exception:
        return None

def fetch_region_price(product_ref: str, region_code: str, locale: str, country: str, title_hint: Optional[str]=None) -> PriceInfo:
    url = build_product_url(locale, product_ref)
    html = fetch_html(url)

    if not html and title_hint:
        alt = resolve_by_search(title_hint, locale)
        if alt:
            url = alt
            html = fetch_html(url)

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
        product_id=pid,
        url=url,
        source=source
    )

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="PlayStation Pricing (Regions)", page_icon="🎮", layout="centered")
st.title("🎮 PlayStation Store — Regional Pricing Pull (MVP v1.3)")
st.caption("GameRevenue.ai · Structured parsing only (Next.js JSON, JSON-LD, meta tags). Targets USD, GBP, EUR, JPY, BRL, CAD.")

st.markdown("Input a PlayStation product: paste a Store URL or a Product ID (e.g., UP0006-PPSA02145_00-RESIDENTEVIL8000).")
product_ref = st.text_input("Product URL or Product ID", value="", placeholder="https://store.playstation.com/en-us/product/UP0006-PPSA02145_00-RESIDENTEVIL8000")

title_hint = st.text_input("Optional: Title hint for fallback search", value="", placeholder="e.g., Helldivers 2")

region_keys = ["USD", "GBP", "EUR", "JPY", "BRL", "CAD"]
picked = st.multiselect("Regions to pull", region_keys, default=region_keys)

if st.button("Pull Prices"):
    if not product_ref.strip() and not title_hint.strip():
        st.error("Please enter a Product URL/ID or at least a Title hint.")
    else:
        results: List[PriceInfo] = []
        with st.spinner("Fetching regional prices..."):
            for rk in picked:
                meta = TARGET_LOCALES[rk]
                pi = fetch_region_price(
                    product_ref=product_ref.strip() or title_hint.strip(),
                    region_code=rk,
                    locale=meta["locale"],
                    country=meta["country"],
                    title_hint=title_hint.strip() or None
                )
                results.append(pi)

        rows = []
        main_title = None
        product_id_final = None
        for r in results:
            if r.title and not main_title:
                main_title = r.title
            if r.product_id and not product_id_final:
                product_id_final = r.product_id
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

        if main_title or product_id_final:
            st.subheader(main_title or "")
            if product_id_final:
                st.caption(f"Product ID: `{product_id_final}`")

        st.dataframe(df, use_container_width=True)

        st.download_button(
            "Download CSV",
            df.to_csv(index=False).encode("utf-8"),
            file_name="ps_prices.csv",
            mime="text/csv"
        )

        st.markdown("Parser notes: Uses only structured sources (Next.js JSON, JSON-LD, meta tags). If MSRP is missing but current price exists, MSRP is set to current (0% discount). Some products/pages may hide price without locale/cookie; if a region returns None, the SKU may be unavailable there.")
