
# streamlit_app_combined_v2_1.py
import random, time, re, json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import requests
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

st.set_page_config(page_title="Game Pricing Recommendation Tool", page_icon="🎮", layout="wide")
st.title("🎮 Game Pricing Recommendation Tool – Xbox · Steam · PlayStation")

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

STEAM_CC_MAP: Dict[str, str] = {"US":"US","KZ":"KZ","CN":"CN","UA":"UA","ID":"ID","AR":"AR","TR":"TR","BR":"BR","CL":"CL",
    "IN":"IN","KR":"KR","PH":"PH","JP":"JP","VN":"VN","CO":"CO","NZ":"NZ","CR":"CR","SA":"SA","TW":"TW","SK":"SK","PE":"PE",
    "PL":"PL","SG":"SG","ZA":"ZA","HK":"HK","MX":"MX","GB":"GB","CA":"CA","AU":"AU","MY":"MY","FR":"FR","DE":"FR","AT":"FR",
    "BE":"FR","DK":"FR","FI":"FR","IE":"FR","NL":"FR","PT":"FR","ES":"FR","CZ":"FR","GR":"FR","HU":"FR","TH":"TH","UY":"UY",
    "QA":"QA","KW":"KW","AE":"AE","SV":"SV","PK":"PK","AM":"AM","CH":"CH","IL":"IL","RU":"RU"}

XBOX_LOCALE_MAP: Dict[str, Optional[str]] = {
    "US":"en-us","KZ":None,"CN":"zh-CN","UA":"uk-ua","ID":"id-id","AR":"es-ar","TR":"tr-tr","BR":"pt-br","CL":"es-cl",
    "IN":"en-in","KR":"ko-kr","PH":"en-ph","JP":"ja-jp","VN":"vi-vn","CO":"es-co","NZ":"en-nz","CR":"es-cr","SA":"ar-sa",
    "SE":None,"TW":"zh-tw","SK":"sk-sk","PE":"es-pe","PL":"pl-pl","SG":"en-sg","ZA":"en-za","HK":"zh-hk","MX":"es-mx",
    "GB":"en-gb","CA":"en-ca","AU":"en-au","MY":"en-my","FR":"fr-fr","DE":"de-de","AT":"de-at","BE":"fr-fr","DK":None,
    "FI":"fi-fi","IE":"en-ie","NL":"nl-nl","PT":"pt-pt","ES":"es-es","CZ":"cs-cz","GR":"el-gr","HU":"hu-hu","TH":"th-th",
    "UY":None,"QA":"ar-qa","KW":"ar-kw","AE":"ar-ae","SV":None,"PK":None,"AM":None,"CH":"de-ch","IL":"he-il","RU":"ru-ru"}
def xbox_locale_for(market: str) -> str:
    return XBOX_LOCALE_MAP.get(market.upper()) or "en-us"

# PlayStation locale/currency map (prefers English when available)
PS_ALL_LOCALES = [
    {"country":"US","locale":"en-us","currency":"USD"},
    {"country":"CA","locale":"en-ca","currency":"CAD"},{"country":"CA","locale":"fr-ca","currency":"CAD"},
    {"country":"MX","locale":"es-mx","currency":"MXN"},
    {"country":"BR","locale":"pt-br","currency":"BRL"},
    {"country":"AR","locale":"es-ar","currency":"ARS"},
    {"country":"CL","locale":"es-cl","currency":"CLP"},
    {"country":"CO","locale":"es-co","currency":"COP"},
    {"country":"PE","locale":"es-pe","currency":"PEN"},
    {"country":"UY","locale":"es-uy","currency":"UYU"},
    {"country":"CR","locale":"es-cr","currency":"CRC"},
    {"country":"GT","locale":"es-gt","currency":"GTQ"},
    {"country":"HN","locale":"es-hn","currency":"HNL"},
    {"country":"NI","locale":"es-ni","currency":"NIO"},
    {"country":"PA","locale":"es-pa","currency":"USD"},
    {"country":"PY","locale":"es-py","currency":"PYG"},
    {"country":"SV","locale":"es-sv","currency":"USD"},
    {"country":"DO","locale":"es-do","currency":"DOP"},
    {"country":"BO","locale":"es-bo","currency":"BOB"},
    {"country":"GB","locale":"en-gb","currency":"GBP"},
    {"country":"IE","locale":"en-ie","currency":"EUR"},
    {"country":"FR","locale":"fr-fr","currency":"EUR"},
    {"country":"BE","locale":"fr-be","currency":"EUR"},
    {"country":"BE","locale":"nl-be","currency":"EUR"},
    {"country":"NL","locale":"nl-nl","currency":"EUR"},
    {"country":"LU","locale":"fr-lu","currency":"EUR"},
    {"country":"DE","locale":"de-de","currency":"EUR"},
    {"country":"AT","locale":"de-at","currency":"EUR"},
    {"country":"CH","locale":"de-ch","currency":"CHF"},
    {"country":"CH","locale":"fr-ch","currency":"CHF"},
    {"country":"CH","locale":"it-ch","currency":"CHF"},
    {"country":"IT","locale":"it-it","currency":"EUR"},
    {"country":"ES","locale":"es-es","currency":"EUR"},
    {"country":"PT","locale":"pt-pt","currency":"EUR"},
    {"country":"PL","locale":"pl-pl","currency":"PLN"},
    {"country":"CZ","locale":"cs-cz","currency":"CZK"},
    {"country":"SK","locale":"sk-sk","currency":"EUR"},
    {"country":"HU","locale":"hu-hu","currency":"HUF"},
    {"country":"RO","locale":"ro-ro","currency":"RON"},
    {"country":"BG","locale":"bg-bg","currency":"BGN"},
    {"country":"GR","locale":"el-gr","currency":"EUR"},
    {"country":"HR","locale":"hr-hr","currency":"EUR"},
    {"country":"SI","locale":"sl-si","currency":"EUR"},
    {"country":"RS","locale":"sr-rs","currency":"RSD"},
    {"country":"TR","locale":"tr-tr","currency":"TRY"},
    {"country":"NO","locale":"no-no","currency":"NOK"},
    {"country":"SE","locale":"sv-se","currency":"SEK"},
    {"country":"DK","locale":"da-dk","currency":"DKK"},
    {"country":"FI","locale":"fi-fi","currency":"EUR"},
    {"country":"IS","locale":"is-is","currency":"ISK"},
    {"country":"UA","locale":"uk-ua","currency":"UAH"},
    {"country":"SA","locale":"ar-sa","currency":"SAR"},
    {"country":"AE","locale":"en-ae","currency":"AED"},
    {"country":"AE","locale":"ar-ae","currency":"AED"},
    {"country":"IL","locale":"he-il","currency":"ILS"},
    {"country":"ZA","locale":"en-za","currency":"ZAR"},
    {"country":"AU","locale":"en-au","currency":"AUD"},
    {"country":"NZ","locale":"en-nz","currency":"NZD"},
    {"country":"SG","locale":"en-sg","currency":"SGD"},
    {"country":"MY","locale":"en-my","currency":"MYR"},
    {"country":"TH","locale":"th-th","currency":"THB"},
    {"country":"ID","locale":"id-id","currency":"IDR"},
    {"country":"PH","locale":"en-ph","currency":"PHP"},
    {"country":"VN","locale":"vi-vn","currency":"VND"},
    {"country":"HK","locale":"en-hk","currency":"HKD"},
    {"country":"HK","locale":"zh-hk","currency":"HKD"},
    {"country":"TW","locale":"zh-tw","currency":"TWD"},
    {"country":"KR","locale":"ko-kr","currency":"KRW"},
    {"country":"JP","locale":"ja-jp","currency":"JPY"},
    {"country":"IN","locale":"en-in","currency":"INR"},
]
_PS_PREF: Dict[str, Dict[str, str]] = {}
for row in PS_ALL_LOCALES:
    c = row["country"].upper()
    if c not in _PS_PREF:
        _PS_PREF[c] = row
    if row["locale"].startswith("en-"):
        _PS_PREF[c] = row
def ps_market_meta(market_iso: str) -> Tuple[str, str]:
    m = _PS_PREF.get(market_iso.upper())
    return (m["locale"], m["currency"]) if m else ("en-us","USD")

# ---------- Defaults (PS pre-populated with canonical URLs for 6 titles) ----------
DEFAULT_STEAM_ROWS = [
    {"include": True, "title": "The Outer Worlds 2", "appid": "1449110", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""},
    {"include": True, "title": "Madden NFL 26", "appid": "3230400", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""},
    {"include": True, "title": "Call of Duty: Black Ops 6", "appid": "2933620", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""},
    {"include": True, "title": "NBA 2K26", "appid": "3472040", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""},
    {"include": True, "title": "Borderlands 4", "appid": "1285190", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""},
    {"include": True, "title": "HELLDIVERS 2", "appid": "553850", "scale_factor": 1.75, "weight": 1.0, "_steam_error": ""},
]
DEFAULT_XBOX_ROWS = [
    {"include": True, "title": "The Outer Worlds 2", "store_id": "9NSPRSXXZZLG", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""},
    {"include": True, "title": "Madden NFL 26", "store_id": "9NVD16NP4J8T", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""},
    {"include": True, "title": "Call of Duty: Black Ops 6", "store_id": "9PNCL2R6G8D0", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""},
    {"include": True, "title": "NBA 2K26", "store_id": "9PJ2RVRC0L1X", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""},
    {"include": True, "title": "Borderlands 4", "store_id": "9MX6HKF5647G", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""},
    {"include": True, "title": "HELLDIVERS 2", "store_id": "9P3PT7PQJD0M", "scale_factor": 1.75, "weight": 1.0, "_xbox_error": ""},
]
# These PS URLs are from your screenshots (you can edit them later if needed)
DEFAULT_PS_ROWS = [
    {"include": True, "title": "The Outer Worlds 2", "ps_ref": "https://store.playstation.com/en-us/product/UP6312-PPSA16483_00-OW2STANDARDPS5US", "edition_hint": "Standard", "scale_factor": 1.0, "weight": 1.0, "_ps_error": ""},
    {"include": True, "title": "Madden NFL 26", "ps_ref": "https://store.playstation.com/en-us/product/UP0006-PPSA26127_00-MADDENNFL26GAME0", "edition_hint": "Standard", "scale_factor": 1.0, "weight": 1.0, "_ps_error": ""},
    {"include": True, "title": "Call of Duty: Black Ops 6", "ps_ref": "https://store.playstation.com/en-us/product/UP0002-PPSA17544_00-BO6CROSSGENBUNDLE", "edition_hint": "Standard", "scale_factor": 1.0, "weight": 1.0, "_ps_error": ""},
    {"include": True, "title": "NBA 2K26", "ps_ref": "", "edition_hint": "Standard", "scale_factor": 1.0, "weight": 1.0, "_ps_error": ""},
    {"include": True, "title": "Borderlands 4", "ps_ref": "", "edition_hint": "Standard", "scale_factor": 1.0, "weight": 1.0, "_ps_error": ""},
    {"include": True, "title": "HELLDIVERS 2", "ps_ref": "https://store.playstation.com/en-us/product/UP9000-PPSA14719_00-ARROWHEADGAAS000", "edition_hint": "", "scale_factor": 1.75, "weight": 1.0, "_ps_error": ""},
]

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
        if x > 0: cand.append(x)
    return round(min(cand, key=lambda v: (abs(v-price), -v)), 2)

def apply_vanity(country: str, price: float) -> float:
    rule = VANITY_RULES.get(country.upper())
    if rule and rule.get("nines"): return _nearest_x9_suffix(float(price), float(rule["suffix"]))
    return round(price, 2)

def fetch_usd_rates(force: bool = False) -> Dict[str, float]:
    now = time.time()
    if ("usd_rates" in st.session_state and "usd_rates_ts" in st.session_state and now - st.session_state["usd_rates_ts"] < 7200 and not force):
        return dict(st.session_state["usd_rates"])
    rates = {"USD": 1.0}
    try:
        resp = requests.get("https://api.exchangerate.host/latest", params={"base": "USD"}, timeout=15)
        if resp.status_code == 200:
            data = resp.json() or {}
            if "rates" in data:
                rates.update({k.upper(): float(v) for k,v in data["rates"].items() if isinstance(v,(int,float)) and v>0})
    except Exception:
        pass
    if len(rates) == 1:
        try:
            r2 = requests.get("https://open.er-api.com/v6/latest/USD", timeout=15)
            d2 = r2.json() if r2.status_code == 200 else {}
            if d2.get("result")=="success":
                rates.update({k.upper(): float(v) for k,v in d2.get("rates",{}).items() if isinstance(v,(int,float)) and v>0})
        except Exception:
            pass
    st.session_state["usd_rates"] = dict(rates); st.session_state["usd_rates_ts"] = now
    return rates

def to_usd(amount: Optional[float], currency: Optional[str], rates: Dict[str, float]) -> Optional[float]:
    if amount is None or currency is None: return None
    r = rates.get(currency.upper())
    if not r or r<=0: return None
    return round(float(amount)/r, 2)

# ---------------- Steam / Xbox helpers (unchanged) ----------------
STEAM_APPDETAILS = "https://store.steampowered.com/api/appdetails"
STEAM_PACKAGEDETAILS = "https://store.steampowered.com/api/packagedetails"
def _steam_appdetails(appid: str, cc: str) -> Optional[dict]:
    try:
        r = requests.get(STEAM_APPDETAILS, params={"appids": appid, "cc": cc, "l":"en"}, headers=UA, timeout=25)
        data = r.json().get(str(appid), {})
        return data.get("data") if (data and data.get("success")) else None
    except Exception:
        return None
def _steam_packagedetails(ids: List[int], cc: str) -> Dict[int, dict]:
    out: Dict[int, dict] = {}
    try:
        r = requests.get(STEAM_PACKAGEDETAILS, params={"packageids": ",".join(str(i) for i in ids), "cc": cc, "l":"en"}, headers=UA, timeout=25)
        data = r.json() if r.status_code == 200 else {}
        for pid, obj in (data or {}).items():
            if isinstance(obj, dict) and obj.get("success") and isinstance(obj.get("data"), dict):
                out[int(pid)] = obj["data"]
    except Exception:
        pass
    return out
def fetch_steam_price(appid: str, cc_iso: str, forced_title: Optional[str] = None) -> Tuple[Optional[PriceRow], Optional[MissRow]]:
    cc = STEAM_CC_MAP.get(cc_iso.upper(), cc_iso.upper())
    data = _steam_appdetails(appid, cc)
    if not data: return None, MissRow("Steam", forced_title or appid, cc_iso, "appdetails_no_data")
    pov = data.get("price_overview") or {}
    cents = None
    if isinstance(pov.get("initial"), int) and pov.get("initial")>0: cents = pov["initial"]
    elif isinstance(pov.get("final"), int) and pov.get("final")>0: cents = pov["final"]
    if cents:
        price = round(cents/100.0, 2); currency = (pov.get("currency") or "").upper() or None
        name = forced_title or data.get("name") or f"Steam App {appid}"
        return PriceRow("Steam", name, cc_iso.upper(), currency, price, f"https://store.steampowered.com/app/{appid}", f"steam:{appid}"), None
    sub_ids: List[int] = []
    if isinstance(data.get("packages"), list): sub_ids += [int(x) for x in data["packages"] if isinstance(x,int)]
    for grp in data.get("package_groups", []):
        for sub in grp.get("subs", []):
            sid = sub.get("packageid")
            if isinstance(sid, int): sub_ids.append(sid)
    sub_ids = list(dict.fromkeys(sub_ids))
    if not sub_ids: return None, MissRow("Steam", forced_title or data.get("name") or appid, cc_iso, "packagedetails_no_price")
    packs = _steam_packagedetails(sub_ids, cc=cc)
    for _, p in packs.items():
        po = (p.get("price") or {})
        cents = po.get("initial") if isinstance(po.get("initial"),int) and po.get("initial")>0 else po.get("final")
        if isinstance(cents,int) and cents>0:
            price = round(cents/100.0, 2); currency = (po.get("currency") or "").upper() or None
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
        if not products: return None, None
        p0 = products[0]
        for sku in (p0.get("DisplaySkuAvailabilities") or p0.get("displaySkuAvailabilities") or []):
            for av in (sku.get("Availabilities") or sku.get("availabilities") or []):
                omd = av.get("OrderManagementData") or av.get("orderManagementData") or {}
                price = omd.get("Price") or omd.get("price") or {}
                amount = price.get("MSRP") or price.get("msrp") or price.get("ListPrice") or price.get("listPrice")
                currency = price.get("CurrencyCode") or price.get("currencyCode")
                if amount: return float(amount), (str(currency).upper() if currency else None)
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

# ---------------- PlayStation helpers ----------------
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
                   "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Cache-Control": "no-cache","Pragma": "no-cache","Connection": "keep-alive"}
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
        return r.text if r.status_code == 200 else None
    except requests.RequestException:
        return None
def _parse_next_json(html: str) -> Optional[dict]:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not tag or not tag.string: return None
    try:
        return json.loads(tag.string)
    except Exception:
        return None
def _num(x: Any) -> Optional[float]:
    try:
        if x is None: return None
        return float(str(x).strip().replace(",",""))
    except Exception:
        return None
def _from_next_json(next_json: dict) -> Tuple[Optional[str], Optional[str], Optional[float], Optional[float], Optional[str]]:
    try:
        props = next_json.get("props", {}); page_props = props.get("pageProps", {})
        product = page_props.get("product") or page_props.get("pageData") or page_props.get("telemetryData") or {}
        title = product.get("name") or product.get("title") or page_props.get("title")
        product_id = product.get("id") or product.get("productId") or product.get("slug") or page_props.get("productId")
        msrp = None; current = None; currency = None
        def pull_price(obj: dict):
            nonlocal msrp, current, currency
            if not isinstance(obj, dict): return
            msrp = _num(obj.get("basePrice")) or _num(obj.get("strikethroughPrice")) or _num(obj.get("regularPrice")) or _num(obj.get("originalPrice")) or msrp
            current = _num(obj.get("discountedPrice") or obj.get("finalPrice") or obj.get("current") or obj.get("value")) or current
            currency = obj.get("currency") or currency
        pull_price(product.get("price") if isinstance(product, dict) else None)
        if current is None:
            default_sku = product.get("defaultSku") if isinstance(product, dict) else None
            if isinstance(default_sku, dict): pull_price(default_sku.get("price") or {})
        if current is None:
            skus = product.get("skus") if isinstance(product, dict) else None
            if isinstance(skus, list):
                for sku in skus:
                    pull_price(sku.get("price") or {})
                    if current is not None: break
        if current is None:
            pp = page_props.get("price") or page_props.get("store", {}).get("price")
            pull_price(pp or {})
        return title, product_id, msrp, current, currency
    except Exception:
        return None, None, None, None, None
def _extract_product_id_from_href(href: str) -> Optional[str]:
    if not href: return None
    m = PRODUCT_ID_RE.search(href)
    return m.group(1) if m else None
def search_ps_by_title(locale: str, title: str, edition_hint: Optional[str]=None) -> Tuple[Optional[str], Optional[str]]:
    try:
        q = requests.utils.quote(title)
        search_url = f"https://store.playstation.com/{locale}/search/{q}"
        s_html = _fetch_html(search_url, locale=locale)
        if not s_html: return None, None
        soup = BeautifulSoup(s_html, "html.parser")
        candidates = []
        for a in soup.find_all("a", href=True):
            pid = _extract_product_id_from_href(a["href"])
            if pid:
                t = a.get("title") or a.get("aria-label") or ""
                candidates.append((pid, t))
        def score(item):
            pid, t = item; T = (t or "").lower(); s = 0
            if "standard" in T: s += 2
            if edition_hint and edition_hint.lower() in T: s += 3
            if title.lower() in T: s += 2
            return s
        candidates.sort(key=score, reverse=True)
        if candidates:
            pid, _ = candidates[0]
            return pid, f"https://store.playstation.com/{locale}/product/{pid}"
        return None, None
    except Exception:
        return None, None
def _build_product_url(locale: str, product_id: str) -> str:
    return f"https://store.playstation.com/{locale}/product/{product_id}"
def fetch_playstation_price(ps_ref: str, market_iso: str, forced_title: Optional[str] = None, title_hint: Optional[str] = None, edition_hint: Optional[str] = None, prefer_msrp: bool = True) -> Tuple[Optional[PriceRow], Optional[MissRow]]:
    locale, currency = ps_market_meta(market_iso)
    original_ref = (ps_ref or "").strip()
    pid = None
    if original_ref:
        if original_ref.startswith("http"):
            pid = _extract_product_id_from_href(original_ref)
            if not pid:
                html = _fetch_html(original_ref, locale=None)
                if html:
                    soup = BeautifulSoup(html, "html.parser")
                    for a in soup.find_all("a", href=True):
                        pid = _extract_product_id_from_href(a["href"])
                        if pid: break
        else:
            pid = original_ref
    if not pid:
        t = title_hint or forced_title or original_ref
        if not t: return None, MissRow("PlayStation", forced_title or "unknown", market_iso, "no_ref_or_title")
        pid, _ = search_ps_by_title(locale, t, edition_hint)
        if not pid: return None, MissRow("PlayStation", forced_title or t, market_iso, "cannot_resolve_ps_id")
    url = _build_product_url(locale, pid)
    html = _fetch_html(url, locale=locale)
    title = None; msrp = current = None; cur = None
    if html:
        nxt = _parse_next_json(html)
        if nxt:
            t, p, m, c, pcurr = _from_next_json(nxt)
            title = t or title
            if m is not None and m>0: msrp = m
            if c is not None and c>0: current = c; cur = pcurr or currency
    amount = None
    if prefer_msrp and msrp: amount = msrp
    if amount is None: amount = msrp if msrp else current
    if amount is None:
        return None, MissRow("PlayStation", forced_title or (title or f"PS Product {pid}"), market_iso, "no_price_found")
    identity = f"ps:{original_ref or pid}"
    return PriceRow("PlayStation", forced_title or (title or f"PS Product {pid}"), market_iso.upper(), (cur or currency), float(amount), url, identity), None

# ---------------- Validators / autofill ----------------
def validate_and_fill_ps_rows(rows: List[dict]) -> List[dict]:
    out = []; locale, _ = ps_market_meta("US")
    for r in rows:
        title = (r.get("title") or "").strip()
        ref = (r.get("ps_ref") or "").strip()
        edition = (r.get("edition_hint") or "").strip() or None
        pid = None; canonical_title = None
        if not ref and title:
            pid, page_url = search_ps_by_title(locale, title, edition)
            if pid: ref = page_url
        if ref and ref.startswith("http"):
            pid = _extract_product_id_from_href(ref)
            if not pid:
                html = _fetch_html(ref, locale=None)
                if html:
                    soup = BeautifulSoup(html, "html.parser")
                    for a in soup.find_all("a", href=True):
                        pid = _extract_product_id_from_href(a["href"])
                        if pid: break
            if pid: ref = _build_product_url(locale, pid)
        elif ref and not ref.startswith("http"):
            pid = ref; ref = _build_product_url(locale, pid)
        if pid:
            html = _fetch_html(_build_product_url(locale, pid), locale=locale)
            if html:
                nxt = _parse_next_json(html)
                if nxt:
                    t, *_ = _from_next_json(nxt)
                    if t: canonical_title = t
        if not pid:
            r["_ps_error"] = "cannot resolve product id"
        else:
            r["_ps_error"] = ""; r["ps_ref"] = ref
            if canonical_title: r["title"] = canonical_title
        out.append(r)
    return out

def validate_and_fill_steam_rows(rows: List[dict]) -> List[dict]:
    return rows
def validate_and_fill_xbox_rows(rows: List[dict]) -> List[dict]:
    return rows

# ---------------- UI ----------------
with st.sidebar:
    st.header("Controls")
    default_markets = ",".join(sorted(COUNTRY_NAMES.keys()))
    user_markets = st.text_area("Markets (comma-separated ISO country codes)", value=default_markets, height=120)
    markets = [m.strip().upper() for m in user_markets.split(",") if m.strip()]
    prefer_msrp = st.checkbox("Prefer MSRP (ignore discounts)", value=True, help="When available, use MSRP instead of temporary sale prices.")

    if "steam_rows" not in st.session_state: st.session_state.steam_rows = DEFAULT_STEAM_ROWS.copy()
    if "xbox_rows" not in st.session_state: st.session_state.xbox_rows = DEFAULT_XBOX_ROWS.copy()
    if "ps_rows" not in st.session_state:   st.session_state.ps_rows   = DEFAULT_PS_ROWS.copy()

    st.subheader("PlayStation basket")
    ps_df = st.data_editor(pd.DataFrame(st.session_state.ps_rows), key="ps_editor", num_rows="dynamic", use_container_width=True,
        column_config={
            "include": st.column_config.CheckboxColumn(default=True),
            "title": st.column_config.TextColumn(),
            "ps_ref": st.column_config.TextColumn(help="Paste a PS Store URL (/product/...) or a PPSA id. Leave blank to resolve via title."),
            "edition_hint": st.column_config.TextColumn(help="Optional keyword to bias SKU selection (e.g., 'Standard')."),
            "scale_factor": st.column_config.NumberColumn(step=0.05, min_value=0.0, max_value=10.0, format="%.2f"),
            "weight": st.column_config.NumberColumn(step=0.1, min_value=0.0, max_value=10.0, format="%.2f"),
            "_ps_error": st.column_config.TextColumn("error", disabled=True),
        })
    st.session_state.ps_rows = ps_df.to_dict(orient="records")
    e1, e2 = st.columns(2)
    with e1:
        if st.button("🔎 Validate & auto-fill (PlayStation)"): st.session_state.ps_rows = validate_and_fill_ps_rows(st.session_state.ps_rows); st.rerun()
    with e2:
        if st.button("➕ Add PS row"): st.session_state.ps_rows.append({"include": True, "title": "", "ps_ref": "", "edition_hint": "", "scale_factor": 1.0, "weight": 1.0, "_ps_error": ""}); st.rerun()

    st.divider()
    run = st.button("Run Pricing Pull", type="primary")

def country_map_series(df):
    df = df.copy()
    df.insert(2, "country_name", df["country"].map(country_name))
    return df

if run:
    steam_rows = [r for r in st.session_state.steam_rows if r.get("include")]
    xbox_rows  = [r for r in st.session_state.xbox_rows  if r.get("include")]
    ps_rows    = [r for r in st.session_state.ps_rows    if r.get("include")]

    steam_meta   = { f"steam:{str(r.get('appid','')).strip()}": {"weight": float(r.get("weight",1.0)), "scale": float(r.get("scale_factor",1.0))} for r in steam_rows if r.get("appid") }
    xbox_meta    = { f"xbox:{str(r.get('store_id','')).strip()}": {"weight": float(r.get("weight",1.0)), "scale": float(r.get("scale_factor",1.0))} for r in xbox_rows if r.get("store_id") }
    ps_meta      = { f"ps:{(str(r.get('ps_ref','')).strip() or str(r.get('title','')).strip())}": {"weight": float(r.get("weight",1.0)), "scale": float(r.get("scale_factor",1.0))} for r in ps_rows }

    steam_title  = { f"steam:{str(r['appid']).strip()}": (r.get("title") or f"Steam App {r['appid']}") for r in steam_rows if r.get("appid") }
    xbox_title   = { f"xbox:{str(r['store_id']).strip()}": (r.get("title") or f"Xbox Product {r['store_id']}") for r in xbox_rows if r.get("store_id") }
    ps_title     = { f"ps:{(str(r.get('ps_ref','')).strip() or str(r.get('title','')).strip())}": (r.get("title") or "PS Product") for r in ps_rows }

    TITLE_MAP = {**steam_title, **xbox_title, **ps_title}
    META_MAP  = {**steam_meta, **xbox_meta, **ps_meta}

    rows: List[PriceRow] = []; misses: List[MissRow] = []
    with st.status("Pulling prices across markets…", expanded=False):
        futures = []
        with ThreadPoolExecutor(max_workers=18) as ex:
            for cc in [m.strip().upper() for m in st.session_state.get("last_markets", [])] or []:
                pass  # no-op
            for cc in [m.strip().upper() for m in st.session_state.get("last_markets", [])] or []:
                pass
            for cc in [m for m in (st.session_state.get('run_markets') or markets)]:
                for r in steam_rows:
                    if not r.get("appid"): continue
                    futures.append(ex.submit(fetch_steam_price, str(r["appid"]).strip(), cc, TITLE_MAP[f"steam:{str(r['appid']).strip()}"]))
                for r in xbox_rows:
                    if not r.get("store_id"): continue
                    futures.append(ex.submit(fetch_xbox_price, TITLE_MAP[f"xbox:{str(r['store_id']).strip()}"], str(r["store_id"]).strip(), cc))
                for r in ps_rows:
                    identity_key = f"ps:{(str(r.get('ps_ref','')).strip() or str(r.get('title','')).strip())}"
                    futures.append(ex.submit(fetch_playstation_price, str(r.get("ps_ref","")).strip(), cc, TITLE_MAP.get(identity_key), r.get("title") or None, r.get("edition_hint") or None, prefer_msrp))

            for f in as_completed(futures):
                try:
                    row, miss = f.result()
                except Exception:
                    row, miss = None, MissRow("unknown","unknown","unknown","exception")
                if row: rows.append(row)
                if miss: misses.append(miss)

    raw_df = pd.DataFrame([asdict(r) for r in rows])
    if not raw_df.empty:
        raw_df = country_map_series(raw_df)
        def _meta(identity): return META_MAP.get(identity, {"weight":1.0, "scale":1.0})
        meta_df = pd.DataFrame(list(raw_df["identity"].map(lambda i: _meta(i))))
        raw_df = pd.concat([raw_df, meta_df], axis=1)
        raw_df["title"] = raw_df["identity"].map(lambda i: TITLE_MAP.get(i, "Unknown"))
        raw_df["price"] = raw_df["price"] * raw_df["scale"]
        rates = fetch_usd_rates(False)
        raw_df["price_usd"] = [to_usd(p, c, rates) for p,c in zip(raw_df["price"], raw_df["currency"])]
        st.subheader("Raw Basket Rows"); st.dataframe(raw_df)

        grp = raw_df.groupby(["platform","country","currency"], dropna=False)
        sums = grp.apply(lambda g: (g["price"] * g["weight"]).sum()).rename("weighted_sum")
        wts  = grp["weight"].sum().rename("weight_total")
        reco = pd.concat([sums, wts], axis=1).reset_index()
        reco["RecommendedPrice"] = reco.apply(lambda r: (r["weighted_sum"]/r["weight_total"]) if r["weight_total"]>0 else None, axis=1)
        reco = reco[["platform","country","currency","RecommendedPrice"]]
        reco = country_map_series(reco)

        def vanity_apply(df: pd.DataFrame) -> pd.DataFrame:
            if df.empty: return df
            out = df.copy().reset_index(drop=True)
            out["RecommendedPrice"] = [apply_vanity(c,p) for c,p in zip(out["country"], out["RecommendedPrice"])]
            return out
        reco_xbox  = vanity_apply(reco[reco["platform"]=="Xbox"][["country_name","country","currency","RecommendedPrice"]])
        reco_steam = vanity_apply(reco[reco["platform"]=="Steam"][["country_name","country","currency","RecommendedPrice"]])
        reco_ps    = vanity_apply(reco[reco["platform"]=="PlayStation"][["country_name","country","currency","RecommendedPrice"]])

        for df in (reco_xbox, reco_steam, reco_ps):
            if not df.empty:
                df["RecommendedPriceUSD"] = [to_usd(p, cur, rates) for p,cur in zip(df["RecommendedPrice"], df["currency"])]

        def fx_view(df: pd.DataFrame, label: str) -> pd.DataFrame:
            us_row = df.loc[df["country"]=="US"]
            if us_row.empty: return pd.DataFrame()
            us_local = float(us_row["RecommendedPrice"].iloc[0]); us_ccy = str(us_row["currency"].iloc[0])
            us_usd = to_usd(us_local, us_ccy, rates)
            out = df[["country_name","country","currency","RecommendedPrice"]].copy()
            out.rename(columns={"RecommendedPrice":"LocalPrice"}, inplace=True)
            out["USDPrice"] = [to_usd(p, cur, rates) for p,cur in zip(out["LocalPrice"], out["currency"])]
            if us_usd is not None:
                out["DiffUSD"] = [None if pd.isna(v) else round(v - us_usd, 2) for v in out["USDPrice"]]
                out["PctDiff"] = [None if pd.isna(v) or us_usd==0 else str(round((v/us_usd - 1.0)*100.0, 0)) + "%" for v in out["USDPrice"]]
            out.insert(0, "platform", label)
            return out.sort_values("country_name").reset_index(drop=True)

        fx_x = fx_view(reco_xbox, "Xbox"); fx_s = fx_view(reco_steam, "Steam"); fx_p = fx_view(reco_ps, "PlayStation")

        if not fx_x.empty: st.subheader("Xbox Regional Pricing Recommendation"); st.dataframe(fx_x)
        if not fx_s.empty: st.subheader("Steam Regional Pricing Recommendation"); st.dataframe(fx_s)
        if not fx_p.empty: st.subheader("PlayStation Regional Pricing Recommendation"); st.dataframe(fx_p)

        merged = reco_xbox.rename(columns={"RecommendedPrice":"XboxRecommended","RecommendedPriceUSD":"XboxRecommendedUSD"})
        merged = pd.merge(merged, reco_steam.rename(columns={"RecommendedPrice":"SteamRecommended","RecommendedPriceUSD":"SteamRecommendedUSD"}),
                          on=["country_name","country","currency"], how="outer")
        merged = pd.merge(merged, reco_ps.rename(columns={"RecommendedPrice":"PSRecommended","RecommendedPriceUSD":"PSRecommendedUSD"}),
                          on=["country_name","country","currency"], how="outer").sort_values(["country"]).reset_index(drop=True)

        st.subheader("Combined Recommendations (Xbox + Steam + PlayStation)")
        st.dataframe(merged)
        st.download_button("⬇️ Download CSV (combined recommendations)", data=merged.to_csv(index=False).encode("utf-8"),
                           file_name="aaa_tier_recommendations_xsx_steam_ps.csv", mime="text/csv")

    if misses:
        miss_df = pd.DataFrame([asdict(m) for m in misses]).sort_values(["platform","title","country"]).reset_index(drop=True)
        st.subheader("Diagnostics (no price found)"); st.dataframe(miss_df)
else:
    st.caption("Use the sidebar to edit baskets & markets, then Run Pricing Pull.")
