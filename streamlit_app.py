# streamlit_app.py
# ------------------------------------------------------------
# AAA Pricing Tier Composer for Xbox + Steam (All Markets)
# - Steam pulls: store.steampowered.com "appdetails" (use Steam-specific cc mapping)
# - Xbox pulls: displaycatalog/storesdk (use Xbox-specific locale mapping)
# - HELLDIVERS 2 scaled by (price/4)*7
# - Composite per-country recommendations (Xbox / Steam) + vanity endings
# - Parallel fetching for speed, CSV export, and a country_name column
# ------------------------------------------------------------

import random
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed

# -----------------------------
# App Config
# -----------------------------
st.set_page_config(page_title="AAA Tier Pricing Composer (Xbox + Steam)", page_icon="🎮", layout="wide")
st.title("🎮 AAA Tier Pricing Composer — Xbox + Steam (All Markets)")
st.caption("Steam pulls use Steam-specific country codes; Xbox pulls use Xbox-specific locales. HELLDIVERS 2 is scaled by (price/4)*7.")

# -----------------------------
# Country names (for display/export)
# -----------------------------
COUNTRY_NAMES: Dict[str, str] = {
    # Americas
    "US":"United States","CA":"Canada","MX":"Mexico","BR":"Brazil","AR":"Argentina","CL":"Chile","CO":"Colombia",
    "PE":"Peru","UY":"Uruguay","PY":"Paraguay","EC":"Ecuador","CR":"Costa Rica","PA":"Panama",
    "DO":"Dominican Republic","GT":"Guatemala","HN":"Honduras","NI":"Nicaragua","SV":"El Salvador",
    # Europe
    "GB":"United Kingdom","IE":"Ireland","FR":"France","DE":"Germany","IT":"Italy","ES":"Spain","PT":"Portugal",
    "NL":"Netherlands","BE":"Belgium","LU":"Luxembourg","AT":"Austria","CH":"Switzerland","DK":"Denmark","SE":"Sweden",
    "NO":"Norway","FI":"Finland","PL":"Poland","CZ":"Czechia","SK":"Slovakia","HU":"Hungary","RO":"Romania",
    "BG":"Bulgaria","GR":"Greece","EE":"Estonia","LV":"Latvia","LT":"Lithuania","MT":"Malta","CY":"Cyprus","UA":"Ukraine",
    # Middle East & Africa
    "TR":"Türkiye","IL":"Israel","SA":"Saudi Arabia","AE":"United Arab Emirates","QA":"Qatar","KW":"Kuwait","BH":"Bahrain",
    "OM":"Oman","JO":"Jordan","EG":"Egypt","MA":"Morocco","ZA":"South Africa",
    # Asia-Pacific
    "JP":"Japan","KR":"South Korea","TW":"Taiwan","HK":"Hong Kong","SG":"Singapore","MY":"Malaysia",
    "TH":"Thailand","ID":"Indonesia","PH":"Philippines","VN":"Vietnam","IN":"India","AU":"Australia","NZ":"New Zealand",
}

def country_name(code: str) -> str:
    return COUNTRY_NAMES.get(code.upper(), code.upper())

# -----------------------------
# Platform-specific market code maps (from user's sheet)
# -----------------------------
# STEAM: map our ISO input -> Steam's accepted "cc" code
STEAM_CC_MAP: Dict[str, str] = {
    # Americas / APAC / EMEA (based on screenshot)
    "US":"US","KZ":"KZ","CN":"CN","UA":"UA","ID":"ID","AR":"AR","TR":"TR","BR":"BR","CL":"CL","IN":"IN","KR":"KR","PH":"PH",
    "JP":"JP","VN":"VN","CO":"CO","NZ":"NZ","CR":"CR","SA":"SA","TW":"TW","SK":"SK","PE":"PE","PL":"PL","SG":"SG","ZA":"ZA",
    "HK":"HK","MX":"MX","GB":"GB","CA":"CA","AU":"AU","MY":"MY","FR":"FR","DE":"FR","AT":"FR","BE":"FR","DK":"FR","FI":"FR",
    "IE":"FR","NL":"FR","PT":"FR","ES":"FR","CZ":"FR","GR":"FR","HU":"FR","TH":"TH","UY":"UY","QA":"QA","KW":"KW","AE":"AE",
    "SV":"SV","PK":"PK","AM":"AM","CH":"CH","IL":"IL","RU":"RU",
}

# XBOX: map our ISO input -> Xbox locale (e.g., en-us, pt-br)
XBOX_LOCALE_MAP: Dict[str, str] = {
    "US":"en-us","KZ":None,"CN":"zh-CN","UA":"uk-ua","ID":"id-id","AR":"es-ar","TR":"tr-tr","BR":"pt-br","CL":"es-cl",
    "IN":"en-in","KR":"ko-kr","PH":"en-ph","JP":"ja-jp","VN":"vi-vn","CO":"es-co","NZ":"en-nz","CR":"es-cr","SA":"ar-sa",
    "SE":None,"TW":"zh-tw","SK":"sk-sk","PE":"es-pe","PL":"pl-pl","SG":"en-sg","ZA":"en-za","HK":"zh-hk","MX":"es-mx",
    "GB":"en-gb","CA":"en-ca","AU":"en-au","MY":"en-my","FR":"fr-fr","DE":"de-de","AT":"de-at","BE":"fr-fr","DK":None,
    "FI":"fi-fi","IE":"en-ie","NL":"nl-nl","PT":"pt-pt","ES":"es-es","CZ":"cs-cz","GR":"el-gr","HU":"hu-hu","TH":"th-th",
    "UY":None,"QA":"ar-qa","KW":"ar-kw","AE":"ar-ae","SV":None,"PK":None,"AM":None,"CH":"de-ch","IL":"he-il","RU":"ru-ru",
}

def xbox_locale_for(market: str) -> str:
    # If mapping is None, fall back to our general locale table or en-US
    code = XBOX_LOCALE_MAP.get(market.upper())
    if not code:
        return {
            "US":"en-us","CA":"en-ca","GB":"en-gb","AU":"en-au","NZ":"en-nz","IE":"en-ie",
            "MX":"es-mx","AR":"es-ar","CL":"es-cl","CO":"es-co","ES":"es-es","PE":"es-pe","CR":"es-cr",
            "BR":"pt-br","PT":"pt-pt",
            "FR":"fr-fr","BE":"fr-fr","CH":"de-ch","DE":"de-de","AT":"de-at","NL":"nl-nl","IT":"it-it",
            "JP":"ja-jp","KR":"ko-kr","TW":"zh-tw","HK":"zh-hk","CN":"zh-cn",
            "PL":"pl-pl","CZ":"cs-cz","SK":"sk-sk","HU":"hu-hu","GR":"el-gr","FI":"fi-fi","DK":"da-dk","SE":"sv-se",
            "TR":"tr-tr","IL":"he-il","AE":"ar-ae","QA":"ar-qa","KW":"ar-kw","SA":"ar-sa","ZA":"en-za","RU":"ru-ru",
            "IN":"en-in","SG":"en-sg","MY":"en-my","PH":"en-ph","TH":"th-th","VN":"vi-vn","ID":"id-id",
        }.get(market.upper(), "en-us")
    return code

def steam_cc_for(market: str) -> str:
    return STEAM_CC_MAP.get(market.upper(), market.upper())

# -----------------------------
# Game IDs
# -----------------------------
STEAM_APPIDS: Dict[str, str] = {
    "The Outer Worlds 2": "1449110",
    "Madden NFL 26": "3230400",
    "Call of Duty: Black Ops 6": "2933620",
    "NBA 2K26": "3472040",
    "Borderlands 4": "1285190",
    "HELLDIVERS 2": "553850",
}

XBOX_PRODUCT_IDS: Dict[str, str] = {
    "The Outer Worlds 2": "9P8RMKXRML7D",
    "Madden NFL 26": "9NVD16NP4J8T",  # alt: 9PGVZ5XPQ9SP
    "Call of Duty: Black Ops 6": "9PNCL2R6G8D0",
    "NBA 2K26": "9NFKCJNBR34N",
    "Borderlands 4": "9MX6HKF5647G",
    "HELLDIVERS 2": "9P3PT7PQJD0M",
}

XBOX_PRODUCT_ALIASES: Dict[str, List[str]] = {
    "Madden NFL 26": ["9NVD16NP4J8T", "9PGVZ5XPQ9SP"],
    "Call of Duty: Black Ops 6": ["9PNCL2R6G8D0"],
    # If you discover OW2/NBA2K26 alternates for NZ/AU, add them here:
    # "The Outer Worlds 2": ["<alt-id>"],
    # "NBA 2K26": ["<alt-id>"],
}

# -----------------------------
# Other constants
# -----------------------------
ZERO_DEC_CURRENCIES = {"JPY","KRW","VND","CLP","ISK"}
VANITY_RULES = {"AU":{"suffix":0.95,"nines":True},"NZ":{"suffix":0.95,"nines":True},"CA":{"suffix":0.99,"nines":True}}

# -----------------------------
# Helpers
# -----------------------------
@dataclass
class PriceRow:
    platform: str
    title: str
    country: str  # ISO-2 we keyed by
    currency: Optional[str]
    price: Optional[float]
    source_url: Optional[str]

def _nearest_x9_suffix(price: float, cents_suffix: float) -> float:
    base_tens = int(price // 10); cand = []
    for k in range(base_tens-2, base_tens+3):
        x = 10*k + 9 + cents_suffix
        if x > 0: cand.append(x)
    return round(min(cand, key=lambda v: (abs(v-price), -v)), 2)

def apply_vanity(country: str, price: float) -> float:
    rule = VANITY_RULES.get(country.upper())
    if rule and rule.get("nines"):
        return _nearest_x9_suffix(float(price), float(rule["suffix"]))
    return round(price, 2)

# -----------------------------
# Steam fetcher
# -----------------------------
STEAM_APPDETAILS = "https://store.steampowered.com/api/appdetails"

def fetch_steam_price(appid: str, cc_iso: str, forced_title: Optional[str] = None) -> Optional[PriceRow]:
    try:
        cc = steam_cc_for(cc_iso)
        params = {"appids": appid, "cc": cc, "l": "en", "filters": "price_overview"}
        r = requests.get(STEAM_APPDETAILS, params=params, timeout=20)
        data = r.json().get(str(appid), {})
        if not data or not data.get("success"): return None
        pov = (data.get("data") or {}).get("price_overview") or {}
        cents = pov.get("initial") if isinstance(pov.get("initial"), int) and pov.get("initial")>0 else pov.get("final")
        if not isinstance(cents, int) or cents<=0: return None
        price = round(cents/100.0, 2); currency = pov.get("currency"); name = forced_title or (data.get("data") or {}).get("name") or f"Steam App {appid}"
        return PriceRow("Steam", name, cc_iso.upper(), str(currency).upper() if currency else None, price, f"https://store.steampowered.com/app/{appid}")
    except Exception:
        return None

# -----------------------------
# Xbox fetcher
# -----------------------------
STORESDK_URL = "https://storeedgefd.dsx.mp.microsoft.com/v9.0/sdk/products"
DISPLAYCATALOG_URL = "https://displaycatalog.mp.microsoft.com/v7.0/products"

def _ms_cv() -> str:
    import string
    return "".join(random.choice(string.ascii_letters+string.digits) for _ in range(24))

def _parse_xbox_price_from_products(payload: dict) -> Tuple[Optional[float], Optional[str]]:
    try:
        products = payload.get("Products") or payload.get("products")
        if not products: return None, None
        p0 = products[0]
        dsa = p0.get("DisplaySkuAvailabilities") or p0.get("displaySkuAvailabilities") or []
        for sku in dsa:
            avs = sku.get("Availabilities") or sku.get("availabilities") or []
            for av in avs:
                omd = av.get("OrderManagementData") or av.get("orderManagementData") or {}
                price = omd.get("Price") or omd.get("price") or {}
                amount = price.get("MSRP") or price.get("msrp") or price.get("ListPrice") or price.get("listPrice")
                currency = price.get("CurrencyCode") or price.get("currencyCode")
                if amount:
                    try: return float(amount), (str(currency).upper() if currency else None)
                    except Exception: pass
        return None, None
    except Exception:
        return None, None

def fetch_xbox_price_one_market(product_id: str, market_iso: str, locale: str) -> Optional[Tuple[float, str]]:
    headers = {"MS-CV": _ms_cv(), "Accept": "application/json"}
    try:
        r = requests.get(STORESDK_URL, params={"bigIds": product_id, "market": market_iso.upper(), "locale": locale}, headers=headers, timeout=20)
        if r.status_code == 200:
            amt, ccy = _parse_xbox_price_from_products(r.json())
            if amt: return amt, ccy
    except Exception:
        pass
    try:
        r = requests.get(DISPLAYCATALOG_URL, params={"bigIds": product_id, "market": market_iso.upper(), "languages": locale, "fieldsTemplate": "Details"}, headers=headers, timeout=20)
        if r.status_code == 200:
            amt, ccy = _parse_xbox_price_from_products(r.json())
            if amt: return amt, ccy
    except Exception:
        pass
    return None

def fetch_xbox_price(product_name: str, product_id: str, market_iso: str) -> Optional[PriceRow]:
    ids = [product_id] + XBOX_PRODUCT_ALIASES.get(product_name, [])[1:]
    loc = xbox_locale_for(market_iso)
    for pid in ids:
        got = fetch_xbox_price_one_market(pid, market_iso, loc)
        if got:
            amt, ccy = got
            return PriceRow("Xbox", product_name, market_iso.upper(), ccy.upper() if ccy else None, float(amt), f"https://www.xbox.com/{loc.split('-')[0]}/games/store/placeholder/{pid}")
    # fallback to en-US
    for pid in ids:
        got = fetch_xbox_price_one_market(pid, market_iso, "en-US")
        if got:
            amt, ccy = got
            return PriceRow("Xbox", product_name, market_iso.upper(), ccy.upper() if ccy else None, float(amt), f"https://www.xbox.com/en-US/games/store/placeholder/{pid}")
    return None

# -----------------------------
# Basket & normalization
# -----------------------------
BASKET_TITLES = ["The Outer Worlds 2","Madden NFL 26","Call of Duty: Black Ops 6","NBA 2K26","Borderlands 4","HELLDIVERS 2"]

def normalize_row(row: PriceRow) -> PriceRow:
    if row.title.lower().startswith("helldivers 2") and row.price is not None:
        return PriceRow(row.platform, row.title+" (scaled)", row.country, row.currency, round((row.price/4.0)*7.0, 2), row.source_url)
    return row

# -----------------------------
# Sidebar controls
# -----------------------------
with st.sidebar:
    st.header("Controls")

    # Market list entry
    default_markets = ",".join(sorted(COUNTRY_NAMES.keys()))
    user_markets = st.text_area("Markets (comma-separated ISO country codes)", value=default_markets, height=140)
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
# Run + output
# -----------------------------
if run:
    rows: List[PriceRow] = []
    with st.status("Pulling prices across markets…", expanded=False) as status:
        futures = []
        with ThreadPoolExecutor(max_workers=14) as ex:
            # Steam jobs
            for cc in markets:
                for title in BASKET_TITLES:
                    appid = STEAM_APPIDS.get(title)
                    if appid: futures.append(ex.submit(fetch_steam_price, appid, cc, title))
            # Xbox jobs
            for cc in markets:
                for title in BASKET_TITLES:
                    pid = XBOX_PRODUCT_IDS.get(title)
                    if pid: futures.append(ex.submit(fetch_xbox_price, title, pid, cc))

            for f in as_completed(futures):
                try: r = f.result()
                except Exception: r = None
                if r: rows.append(normalize_row(r))

        if not rows:
            status.update(label="No data returned — check IDs or try fewer markets.", state="error")
            st.stop()
        status.update(label="Done!", state="complete")

    raw_df = pd.DataFrame([asdict(r) for r in rows])
    # Insert human-readable name before 'country'
    raw_df.insert(2, "country_name", raw_df["country"].map(country_name))

    # Recommendations per platform
    reco = (raw_df.groupby(["platform","country","currency"], dropna=False)["price"]
                 .mean().reset_index().rename(columns={"price":"RecommendedPrice"}))
    reco.insert(1, "country_name", reco["country"].map(country_name))

    reco_xbox  = reco[reco["platform"]=="Xbox"][["country_name","country","currency","RecommendedPrice"]].reset_index(drop=True)
    reco_steam = reco[reco["platform"]=="Steam"][["country_name","country","currency","RecommendedPrice"]].reset_index(drop=True)

    # Vanity rounding by country
    if not reco_xbox.empty:
        reco_xbox["RecommendedPrice"]  = [apply_vanity(c,p) for c,p in zip(reco_xbox["country"],  reco_xbox["RecommendedPrice"])]
    if not reco_steam.empty:
        reco_steam["RecommendedPrice"] = [apply_vanity(c,p) for c,p in zip(reco_steam["country"], reco_steam["RecommendedPrice"])]

    st.subheader("Raw Basket Rows (after normalization)")
    st.dataframe(raw_df)

    st.subheader("Price Recommendations — Xbox (per country)")
    st.dataframe(reco_xbox)

    st.subheader("Price Recommendations — Steam (per country)")
    st.dataframe(reco_steam)

    merged = pd.merge(
        reco_xbox.rename(columns={"RecommendedPrice":"XboxRecommended"}),
        reco_steam.rename(columns={"RecommendedPrice":"SteamRecommended"}),
        on=["country_name","country","currency"],
        how="outer",
    ).sort_values(["country"]).reset_index(drop=True)

    st.subheader("Combined Recommendations (Xbox + Steam)")
    st.dataframe(merged)

    csv = merged.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV (combined recommendations)", data=csv, file_name="aaa_tier_recommendations_xbox_steam.csv", mime="text/csv")
else:
    st.info("Configure IDs/markets in the sidebar, then click **Run Pricing Pull** to generate recommendations.", icon="🛠️")
