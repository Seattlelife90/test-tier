
    import json
    import re
    from dataclasses import dataclass
    from typing import Dict, List, Optional, Tuple

    import requests
    from bs4 import BeautifulSoup
    import pandas as pd
    import streamlit as st

    # ---------------------------
    # PlayStation Pricing Scraper
    # ---------------------------
    # Strategy:
    # 1) For each target locale, open the region-specific product page URL and parse
    #    the embedded Next.js JSON ("__NEXT_DATA__") for pricing.
    # 2) Support two input modes:
    #    - Product URL (copy/paste from store.playstation.com)
    #    - Product ID / Concept ID (we auto-build URLs per locale)
    # 3) Optional: simple region-scoped search as a fallback when only a title is provided.
    #
    # Note: Sony frequently updates the store. This parser is defensive:
    #  - It prefers structured JSON under __NEXT_DATA__
    #  - It gracefully falls back to scanning for likely price blobs in the HTML if the schema shifts
    #
    # Tested locales/currencies in this version:
    #  - USD (en-us, US)
    #  - GBP (en-gb, GB)
    #  - EUR (de-de, DE)
    #  - JPY (ja-jp, JP)
    #  - BRL (pt-br, BR)
    #  - CAD (en-ca, CA)

    TARGET_LOCALES = {
        "USD": {"locale": "en-us", "country": "US"},
        "GBP": {"locale": "en-gb", "country": "GB"},
        "EUR": {"locale": "de-de", "country": "DE"},
        "JPY": {"locale": "ja-jp", "country": "JP"},
        "BRL": {"locale": "pt-br", "country": "BR"},
        "CAD": {"locale": "en-ca", "country": "CA"},
    }

    HEADERS = {
        # Mimic a normal browser to avoid bot blocks; PlayStation often checks UA.
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
    }

    # Regex helpers
    MONEY_RE = re.compile(r"(\d+[\.,]?\d*)")

    @dataclass
    class PriceInfo:
        currency: str
        msrp: Optional[float]
        current_price: Optional[float]
        discount_percent: Optional[float]
        region: str
        locale: str
        country: str
        title: Optional[str] = None
        product_id: Optional[str] = None
        url: Optional[str] = None

    def build_product_url(locale: str, product_id_or_path: str) -> str:
        """
        Accepts either a full URL, or a product id like 'UP0001-CUSA00572_00-GTAV000000000000'.
        If an ID is given, builds: https://store.playstation.com/{locale}/product/{id}
        """
        if product_id_or_path.startswith("http"):
            # If it's already a URL, just adapt locale if needed
            try:
                # Normalize to given locale by replacing the locale segment if present
                parts = product_id_or_path.split("/")
                if "store.playstation.com" in product_id_or_path and len(parts) > 3:
                    parts[3] = locale  # e.g., en-us
                    return "/".join(parts)
            except Exception:
                pass
            return product_id_or_path
        else:
            return f"https://store.playstation.com/{locale}/product/{product_id_or_path}"

    def fetch_html(url: str, timeout: int = 20) -> Optional[str]:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
            # Some locales redirect; try allowing redirects (requests does by default)
            return None
        except requests.RequestException:
            return None

    def parse_next_data(html: str) -> Optional[dict]:
        """
        Extract the Next.js JSON embedded in a <script id="__NEXT_DATA__" type="application/json">.
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            tag = soup.find("script", id="__NEXT_DATA__")
            if not tag or not tag.string:
                return None
            return json.loads(tag.string)
        except Exception:
            return None

    def extract_price_from_next_data(next_json: dict) -> Tuple[Optional[str], Optional[str], Optional[float], Optional[float], Optional[str], Optional[str]]:
        """
        Attempt to traverse the Next.js data to find:
        - title
        - product_id
        - msrp (strikethrough / "basePrice")
        - current_price
        - currency
        - region_code (if available in data)

        The exact schema can change. We check a few likely paths.
        Returns: (title, product_id, msrp, current, currency, region_hint)
        """
        try:
            # Common pattern: next_json["props"]["pageProps"]["product"] or similar
            props = next_json.get("props", {})
            page_props = props.get("pageProps", {})

            # Try primary keys we often see
            product = page_props.get("product") or page_props.get("pageData") or page_props.get("telemetryData") or {}

            # Heuristics for title / id
            title = product.get("name") or product.get("title") or page_props.get("title")
            product_id = (
                product.get("id")
                or product.get("productId")
                or product.get("slug")
                or page_props.get("productId")
            )

            # Pricing blobs vary: look for something called "skus", "price", "defaultSku", "pricing"
            msrp_val = None
            current_val = None
            currency = None

            # 1) Look for a nested "price" dict
            price_dict = product.get("price") if isinstance(product, dict) else None
            if isinstance(price_dict, dict):
                msrp_val = float(price_dict.get("basePrice")) if price_dict.get("basePrice") else None
                current_val = float(price_dict.get("discountedPrice") or price_dict.get("finalPrice") or price_dict.get("current")) if                     (price_dict.get("discountedPrice") or price_dict.get("finalPrice") or price_dict.get("current")) else None
                currency = price_dict.get("currency")

            # 2) Try "defaultSku" -> "price"
            if current_val is None:
                default_sku = product.get("defaultSku") if isinstance(product, dict) else None
                if isinstance(default_sku, dict):
                    p = default_sku.get("price") if isinstance(default_sku.get("price"), dict) else None
                    if p:
                        msrp_val = float(p.get("basePrice")) if p.get("basePrice") else msrp_val
                        current_val = float(p.get("discountedPrice") or p.get("finalPrice") or p.get("current") or (p.get("value") if isinstance(p.get("value"), (int, float, str)) else None) or 0) or None
                        currency = p.get("currency") or currency

            # 3) Try searching "skus" list
            if current_val is None:
                skus = product.get("skus") if isinstance(product, dict) else None
                if isinstance(skus, list) and skus:
                    # Pick the first sku that has a price
                    for sku in skus:
                        p = sku.get("price") if isinstance(sku.get("price"), dict) else None
                        if p:
                            msrp_val = float(p.get("basePrice")) if p.get("basePrice") else msrp_val
                            current_val = float(p.get("discountedPrice") or p.get("finalPrice") or p.get("current") or (p.get("value") if isinstance(p.get("value"), (int, float, str)) else None) or 0) or None
                            currency = p.get("currency") or currency
                            break

            # 4) Some schemas stash pricing under pageProps["price"] or ["store"]["price"]
            if current_val is None:
                alt_price = page_props.get("price") or page_props.get("store", {}).get("price")
                if isinstance(alt_price, dict):
                    msrp_val = float(alt_price.get("basePrice")) if alt_price.get("basePrice") else msrp_val
                    current_val = float(alt_price.get("discountedPrice") or alt_price.get("finalPrice") or alt_price.get("current") or 0) or None
                    currency = alt_price.get("currency") or currency

            # Region hint (if present somewhere)
            region_hint = page_props.get("region") or page_props.get("locale") or None

            return title, product_id, msrp_val, current_val, currency, region_hint
        except Exception:
            return None, None, None, None, None, None

    def very_naive_price_scrape(html: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Fallback: If Next.js payload isn't found or schema is unknown,
        try to pull two money-like numbers from the page and infer msrp/current.
        This is a last-resort heuristic.
        """
        try:
            # Try looking for common currency codes or symbols near numbers
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(" ", strip=True)

            # Look for "Was $xx.xx" / "Now $yy.yy" patterns
            was_now = re.search(r"(Was|Strikethrough)\s*([\$€£¥R\$]?\s*\d+[\.,]\d{2}).{0,40}?(Now|Current|Price)\s*([\$€£¥R\$]?\s*\d+[\.,]\d{2})", text, flags=re.IGNORECASE)
            if was_now:
                msrp = float(MONEY_RE.search(was_now.group(2)).group(1).replace(",", "."))
                current = float(MONEY_RE.search(was_now.group(4)).group(1).replace(",", "."))
                currency_guess = None
                return msrp, current, currency_guess

            # Otherwise, just grab the first two money-like numbers
            nums = MONEY_RE.findall(text)
            nums = [n.replace(",", ".") for n in nums if n]
            msrp = float(nums[0]) if len(nums) >= 1 else None
            current = float(nums[1]) if len(nums) >= 2 else msrp
            return msrp, current, None
        except Exception:
            return None, None, None

    def calc_discount(msrp: Optional[float], current: Optional[float]) -> Optional[float]:
        if msrp is None or current is None or msrp <= 0:
            return None
        return round(100 * (1 - (current / msrp)), 2)

    def resolve_by_search(title_query: str, locale: str) -> Optional[str]:
        """
        Minimal search fallback: tries the public search page and returns the first product URL.
        Note: This is best-effort and may break if search page structure changes.
        """
        try:
            search_url = f"https://store.playstation.com/{locale}/search/{requests.utils.quote(title_query)}"
            html = fetch_html(search_url)
            if not html:
                return None
            next_data = parse_next_data(html)
            if not next_data:
                return None
            # Heuristic: find first product in props/pageProps that has a "productId" or "id" and build a product URL
            props = next_data.get("props", {})
            page_props = props.get("pageProps", {})
            results = page_props.get("results") or page_props.get("searchResults") or page_props.get("items") or []
            if isinstance(results, list):
                for item in results:
                    pid = item.get("id") or item.get("productId")
                    if pid:
                        return f"https://store.playstation.com/{locale}/product/{pid}"
            # Some schemas put results under nested keys
            for k, v in page_props.items():
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
        """
        For a given region (locale/country), fetch the product page and parse prices.
        product_ref may be a full URL or a product ID/concept ID.
        """
        url = build_product_url(locale, product_ref)
        html = fetch_html(url)

        # If 404 or invalid, try search if we have a title hint
        if not html and title_hint:
            alt_url = resolve_by_search(title_hint, locale)
            if alt_url:
                url = alt_url
                html = fetch_html(url)

        title = None
        pid = None
        msrp = None
        current = None
        currency = None

        if html:
            next_json = parse_next_data(html)
            if next_json:
                title, pid, msrp, current, currency, _ = extract_price_from_next_data(next_json)

            # Fallback heuristic if needed
            if current is None:
                msrp2, current2, currency_guess = very_naive_price_scrape(html)
                msrp = msrp if msrp is not None else msrp2
                current = current2 if current2 is not None else current
                currency = currency or currency_guess

        discount = calc_discount(msrp, current)

        return PriceInfo(
            currency=region_code,
            msrp=msrp,
            current_price=current,
            discount_percent=discount,
            region=region_code,
            locale=locale,
            country=country,
            title=title,
            product_id=pid,
            url=url
        )

    # ---------------------------
    # Streamlit UI
    # ---------------------------
    st.set_page_config(page_title="PlayStation Pricing (Regions)", page_icon="🎮", layout="centered")
    st.title("🎮 PlayStation Store — Regional Pricing Pull (MVP v1)")
    st.caption("GameRevenue.ai · Pulls pricing by region directly from public product pages. This app targets USD, GBP, EUR, JPY, BRL, CAD.")

    st.markdown("**Input a PlayStation product:** paste a Store URL _or_ a Product ID (e.g., `UP0006-PPSA02145_00-RESIDENTEVIL8000`).")
    product_ref = st.text_input("Product URL or Product ID", value="", placeholder="https://store.playstation.com/en-us/product/UP0006-PPSA02145_00-RESIDENTEVIL8000")

    title_hint = st.text_input("Optional: Title hint for fallback search", value="", placeholder="e.g., Helldivers 2")

    # Region selection (preselected to requested six)
    region_keys = ["USD", "GBP", "EUR", "JPY", "BRL", "CAD"]
    picked = st.multiselect("Regions to pull", region_keys, default=region_keys)

    run = st.button("Pull Prices")

    if run:
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

            # Build DataFrame
            rows = []
            main_title = None
            product_id_final = None
            for r in results:
                if r.title and not main_title:
                    main_title = r.title
                if r.product_id and not product_id_final:
                    product_id_final = r.product_id
                rows.append({
                    "Region": f"{r.region} ({r.locale.upper()})",
                    "Country": r.country,
                    "Currency": r.region,
                    "MSRP": r.msrp,
                    "Current Price": r.current_price,
                    "Discount %": r.discount_percent,
                    "Product URL": r.url
                })
            df = pd.DataFrame(rows)

            if main_title or product_id_final:
                st.subheader(main_title or "")
                if product_id_final:
                    st.caption(f"Product ID: `{product_id_final}`")

            st.dataframe(df, use_container_width=True)

            # Show simple notes / debugging aids
            st.markdown("##### Notes")
            st.markdown(
                "- If some regions return `None`, the product may be unavailable there, or the page schema is different.
"
                "- The parser first tries the embedded Next.js JSON, then falls back to heuristics.
"
                "- If PlayStation updates their store again, adjust `extract_price_from_next_data`."
            )

            # Allow CSV export
            st.download_button(
                "Download CSV",
                df.to_csv(index=False).encode("utf-8"),
                file_name="ps_prices.csv",
                mime="text/csv"
            )
