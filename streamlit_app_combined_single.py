# streamlit_app_combined_single.py
# v1.0 - Single-file app (Xbox + Steam + PlayStation with PS silo mapping)
# Drop this one file into your repo and set Streamlit "Main file path" to this filename.

from __future__ import annotations
import re, json, time, math
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st

# --------------------------
# Helpers & global settings
# --------------------------

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language":"en-US,en;q=0.8"})

@st.cache_data(show_spinner=False)
def _get_fx() -> Dict[str,float]:
    # Simple FX seed for USD conversion; replace with a live service if you have one.
    return {
        "USD": 1.0, "EUR": 1.10, "GBP": 1.27, "AUD": 0.66, "CAD": 0.73,
        "BRL": 0.18, "ARS": 0.0012, "CLP": 0.0011, "COP": 0.00026,
        "HKD": 0.13, "JPY": 0.0066, "CNY": 0.14, "KRW": 0.00073,
        "MXN": 0.056, "ZAR": 0.055, "TRY": 0.030, "PLN": 0.25,
        "CZK": 0.043, "DKK": 0.15, "SEK": 0.093, "NOK": 0.091, "HUF": 0.0028,
        "TWD": 0.031, "MYR": 0.21, "SGD": 0.74, "NZD": 0.60, "AED": 0.27, "ILS": 0.27, "CHF": 1.10, "BGN": 0.56, "RON": 0.22
    }

def usd(v: Optional[float], cur: str) -> Optional[float]:
    fx = _get_fx()
    if v is None: return None
    r = fx.get(cur.upper())
    return round(v * r, 2) if r else None

# --------------------------
# PlayStation SILO (mapping + scraper)
# --------------------------

# Minimal PS supported locale map (extend as needed)
PS_MARKETS = [
    ("United States", "US", "en-us", "USD"),
    ("Canada", "CA", "en-ca", "CAD"),
    ("United Kingdom", "GB", "en-gb", "GBP"),
    ("Australia", "AU", "en-au", "AUD"),
    ("New Zealand", "NZ", "en-nz", "NZD"),
    ("Brazil", "BR", "pt-br", "BRL"),
    ("Mexico", "MX", "es-mx", "USD"),
    ("Argentina", "AR", "es-ar", "USD"),
    ("Chile", "CL", "es-cl", "USD"),
    ("Colombia", "CO", "es-co", "USD"),
    ("France", "FR", "fr-fr", "EUR"),
    ("Germany", "DE", "de-de", "EUR"),
    ("Spain", "ES", "es-es", "EUR"),
    ("Italy", "IT", "it-it", "EUR"),
    ("Netherlands", "NL", "nl-nl", "EUR"),
    ("Belgium", "BE", "fr-fr", "EUR"),
    ("Sweden", "SE", "sv-se", "SEK"),
    ("Denmark", "DK", "da-dk", "DKK"),
    ("Czech Republic", "CZ", "cs-cz", "CZK"),
    ("Poland", "PL", "pl-pl", "PLN"),
    ("Greece", "GR", "el-gr", "EUR"),
    ("Hungary", "HU", "hu-hu", "USD"),
    ("Ireland", "IE", "en-ie", "EUR"),
    ("Finland", "FI", "fi-fi", "EUR"),
    ("Portugal", "PT", "pt-pt", "EUR"),
    ("Austria", "AT", "de-de", "EUR"),
    ("Switzerland", "CH", "de-ch", "CHF"),
    ("Turkey", "TR", "tr-tr", "TRY"),
    ("Israel", "IL", "he-il", "ILS"),
    ("Saudi Arabia", "SA", "ar-sa", "USD"),
    ("United Arab Emirates", "AE", "ar-ae", "AED"),
    ("Hong Kong", "HK", "en-hk", "HKD"),
    ("Japan", "JP", "ja-jp", "JPY"),
    ("Korea", "KR", "ko-kr", "KRW"),
    ("Taiwan", "TW", "zh-tw", "TWD"),
    ("Singapore", "SG", "en-sg", "SGD"),
    ("Malaysia", "MY", "en-my", "MYR"),
]

PS_MAP = {c: {"country_name":n, "locale":loc, "currency":cur} for (n,c,loc,cur) in PS_MARKETS}

def _normalize_ps_ref(s: str) -> str:
    if s is None: return ""
    s = s.strip()
    if re.match(r"^https?://", s, re.I):
        m = re.search(r"/product/([A-Z0-9_-]+)", s)
        return m.group(1) if m else s.split("/")[-1]
    return s

def _ps_build_url(code: str, locale: str) -> str:
    return f"https://store.playstation.com/{locale}/product/{code}"

def _ps_parse_prices(html: str, prefer_msrp_flag: bool) -> Optional[float]:
    # Basic heuristic: try to find a strike-through (MSRP), else main price.
    soup = BeautifulSoup(html, "html.parser")

    # Try to find a strikethrough original price
    msrp = None
    for tag in soup.find_all(["s", "del"]):
        txt = tag.get_text(" ", strip=True)
        m = re.search(r"(\d[\d,]*\.\d{2})", txt or "")
        if m:
            try:
                msrp = float(m.group(1).replace(",", ""))
                break
            except: pass

    # Find the largest visible price number as current
    cur = None
    best = 0.0
    for c in soup.find_all(["span","div"]):
        txt = c.get_text(" ", strip=True)
        if not txt: continue
        if any(k in txt.lower() for k in ["add to cart","subscribe","trial","offer ends","save"]):
            continue
        m = re.search(r"(\d[\d,]*\.\d{2})", txt)
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
                if val > best:
                    best = val; cur = val
            except: pass

    if prefer_msrp_flag and msrp:
        return msrp
    return cur or msrp

def fetch_ps_price(code_or_url: str, country: str, prefer_msrp: bool) -> Tuple[Optional[float], Optional[str]]:
    country = country.upper()
    meta = PS_MAP.get(country)
    if not meta: return None, "unsupported_country"
    code = _normalize_ps_ref(code_or_url)
    url = _ps_build_url(code, meta["locale"])
    try:
        r = SESSION.get(url, timeout=20)
        if r.status_code >= 400:
            return None, f"http_{r.status_code}"
        price = _ps_parse_prices(r.text, prefer_msrp)
        return price, None if price is not None else "no_price_found"
    except requests.RequestException:
        return None, "network_error"

# --------------------------
# Steam (official API)
# --------------------------

def fetch_steam_price(appid: int, country: str, prefer_msrp: bool) -> Tuple[Optional[float], Optional[str]]:
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc={country}&filters=price_overview"
    try:
        r = SESSION.get(url, timeout=20)
        j = r.json()
        data = j.get(str(appid), {}).get("data", {})
        po = data.get("price_overview")
        if not po:
            return None, "no_price"
        initial = po.get("initial")/100 if po.get("initial") else None
        final = po.get("final")/100 if po.get("final") else None
        price = initial if prefer_msrp and initial else final or initial
        return price, None
    except:
        return None, "error"

# --------------------------
# Xbox (Display Catalog API – simplified)
# --------------------------

def fetch_xbox_price(store_id: str, country: str, prefer_msrp: bool) -> Tuple[Optional[float], Optional[str]]:
    market = country.upper()
    lang = "en-" + market.lower()
    url = ("https://displaycatalog.mp.microsoft.com/v7.0/products"
           f"?bigIds={store_id}&market={market}&languages={lang}&MS-CV=DGU1mcuYo0WMMp+F.1")
    try:
        r = SESSION.get(url, timeout=20)
        j = r.json()
        items = j.get("Products", [])
        if not items:
            return None, "no_product"
        dsa = items[0].get("DisplaySkuAvailabilities", [{}])[0]
        list_price = None; cur_price = None
        for av in dsa.get("Availabilities", []):
            pp = av.get("OrderManagementData", {}).get("Price", {})
            if pp.get("ListPrice") is not None:
                list_price = pp["ListPrice"]
            if pp.get("RetailPrice") is not None:
                cur_price = pp["RetailPrice"]
            if pp.get("MSRP") is not None:
                list_price = pp["MSRP"]
        price = list_price if prefer_msrp and list_price else (cur_price or list_price)
        return price, None
    except:
        return None, "error"

# --------------------------
# UI
# --------------------------

st.set_page_config(page_title="Game Pricing – Single File", layout="wide")
st.title("🎮 Game Pricing — Single File (Xbox • Steam • PlayStation)")

with st.sidebar:
    st.markdown("**Quick run** limits to 10 markets to reduce wait time.")
    quick = st.checkbox("Quick run (first 10 markets)", value=True)
    prefer_msrp = st.checkbox("Prefer MSRP (ignore discounts)", value=True)

    markets_input = st.text_area(
        "Markets (ISO country codes, comma-separated)",
        "US,CA,GB,AU,NZ,BR,MX,AR,CL,CO,FR,DE,ES,IT,NL,SE,DK,CZ,PL,GR,HU,IE,FI,PT,AT,CH,TR,IL,SA,AE,HK,JP,KR,TW,SG,MY",
        height=90
    )
    markets = [m.strip().upper() for m in markets_input.split(",") if m.strip()]
    if quick:
        markets = markets[:10]

# BASKETS (editable tables)
st.subheader("Steam basket")
steam_df = pd.DataFrame([
    {"include": True, "title": "The Outer Worlds 2", "appid": 1449110, "scale_factor": 1.0, "weight": 1},
    {"include": True, "title": "Madden NFL 26", "appid": 3230400, "scale_factor": 1.0, "weight": 1},
    {"include": True, "title": "Call of Duty: Black Ops 6", "appid": 2933620, "scale_factor": 1.0, "weight": 1},
    {"include": True, "title": "NBA 2K26", "appid": 3472040, "scale_factor": 1.0, "weight": 1},
    {"include": True, "title": "Borderlands 4", "appid": 1285190, "scale_factor": 1.0, "weight": 1},
    {"include": True, "title": "HELLDIVERS 2", "appid": 553850, "scale_factor": 1.75, "weight": 1},
])
steam_edit = st.data_editor(steam_df, use_container_width=True, hide_index=True)

st.subheader("Xbox basket")
xbox_df = pd.DataFrame([
    {"include": True, "title": "The Outer Worlds 2", "store_id": "9NSPRSXXZZLG", "scale_factor": 1.0, "weight": 1},
    {"include": True, "title": "Madden NFL 26", "store_id": "9NVD16NP4J8T", "scale_factor": 1.0, "weight": 1},
    {"include": True, "title": "Call of Duty: Black Ops 6", "store_id": "9PNCL2R6G8D0", "scale_factor": 1.0, "weight": 1},
    {"include": True, "title": "NBA 2K26", "store_id": "9PJ2RVRCO1LX", "scale_factor": 1.0, "weight": 1},
    {"include": True, "title": "Borderlands 4", "store_id": "9MX6HKF5647G", "scale_factor": 1.0, "weight": 1},
    {"include": True, "title": "HELLDIVERS 2", "store_id": "9P3PT7PQJD0M", "scale_factor": 1.75, "weight": 1},
])
xbox_edit = st.data_editor(xbox_df, use_container_width=True, hide_index=True)

st.subheader("PlayStation basket (PS silo)")
ps_df = pd.DataFrame([
    {"include": True, "title": "The Outer Worlds 2", "ps_ref": "UP1001-PPSA01494_00-0000000000000AK2"},
    {"include": True, "title": "Madden NFL 26", "ps_ref": "UP0006-PPSA26127_00-MADDENNFL26GAME0"},
    {"include": True, "title": "Call of Duty: Black Ops 6", "ps_ref": "UP0002-PPSA17544_00-BO6CROSSGENBUNDLE"},
    {"include": True, "title": "NBA 2K26", "ps_ref": "UP1001-PPSA28420_00-NBA2K26000000000"},
    {"include": True, "title": "Borderlands 4", "ps_ref": "UP1001-PPSA01494_00-0000000000000AK2"},
    {"include": True, "title": "HELLDIVERS 2", "ps_ref": "UP9000-PPSA03088_00-HELLDIVERS2GAME00"},
])
ps_edit = st.data_editor(ps_df, use_container_width=True, hide_index=True)

run = st.button("Run Pricing Pull", type="primary")
st.write("")

if run:
    rows = []
    reasons = []
    st.info("Pulling prices across markets…")
    progress = st.progress(0.0, text="Working…")

    items = []
    for _,r in steam_edit.iterrows():
        if not r.get("include"): continue
        items.append(("Steam", r["title"], r["appid"], r["scale_factor"], r["weight"]))
    for _,r in xbox_edit.iterrows():
        if not r.get("include"): continue
        items.append(("Xbox", r["title"], r["store_id"], r["scale_factor"], r["weight"]))
    for _,r in ps_edit.iterrows():
        if not r.get("include"): continue
        items.append(("PlayStation", r["title"], r["ps_ref"], 1.0, 1))

    total = max(1, len(items)*len(markets))
    done = 0

    for plat, title, ident, scale, weight in items:
        for c in markets:
            price_local = None
            cur = None
            reason = None
            if plat == "Steam":
                p, reason = fetch_steam_price(int(ident), c, prefer_msrp)
                price_local = p
                # currency heuristic just for display
                cur = ""  # Steam API currency varies; left blank here
            elif plat == "Xbox":
                p, reason = fetch_xbox_price(str(ident), c, prefer_msrp)
                price_local = p
                cur = ""  # Xbox provides currency in deeper schema; left blank in this simple view
            else:  # PlayStation silo
                p, reason = fetch_ps_price(str(ident), c, prefer_msrp)
                price_local = p
                meta = PS_MAP.get(c, {})
                cur = meta.get("currency", "")

            rows.append({
                "platform": plat,
                "title": title,
                "country_name": c,
                "country": c,
                "currency": cur,
                "price": price_local*scale if price_local else None,
                "source_url": "" if plat!="PlayStation" else _ps_build_url(_normalize_ps_ref(str(ident)), PS_MAP.get(c,{}).get("locale","en-us")),
                "identity": f"{plat.lower()}:{ident}",
                "scale": scale,
                "weight": weight
            })
            if reason:
                reasons.append({"platform": plat, "title": title, "country": c, "reason": reason})
            done += 1
            progress.progress(min(1.0, done/total))

    df = pd.DataFrame(rows)
    st.subheader("Raw Basket Rows (after scaling)")
    st.dataframe(df, use_container_width=True)

    # Simple per-country recommendation = weighted average per platform
    def summarize(platform_name: str) -> pd.DataFrame:
        sub = df[df["platform"]==platform_name].copy()
        if sub.empty:
            return pd.DataFrame(columns=["platform","country_name","country","currency","RecommendedPrice","USDPrice","DiffUSD"])
        sub["wprice"] = sub["price"] * sub["weight"]
        g = sub.groupby(["country_name","country","currency"], as_index=False).agg({"wprice":"sum","weight":"sum"})
        g["RecommendedPrice"] = (g["wprice"]/g["weight"]).round(2)
        g["USDPrice"] = [usd(v, cur) if cur else None for v,cur in zip(g["RecommendedPrice"], g["currency"])]
        base_usd = g["USDPrice"].iloc[0] if not g["USDPrice"].isna().all() else None
        g["DiffUSD"] = [ (v - base_usd) if (v is not None and base_usd is not None) else None for v in g["USDPrice"] ]
        g.insert(0, "platform", platform_name)
        g = g[["platform","country_name","country","currency","RecommendedPrice","USDPrice","DiffUSD"]]
        return g

    st.subheader("Xbox Regional Pricing Recommendation")
    st.dataframe(summarize("Xbox"), use_container_width=True)

    st.subheader("Steam Regional Pricing Recommendation")
    st.dataframe(summarize("Steam"), use_container_width=True)

    st.subheader("PlayStation Regional Pricing Recommendation")
    st.dataframe(summarize("PlayStation"), use_container_width=True)

    # Diagnostics
    if reasons:
        st.subheader("Diagnostics (no price found / errors)")
        st.dataframe(pd.DataFrame(reasons), use_container_width=True)

    # Export
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV (raw results)", data=csv, file_name="pricing_pull_raw.csv", mime="text/csv")
else:
    st.info("Set your baskets and click **Run Pricing Pull**.")
