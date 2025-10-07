
# streamlit_app_combined.py
# ------------------------------------------------------------
# Game Pricing Recommendation Tool (Xbox + Steam + PlayStation)
# Features: Editable baskets, per-row scale factor, weighted means,
# platform-true pulls, canonical English titles, USD conversion,
# vanity rounding, variance vs US, "Regional Pricing Recommendation" views.
# ------------------------------------------------------------

import random, time, re, json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import requests
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

# -----------------------------
# App header
# -----------------------------
st.set_page_config(page_title="Game Pricing Recommendation Tool", page_icon="🎮", layout="wide")
st.title("🎮 Game Pricing Recommendation Tool")
st.caption("Editable baskets · Per-row scale factor · Weighted means · Platform-true pulls · Canonical titles · USD conversion + variance views")

# -----------------------------
# Country names
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
# Steam / Xbox market mappings
# -----------------------------
STEAM_CC_MAP: Dict[str, str] = {
    "US":"US","KZ":"KZ","CN":"CN","UA":"UA","ID":"ID","AR":"AR","TR":"TR","BR":"BR","CL":"CL","IN":"IN","KR":"KR","PH":"PH",
    "JP":"JP","VN":"VN","CO":"CO","NZ":"NZ","CR":"CR","SA":"SA","TW":"TW","SK":"SK","PE":"PE","PL":"PL","SG":"SG","ZA":"ZA",
    "HK":"HK","MX":"MX","GB":"GB","CA":"CA","AU":"AU","MY":"MY","FR":"FR","DE":"FR","AT":"FR","BE":"FR","DK":"FR","FI":"FR",
    "IE":"FR","NL":"FR","PT":"FR","ES":"FR","CZ":"FR","GR":"FR","HU":"FR","TH":"TH","UY":"UY","QA":"QA","KW":"KW","AE":"AE",
    "SV":"SV","PK":"PK","AM":"AM","CH":"CH","IL":"IL","RU":"RU",
}
def steam_cc_for(market: str) -> str:
    return STEAM_CC_MAP.get(market.upper(), market.upper())

XBOX_LOCALE_MAP: Dict[str, Optional[str]] = {
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
    return "en-us"

# -----------------------------
# PlayStation market mappings (from PS v1.7)
# We choose a single preferred locale per ISO country code.
# -----------------------------
PS_ALL_LOCALES: List[Dict[str, str]] = [
    {"key":"US","country":"US","locale":"en-us","currency":"USD"},
    {"key":"Canada (EN)","country":"CA","locale":"en-ca","currency":"CAD"},
    {"key":"Canada (FR)","country":"CA","locale":"fr-ca","currency":"CAD"},
    {"key":"Mexico","country":"MX","locale":"es-mx","currency":"MXN"},
    {"key":"Brazil","country":"BR","locale":"pt-br","currency":"BRL"},
    {"key":"Argentina","country":"AR","locale":"es-ar","currency":"ARS"},
    {"key":"Chile","country":"CL","locale":"es-cl","currency":"CLP"},
    {"key":"Colombia","country":"CO","locale":"es-co","currency":"COP"},
    {"key":"Peru","country":"PE","locale":"es-pe","currency":"PEN"},
    {"key":"Uruguay","country":"UY","locale":"es-uy","currency":"UYU"},
    {"key":"Costa Rica","country":"CR","locale":"es-cr","currency":"CRC"},
    {"key":"Guatemala","country":"GT","locale":"es-gt","currency":"GTQ"},
    {"key":"Honduras","country":"HN","locale":"es-hn","currency":"HNL"},
    {"key":"Nicaragua","country":"NI","locale":"es-ni","currency":"NIO"},
    {"key":"Panama","country":"PA","locale":"es-pa","currency":"USD"},
    {"key":"Paraguay","country":"PY","locale":"es-py","currency":"PYG"},
    {"key":"El Salvador","country":"SV","locale":"es-sv","currency":"USD"},
    {"key":"Dominican Republic","country":"DO","locale":"es-do","currency":"DOP"},
    {"key":"Bolivia","country":"BO","locale":"es-bo","currency":"BOB"},
    {"key":"UK","country":"GB","locale":"en-gb","currency":"GBP"},
    {"key":"Ireland","country":"IE","locale":"en-ie","currency":"EUR"},
    {"key":"France","country":"FR","locale":"fr-fr","currency":"EUR"},
    {"key":"Belgium (FR)","country":"BE","locale":"fr-be","currency":"EUR"},
    {"key":"Belgium (NL)","country":"BE","locale":"nl-be","currency":"EUR"},
    {"key":"Netherlands","country":"NL","locale":"nl-nl","currency":"EUR"},
    {"key":"Luxembourg (FR)","country":"LU","locale":"fr-lu","currency":"EUR"},
    {"key":"Germany","country":"DE","locale":"de-de","currency":"EUR"},
    {"key":"Austria","country":"AT","locale":"de-at","currency":"EUR"},
    {"key":"Switzerland (DE)","country":"CH","locale":"de-ch","currency":"CHF"},
    {"key":"Switzerland (FR)","country":"CH","locale":"fr-ch","currency":"CHF"},
    {"key":"Switzerland (IT)","country":"CH","locale":"it-ch","currency":"CHF"},
    {"key":"Italy","country":"IT","locale":"it-it","currency":"EUR"},
    {"key":"Spain","country":"ES","locale":"es-es","currency":"EUR"},
    {"key":"Portugal","country":"PT","locale":"pt-pt","currency":"EUR"},
    {"key":"Poland","country":"PL","locale":"pl-pl","currency":"PLN"},
    {"key":"Czechia","country":"CZ","locale":"cs-cz","currency":"CZK"},
    {"key":"Slovakia","country":"SK","locale":"sk-sk","currency":"EUR"},
    {"key":"Hungary","country":"HU","locale":"hu-hu","currency":"HUF"},
    {"key":"Romania","country":"RO","locale":"ro-ro","currency":"RON"},
    {"key":"Bulgaria","country":"BG","locale":"bg-bg","currency":"BGN"},
    {"key":"Greece","country":"GR","locale":"el-gr","currency":"EUR"},
    {"key":"Croatia","country":"HR","locale":"hr-hr","currency":"EUR"},
    {"key":"Slovenia","country":"SI","locale":"sl-si","currency":"EUR"},
    {"key":"Serbia","country":"RS","locale":"sr-rs","currency":"RSD"},
    {"key":"Turkey","country":"TR","locale":"tr-tr","currency":"TRY"},
    {"key":"Norway","country":"NO","locale":"no-no","currency":"NOK"},
    {"key":"Sweden","country":"SE","locale":"sv-se","currency":"SEK"},
    {"key":"Denmark","country":"DK","locale":"da-dk","currency":"DKK"},
    {"key":"Finland","country":"FI","locale":"fi-fi","currency":"EUR"},
    {"key":"Iceland","country":"IS","locale":"is-is","currency":"ISK"},
    {"key":"Ukraine","country":"UA","locale":"uk-ua","currency":"UAH"},
    {"key":"Saudi Arabia","country":"SA","locale":"ar-sa","currency":"SAR"},
    {"key":"United Arab Emirates (EN)","country":"AE","locale":"en-ae","currency":"AED"},
    {"key":"United Arab Emirates (AR)","country":"AE","locale":"ar-ae","currency":"AED"},
    {"key":"Israel","country":"IL","locale":"he-il","currency":"ILS"},
    {"key":"South Africa","country":"ZA","locale":"en-za","currency":"ZAR"},
    {"key":"Australia","country":"AU","locale":"en-au","currency":"AUD"},
    {"key":"New Zealand","country":"NZ","locale":"en-nz","currency":"NZD"},
    {"key":"Singapore","country":"SG","locale":"en-sg","currency":"SGD"},
    {"key":"Malaysia","country":"MY","locale":"en-my","currency":"MYR"},
    {"key":"Thailand","country":"TH","locale":"th-th","currency":"THB"},
    {"key":"Indonesia","country":"ID","locale":"id-id","currency":"IDR"},
    {"key":"Philippines","country":"PH","locale":"en-ph","currency":"PHP"},
    {"key":"Vietnam","country":"VN","locale":"vi-vn","currency":"VND"},
    {"key":"Hong Kong (ZH)","country":"HK","locale":"zh-hk","currency":"HKD"},
    {"key":"Hong Kong (EN)","country":"HK","locale":"en-hk","currency":"HKD"},
    {"key":"Taiwan","country":"TW","locale":"zh-tw","currency":"TWD"},
    {"key":"Korea","country":"KR","locale":"ko-kr","currency":"KRW"},
    {"key":"Japan","country":"JP","locale":"ja-jp","currency":"JPY"},
    {"key":"India","country":"IN","locale":"en-in","currency":"INR"},
]
# Pick a preferred locale per country (prefer English variant where available)
_PS_PREF: Dict[str, Dict[str, str]] = {}
for row in PS_ALL_LOCALES:
    c = row["country"].upper()
    if c not in _PS_PREF:
        _PS_PREF[c] = row
    # prefer English where duplicate country exists
    if c in _PS_PREF and row["locale"].startswith("en-"):
        _PS_PREF[c] = row

def ps_market_meta(market_iso: str) -> Tuple[str, str]:
    m = _PS_PREF.get(market_iso.upper())
    if not m:
        # default to US
        return "en-us", "USD"
    return m["locale"], m["currency"]

# -----------------------------
# Defaults
# -----------------------------
DEFAULT_STEAM_ROWS = [
    {"include": True, "title": "The Outer Worlds 2", "appid": "1449110", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""},
    {"include": True, "title": "Madden NFL 26",       "appid": "3230400", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""},
    {"include": True, "title": "Call of Duty: Black Ops 6", "appid": "2933620", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""},
    {"include": True, "title": "NBA 2K26",            "appid": "3472040", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""},
    {"include": True, "title": "Borderlands 4",       "appid": "1285190", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""},
    {"include": True, "title": "HELLDIVERS 2",        "appid": "553850",  "scale_factor": 1.75, "weight": 1.0, "_steam_error": ""},
]
DEFAULT_XBOX_ROWS = [
    {"include": True, "title": "The Outer Worlds 2", "store_id": "9NSPRSXXZZLG", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""},
    {"include": True, "title": "Madden NFL 26",      "store_id": "9NVD16NP4J8T", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""},
    {"include": True, "title": "Call of Duty: Black Ops 6", "store_id": "9PNCL2R6G8D0", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""},
    {"include": True, "title": "NBA 2K26",           "store_id": "9PJ2RVRC0L1X", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""},
    {"include": True, "title": "Borderlands 4",      "store_id": "9MX6HKF5647G", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""},
    {"include": True, "title": "HELLDIVERS 2",       "store_id": "9P3PT7PQJD0M", "scale_factor": 1.75, "weight": 1.0, "_xbox_error": ""},
]
DEFAULT_PS_ROWS = [
    {"include": True, "title": "HELLDIVERS 2", "ps_ref": "https://store.playstation.com/en-us/product/UP9000-PPSA14719_00-ARROWHEADGAAS000", "edition_hint": "", "scale_factor": 1.75, "weight": 1.0, "_ps_error": ""},
    {"include": True, "title": "NBA 2K26",     "ps_ref": "", "edition_hint": "", "scale_factor": 1.0, "weight": 1.0, "_ps_error": ""},
]

# Vanity endings (sample)
VANITY_RULES = {"AU":{"suffix":0.95,"nines":True},"NZ":{"suffix":0.95,"nines":True},"CA":{"suffix":0.99,"nines":True}}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

@dataclass
class PriceRow:
    platform: str
    title: str
    country: str
    currency: Optional[str]
    price: Optional[float]
    source_url: Optional[str]
    identity: str

@dataclass
class MissRow:
    platform: str
    title: str
    country: str
    reason: str

def _nearest_x9_suffix(price: float, cents_suffix: float) -> float:
    base_tens = int(price // 10)
    cand = []
    for k in range(base_tens-2, base_tens+4):
        x = 10*k + 9 + cents_suffix
        if x > 0:
            cand.append(x)
    return round(min(cand, key=lambda v: (abs(v-price), -v)), 2)

def apply_vanity(country: str, price: float) -> float:
    rule = VANITY_RULES.get(country.upper())
    if rule and rule.get("nines"):
        return _nearest_x9_suffix(float(price), float(rule["suffix"]))
    return round(price, 2)

# -----------------------------
# USD conversion
# -----------------------------
def fetch_usd_rates(force: bool = False) -> Dict[str, float]:
    """Fetch currency rates with USD as base. Cache ~2h. Two-provider fallback."""
    now = time.time()
    cache_ok = (
        "usd_rates" in st.session_state and
        "usd_rates_ts" in st.session_state and
        (now - st.session_state["usd_rates_ts"] < 7200) and
        not force
    )
    if cache_ok:
        return dict(st.session_state["usd_rates"])

    rates = {"USD": 1.0}
    # primary
    try:
        resp = requests.get("https://api.exchangerate.host/latest", params={"base": "USD"}, timeout=15)
        if resp.status_code == 200:
            data = resp.json() or {}
            if "rates" in data and isinstance(data["rates"], dict):
                for k, v in data["rates"].items():
                    if isinstance(v, (int, float)) and v > 0:
                        rates[k.upper()] = float(v)
    except Exception:
        pass
    # fallback
    if len(rates) <= 1:
        try:
            r2 = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15)
            if r2.status_code == 200:
                d2 = r2.json() or {}
                if d2.get("result") == "success" and isinstance(d2.get("rates"), dict):
                    for k,v in d2["rates"].items():
                        if isinstance(v, (int,float)) and v>0:
                            rates[k.upper()] = float(v)
        except Exception:
            pass

    st.session_state["usd_rates"] = dict(rates)
    st.session_state["usd_rates_ts"] = now
    return rates

def to_usd(amount: Optional[float], currency: Optional[str], rates: Dict[str, float]) -> Optional[float]:
    if amount is None or currency is None:
        return None
    cur = currency.upper()
    r = rates.get(cur)
    if not r or r <= 0:
        return None
    # base=USD -> 'r' is how many CUR for 1 USD, so USD = amount / r
    return round(float(amount) / r, 2)

# -----------------------------
# Steam / Xbox price helpers
# -----------------------------
STEAM_APPDETAILS = "https://store.steampowered.com/api/appdetails"
STEAM_PACKAGEDETAILS = "https://store.steampowered.com/api/packagedetails"

def _steam_appdetails(appid: str, cc: str) -> Optional[dict]:
    try:
        r = requests.get(STEAM_APPDETAILS, params={"appids": appid, "cc": cc, "l":"en"}, headers=UA, timeout=25)
        data = r.json().get(str(appid), {})
        if not data or not data.get("success"):
            return None
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
        return PriceRow("Steam", name, cc_iso.upper(), currency, price, f"https://store.steampowered.com/app/{appid}", f"steam:{appid}"), None
    sub_ids: List[int] = []
    if isinstance(data.get("packages"), list):
        sub_ids += [int(x) for x in data.get("packages") if isinstance(x, int)]
    for grp in data.get("package_groups", []):
        for sub in grp.get("subs", []):
            sid = sub.get("packageid")
            if isinstance(sid, int):
                sub_ids.append(sid)
    sub_ids = list(dict.fromkeys(sub_ids))
    if not sub_ids:
        return None, MissRow("Steam", forced_title or data.get("name") or appid, cc_iso, "packagedetails_no_price")
    packs = _steam_packagedetails(sub_ids, cc=cc)
    for _, p in packs.items():
        price_obj = (p.get("price") or {})
        cents = price_obj.get("initial") if isinstance(price_obj.get("initial"), int) and price_obj.get("initial")>0 else price_obj.get("final")
        if isinstance(cents, int) and cents > 0:
            price = round(cents/100.0, 2)
            currency = (price_obj.get("currency") or "").upper() or None
            name = forced_title or data.get("name") or f"Steam App {appid}"
            return PriceRow("Steam", name, cc_iso.upper(), currency, price, f"https://store.steampowered.com/app/{appid}", f"steam:{appid}"), None
    return None, MissRow("Steam", forced_title or data.get("name") or appid, cc_iso, "packagedetails_no_price")

STORESDK_URL = "https://storeedgefd.dsx.mp.microsoft.com/v9.0/sdk/products"
DISPLAYCATALOG_URL = "https://displaycatalog.mp.microsoft.com/v7.0/products"

def _ms_cv() -> str:
    import string
    return "".join(random.choice(string.ascii_letters+string.digits) for _ in range(24))

def _parse_xbox_price_from_products(payload: dict) -> Tuple[Optional[float], Optional[str]]:
    try:
        products = payload.get("Products") or payload.get("products")
        if not products:
            return None, None
        p0 = products[0]
        # Prefer price nested in OrderManagementData
        for sku in (p0.get("DisplaySkuAvailabilities") or p0.get("displaySkuAvailabilities") or []):
            for av in (sku.get("Availabilities") or sku.get("availabilities") or []):
                omd = av.get("OrderManagementData") or av.get("orderManagementData") or {}
                price = omd.get("Price") or omd.get("price") or {}
                amount = price.get("MSRP") or price.get("msrp") or price.get("ListPrice") or price.get("listPrice")
                currency = price.get("CurrencyCode") or price.get("currencyCode")
                if amount:
                    return float(amount), (str(currency).upper() if currency else None)
        return None, None
    except Exception:
        return None, None

def fetch_xbox_price(product_name: str, product_id: str, market_iso: str) -> Tuple[Optional[PriceRow], Optional[MissRow]]:
    headers = {"MS-CV": _ms_cv(), "Accept": "application/json"}
    loc = xbox_locale_for(market_iso)
    try:
        r = requests.get(STORESDK_URL, params={"bigIds": product_id, "market": market_iso.upper(), "locale": loc}, headers=headers, timeout=25)
        if r.status_code == 200:
            amt, ccy = _parse_xbox_price_from_products(r.json())
            if amt:
                return PriceRow("Xbox", product_name or "Xbox Product", market_iso.upper(), ccy.upper() if ccy else None, float(amt),
                                f"https://www.xbox.com/{loc.split('-')[0]}/games/store/placeholder/{product_id}", f"xbox:{product_id}"), None
    except Exception:
        pass
    try:
        r = requests.get(DISPLAYCATALOG_URL, params={"bigIds": product_id, "market": market_iso.upper(), "languages": "en-US", "fieldsTemplate": "Details"}, headers=headers, timeout=25)
        if r.status_code == 200:
            amt, ccy = _parse_xbox_price_from_products(r.json())
            if amt:
                return PriceRow("Xbox", product_name or "Xbox Product", market_iso.upper(), ccy.upper() if ccy else None, float(amt),
                                f"https://www.xbox.com/en-US/games/store/placeholder/{product_id}", f"xbox:{product_id}"), None
    except Exception:
        pass
    return None, MissRow("Xbox", product_name or product_id, market_iso, "no_price_entries")

# -----------------------------
# PlayStation helpers (extracted from PS v1.7 and adapted)
# -----------------------------
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
}
PRODUCT_ID_RE = re.compile(r"/product/([^/?#]+)")

def _build_headers(locale: Optional[str] = None) -> Dict[str, str]:
    h = dict(DEFAULT_HEADERS)
    if locale:
        lang = locale.split("-")[0]
        h["Accept-Language"] = f"{lang}-{locale.split('-')[-1].upper()},{lang};q=0.8"
    else:
        h["Accept-Language"] = "en-US,en;q=0.9"
    return h

def _fetch_html(url: str, locale: Optional[str] = None, timeout: int = 25) -> Optional[str]:
    try:
        r = requests.get(url, headers=_build_headers(locale), timeout=timeout)
        if r.status_code == 200:
            return r.text
        return None
    except requests.RequestException:
        return None

def _parse_next_json(html: str) -> Optional[dict]:
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

def _from_next_json(next_json: dict) -> Tuple[Optional[str], Optional[str], Optional[float], Optional[float], Optional[str]]:
    try:
        props = next_json.get("props", {})
        page_props = props.get("pageProps", {})
        product = page_props.get("product") or page_props.get("pageData") or page_props.get("telemetryData") or {}

        title = product.get("name") or product.get("title") or page_props.get("title")
        product_id = product.get("id") or product.get("productId") or product.get("slug") or page_props.get("productId")

        msrp = None
        current = None
        currency = None

        p = product.get("price") if isinstance(product, dict) else None
        if isinstance(p, dict):
            msrp = _num(p.get("basePrice")) or msrp
            current = _num(p.get("discountedPrice") or p.get("finalPrice") or p.get("current") or p.get("value")) or current
            currency = p.get("currency") or currency

        if current is None:
            default_sku = product.get("defaultSku") if isinstance(product, dict) else None
            if isinstance(default_sku, dict):
                p2 = default_sku.get("price") if isinstance(default_sku.get("price"), dict) else None
                if p2:
                    msrp = _num(p2.get("basePrice")) or msrp
                    current = _num(p2.get("discountedPrice") or p2.get("finalPrice") or p2.get("current") or p2.get("value")) or current
                    currency = p2.get("currency") or currency

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

        if current is None:
            pp = page_props.get("price") or page_props.get("store", {}).get("price")
            if isinstance(pp, dict):
                msrp = _num(pp.get("basePrice")) or msrp
                current = _num(pp.get("discountedPrice") or pp.get("finalPrice") or pp.get("current")) or current
                currency = pp.get("currency") or currency

        return title, product_id, msrp, current, currency
    except Exception:
        return None, None, None, None, None

def _parse_json_ld(html: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
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
                types = set(str(x).lower() for x in t)
            else:
                types = {str(t).lower()} if t else set()
            if {"product","videogame","offer"} & types or "offers" in obj:
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

def _parse_meta_tags(html: str) -> Tuple[Optional[float], Optional[str]]:
    soup = BeautifulSoup(html, "html.parser")
    meta_amt = soup.find("meta", property="og:price:amount")
    meta_cur = soup.find("meta", property="og:price:currency")
    if meta_amt and meta_amt.get("content"):
        try:
            price = _num(meta_amt.get("content"))
        except Exception:
            price = None
        currency = meta_cur.get("content") if meta_cur and meta_cur.get("content") else None
        if price is not None:
            return price, currency
    ip = soup.find(attrs={"itemprop":"price"})
    ipcur = soup.find(attrs={"itemprop":"priceCurrency"})
    if ip and ip.get("content"):
        price = _num(ip.get("content"))
        currency = ipcur.get("content") if ipcur and ipcur.get("content") else None
        if price is not None:
            return price, currency
    return None, None

def _extract_product_id_from_href(href: str) -> Optional[str]:
    if not href:
        return None
    m = PRODUCT_ID_RE.search(href)
    if m:
        return m.group(1)
    return None

def _resolve_ps_product_id(input_ref: str, locale: str, title_hint: Optional[str]=None, edition_hint: Optional[str]=None) -> Tuple[Optional[str], Optional[str]]:
    """Return (product_id, discovered_title). Accepts a product URL or product ID."""
    if not input_ref:
        return None, None
    s = input_ref.strip()
    if not s.startswith("http"):
        return s, None

    pid = _extract_product_id_from_href(s)
    if pid:
        return pid, None

    html = _fetch_html(s, locale=None)
    discovered_title = None
    if html:
        soup = BeautifulSoup(html, "html.parser")
        discovered_title = soup.title.string.strip() if (soup.title and soup.title.string) else None
        for a in soup.find_all("a", href=True):
            pid = _extract_product_id_from_href(a["href"])
            if pid:
                return pid, discovered_title

    # last-resort search by title hint if provided
    t = title_hint or discovered_title
    if t:
        try:
            q = requests.utils.quote(t)
            search_url = f"https://store.playstation.com/{locale}/search/{q}"
            s_html = _fetch_html(search_url, locale=locale)
            if s_html:
                soup2 = BeautifulSoup(s_html, "html.parser")
                for a in soup2.find_all("a", href=True):
                    pid = _extract_product_id_from_href(a["href"])
                    if pid:
                        return pid, t
        except Exception:
            pass
    return None, discovered_title

def _build_product_url(locale: str, product_id: str) -> str:
    return f"https://store.playstation.com/{locale}/product/{product_id}"

def fetch_playstation_price(ps_ref: str, market_iso: str, forced_title: Optional[str] = None, title_hint: Optional[str] = None, edition_hint: Optional[str] = None) -> Tuple[Optional[PriceRow], Optional[MissRow]]:
    locale, currency = ps_market_meta(market_iso)
    # resolve product id if needed (cache in session for performance)
    cache_key = f"ps_resolve::{ps_ref.strip()}"
    if "ps_resolve_cache" not in st.session_state:
        st.session_state.ps_resolve_cache = {}
    pid = st.session_state.ps_resolve_cache.get(cache_key)
    if not pid:
        pid, _ = _resolve_ps_product_id(ps_ref.strip(), locale=locale, title_hint=title_hint, edition_hint=edition_hint)
        if pid:
            st.session_state.ps_resolve_cache[cache_key] = pid
        else:
            return None, MissRow("PlayStation", forced_title or (title_hint or ps_ref), market_iso, "cannot_resolve_ps_id")

    url = _build_product_url(locale, pid)
    html = _fetch_html(url, locale=locale)

    title = None
    msrp = current = None
    cur = None

    if html:
        nxt = _parse_next_json(html)
        if nxt:
            t, p, m, c, pcurr = _from_next_json(nxt)
            title = t or title
            if m is not None and m > 0: msrp = m
            if c is not None and c > 0:
                current = c
                cur = (pcurr or currency)
        if current is None:
            t2, c2, pcurr2 = _parse_json_ld(html)
            title = t2 or title
            if c2 is not None and c2 > 0:
                current = c2
                cur = (pcurr2 or currency)
                if msrp is None: msrp = current
        if current is None:
            c3, pcurr3 = _parse_meta_tags(html)
            if c3 is not None and c3 > 0:
                current = c3
                cur = (pcurr3 or currency)
                if msrp is None: msrp = current

    # prefer MSRP when present, else fall back to current / final
    amount = msrp if (msrp is not None and msrp > 0) else current
    if amount is None:
        return None, MissRow("PlayStation", forced_title or (title or f"PS Product {pid}"), market_iso, "no_price_found")

    return PriceRow("PlayStation", forced_title or (title or f"PS Product {pid}"), market_iso.upper(), (cur or currency), float(amount), url, f"ps:{pid}"), None

# -----------------------------
# Validators
# -----------------------------
def validate_and_fill_steam_rows(rows: List[dict]) -> List[dict]:
    updated = []
    for r in rows:
        appid = str(r.get("appid") or "").strip()
        if not appid.isdigit():
            r["_steam_error"] = "appid must be numeric"
            updated.append(r); continue
        data = _steam_appdetails(appid, cc="US")
        if not data:
            r["_steam_error"] = "not found on Steam API"
        else:
            r["_steam_error"] = ""
            if not r.get("title"):
                r["title"] = data.get("name") or r.get("title")
        updated.append(r)
    return updated

def validate_and_fill_xbox_rows(rows: List[dict]) -> List[dict]:
    updated = []
    headers = {"MS-CV": _ms_cv(), "Accept": "application/json"}
    for r in rows:
        store_id = str(r.get("store_id") or "").strip()
        if len(store_id) != 12 or not store_id.upper().startswith("9"):
            r["_xbox_error"] = "store_id should be 12 chars (usually starts with 9)"
            updated.append(r); continue
        try:
            resp = requests.get(DISPLAYCATALOG_URL, params={"bigIds": store_id, "market": "US", "languages": "en-US", "fieldsTemplate": "Details"}, headers=headers, timeout=12)
            j = resp.json() if resp.status_code == 200 else {}
            products = j.get("Products") or j.get("products") or []
            if not products:
                r["_xbox_error"] = "not found on Xbox catalog"
            else:
                r["_xbox_error"] = ""
                if not r.get("title"):
                    lp = (products[0].get("LocalizedProperties") or products[0].get("localizedProperties") or [])
                    if lp and lp[0].get("ProductTitle"):
                        r["title"] = lp[0]["ProductTitle"]
        except Exception:
            r["_xbox_error"] = "lookup error"
        updated.append(r)
    return updated

def validate_and_fill_ps_rows(rows: List[dict]) -> List[dict]:
    updated = []
    for r in rows:
        ps_ref = str(r.get("ps_ref") or "").strip()
        if not ps_ref:
            r["_ps_error"] = "enter a PS product URL or product ID"
            updated.append(r); continue
        # Try resolving in US
        pid, _ = _resolve_ps_product_id(ps_ref, locale="en-us", title_hint=r.get("title") or None, edition_hint=r.get("edition_hint") or None)
        if not pid:
            r["_ps_error"] = "cannot resolve product id"
        else:
            r["_ps_error"] = ""
        updated.append(r)
    return updated

# -----------------------------
# Sidebar editors
# -----------------------------
with st.sidebar:
    st.header("Controls")
    default_markets = ",".join(sorted(COUNTRY_NAMES.keys()))
    user_markets = st.text_area("Markets (comma-separated ISO country codes)", value=default_markets, height=120)
    markets = [m.strip().upper() for m in user_markets.split(",") if m.strip()]

    st.markdown("""**Scale factor help**  
- Leave **1.0** for no scaling.  
- **39.99 → 69.99** ⇒ **1.75** (7 ÷ 4)  
- **49.99 → 69.99** ⇒ **1.40** (7 ÷ 5)  
- **29.99 → 69.99** ⇒ **2.33**  
*General rule: scale_factor = target_price ÷ source_price.*""")

    if "steam_rows" not in st.session_state:
        st.session_state.steam_rows = DEFAULT_STEAM_ROWS.copy()
    if "xbox_rows" not in st.session_state:
        st.session_state.xbox_rows = DEFAULT_XBOX_ROWS.copy()
    if "ps_rows" not in st.session_state:
        st.session_state.ps_rows = DEFAULT_PS_ROWS.copy()

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
            "scale_factor": st.column_config.NumberColumn(step=0.05, min_value=0.0, max_value=10.0, format="%.2f"),
            "weight":  st.column_config.NumberColumn(step=0.1, min_value=0.0, max_value=10.0, format="%.2f"),
            "_steam_error": st.column_config.TextColumn("error", disabled=True),
        },
    )
    st.session_state.steam_rows = steam_df.to_dict(orient="records")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔎 Validate & auto-fill (Steam)"):
            st.session_state.steam_rows = validate_and_fill_steam_rows(st.session_state.steam_rows)
            st.rerun()
    with c2:
        if st.button("➕ Add Steam row"):
            st.session_state.steam_rows.append({"include": True, "title": "", "appid": "", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""})
            st.rerun()

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
            "scale_factor": st.column_config.NumberColumn(step=0.05, min_value=0.0, max_value=10.0, format="%.2f"),
            "weight":  st.column_config.NumberColumn(step=0.1, min_value=0.0, max_value=10.0, format="%.2f"),
            "_xbox_error": st.column_config.TextColumn("error", disabled=True),
        },
    )
    st.session_state.xbox_rows = xbox_df.to_dict(orient="records")

    d1, d2 = st.columns(2)
    with d1:
        if st.button("🔎 Validate & auto-fill (Xbox)"):
            st.session_state.xbox_rows = validate_and_fill_xbox_rows(st.session_state.xbox_rows)
            st.rerun()
    with d2:
        if st.button("➕ Add Xbox row"):
            st.session_state.xbox_rows.append({"include": True, "title": "", "store_id": "", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""})
            st.rerun()

    st.subheader("PlayStation basket")
    ps_df = st.data_editor(
        pd.DataFrame(st.session_state.ps_rows),
        key="ps_editor",
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "include": st.column_config.CheckboxColumn(default=True),
            "title":   st.column_config.TextColumn(),
            "ps_ref":  st.column_config.TextColumn(help="Paste a PlayStation Store URL (/concept or /product) or a product ID (PPSA…)"),
            "edition_hint": st.column_config.TextColumn(help="Optional keyword to bias selection (e.g., 'Standard', 'Online')"),
            "scale_factor": st.column_config.NumberColumn(step=0.05, min_value=0.0, max_value=10.0, format="%.2f"),
            "weight":  st.column_config.NumberColumn(step=0.1, min_value=0.0, max_value=10.0, format="%.2f"),
            "_ps_error": st.column_config.TextColumn("error", disabled=True),
        },
    )
    st.session_state.ps_rows = ps_df.to_dict(orient="records")

    e1, e2 = st.columns(2)
    with e1:
        if st.button("🔎 Validate & auto-fill (PlayStation)"):
            st.session_state.ps_rows = validate_and_fill_ps_rows(st.session_state.ps_rows)
            st.rerun()
    with e2:
        if st.button("➕ Add PS row"):
            st.session_state.ps_rows.append({"include": True, "title": "", "ps_ref": "", "edition_hint": "", "scale_factor": 1.0, "weight": 1.0, "_ps_error": ""})
            st.rerun()

    st.divider()
    run = st.button("Run Pricing Pull", type="primary")

# -----------------------------
# Run + compute
# -----------------------------
if run:
    steam_rows = [r for r in st.session_state.steam_rows if r.get("include") and r.get("appid")]
    xbox_rows  = [r for r in st.session_state.xbox_rows  if r.get("include") and r.get("store_id")]
    ps_rows    = [r for r in st.session_state.ps_rows    if r.get("include") and r.get("ps_ref")]

    # meta & canonical titles keyed by identity
    steam_meta   = { f"steam:{str(r['appid']).strip()}": {"weight": float(r.get("weight",1.0)), "scale": float(r.get("scale_factor",1.0))} for r in steam_rows }
    xbox_meta    = { f"xbox:{str(r['store_id']).strip()}": {"weight": float(r.get("weight",1.0)), "scale": float(r.get("scale_factor",1.0))} for r in xbox_rows }
    ps_meta      = { f"ps:{str(r['ps_ref']).strip()}": {"weight": float(r.get("weight",1.0)), "scale": float(r.get("scale_factor",1.0))} for r in ps_rows }

    steam_title  = { f"steam:{str(r['appid']).strip()}": (r.get("title") or f"Steam App {r['appid']}") for r in steam_rows }
    xbox_title   = { f"xbox:{str(r['store_id']).strip()}": (r.get("title") or f"Xbox Product {r['store_id']}") for r in xbox_rows }
    ps_title     = { f"ps:{str(r['ps_ref']).strip()}": (r.get("title") or f"PS Product") for r in ps_rows }

    TITLE_MAP = {**steam_title, **xbox_title, **ps_title}
    META_MAP  = {**steam_meta, **xbox_meta, **ps_meta}

    rows: List[PriceRow] = []
    misses: List[MissRow] = []
    with st.status("Pulling prices across markets…", expanded=False) as status:
        futures = []
        with ThreadPoolExecutor(max_workers=20) as ex:
            for cc in markets:
                for r in steam_rows:
                    futures.append(ex.submit(fetch_steam_price, str(r["appid"]).strip(), cc, TITLE_MAP[f"steam:{str(r['appid']).strip()}"]))
            for cc in markets:
                for r in xbox_rows:
                    futures.append(ex.submit(fetch_xbox_price, TITLE_MAP[f"xbox:{str(r['store_id']).strip()}"], str(r["store_id"]).strip(), cc))
            for cc in markets:
                for r in ps_rows:
                    futures.append(ex.submit(fetch_playstation_price, str(r["ps_ref"]).strip(), cc, TITLE_MAP[f"ps:{str(r['ps_ref']).strip()}"], r.get("title") or None, r.get("edition_hint") or None))

            for f in as_completed(futures):
                try:
                    result = f.result()
                except Exception:
                    result = (None, MissRow("unknown","unknown","unknown","exception"))
                row, miss = result
                if row: rows.append(row)
                if miss: misses.append(miss)

        status.update(label="Done!", state="complete")

    raw_df = pd.DataFrame([asdict(r) for r in rows])
    if not raw_df.empty:
        # enrich
        raw_df.insert(2, "country_name", raw_df["country"].map(country_name))
        def _meta(identity):
            return META_MAP.get(identity, {"weight":1.0, "scale":1.0})
        meta_df = pd.DataFrame(list(raw_df["identity"].map(lambda i: _meta(i))))
        raw_df = pd.concat([raw_df, meta_df], axis=1)
        raw_df["title"] = raw_df["identity"].map(lambda i: TITLE_MAP.get(i, "Unknown"))
        # scale price
        raw_df["price"] = raw_df["price"] * raw_df["scale"]
        raw_df["title"] = raw_df.apply(lambda r: f"{r['title']} (scaled)" if r["scale"] and abs(r["scale"]-1.0) > 1e-6 else r["title"], axis=1)

        # ---- USD conversion on RAW rows
        rates = fetch_usd_rates(force=False)
        raw_df["price_usd"] = [to_usd(p, c, rates) for p,c in zip(raw_df["price"], raw_df["currency"])]

        st.subheader("Raw Basket Rows (after scaling)")
        st.dataframe(raw_df)

        # weighted mean per country/platform
        grp = raw_df.groupby(["platform","country","currency"], dropna=False)
        sums = grp.apply(lambda g: (g["price"] * g["weight"]).sum()).rename("weighted_sum")
        wts  = grp["weight"].sum().rename("weight_total")
        reco = pd.concat([sums, wts], axis=1).reset_index()
        reco["RecommendedPrice"] = reco.apply(lambda r: (r["weighted_sum"]/r["weight_total"]) if r["weight_total"]>0 else None, axis=1)
        reco = reco[["platform","country","currency","RecommendedPrice"]]
        reco.insert(1, "country_name", reco["country"].map(country_name))

        # vanity per platform
        def vanity_apply(df: pd.DataFrame) -> pd.DataFrame:
            if df.empty: return df
            out = df.copy().reset_index(drop=True)
            out["RecommendedPrice"] = [apply_vanity(c,p) for c,p in zip(out["country"], out["RecommendedPrice"])]
            return out

        reco_xbox  = vanity_apply(reco[reco["platform"]=="Xbox"][["country_name","country","currency","RecommendedPrice"]])
        reco_steam = vanity_apply(reco[reco["platform"]=="Steam"][["country_name","country","currency","RecommendedPrice"]])
        reco_ps    = vanity_apply(reco[reco["platform"]=="PlayStation"][["country_name","country","currency","RecommendedPrice"]])

        # ---- USD conversion on RECO tables
        for df in (reco_xbox, reco_steam, reco_ps):
            if not df.empty:
                df["RecommendedPriceUSD"] = [to_usd(p, cur, rates) for p,cur in zip(df["RecommendedPrice"], df["currency"])]

        # ---------------- Regional Pricing Recommendation views ----------------
        def fx_view(df: pd.DataFrame, label: str) -> pd.DataFrame:
            # derive US benchmark automatically
            us_row = df.loc[df["country"]=="US"]
            if us_row.empty:
                return pd.DataFrame()  # no US row to benchmark
            us_local = float(us_row["RecommendedPrice"].iloc[0])
            us_ccy   = str(us_row["currency"].iloc[0])
            us_usd   = to_usd(us_local, us_ccy, rates) or None

            out = df[["country_name","country","currency","RecommendedPrice"]].copy()
            out.rename(columns={"RecommendedPrice":"LocalPrice"}, inplace=True)
            out["USDPrice"] = [to_usd(p, cur, rates) for p,cur in zip(out["LocalPrice"], out["currency"])]
            if us_usd is not None:
                out["DiffUSD"] = [None if pd.isna(v) else round(v - us_usd, 2) for v in out["USDPrice"]]
                out["PctDiff"] = [None if pd.isna(v) or us_usd==0 else str(round((v/us_usd - 1.0)*100.0, 0)) + "%" for v in out["USDPrice"]]
            out.insert(0, "platform", label)
            return out.sort_values("country_name").reset_index(drop=True)

        fx_x = fx_view(reco_xbox, "Xbox") if not reco_xbox.empty else pd.DataFrame()
        fx_s = fx_view(reco_steam, "Steam") if not reco_steam.empty else pd.DataFrame()
        fx_p = fx_view(reco_ps, "PlayStation") if not reco_ps.empty else pd.DataFrame()

        if not fx_x.empty:
            st.subheader("Xbox Regional Pricing Recommendation (Local, USD, %Diff vs US)")
            st.dataframe(fx_x)
        if not fx_s.empty:
            st.subheader("Steam Regional Pricing Recommendation (Local, USD, %Diff vs US)")
            st.dataframe(fx_s)
        if not fx_p.empty:
            st.subheader("PlayStation Regional Pricing Recommendation (Local, USD, %Diff vs US)")
            st.dataframe(fx_p)
        # ----------------------------------------------------------------------

        merged = reco_xbox.rename(columns={"RecommendedPrice":"XboxRecommended","RecommendedPriceUSD":"XboxRecommendedUSD"})
        merged = pd.merge(
            merged,
            reco_steam.rename(columns={"RecommendedPrice":"SteamRecommended","RecommendedPriceUSD":"SteamRecommendedUSD"}),
            on=["country_name","country","currency"],
            how="outer",
        )
        merged = pd.merge(
            merged,
            reco_ps.rename(columns={"RecommendedPrice":"PSRecommended","RecommendedPriceUSD":"PSRecommendedUSD"}),
            on=["country_name","country","currency"],
            how="outer",
        ).sort_values(["country"]).reset_index(drop=True)

        st.subheader("Combined Recommendations (Xbox + Steam + PlayStation)")
        st.dataframe(merged)

        csv = merged.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV (combined recommendations)", data=csv, file_name="aaa_tier_recommendations_xbox_steam_ps.csv", mime="text/csv")

    if misses:
        miss_df = pd.DataFrame([asdict(m) for m in misses]).sort_values(["platform","title","country"]).reset_index(drop=True)
        st.subheader("Diagnostics (no price found)")
        st.dataframe(miss_df)

else:
    st.info("Edit the baskets in the sidebar, set markets, then click **Run Pricing Pull**.", icon="🛠️")
