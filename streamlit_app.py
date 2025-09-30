# streamlit_app.py
# ------------------------------------------------------------
# AAA Pricing Tier Composer for Xbox + Steam (All Markets)
# - Pulls live prices from Steam (store.steampowered.com API)
# - Pulls live prices from Xbox Store (displaycatalog / storesdk endpoints)
# - Normalizes Helldivers 2 by (local_price / 4) * 7 to scale $39.99 -> $69.99 equivalent
# - Computes composite per-country recommendations separately for Xbox and Steam
# - Exports a CSV and shows interactive tables in UI
# ------------------------------------------------------------

import math
import random
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st

# -----------------------------
# App Config
# -----------------------------
st.set_page_config(
    page_title="AAA Tier Pricing Composer (Xbox + Steam)",
    page_icon="🎮",
    layout="wide",
)

st.title("🎮 AAA Tier Pricing Composer — Xbox + Steam (All Markets)")
st.caption(
    "Live pulls from Steam (Store API) and Xbox Store. Helldivers 2 is scaled by (price/4)*7 to normalize to a $69.99 basket."
)

# -----------------------------
# Models
# -----------------------------
@dataclass
class PriceRow:
    platform: str  # "Steam" or "Xbox"
    title: str
    country: str  # 2-letter market/cc (e.g., US, GB)
    currency: Optional[str]
    price: Optional[float]
    source_url: Optional[str]


# -----------------------------
# Constants / Defaults
# -----------------------------
# Steam appids for our basket games (validated as of 2025-09-29)
STEAM_APPIDS: Dict[str, str] = {
    "The Outer Worlds 2": "1449110",
    "Madden NFL 26": "3230400",
    "Call of Duty: Black Ops 6": "2933620",
    "NBA 2K26": "3472040",
    "Borderlands 4": "1285190",
    "HELLDIVERS 2": "553850",  # note: will be scaled in normalization
}

# Xbox Store product IDs (StoreId / BigId in page URLs); standard/base editions where possible
XBOX_PRODUCT_IDS: Dict[str, str] = {
    "The Outer Worlds 2": "9P8RMKXRML7D",
    "Madden NFL 26": "9NVD16NP4J8T",  # alt listing seen: 9PGVZ5XPQ9SP — app tries both
    "Call of Duty: Black Ops 6": "9PNCL2R6G8D0",  # Windows listing shown in URL; used for price where available
    "NBA 2K26": "9NFKCJNBR34N",
    "Borderlands 4": "9MX6HKF5647G",
    "HELLDIVERS 2": "9P3PT7PQJD0M",  # Xbox Series X|S
}

# If a product id appears to vary by edition/PC/console, the fetcher will try known alternates here
XBOX_PRODUCT_ALIASES: Dict[str, List[str]] = {
    "Madden NFL 26": ["9NVD16NP4J8T", "9PGVZ5XPQ9SP"],
    "Call of Duty: Black Ops 6": ["9PNCL2R6G8D0"],
}

# Markets: "all available" — curated set commonly supported by both platforms
# You can paste a custom list in the sidebar if desired.
ALL_MARKETS: List[str] = [
    # Americas
    "US","CA","MX","BR","AR","CL","CO","PE","UY","PY","EC","BO","CR","PA","DO","GT","HN","NI","SV","JM","TT","BS","BZ","BB","AW","AG","AI","BM","KY","MQ","GP","GF",
    # Europe
    "GB","IE","FR","DE","IT","ES","PT","NL","BE","LU","AT","CH","DK","SE","NO","FI","IS","PL","CZ","SK","HU","RO","BG","GR","SI","HR","RS","BA","MK","AL","EE","LV","LT","MT","CY","UA",
    # Middle East & Africa
    "TR","IL","SA","AE","QA","KW","BH","OM","JO","EG","MA","TN","ZA","NG","KE",
    # Asia-Pacific
    "JP","KR","TW","HK","SG","MY","TH","ID","PH","VN","IN","AU","NZ"
]

# Zero-decimal currencies (no minor unit) — for display/formatting if detected
ZERO_DEC_CURRENCIES = {"JPY", "KRW", "VND", "CLP", "ISK"}

# -----------------------------
# Helpers
# -----------------------------

def _sleep_human(min_s: float = 0.6, max_s: float = 1.3):
    time.sleep(random.uniform(min_s, max_s))


def format_price(amount: Optional[float], currency: Optional[str]) -> str:
    if amount is None:
        return "—"
    if not currency:
        return f"{amount:,.2f}"
    if currency.upper() in ZERO_DEC_CURRENCIES:
        return f"{int(round(amount)):,} {currency.upper()}"
    return f"{amount:,.2f} {currency.upper()}"


# -----------------------------
# Steam Fetcher (Store API — appdetails)
# -----------------------------
STEAM_APPDETAILS = "https://store.steampowered.com/api/appdetails"


def fetch_steam_price(appid: str, cc: str, forced_title: Optional[str] = None) -> Optional[PriceRow]:
    try:
        params = {
            "appids": appid,
            "cc": cc,
            "l": "en",
            "filters": "price_overview",
        }
        r = requests.get(STEAM_APPDETAILS, params=params, timeout=20)
        data = r.json().get(str(appid), {})
        if not data or not data.get("success"):
            return None
        body = data.get("data", {})
        pov = body.get("price_overview") or {}
        # Prefer 'initial' cents (MSRP) when present; else 'final'
        cents = pov.get("initial") if isinstance(pov.get("initial"), int) and pov.get("initial") > 0 else pov.get("final")
        if not isinstance(cents, int) or cents <= 0:
            return None
        price = round(cents / 100.0, 2)
        currency = pov.get("currency")
        name = forced_title or body.get("name") or f"Steam App {appid}"
        return PriceRow(
            platform="Steam",
            title=name,
            country=cc.upper(),
            currency=str(currency).upper() if currency else None,
            price=price,
            source_url=f"https://store.steampowered.com/app/{appid}",
        )
    except Exception:
        return None


# -----------------------------
# Xbox Fetcher (displaycatalog / storesdk)
# -----------------------------
# We'll try the newer storesdk endpoint first; if it fails, fallback to displaycatalog v7.0
# Note: Some requests may require the MS-CV header; we include a random value.

STORESDK_URL = "https://storeedgefd.dsx.mp.microsoft.com/v9.0/sdk/products"
DISPLAYCATALOG_URL = "https://displaycatalog.mp.microsoft.com/v7.0/products"


def _ms_cv() -> str:
    # lightweight CV token (opaque) — not authenticated
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.choice(alphabet) for _ in range(24))


def _parse_xbox_price_from_products(payload: dict) -> Tuple[Optional[float], Optional[str]]:
    try:
        products = payload.get("Products") or payload.get("products")
        if not products:
            return None, None
        # Walk the first product's first availability price
        p0 = products[0]
        dsa = p0.get("DisplaySkuAvailabilities") or p0.get("displaySkuAvailabilities") or []
        if not dsa:
            return None, None
        # choose the first SKU availability that has a price
        for sku in dsa:
            avs = sku.get("Availabilities") or sku.get("availabilities") or []
            for av in avs:
                omd = av.get("OrderManagementData") or av.get("orderManagementData") or {}
                price = omd.get("Price") or omd.get("price") or {}
                amount = price.get("ListPrice") or price.get("listPrice") or price.get("MSRP") or price.get("msrp")
                currency = price.get("CurrencyCode") or price.get("currencyCode")
                if amount:
                    try:
                        return float(amount), (str(currency).upper() if currency else None)
                    except Exception:
                        pass
        return None, None
    except Exception:
        return None, None


def fetch_xbox_price_one_market(product_id: str, market: str, locale: str = "en-US") -> Optional[Tuple[float, str]]:
    headers = {"MS-CV": _ms_cv(), "Accept": "application/json"}
    # Try storesdk v9
    try:
        params = {"bigIds": product_id, "market": market.upper(), "locale": locale}
        r = requests.get(STORESDK_URL, params=params, headers=headers, timeout=20)
        if r.status_code == 200:
            amount, ccy = _parse_xbox_price_from_products(r.json())
            if amount:
                return amount, ccy
    except Exception:
        pass
    # Fallback to displaycatalog v7
    try:
        params = {"bigIds": product_id, "market": market.upper(), "languages": locale, "fieldsTemplate": "Details"}
        r = requests.get(DISPLAYCATALOG_URL, params=params, headers=headers, timeout=20)
        if r.status_code == 200:
            amount, ccy = _parse_xbox_price_from_products(r.json())
            if amount:
                return amount, ccy
    except Exception:
        pass
    return None


def fetch_xbox_price(product_name: str, product_id: str, market: str, locale: str = "en-US") -> Optional[PriceRow]:
    # Try aliases if present (some titles have multiple IDs for regions/editions)
    ids_to_try = [product_id] + XBOX_PRODUCT_ALIASES.get(product_name, [])[1:]
    for pid in ids_to_try:
        got = fetch_xbox_price_one_market(pid, market=market, locale=locale)
        if got:
            amount, ccy = got
            return PriceRow(
                platform="Xbox",
                title=product_name,
                country=market.upper(),
                currency=ccy.upper() if ccy else None,
                price=float(amount),
                source_url=f"https://www.xbox.com/en-US/games/store/placeholder/{pid}",
            )
    return None


# -----------------------------
# Normalization / Composite
# -----------------------------

BASKET_TITLES = [
    "The Outer Worlds 2",
    "Madden NFL 26",
    "Call of Duty: Black Ops 6",
    "NBA 2K26",
    "Borderlands 4",
    "HELLDIVERS 2",  # will be scaled
]


def normalize_row(row: PriceRow) -> PriceRow:
    """Apply Helldivers scaling (price/4)*7 if applicable. Others pass-through."""
    if row.title.strip().lower().startswith("helldivers 2"):
        try:
            if row.price is not None:
                row = PriceRow(
                    platform=row.platform,
                    title=row.title + " (scaled)",
                    country=row.country,
                    currency=row.currency,
                    price=round((row.price / 4.0) * 7.0, 2),
                    source_url=row.source_url,
                )
        except Exception:
            pass
    return row


def compute_recommendations(markets: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns: (raw_rows_df, per_country_reco_xbox, per_country_reco_steam)"""
    rows: List[PriceRow] = []

    # Pull Steam first
    for cc in markets:
        for title in BASKET_TITLES:
            appid = STEAM_APPIDS.get(title)
            if not appid:
                continue
            r = fetch_steam_price(appid, cc=cc, forced_title=title)
            if r:
                rows.append(normalize_row(r))
            _sleep_human()

    # Pull Xbox
    for cc in markets:
        for title in BASKET_TITLES:
            pid = XBOX_PRODUCT_IDS.get(title)
            if not pid:
                continue
            r = fetch_xbox_price(title, product_id=pid, market=cc, locale="en-US")
            if r:
                rows.append(normalize_row(r))
            _sleep_human()

    # Assemble DataFrame
    df = pd.DataFrame([asdict(r) for r in rows])
    if df.empty:
        return df, pd.DataFrame(), pd.DataFrame()

    # Compute per platform per country recommendations (mean of available items)
    reco = (
        df.groupby(["platform", "country", "currency"], dropna=False)["price"]
        .mean()
        .reset_index()
        .rename(columns={"price": "RecommendedPrice"})
    )

    # Split into Xbox and Steam tables for clarity
    reco_xbox = reco[reco["platform"] == "Xbox"]["country currency RecommendedPrice".split()].reset_index(drop=True)
    reco_steam = reco[reco["platform"] == "Steam"]["country currency RecommendedPrice".split()].reset_index(drop=True)

    return df, reco_xbox, reco_steam


# -----------------------------
# UI — Controls
# -----------------------------
with st.sidebar:
    st.header("Controls")
    default_markets_text = ",".join(ALL_MARKETS)
    user_markets = st.text_area(
        "Markets (comma-separated ISO country codes)",
        value=default_markets_text,
        height=120,
        help="Use two-letter country codes (e.g., US, GB, BR). Leave as-is for a broad default set.",
    )
    markets = [m.strip().upper() for m in user_markets.split(",") if m.strip()]

    st.subheader("Game IDs (override if needed)")
    st.caption("Steam AppIDs")
    for k, v in list(STEAM_APPIDS.items()):
        STEAM_APPIDS[k] = st.text_input(f"Steam — {k}", value=v)

    st.caption("Xbox Product IDs (StoreId)")
    for k, v in list(XBOX_PRODUCT_IDS.items()):
        XBOX_PRODUCT_IDS[k] = st.text_input(f"Xbox — {k}", value=v)

    st.divider()
    run = st.button("Run Pricing Pull", type="primary")

# -----------------------------
# Execute & Display
# -----------------------------
if run:
    with st.status("Pulling prices across markets…", expanded=False) as status:
        raw_df, xbox_df, steam_df = compute_recommendations(markets)
        if raw_df.empty:
            status.update(label="No data returned — check IDs or try fewer markets.", state="error")
            st.stop()
        status.update(label="Done!", state="complete")

    st.subheader("Raw Basket Rows (after normalization)")
    st.dataframe(raw_df)

    # Two separate price recommendations per country
    st.subheader("Price Recommendations — Xbox (per country)")
    st.dataframe(xbox_df)

    st.subheader("Price Recommendations — Steam (per country)")
    st.dataframe(steam_df)

    # Merge for one export with two columns if desired
    merged = pd.merge(
        xbox_df.rename(columns={"RecommendedPrice": "XboxRecommended"}),
        steam_df.rename(columns={"RecommendedPrice": "SteamRecommended"}),
        on=["country", "currency"],
        how="outer",
        suffixes=("_Xbox", "_Steam"),
    ).sort_values(["country"]).reset_index(drop=True)

    st.subheader("Combined Recommendations (Xbox + Steam)")
    st.dataframe(merged)

    csv = merged.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download CSV (combined recommendations)",
        data=csv,
        file_name="aaa_tier_recommendations_xbox_steam.csv",
        mime="text/csv",
    )

else:
    st.info(
        "Configure IDs/markets in the sidebar, then click **Run Pricing Pull** to generate recommendations.",
        icon="🛠️",
    )

# -----------------------------
# Notes / Caveats (shown collapsed in UI)
# -----------------------------
with st.expander("Implementation Notes & Caveats"):
    st.markdown(
        """
        - **Steam** uses the official Store endpoint `api/appdetails` with `filters=price_overview` (prefers `initial` cents when available).
        - **Xbox** fetch tries the `storesdk` v9 endpoint first, then falls back to the `displaycatalog` v7 endpoint; both are public-facing endpoints used by Microsoft Store.
        - **Helldivers 2 scaling**: For each country, we compute `(local_price / 4) * 7` to normalize the $39.99 title to a $69.99-equivalent contribution in the basket.
        - **Composite method**: Simple mean of available basket items by platform/country. You can change this to median/trimmed mean easily.
        - **Currency formatting**: Zero-decimal currencies (JPY/KRW/VND/CLP/ISK) are rendered without decimals; others use two decimals for display.
        - **Throughput**: API calls are rate-limited with human sleeps. For very large market lists, consider increasing delays to reduce 429/ban risk.
        - **Edits**: If any Xbox StoreId differs per region/edition, paste the desired ID(s) in the sidebar. The app attempts known aliases for a couple of titles.
        """
    )
