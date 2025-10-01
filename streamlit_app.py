# streamlit_app.py
# ------------------------------------------------------------
# AAA Pricing Tier Composer (Xbox + Steam)
# - Editable baskets (add/remove titles per platform)
# - Platform-specific market codes (Steam cc vs Xbox locale)
# - Steam fallback to packagedetails when price_overview is missing
# - Xbox MSRP preference, locale-first + en-US fallback
# - Optional ALT Store IDs for OW2 / NBA2K26
# - Helldivers-style scaling flags per row (price/4*7)
# - Vanity endings (AU/NZ → …9.95; CA → …9.99)
# - Parallel fetching, diagnostics, country_name column, CSV export
# ------------------------------------------------------------

import json
import random
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Set

import pandas as pd
import requests
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed

# -----------------------------
# App Config
# -----------------------------
st.set_page_config(page_title="AAA Tier Pricing Composer (Xbox + Steam)", page_icon="🎮", layout="wide")
st.title("🎮 AAA Tier Pricing Composer — Xbox + Steam")
st.caption("Editable basket · Platform-true pulls · Helldivers scaling · Vanity endings")

# -----------------------------
# Country names (for display)
# -----------------------------
COUNTRY_NAMES: Dict[str, str] = {
    "US":"United States","CA":"Canada","MX":"Mexico","BR":"Brazil","AR":"Argentina","CL":"Chile","CO":"Colombia",
    "PE":"Peru","UY":"Uruguay","PY":"Paraguay","EC":"Ecuador","CR":"Costa Rica","PA":"Panama","DO":"Dominican Republic",
    "GT":"Guatemala","HN":"Honduras","NI":"Nicaragua","SV":"El Salvador",
    "GB":"United Kingdom","IE":"Ireland","FR":"France","DE":"Germany","IT":"Italy","ES":"Spain","PT":"Portugal",
    "NL":"Netherlands","BE":"Belgium","LU":"Luxembourg","AT":"Austria","CH":"Switzerland","DK":"Denmark","SE":"Sweden",
    "NO":"Norway","FI":"Finland","PL":"Poland","CZ":"Czechia","SK":"Slovakia","HU":"Hungary","RO":"Romania",
    "BG":"Bulgaria","GR":"Greece","EE":"Estonia","LV":"Latvia","LT":"Lithuania","MT":"Malta","CY":"Cyprus","UA":"Ukraine",
    "TR":"Türkiye","IL":"Israel","SA":"Saudi Arabia","AE":"United Arab Emirates","QA":"Qatar","KW":"Kuwait","BH":"Bahrain",
    "OM":"Oman","JO":"Jordan","EG":"Egypt","MA":"Morocco","ZA":"South Africa",
    "JP":"Japan","KR":"South Korea","TW":"Taiwan","HK":"Hong Kong","SG":"Singapore","MY":"Malaysia",
    "TH":"Thailand","ID":"Indonesia","PH":"Philippines","VN":"Vietnam","IN":"India","AU":"Australia","NZ":"New Zealand",
    "KZ":"Kazakhstan","CN":"China",
}
def country_name(code: str) -> str:
    return COUNTRY_NAMES.get(code.upper(), code.upper())

# -----------------------------
# Platform-specific market code maps (from your sheet)
# -----------------------------
# Steam cc mapping (yellow column)
STEAM_CC_MAP: Dict[str, str] = {
    "US":"US","KZ":"KZ","CN":"CN","UA":"UA","ID":"ID","AR":"AR","TR":"TR","BR":"BR","CL":"CL","IN":"IN","KR":"KR","PH":"PH",
    "JP":"JP","VN":"VN","CO":"CO","NZ":"NZ","CR":"CR","SA":"SA","TW":"TW","SK":"SK","PE":"PE","PL":"PL","SG":"SG","ZA":"ZA",
    "HK":"HK","MX":"MX","GB":"GB","CA":"CA","AU":"AU","MY":"MY","FR":"FR","DE":"FR","AT":"FR","BE":"FR","DK":"FR","FI":"FR",
    "IE":"FR","NL":"FR","PT":"FR","ES":"FR","CZ":"FR","GR":"FR","HU":"FR","TH":"TH","UY":"UY","QA":"QA","KW":"KW","AE":"AE",
    "SV":"SV","PK":"PK","AM":"AM","CH":"CH","IL":"IL","RU":"RU",
}
def steam_cc_for(market: str) -> str:
    return STEAM_CC_MAP.get(market.upper(), market.upper())

# Xbox locale mapping (Xbox column)
XBOX_LOCALE_MAP: Dict[str, str] = {
    "US":"en-us","KZ":None,"CN":"zh-CN","UA":"uk-ua","ID":"id-id","AR":"es-ar","TR":"tr-tr","BR":"pt-br","CL":"es-cl",
    "IN":"en-in","KR":"ko-kr","PH":"en-ph","JP":"ja-jp","VN":"vi-vn","CO":"es-co","NZ":"en-nz","CR":"es-cr","SA":"ar-sa",
    "SE":None,"TW":"zh-tw","SK":"sk-sk","PE":"es-pe","PL":"pl-pl","SG":"en-sg","ZA":"en-za","HK":"zh-hk","MX":"es-mx",
    "GB":"en-gb","CA":"en-ca","AU":"en-au","MY":"en-my","FR":"fr-fr","DE":"de-de","AT":"de-at","BE":"fr-fr","DK":None,
    "FI":"fi-fi","IE":"en-ie","NL":"nl-nl","PT":"pt-pt","ES":"es-es","CZ":"cs-cz","GR":"el-gr","HU":"hu-hu","TH":"th-th",
    "UY":None,"QA":"ar-qa","KW":"ar-kw","AE":"ar-ae","SV":None,"PK":None,"AM":None,"CH":"de-ch","IL":"he-il","RU":"ru-ru",
}
def xbox_locale_for(market: str) -> str:
    code = XBOX_LOCALE_MAP.get(market.upper())
    if code:
        return code
    fallback = {"US":"en-us","CA":"en-ca","GB":"en-gb","AU":"en-au","NZ":"en-nz","IE":"en-ie","ZA":"en-za",
        "MX":"es-mx","AR":"es-ar","CL":"es-cl","CO":"es-co","ES":"es-es","PE":"es-pe","CR":"es-cr",
        "BR":"pt-br","PT":"pt-pt","FR":"fr-fr","DE":"de-de","AT":"de-at","NL":"nl-nl","IT":"it-it",
        "JP":"ja-jp","KR":"ko-kr","TW":"zh-tw","HK":"zh-hk","CN":"zh-cn",
        "PL":"pl-pl","CZ":"cs-cz","SK":"sk-sk","HU":"hu-hu","GR":"el-gr","FI":"fi-fi","DK":"da-dk","SE":"sv-se",
        "TR":"tr-tr","IL":"he-il","AE":"ar-ae","QA":"ar-qa","KW":"ar-kw","SA":"ar-sa","RU":"ru-ru",
        "IN":"en-in","SG":"en-sg","MY":"en-my","PH":"en-ph","TH":"th-th","VN":"vi-vn","ID":"id-id"}
    return fallback.get(market.upper(), "en-us")

# -----------------------------
# Defaults for baskets (seed)
# -----------------------------
DEFAULT_STEAM_ROWS = [
    {"include": True, "title": "The Outer Worlds 2", "appid": "1449110", "scale_helldivers": False, "weight": 1.0},
    {"include": True, "title": "Madden NFL 26", "appid": "3230400", "scale_helldivers": False, "weight": 1.0},
    {"include": True, "title": "Call of Duty: Black Ops 6", "appid": "2933620", "scale_helldivers": False, "weight": 1.0},
    {"include": True, "title": "NBA 2K26", "appid": "3472040", "scale_helldivers": False, "weight": 1.0},
    {"include": True, "title": "Borderlands 4", "appid": "1285190", "scale_helldivers": False, "weight": 1.0},
    {"include": True, "title": "HELLDIVERS 2", "appid": "553850", "scale_helldivers": True, "weight": 1.0},
]
DEFAULT_XBOX_ROWS = [
    {"include": True, "title": "The Outer Worlds 2", "store_id": "9NSPRSXXZZLG", "scale_helldivers": False, "weight": 1.0},
    {"include": True, "title": "Madden NFL 26", "store_id": "9NVD16NP4J8T", "scale_helldivers": False, "weight": 1.0},
    {"include": True, "title": "Call of Duty: Black Ops 6", "store_id": "9PNCL2R6G8D0", "scale_helldivers": False, "weight": 1.0},
    {"include": True, "title": "NBA 2K26", "store_id": "9PJ2RVRC0L1X", "scale_helldivers": False, "weight": 1.0},
    {"include": True, "title": "Borderlands 4", "store_id": "9MX6HKF5647G", "scale_helldivers": False, "weight": 1.0},
    {"include": True, "title": "HELLDIVERS 2", "store_id": "9P3PT7PQJD0M", "scale_helldivers": True, "weight": 1.0},
]

# -----------------------------
# Other constants
# -----------------------------
VANITY_RULES = {"AU":{"suffix":0.95,"nines":True},"NZ":{"suffix":0.95,"nines":True},"CA":{"suffix":0.99,"nines":True}}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

@dataclass
class PriceRow:
    platform: str
    title: str
    country: str    # ISO country we keyed by
    currency: Optional[str]
    price: Optional[float]
    source_url: Optional[str]

@dataclass
class MissRow:
    platform: str
    title: str
    country: str
    reason: str

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
# Steam fetchers
# -----------------------------
STEAM_APPDETAILS = "https://store.steampowered.com/api/appdetails"
STEAM_PACKAGEDETAILS = "https://store.steampowered.com/api/packagedetails"

def _steam_appdetails(appid: str, cc: str) -> Optional[dict]:
    try:
        r = requests.get(STEAM_APPDETAILS, params={"appids": appid, "cc": cc, "l":"en"}, headers=UA, timeout=25)
        data = r.json().get(str(appid), {})
        if not data or not data.get("success"): return None
        return data.get("data") or {}
    except Exception:
        return None

def _steam_packagedetails(ids: List[int], cc: str) -> Dict[int, dict]:
    out: Dict[int, dict] = {}
    try:
        pid_str = ",".join(str(i) for i in ids)
        r = requests.get(STEAM_PACKAGEDETAILS, params={"packageids": pid_str, "cc": cc, "l":"en"}, headers=UA, timeout=25)
        data = r.json() if r.status_code == 200 else {}
        for pid, obj in (data or {}).items():
            if isinstance(obj, dict) and obj.get("success") and isinstance(obj.get("data"), dict):
                out[int(pid)] = obj["data"]
    except Exception:
        pass
    return out

def fetch_steam_price(appid: str, cc_iso: str, forced_title: Optional[str] = None) -> Tuple[Optional[PriceRow], Optional[MissRow]]:
    cc = steam_cc_for(cc_iso)
    data = _steam_appdetails(appid, cc)
    if not data:
        return None, MissRow("Steam", forced_title or appid, cc_iso, "appdetails_no_data")
    # Try price_overview
    pov = data.get("price_overview") or {}
    cents = None
    if isinstance(pov.get("initial"), int) and pov.get("initial") > 0:
        cents = pov.get("initial")
    elif isinstance(pov.get("final"), int) and pov.get("final") > 0:
        cents = pov.get("final")
    if cents:
        price = round(cents/100.0, 2)
        currency = (pov.get("currency") or "").upper() or None
        name = forced_title or data.get("name") or f"Steam App {appid}"
        return PriceRow("Steam", name, cc_iso.upper(), currency, price, f"https://store.steampowered.com/app/{appid}"), None
    # Fallback: packagedetails
    sub_ids: List[int] = []
    if isinstance(data.get("packages"), list):
        sub_ids += [int(x) for x in data.get("packages") if isinstance(x, int)]
    for grp in data.get("package_groups", []):
        for sub in grp.get("subs", []):
            sid = sub.get("packageid")
            if isinstance(sid, int): sub_ids.append(sid)
    sub_ids = list(dict.fromkeys(sub_ids))
    if not sub_ids:
        return None, MissRow("Steam", forced_title or data.get("name") or appid, cc_iso, "no_price_overview_no_packages")
    packs = _steam_packagedetails(sub_ids, cc=cc)
    for _, p in packs.items():
        price_obj = (p.get("price") or {})
        cents = price_obj.get("initial") if isinstance(price_obj.get("initial"), int) and price_obj.get("initial")>0 else price_obj.get("final")
        if isinstance(cents, int) and cents > 0:
            price = round(cents/100.0, 2)
            currency = (price_obj.get("currency") or "").upper() or None
            name = forced_title or data.get("name") or f"Steam App {appid}"
            return PriceRow("Steam", name, cc_iso.upper(), currency, price, f"https://store.steampowered.com/app/{appid}"), None
    return None, MissRow("Steam", forced_title or data.get("name") or appid, cc_iso, "packagedetails_no_price")

# -----------------------------
# Xbox fetchers
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

def fetch_xbox_price_one_market(product_id: str, market_iso: str, locale: str) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    headers = {"MS-CV": _ms_cv(), "Accept": "application/json"}
    # storesdk
    try:
        r = requests.get(STORESDK_URL, params={"bigIds": product_id, "market": market_iso.upper(), "locale": locale}, headers=headers, timeout=25)
        if r.status_code == 200:
            amount, ccy = _parse_xbox_price_from_products(r.json())
            if amount: return amount, ccy, None
    except Exception:
        pass
    # displaycatalog
    try:
        r = requests.get(DISPLAYCATALOG_URL, params={"bigIds": product_id, "market": market_iso.upper(), "languages": locale, "fieldsTemplate": "Details"}, headers=headers, timeout=25)
        if r.status_code == 200:
            amount, ccy = _parse_xbox_price_from_products(r.json())
            if amount: return amount, ccy, None
    except Exception:
        pass
    return None, None, "no_price_entries"

def fetch_xbox_price(product_name: str, product_id: str, market_iso: str, alt_ids: List[str]) -> Tuple[Optional[PriceRow], Optional[MissRow]]:
    loc = xbox_locale_for(market_iso)
    ids_to_try = [product_id] + [i for i in alt_ids if i and i != product_id]
    tried_any = False
    for pid in ids_to_try:
        tried_any = True
        amt, ccy, _ = fetch_xbox_price_one_market(pid, market_iso, loc)
        if amt:
            return PriceRow("Xbox", product_name, market_iso.upper(), ccy.upper() if ccy else None, float(amt), f"https://www.xbox.com/{loc.split('-')[0]}/games/store/placeholder/{pid}"), None
    # fallback to en-US
    for pid in ids_to_try:
        amt, ccy, _ = fetch_xbox_price_one_market(pid, market_iso, "en-US")
        if amt:
            return PriceRow("Xbox", product_name, market_iso.upper(), ccy.upper() if ccy else None, float(amt), f"https://www.xbox.com/en-US/games/store/placeholder/{pid}"), None
    reason = "tried_alt_ids_no_price" if tried_any else "no_ids"
    return None, MissRow("Xbox", product_name, market_iso, reason)

# -----------------------------
# Sidebar controls — editable baskets
# -----------------------------
with st.sidebar:
    st.header("Controls")
    default_markets = ",".join(sorted(COUNTRY_NAMES.keys()))
    user_markets = st.text_area("Markets (comma-separated ISO country codes)", value=default_markets, height=120)
    markets = [m.strip().upper() for m in user_markets.split(",") if m.strip()]

    # Initialize baskets in session state
    if "steam_rows" not in st.session_state:
        st.session_state.steam_rows = DEFAULT_STEAM_ROWS.copy()
    if "xbox_rows" not in st.session_state:
        st.session_state.xbox_rows = DEFAULT_XBOX_ROWS.copy()

    st.subheader("Steam basket")
    steam_df = st.data_editor(
        pd.DataFrame(st.session_state.steam_rows),
        key="steam_editor",
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "include": st.column_config.CheckboxColumn(default=True),
            "title":   st.column_config.TextColumn(),
            "appid":   st.column_config.TextColumn(),
            "scale_helldivers": st.column_config.CheckboxColumn(default=False),
            "weight": st.column_config.NumberColumn(step=0.1, min_value=0.0, max_value=10.0, format="%.2f"),
        },
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("➕ Add Steam row"):
            st.session_state.steam_rows.append({"include": True, "title": "", "appid": "", "scale_helldivers": False, "weight": 1.0})
    with c2:
        if st.button("🧹 Keep checked (Steam)"):
            st.session_state.steam_rows = [r for r in steam_df.to_dict(orient="records") if r.get("include")]
    with c3:
        if st.button("🔎 Auto-fill Steam names"):
            for r in steam_df.to_dict(orient="records"):
                if r.get("include") and r.get("appid") and not r.get("title"):
                    data = _steam_appdetails(str(r["appid"]), cc="US") or {}
                    name = data.get("name")
                    if name: r["title"] = name
            st.session_state.steam_rows = steam_df.to_dict(orient="records")

    st.subheader("Xbox basket")
    xbox_df = st.data_editor(
        pd.DataFrame(st.session_state.xbox_rows),
        key="xbox_editor",
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "include": st.column_config.CheckboxColumn(default=True),
            "title":   st.column_config.TextColumn(),
            "store_id": st.column_config.TextColumn(),
            "scale_helldivers": st.column_config.CheckboxColumn(default=False),
            "weight": st.column_config.NumberColumn(step=0.1, min_value=0.0, max_value=10.0, format="%.2f"),
        },
    )
    d1, d2, d3 = st.columns(3)
    with d1:
        if st.button("➕ Add Xbox row"):
            st.session_state.xbox_rows.append({"include": True, "title": "", "store_id": "", "scale_helldivers": False, "weight": 1.0})
    with d2:
        if st.button("🧹 Keep checked (Xbox)"):
            st.session_state.xbox_rows = [r for r in xbox_df.to_dict(orient="records") if r.get("include")]
    with d3:
        if st.button("🔎 Auto-fill Xbox names"):
            for r in xbox_df.to_dict(orient="records"):
                if r.get("include") and r.get("store_id") and not r.get("title"):
                    loc = xbox_locale_for("US")
                    headers = {"MS-CV": _ms_cv(), "Accept": "application/json"}
                    try:
                        rr = requests.get(DISPLAYCATALOG_URL, params={"bigIds": r["store_id"], "market": "US", "languages": loc, "fieldsTemplate": "Details"}, headers=headers, timeout=12)
                        j = rr.json()
                        products = j.get("Products") or j.get("products") or []
                        if products:
                            lp = (products[0].get("LocalizedProperties") or products[0].get("localizedProperties") or [])
                            if lp and lp[0].get("ProductTitle"):
                                r["title"] = lp[0]["ProductTitle"]
                    except Exception:
                        pass
            st.session_state.xbox_rows = xbox_df.to_dict(orient="records")

    # Presets (save/load)
    e1, e2 = st.columns(2)
    with e1:
        if st.button("💾 Save preset"):
            preset = {"steam": st.session_state.steam_rows, "xbox": st.session_state.xbox_rows}
            st.download_button("Download preset.json", data=json.dumps(preset, indent=2).encode("utf-8"),
                               file_name="basket_preset.json", mime="application/json", key="preset_dl")
    with e2:
        up = st.file_uploader("Load preset.json", type=["json"], label_visibility="collapsed", key="upl_preset")
        if up:
            try:
                data = json.load(up)
                st.session_state.steam_rows = list(data.get("steam", [])) or DEFAULT_STEAM_ROWS.copy()
                st.session_state.xbox_rows = list(data.get("xbox", [])) or DEFAULT_XBOX_ROWS.copy()
                st.success("Preset loaded. Review the tables above, then run.")
            except Exception:
                st.error("Invalid preset file.")

    # Optional ALT IDs for two known titles
    st.caption("Optional ALT Store IDs (comma-separated; tried after the main ID)")
    alt_ow2 = st.text_input("Xbox ALT IDs — The Outer Worlds 2", value="", key="alt_ow2")
    alt_2k  = st.text_input("Xbox ALT IDs — NBA 2K26", value="", key="alt_2k")

    st.divider()
    run = st.button("Run Pricing Pull", type="primary")

# -----------------------------
# Run
# -----------------------------
if run:
    # Build fetch list from edited tables
    steam_rows = [r for r in st.session_state.steam_rows if r.get("include") and r.get("appid")]
    xbox_rows  = [r for r in st.session_state.xbox_rows  if r.get("include") and r.get("store_id")]
    # Titles flagged for Helldivers scaling
    st.session_state["scale_titles"] = {r["title"] for r in steam_rows + xbox_rows if r.get("scale_helldivers")}

    rows: List[PriceRow] = []
    misses: List[MissRow] = []
    with st.status("Pulling prices across markets…", expanded=False) as status:
        futures = []
        with ThreadPoolExecutor(max_workers=20) as ex:
            # Steam jobs
            for cc in markets:
                for r in steam_rows:
                    futures.append(ex.submit(fetch_steam_price, str(r["appid"]), cc, r.get("title") or None))
            # Xbox jobs
            for cc in markets:
                for r in xbox_rows:
                    title = r.get("title") or "Unknown"
                    pid = str(r["store_id"])
                    alts = []
                    if title.lower().startswith("the outer worlds 2") and alt_ow2.strip():
                        alts = [x.strip() for x in alt_ow2.split(",") if x.strip()]
                    if title.lower().startswith("nba 2k26") and alt_2k.strip():
                        alts = [x.strip() for x in alt_2k.split(",") if x.strip()]
                    futures.append(ex.submit(fetch_xbox_price, title, pid, cc, alts))

            for f in as_completed(futures):
                try:
                    result = f.result()
                except Exception:
                    result = (None, MissRow("unknown","unknown","unknown","exception"))
                row, miss = result
                if row:
                    # Apply Helldivers scaling if title is flagged in basket
                    if row.title in st.session_state.get("scale_titles", set()) and row.price is not None:
                        row = PriceRow(row.platform, row.title + " (scaled)", row.country, row.currency, round((row.price/4.0)*7.0, 2), row.source_url)
                    rows.append(row)
                if miss: misses.append(miss)

        if not rows and not misses:
            status.update(label="No data returned — check IDs or try fewer markets.", state="error")
            st.stop()
        status.update(label="Done!", state="complete")

    raw_df = pd.DataFrame([asdict(r) for r in rows])
    if not raw_df.empty:
        raw_df.insert(2, "country_name", raw_df["country"].map(country_name))

        # Recommendations per platform (mean; weights reserved for future)
        reco = (raw_df.groupby(["platform","country","currency"], dropna=False)["price"]
                     .mean().reset_index().rename(columns={"price":"RecommendedPrice"}))
        reco.insert(1, "country_name", reco["country"].map(country_name))

        reco_xbox  = reco[reco["platform"]=="Xbox"][["country_name","country","currency","RecommendedPrice"]].reset_index(drop=True)
        reco_steam = reco[reco["platform"]=="Steam"][["country_name","country","currency","RecommendedPrice"]].reset_index(drop=True)

        # Vanity endings
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

    # Diagnostics
    if misses:
        miss_df = pd.DataFrame([asdict(m) for m in misses])
        miss_df = miss_df.sort_values(["platform","title","country"]).reset_index(drop=True)
        st.subheader("Diagnostics (no price found)")
        st.dataframe(miss_df)

else:
    st.info("Edit the baskets in the sidebar, set markets, then click **Run Pricing Pull**.", icon="🛠️")
