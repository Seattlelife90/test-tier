# streamlit_app.py
# ------------------------------------------------------------
# AAA Pricing Tier Composer for Xbox + Steam (All Markets)
# - Pulls live prices from Steam (store.steampowered.com API)
# - Pulls live prices from Xbox Store (displaycatalog / storesdk endpoints)
# - Normalizes HELLDIVERS 2 by (local_price / 4) * 7 to scale $39.99 -> $69.99 equivalent
# - Computes composite per-country recommendations separately for Xbox and Steam
# - Applies vanity pricing rules (e.g., AU: xx9.95, CA: xx9.99) to recommendations
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
    "Live pulls from Steam (Store API) and Xbox Store. HELLDIVERS 2 is scaled by (price/4)*7 to normalize to a $69.99 basket."
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
# Steam appids for our basket games
STEAM_APPIDS: Dict[str, str] = {
    "The Outer Worlds 2": "1449110",
    "Madden NFL 26": "3230400",
    "Call of Duty: Black Ops 6": "2933620",
    "NBA 2K26": "3472040",
    "Borderlands 4": "1285190",
    "HELLDIVERS 2": "553850",  # scaled in normalization
}

# Xbox Store product IDs (StoreId / BigId)
XBOX_PRODUCT_IDS: Dict[str, str] = {
    "The Outer Worlds 2": "9P8RMKXRML7D",
    "Madden NFL 26": "9NVD16NP4J8T",  # alt listing seen: 9PGVZ5XPQ9SP — app tries both
    "Call of Duty: Black Ops 6": "9PNCL2R6G8D0",
    "NBA 2K26": "9NFKCJNBR34N",
    "Borderlands 4": "9MX6HKF5647G",
    "HELLDIVERS 2": "9P3PT7PQJD0M",
}

# Aliases (if a product id varies by edition/PC/console)
XBOX_PRODUCT_ALIASES: Dict[str, List[str]] = {
    "Madden NFL 26": ["9NVD16NP4J8T", "9PGVZ5XPQ9SP"],
    "Call of Duty: Black Ops 6": ["9PNCL2R6G8D0"],
}

# Markets: broad set commonly supported by both platforms
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

# Zero-decimal currencies
ZERO_DEC_CURRENCIES = {"JPY", "KRW", "VND", "CLP", "ISK"}

# Locale override per market (helps Xbox availability)
LOCALE_BY_MARKET: Dict[str, str] = {
    "US": "en-US", "CA": "en-CA", "GB": "en-GB", "AU": "en-AU", "NZ": "en-NZ",
    "MX": "es-MX", "BR": "pt-BR", "AR": "es-AR", "CL": "es-CL", "CO": "es-CO",
    "FR": "fr-FR", "DE": "de-DE", "IT": "it-IT", "ES": "es-ES", "PT": "pt-PT",
    "NL": "nl-NL", "BE": "nl-BE", "LU": "fr-LU", "IE": "en-IE",
    "JP": "ja-JP", "KR": "ko-KR", "TW": "zh-TW", "HK": "zh-HK", "SG": "en-SG",
}

# Vanity pricing rules per country
VANITY_RULES = {
    # AU example: 99.63 -> 99.95
    "AU": {"suffix": 0.95, "nines": True},  # xx9.95 closest
    # CA example: 89.36 -> 89.99
    "CA": {"suffix": 0.99, "nines": True},  # xx9.99 closest
    # NZ: match AU convention xx9.95
    "NZ": {"suffix": 0.95, "nines": True},
},  # xx9.95 closest
    # CA example: 89.36 -> 89.99
    "CA": {"suffix": 0.99, "nines": True},  # xx9.99 closest
}

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


def locale_for_market(market: str) -> str:
    return LOCALE_BY_MARKET.get(market.upper(), "en-US")


# Vanity rounding utilities

def _nearest_x9_suffix(price: float, cents_suffix: float) -> float:
    """Return the number closest to price that ends with 9.cents_suffix (e.g., 9.95 or 9.99)."""
    # consider candidates around the tens block of price
    base_tens = int(price // 10)
    candidates = []
    for k in range(base_tens - 2, base_tens + 3):
        cand = 10 * k + 9 + cents_suffix
        if cand > 0:
            candidates.append(cand)
    # choose candidate with minimal absolute diff; tie -> higher price (lean to up)
    best = min(candidates, key=lambda x: (abs(x - price), -x))
    return round(best, 2)


def apply_vanity(country: str, price: float) -> float:
    rule = VANITY_RULES.get(country.upper())
    if not rule:
        return round(price, 2)
    if rule.get("nines") and isinstance(rule.get("suffix"), float):
        return _nearest_x9_suffix(float(price), float(rule["suffix"]))
    return round(price, 2)


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
# ----------------------------- (displaycatalog / storesdk)
# -----------------------------
STORESDK_URL = "https://storeedgefd.dsx.mp.microsoft.com/v9.0/sdk/products"
DISPLAYCATALOG_URL = "https://displaycatalog.mp.microsoft.com/v7.0/products"


def _ms_cv() -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.choice(alphabet) for _ in range(24))


def _parse_xbox_price_from_products(payload: dict) -> Tuple[Optional[float], Optional[str]]:
    try:
        products = payload.get("Products") or payload.get("products")
        if not products:
            return None, None
        p0 = products[0]
        dsa = p0.get("DisplaySkuAvailabilities") or p0.get("displaySkuAvailabilities") or []
        if not dsa:
            return None, None
        for sku in dsa:
            avs = sku.get("Availabilities") or sku.get("availabilities") or []
            for av in avs:
                omd = av.get("OrderManagementData") or av.get("orderManagementData") or {}
                price = omd.get("Price") or omd.get("price") or {}
                # Prefer MSRP over ListPrice to avoid sale prices (e.g., MX 699 vs 1399)
                amount = price.get("MSRP") or price.get("msrp") or price.get("ListPrice") or price.get("listPrice")
                currency = price.get("CurrencyCode") or price.get("currencyCode")
                if amount:
                    try:
                        return float(amount), (str(currency).upper() if currency else None)
                    except Exception:
                        pass
        return None, None
    except Exception:
        return None, None


def fetch_xbox_price_one_market(product_id: str, market: str, locale: str) -> Optional[Tuple[float, str]]:
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


def fetch_xbox_price(product_name: str, product_id: str, market: str) -> Optional[PriceRow]:
    # Try a localized locale for the market; fallback to en-US
    loc = locale_for_market(market)
    ids_to_try = [product_id] + XBOX_PRODUCT_ALIASES.get(product_name, [])[1:]
    # Attempt with localized locale first
    for pid in ids_to_try:
        got = fetch_xbox_price_one_market(pid, market=market, locale=loc)
        if got:
            amount, ccy = got
            return PriceRow(
                platform="Xbox",
                title=product_name,
                country=market.upper(),
                currency=ccy.upper() if ccy else None,
                price=float(amount),
                source_url=f"https://www.xbox.com/{loc.split('-')[0]}/games/store/placeholder/{pid}",
            )
        _sleep_human(0.3, 0.7)
    # Fallback try with en-US locale in case localized one fails for certain regions
    for pid in ids_to_try:
        got = fetch_xbox_price_one_market(pid, market=market, locale="en-US")
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
        _sleep_human(0.3, 0.7)
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
    "HELLDIVERS 2",  # scaled
]


def normalize_row(row: PriceRow) -> PriceRow:
    """Apply HELLDIVERS scaling (price/4)*7 if applicable. Others pass-through."""
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

    # Pull Steam
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
            r = fetch_xbox_price(title, product_id=pid, market=cc)
            if r:
                rows.append(normalize_row(r))
            _sleep_human()

    # Assemble DataFrame
    df = pd.DataFrame([asdict(r) for r in rows])
    if df.empty:
        return df, pd.DataFrame(), pd.DataFrame()

    # Compute mean by platform/country/currency
    reco = (
        df.groupby(["platform", "country", "currency"], dropna=False)["price"].mean().reset_index().rename(columns={"price": "RecommendedPrice"})
    )

    # Split
    reco_xbox = reco[reco["platform"] == "Xbox"]["country currency RecommendedPrice".split()].reset_index(drop=True)
    reco_steam = reco[reco["platform"] == "Steam"]["country currency RecommendedPrice".split()].reset_index(drop=True)

    # Apply vanity rounding rules
    if not reco_xbox.empty:
        reco_xbox["RecommendedPrice"] = [apply_vanity(c, p) for c, p in zip(reco_xbox["country"], reco_xbox["RecommendedPrice"])]
    if not reco_steam.empty:
        reco_steam["RecommendedPrice"] = [apply_vanity(c, p) for c, p in zip(reco_steam["country"], reco_steam["RecommendedPrice"])]

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
    # --- Fast concurrent fetching (Steam + Xbox in parallel) ---
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def steam_jobs():
        for cc in markets:
            for title in BASKET_TITLES:
                appid = STEAM_APPIDS.get(title)
                if appid:
                    yield ("steam", cc, title, appid)

    def xbox_jobs():
        for cc in markets:
            for title in BASKET_TITLES:
                pid = XBOX_PRODUCT_IDS.get(title)
                if pid:
                    yield ("xbox", cc, title, pid)

    rows: List[PriceRow] = []

    with st.status("Pulling prices across markets…", expanded=False) as status:
        futures = []
        # Limit workers to be gentle; we still get a large speedup vs serial
        with ThreadPoolExecutor(max_workers=14) as ex:
            for kind, cc, title, val in list(steam_jobs()) + list(xbox_jobs()):
                if kind == "steam":
                    futures.append(ex.submit(fetch_steam_price, val, cc, title))
                else:
                    futures.append(ex.submit(fetch_xbox_price, title, val, cc))
            for f in as_completed(futures):
                r = f.result()
                if r:
                    rows.append(normalize_row(r))
        if not rows:
            status.update(label="No data returned — check IDs or try fewer markets.", state="error")
            st.stop()
        status.update(label="Done!", state="complete")

    raw_df = pd.DataFrame([asdict(r) for r in rows])

    # Compute recommendations
    reco = (
        raw_df.groupby(["platform", "country", "currency"], dropna=False)["price"].mean().reset_index().rename(columns={"price": "RecommendedPrice"})
    )

    reco_xbox = reco[reco["platform"] == "Xbox"]["country currency RecommendedPrice".split()].reset_index(drop=True)
    reco_steam = reco[reco["platform"] == "Steam"]["country currency RecommendedPrice".split()].reset_index(drop=True)

    # Vanity rounding
    if not reco_xbox.empty:
        reco_xbox["RecommendedPrice"] = [apply_vanity(c, p) for c, p in zip(reco_xbox["country"], reco_xbox["RecommendedPrice"])]
    if not reco_steam.empty:
        reco_steam["RecommendedPrice"] = [apply_vanity(c, p) for c, p in zip(reco_steam["country"], reco_steam["RecommendedPrice"])]

    st.subheader("Raw Basket Rows (after normalization)")
    st.dataframe(raw_df)

    st.subheader("Price Recommendations — Xbox (per country)")
    st.dataframe(reco_xbox)

    st.subheader("Price Recommendations — Steam (per country)")
    st.dataframe(reco_steam)

    merged = pd.merge(
        reco_xbox.rename(columns={"RecommendedPrice": "XboxRecommended"}),
        reco_steam.rename(columns={"RecommendedPrice": "SteamRecommended"}),
        on=["country", "currency"],
        how="outer",
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
# Notes / Caveats
# -----------------------------
with st.expander("Implementation Notes & Caveats"):
    st.markdown(
        """
        - **Steam**: `api/appdetails` with `filters=price_overview`; prefers `initial` (MSRP) when present.
        - **Xbox**: Prefers `MSRP` over `ListPrice`; tries localized locales (e.g., `en-AU`, `en-NZ`, `es-MX`) then falls back to `en-US`.
        - **HELLDIVERS 2 scaling**: `(local_price / 4) * 7`.
        - **Composite**: Mean of basket items by platform/country.
        - **Vanity rounding**: AU & NZ → nearest **xx9.95**; CA → **xx9.99**. Extend via `VANITY_RULES`.
        - **Performance**: Uses concurrent fetching (thread pool). If you see throttling, reduce `max_workers`.
        """
    ) when available.
        - **Xbox**: Prefer `MSRP` over `ListPrice` to avoid picking sale prices (e.g., MX 699 vs 1399). Also tries localized locales (e.g., `en-AU`, `es-MX`) and falls back to `en-US`.
        - **HELLDIVERS 2 scaling**: For each country, `(local_price / 4) * 7`.
        - **Composite**: Simple mean of available basket items by platform/country.
        - **Vanity rules**: AU → nearest **xx9.95**; CA → nearest **xx9.99**. Add more rules easily via `VANITY_RULES`.
        - Consider increasing delays or slicing markets to avoid rate-limits for very large pulls.
        """
    )
