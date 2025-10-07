
import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st

# ----------------------------------------
# PlayStation Pricing Scraper (v1.8)
# ----------------------------------------
# Fixes:
# - Do NOT force currency codes anymore (no fake PHP/HUF with USD amounts)
# - New deep scan of Next.js JSON for locale-priced amounts (e.g., ₱3,899, 25 990 Ft)
# - If a matching amount is found for the expected currency, prefer it
# - Keeps concept-aware logic + parallel fetching; includes India/Ukraine + many locales
#
# Parsing order:
#   1) Next.js JSON (deep scan with currency-aware heuristics)
#   2) JSON-LD
#   3) Meta tags

ALL_LOCALES: List[Dict[str, str]] = [
    # Americas
    {"key":"US", "country":"US", "locale":"en-us", "currency":"USD"},
    {"key":"Canada (EN)", "country":"CA", "locale":"en-ca", "currency":"CAD"},
    {"key":"Canada (FR)", "country":"CA", "locale":"fr-ca", "currency":"CAD"},
    {"key":"Mexico", "country":"MX", "locale":"es-mx", "currency":"MXN"},
    {"key":"Brazil", "country":"BR", "locale":"pt-br", "currency":"BRL"},
    {"key":"Argentina", "country":"AR", "locale":"es-ar", "currency":"ARS"},
    {"key":"Chile", "country":"CL", "locale":"es-cl", "currency":"CLP"},
    {"key":"Colombia", "country":"CO", "locale":"es-co", "currency":"COP"},
    {"key":"Peru", "country":"PE", "locale":"es-pe", "currency":"PEN"},
    {"key":"Uruguay", "country":"UY", "locale":"es-uy", "currency":"UYU"},
    {"key":"Costa Rica", "country":"CR", "locale":"es-cr", "currency":"CRC"},
    {"key":"Guatemala", "country":"GT", "locale":"es-gt", "currency":"GTQ"},
    {"key":"Honduras", "country":"HN", "locale":"es-hn", "currency":"HNL"},
    {"key":"Nicaragua", "country":"NI", "locale":"es-ni", "currency":"NIO"},
    {"key":"Panama", "country":"PA", "locale":"es-pa", "currency":"USD"},
    {"key":"Paraguay", "country":"PY", "locale":"es-py", "currency":"PYG"},
    {"key":"El Salvador", "country":"SV", "locale":"es-sv", "currency":"USD"},
    {"key":"Dominican Republic", "country":"DO", "locale":"es-do", "currency":"DOP"},
    {"key":"Bolivia", "country":"BO", "locale":"es-bo", "currency":"BOB"},

    # Europe
    {"key":"UK", "country":"GB", "locale":"en-gb", "currency":"GBP"},
    {"key":"Ireland", "country":"IE", "locale":"en-ie", "currency":"EUR"},
    {"key":"France", "country":"FR", "locale":"fr-fr", "currency":"EUR"},
    {"key":"Belgium (FR)", "country":"BE", "locale":"fr-be", "currency":"EUR"},
    {"key":"Belgium (NL)", "country":"BE", "locale":"nl-be", "currency":"EUR"},
    {"key":"Netherlands", "country":"NL", "locale":"nl-nl", "currency":"EUR"},
    {"key":"Luxembourg (FR)", "country":"LU", "locale":"fr-lu", "currency":"EUR"},
    {"key":"Germany", "country":"DE", "locale":"de-de", "currency":"EUR"},
    {"key":"Austria", "country":"AT", "locale":"de-at", "currency":"EUR"},
    {"key":"Switzerland (DE)", "country":"CH", "locale":"de-ch", "currency":"CHF"},
    {"key":"Switzerland (FR)", "country":"CH", "locale":"fr-ch", "currency":"CHF"},
    {"key":"Switzerland (IT)", "country":"CH", "locale":"it-ch", "currency":"CHF"},
    {"key":"Italy", "country":"IT", "locale":"it-it", "currency":"EUR"},
    {"key":"Spain", "country":"ES", "locale":"es-es", "currency":"EUR"},
    {"key":"Portugal", "country":"PT", "locale":"pt-pt", "currency":"EUR"},
    {"key":"Poland", "country":"PL", "locale":"pl-pl", "currency":"PLN"},
    {"key":"Czechia", "country":"CZ", "locale":"cs-cz", "currency":"CZK"},
    {"key":"Slovakia", "country":"SK", "locale":"sk-sk", "currency":"EUR"},
    {"key":"Hungary", "country":"HU", "locale":"hu-hu", "currency":"HUF"},
    {"key":"Romania", "country":"RO", "locale":"ro-ro", "currency":"RON"},
    {"key":"Bulgaria", "country":"BG", "locale":"bg-bg", "currency":"BGN"},
    {"key":"Greece", "country":"GR", "locale":"el-gr", "currency":"EUR"},
    {"key":"Croatia", "country":"HR", "locale":"hr-hr", "currency":"EUR"},
    {"key":"Slovenia", "country":"SI", "locale":"sl-si", "currency":"EUR"},
    {"key":"Serbia", "country":"RS", "locale":"sr-rs", "currency":"RSD"},
    {"key":"Turkey", "country":"TR", "locale":"tr-tr", "currency":"TRY"},
    {"key":"Norway", "country":"NO", "locale":"no-no", "currency":"NOK"},
    {"key":"Sweden", "country":"SE", "locale":"sv-se", "currency":"SEK"},
    {"key":"Denmark", "country":"DK", "locale":"da-dk", "currency":"DKK"},
    {"key":"Finland", "country":"FI", "locale":"fi-fi", "currency":"EUR"},
    {"key":"Iceland", "country":"IS", "locale":"is-is", "currency":"ISK"},
    {"key":"Ukraine", "country":"UA", "locale":"uk-ua", "currency":"UAH"},

    # Middle East / Africa
    {"key":"Saudi Arabia", "country":"SA", "locale":"ar-sa", "currency":"SAR"},
    {"key":"United Arab Emirates (EN)", "country":"AE", "locale":"en-ae", "currency":"AED"},
    {"key":"United Arab Emirates (AR)", "country":"AE", "locale":"ar-ae", "currency":"AED"},
    {"key":"Israel", "country":"IL", "locale":"he-il", "currency":"ILS"},
    {"key":"South Africa", "country":"ZA", "locale":"en-za", "currency":"ZAR"},

    # Asia-Pacific
    {"key":"Australia", "country":"AU", "locale":"en-au", "currency":"AUD"},
    {"key":"New Zealand", "country":"NZ", "locale":"en-nz", "currency":"NZD"},
    {"key":"Singapore", "country":"SG", "locale":"en-sg", "currency":"SGD"},
    {"key":"Malaysia", "country":"MY", "locale":"en-my", "currency":"MYR"},
    {"key":"Thailand", "country":"TH", "locale":"th-th", "currency":"THB"},
    {"key":"Indonesia", "country":"ID", "locale":"id-id", "currency":"IDR"},
    {"key":"Philippines", "country":"PH", "locale":"en-ph", "currency":"PHP"},
    {"key":"Vietnam", "country":"VN", "locale":"vi-vn", "currency":"VND"},
    {"key":"Hong Kong (ZH)", "country":"HK", "locale":"zh-hk", "currency":"HKD"},
    {"key":"Hong Kong (EN)", "country":"HK", "locale":"en-hk", "currency":"HKD"},
    {"key":"Taiwan", "country":"TW", "locale":"zh-tw", "currency":"TWD"},
    {"key":"Korea", "country":"KR", "locale":"ko-kr", "currency":"KRW"},
    {"key":"Japan", "country":"JP", "locale":"ja-jp", "currency":"JPY"},
    {"key":"India", "country":"IN", "locale":"en-in", "currency":"INR"},
]

CORE6_KEYS = ["US","UK","Germany","Japan","Brazil","Canada (EN)"]

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
}

# Currency symbols map for deep scan
CURR_SYMBOLS = {
    "USD": ["$", "USD"],
    "EUR": ["€", "EUR"],
    "GBP": ["£", "GBP"],
    "JPY": ["¥", "円", "JPY"],
    "PHP": ["₱", "PHP"],
    "HUF": ["Ft", "HUF", "Ft."],
    "IDR": ["Rp", "IDR"],
    "INR": ["₹", "INR"],
    "UAH": ["₴", "UAH"],
    "PLN": ["zł", "PLN"],
    "CZK": ["Kč", "CZK"],
    "RON": ["lei", "RON", "LEI"],
    "BGN": ["лв.", "BGN"],
    "TRY": ["₺", "TRY"],
    "ZAR": ["R", "ZAR"],
    "NOK": ["kr", "NOK"],
    "SEK": ["kr", "SEK"],
    "DKK": ["kr", "DKK"],
    "ISK": ["kr", "ISK", "ISK"],
    "BRL": ["R$", "BRL"],
    "MXN": ["$", "MXN"],
    "ARS": ["$", "ARS"],
    "COP": ["$", "COP"],
    "CLP": ["$", "CLP"],
    "CAD": ["$", "CAD"],
    "AUD": ["$", "AUD"],
    "NZD": ["$", "NZD"],
    "SGD": ["S$", "SGD"],
    "HKD": ["HK$", "HKD"],
    "TWD": ["NT$", "TWD"],
    "THB": ["฿", "THB"],
    "MYR": ["RM", "MYR"],
    "KRW": ["₩", "KRW"],
    "CHF": ["CHF", "Fr"],
    "RSD": ["RSD", "дин"],
}

PRODUCT_ID_RE = re.compile(r"/product/([^/?#]+)")

BAD_TOKENS = ["UPGRADE","BUNDLE","ADDON","ADD-ON","DELUXE","ULTIMATE","CURRENCY","COIN","COINS","CREDIT","CREDITS","PACK","DLC","SEASON","EXPANSION","TRIAL"]
GOOD_TOKENS = ["STANDARD","ONLINE","BASE","EDITION","GAME"]

@dataclass
class PriceInfo:
    region_key: str
    msrp: Optional[float]
    current: Optional[float]
    discount_pct: Optional[float]
    locale: str
    country: str
    currency_code: Optional[str]
    title: Optional[str] = None
    product_id: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None
    method: Optional[str] = None

# -------- Helpers --------
def build_headers(locale: Optional[str] = None) -> Dict[str, str]:
    h = dict(DEFAULT_HEADERS)
    if locale:
        lang = locale.split("-")[0]
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

def swap_locale(url: str, locale: str) -> str:
    try:
        parts = url.split("/")
        if "store.playstation.com" in url and len(parts) > 3:
            parts[3] = locale
            return "/".join(parts)
    except Exception:
        pass
    return url

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
        s = str(x).strip().replace(" ", "").replace(" ","")
        s = s.replace(",", "")  # we'll correct for decimal in localized parser separately
        return float(s)
    except Exception:
        return None

# Localized number parser: extracts digits with last separator as decimal
def parse_localized_amount(s: str) -> Optional[float]:
    if not isinstance(s, str):
        return None
    # remove currency symbols/letters
    s = re.sub(r"[^\d.,\s]", "", s)
    s = s.replace(" ", " ").strip()
    if not s:
        return None
    # remove spaces used as thousands
    s = re.sub(r"\s", "", s)
    # if both comma and dot appear, choose last as decimal sep
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            dec = ","
        else:
            dec = "."
    elif "," in s:
        dec = ","
    else:
        dec = "."
    if dec == ",":
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return None

# Deep scan Next.js JSON for (amount, currency) candidates.
def next_json_candidates(obj: Any) -> List[Tuple[Optional[float], Optional[str], str]]:
    out: List[Tuple[Optional[float], Optional[str], str]] = []
    def walk(node: Any):
        if isinstance(node, dict):
            # try amount + currency pairs
            keys = list(node.keys())
            currency = node.get("currency") or node.get("priceCurrency") or node.get("currencyCode") or node.get("isoCode")
            # numeric amount variants
            for k in ["discountedPrice","finalPrice","current","value","amount","basePrice","originalPrice","rawValue","price"]:
                if k in node:
                    v = node.get(k)
                    amt = None
                    if isinstance(v, (int, float)):
                        amt = float(v)
                    elif isinstance(v, str):
                        # sometimes formatted: "₱3,899"
                        # try localized parse only when contains non-digits
                        if re.search(r"[^\d.]", v):
                            amt = parse_localized_amount(v)
                        else:
                            amt = _num(v)
                    if amt is not None:
                        out.append((amt, (currency or None), k))
            # also check formatted strings containing known symbols
            for k in keys:
                v = node.get(k)
                if isinstance(v, str):
                    for code, syms in CURR_SYMBOLS.items():
                        if any(sym in v for sym in syms):
                            amt = parse_localized_amount(v)
                            if amt is not None:
                                out.append((amt, code, f"{k}:sym"))
            # recurse
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for it in node:
                walk(it)
    walk(obj)
    return out

def choose_best_amount(cands: List[Tuple[Optional[float], Optional[str], str]], expected: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    if not cands:
        return None, None
    # score candidates
    best = (None, None, -999)
    for amt, cur, src in cands:
        if amt is None:
            continue
        score = 0
        if expected and cur and cur.upper() == expected.upper():
            score += 10
        # prefer larger local-currency magnitudes for currencies that aren't typically ~70
        if expected in {"PHP","HUF","IDR","VND","KRW","CLP","COP","ARS","UAH","ISK","MYR","THB","TWD","RSD","TRY","ZAR","PLN","CZK","RON","BGN"}:
            if amt >= 100:
                score += 2
        # prefer discounted/final/current over base/original
        if src in {"discountedPrice","finalPrice","current","value","amount"}:
            score += 2
        if score > best[2]:
            best = (amt, cur, score)
    return best[0], best[1]

def compute_discount(msrp: Optional[float], current: Optional[float]) -> Optional[float]:
    if msrp is None or current is None or msrp <= 0:
        return None
    return round(100*(1-(current/msrp)),2)

# ---------- Price extraction pipeline ----------
def extract_from_next(html: str, expected_currency: Optional[str]) -> Tuple[Optional[str], Optional[float], Optional[float], Optional[str]]:
    nxt = parse_next_json(html)
    if not nxt:
        return None, None, None, None
    # find title
    title = None
    try:
        props = nxt.get("props", {}); pp = props.get("pageProps", {})
        product = pp.get("product") or pp.get("pageData") or pp.get("telemetryData") or {}
        title = product.get("name") or product.get("title") or pp.get("title")
    except Exception:
        pass

    cands = next_json_candidates(nxt)
    cur_val, cur_code = choose_best_amount(cands, expected_currency)

    msrp_val = None
    # heuristic: try to pick a "basePrice"/"originalPrice" with same currency
    base = [a for a in cands if a[2] in ("basePrice","originalPrice") and (not expected_currency or (a[1] and a[1].upper()==expected_currency.upper()))]
    if base:
        msrp_val = base[0][0]
    # fallback: if no msrp, use current
    if msrp_val is None and cur_val is not None:
        msrp_val = cur_val

    # choose currency code
    currency = cur_code or (expected_currency if cur_val is not None else None)
    return title, msrp_val, cur_val, currency

def parse_json_ld(html: str, expected_currency: Optional[str]) -> Tuple[Optional[str], Optional[float], Optional[float], Optional[str]]:
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")
    for s in scripts:
        try:
            data = json.loads(s.string) if s.string else None
        except Exception:
            continue
        objs = [data] if isinstance(data, dict) else [x for x in data if isinstance(x, dict)]
        for obj in objs:
            t = obj.get("@type")
            if isinstance(t, list):
                types = set(str(x).lower() for x in t)
            else:
                types = {str(t).lower()} if t else set()
            if {"product","videogame","offer"} & types or "offers" in obj:
                title = obj.get("name")
                offers = obj.get("offers")
                if isinstance(offers, dict):
                    price = offers.get("price")
                    currency = offers.get("priceCurrency")
                    amt = parse_localized_amount(str(price)) if isinstance(price, str) else _num(price)
                    if amt is not None:
                        # only accept if currency matches expected or if no expected provided
                        if not expected_currency or (currency and currency.upper()==expected_currency.upper()):
                            return title, amt, amt, currency
                elif isinstance(offers, list):
                    for off in offers:
                        if isinstance(off, dict):
                            price = off.get("price")
                            currency = off.get("priceCurrency")
                            amt = parse_localized_amount(str(price)) if isinstance(price, str) else _num(price)
                            if amt is not None:
                                if not expected_currency or (currency and currency.upper()==expected_currency.upper()):
                                    return title, amt, amt, currency
    return None, None, None, None

def parse_meta_tags(html: str, expected_currency: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    soup = BeautifulSoup(html, "html.parser")
    meta_amt = soup.find("meta", property="og:price:amount")
    meta_cur = soup.find("meta", property="og:price:currency")
    if meta_amt and meta_amt.get("content"):
        amt = parse_localized_amount(meta_amt.get("content")) or _num(meta_amt.get("content"))
        currency = meta_cur.get("content") if meta_cur and meta_cur.get("content") else None
        if amt is not None:
            if not expected_currency or (currency and currency.upper()==expected_currency.upper()):
                return amt, currency
    ip = soup.find(attrs={"itemprop":"price"})
    ipcur = soup.find(attrs={"itemprop":"priceCurrency"})
    if ip and ip.get("content"):
        amt = parse_localized_amount(ip.get("content")) or _num(ip.get("content"))
        currency = ipcur.get("content") if ipcur and ipcur.get("content") else None
        if amt is not None:
            if not expected_currency or (currency and currency.upper()==expected_currency.upper()):
                return amt, currency
    return None, None

# -------------- Concept & Product fetchers --------------
def fetch_concept_region_price(concept_url: str, region_key: str, locale: str, country: str, expected_currency: str) -> 'PriceInfo':
    url = swap_locale(concept_url, locale)
    html = fetch_html(url, locale=locale)

    title = None; msrp = None; current = None; currency = None; src = None
    if html:
        t, m, c, cur = extract_from_next(html, expected_currency)
        if c is not None:
            title, msrp, current, currency, src = t, m, c, cur, "next_json"

        if current is None:
            t2, m2, c2, cur2 = parse_json_ld(html, expected_currency)
            if c2 is not None:
                title, msrp, current, currency, src = t2 or title, m2, c2, cur2, "json_ld"

        if current is None:
            c3, cur3 = parse_meta_tags(html, expected_currency)
            if c3 is not None:
                current = c3; msrp = msrp or current; currency = cur3 or currency; src = "meta"

    discount = compute_discount(msrp, current)
    return PriceInfo(region_key, msrp, current, discount, locale, country, currency, title, None, url, src, "concept")

def extract_product_id_from_href(href: str) -> Optional[str]:
    if not href:
        return None
    m = PRODUCT_ID_RE.search(href)
    if m:
        return m.group(1)
    return None

def score_candidate(pid: str, label: str, prefer_keyword: Optional[str]) -> int:
    s = 0
    pu = pid.upper()
    lu = (label or "").upper()
    if "PPSA" in pu: s += 2
    for bad in BAD_TOKENS:
        if bad in pu or bad in lu: s -= 5
    for good in GOOD_TOKENS:
        if good in pu or good in lu: s += 2
    if prefer_keyword and prefer_keyword.upper() in (pu + " " + lu): s += 5
    return s

def resolve_to_product_id(input_ref: str, locale: str, prefer_keyword: Optional[str]=None, title_hint: Optional[str]=None) -> Tuple[Optional[str], Optional[str]]:
    if not input_ref.startswith("http"):
        return input_ref.strip(), None
    pid = extract_product_id_from_href(input_ref)
    if pid:
        return pid, None

    html = fetch_html(input_ref, locale=None)
    discovered_title = None; candidates: List[Tuple[int,str]] = []

    if html:
        soup = BeautifulSoup(html, "html.parser")
        discovered_title = soup.title.string.strip() if (soup.title and soup.title.string) else None
        for a in soup.find_all("a", href=True):
            pid = extract_product_id_from_href(a["href"])
            if pid:
                label = a.get_text(" ", strip=True) or ""
                candidates.append((score_candidate(pid, label, prefer_keyword), pid))

        nxt = parse_next_json(html)
        if nxt:
            try:
                def find_ids(obj):
                    out = []
                    if isinstance(obj, dict):
                        for k,v in obj.items():
                            if k in ("id","productId") and isinstance(v,str) and ("PPSA" in v or "-" in v):
                                out.append((score_candidate(v,"",prefer_keyword), v))
                            else:
                                out.extend(find_ids(v))
                    elif isinstance(obj, list):
                        for it in obj:
                            out.extend(find_ids(it))
                    return out
                candidates.extend(find_ids(nxt))
            except Exception:
                pass

    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1], discovered_title

    t = title_hint or discovered_title
    if t:
        search_url = f"https://store.playstation.com/{locale}/search/{requests.utils.quote(t)}"
        s_html = fetch_html(search_url, locale=locale)
        if s_html:
            soup2 = BeautifulSoup(s_html, "html.parser")
            for a in soup2.find_all("a", href=True):
                pid = extract_product_id_from_href(a["href"])
                if pid:
                    return pid, t
    return None, discovered_title

def build_product_url(locale: str, product_id: str) -> str:
    return f"https://store.playstation.com/{locale}/product/{product_id}"

def fetch_product_region_price(product_id: str, region_key: str, locale: str, country: str, expected_currency: str) -> 'PriceInfo':
    url = build_product_url(locale, product_id)
    html = fetch_html(url, locale=locale)

    title = None; msrp = None; current = None; currency = None; src = None
    if html:
        t, m, c, cur = extract_from_next(html, expected_currency)
        if c is not None:
            title, msrp, current, currency, src = t, m, c, cur, "next_json"

        if current is None:
            t2, m2, c2, cur2 = parse_json_ld(html, expected_currency)
            if c2 is not None:
                title, msrp, current, currency, src = t2 or title, m2, c2, cur2, "json_ld"

        if current is None:
            c3, cur3 = parse_meta_tags(html, expected_currency)
            if c3 is not None:
                current = c3; msrp = msrp or current; currency = cur3 or currency; src = "meta"

    discount = compute_discount(msrp, current)
    return PriceInfo(region_key, msrp, current, discount, locale, country, currency, title, product_id, url, src, "product")

# -------------- UI --------------
st.set_page_config(page_title="PlayStation Pricing — All Countries", page_icon="🎮", layout="wide")
st.title("🎮 PlayStation Store — Regional Pricing Pull (MVP v1.8)")
st.caption("Fixes local-currency amounts (PHP, HUF, etc.) by deeply scanning Next.js JSON. Concept-aware + parallel pulls.")

st.markdown("Paste a **Store URL or Product ID**. Works with www pages, `/concept/…`, or `/product/{ID}`.")

col_top1, col_top2 = st.columns([3,2])
with col_top1:
    product_ref = st.text_input("Product URL or Product ID", value="", placeholder="https://store.playstation.com/en-us/concept/201930  or  UP0006-PPSA02145_00-RESIDENTEVIL8000")
with col_top2:
    edition_hint = st.text_input("Edition keyword (optional)", value="", placeholder="e.g., Online or Standard")

title_hint = st.text_input("Optional: Title hint (used only if needed)", value="", placeholder="e.g., Helldivers 2")

mode = st.selectbox("Resolution mode", ["Auto (recommended)", "Concept page only", "Product page only"])

preset = st.radio("Region selection", ["All countries", "Core 6 (quick)", "Custom"], horizontal=True)
all_keys = [x["key"] for x in ALL_LOCALES]
if preset == "Custom":
    selected_keys = st.multiselect("Pick countries/locales", all_keys, default=["US","UK","Germany","Japan","Brazil","Canada (EN)"])
elif preset == "Core 6 (quick)":
    selected_keys = ["US","UK","Germany","Japan","Brazil","Canada (EN)"]
else:
    selected_keys = all_keys

max_workers = st.slider("Parallel requests", min_value=4, max_value=24, value=12, help="Higher is faster but more likely to hit throttling.")

if st.button("Pull Prices"):
    if not product_ref.strip() and not title_hint.strip():
        st.error("Please enter a Product URL/ID or at least a Title hint.")
    else:
        is_concept_input = product_ref.startswith("http") and "/concept/" in product_ref
        use_concept = (mode == "Concept page only") or (mode == "Auto (recommended)" and is_concept_input)

        resolved_pid: Optional[str] = None
        if not use_concept:
            with st.spinner("Resolving product ID…"):
                resolved_pid, _ = resolve_to_product_id(product_ref.strip(), locale="en-us", prefer_keyword=edition_hint.strip() or None, title_hint=title_hint.strip() or None)
                if not resolved_pid:
                    st.error("Couldn't resolve a Product ID. Try a product URL or provide a better title/edition hint.")
                    st.stop()
                st.caption(f"Resolved Product ID: `{resolved_pid}`")

        rows: List[PriceInfo] = []
        with st.spinner("Fetching regional prices…"):
            futures = []
            reg_index = {x["key"]: x for x in ALL_LOCALES}
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                for key in selected_keys:
                    meta = reg_index[key]
                    if use_concept:
                        futures.append(ex.submit(
                            fetch_concept_region_price, product_ref.strip(), key, meta["locale"], meta["country"], meta["currency"]
                        ))
                    else:
                        futures.append(ex.submit(
                            fetch_product_region_price, resolved_pid, key, meta["locale"], meta["country"], meta["currency"]
                        ))
                for fut in as_completed(futures):
                    try:
                        rows.append(fut.result())
                    except Exception:
                        rows.append(PriceInfo(region_key="(error)", msrp=None, current=None, discount_pct=None,
                                              locale="", country="", currency_code=None, title=None, product_id=resolved_pid,
                                              url=None, source=None, method="error"))

        rows.sort(key=lambda r: r.region_key)

        data = []
        main_title = None
        for r in rows:
            if r.title and not main_title: main_title = r.title
            data.append({
                "Region": f"{r.region_key} ({r.locale.upper()})",
                "Country": r.country,
                "Currency": r.currency_code,
                "MSRP": r.msrp,
                "Current Price": r.current,
                "Discount %": r.discount_pct,
                "Source": r.source,
                "Method": r.method,
                "Product URL": r.url
            })
        df = pd.DataFrame(data)

        if main_title:
            st.subheader(main_title)

        st.dataframe(df, use_container_width=True, height=520)
        st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), file_name="ps_prices_all.csv", mime="text/csv")

        st.markdown("**Notes**")
        st.markdown("- For some products, msrp=current (no discount exposed in structured data).\n- If a region shows **None**, the SKU may be unavailable there or the page withheld price without cookies/headers.")
