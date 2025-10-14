# multiplatform_pricing_tool_v1.6.py
# FIXED: PlayStation basePrice priority + Enhanced debugging for Call of Duty bundles
# Download this file and run with: streamlit run multiplatform_pricing_tool_v1.6.py

import json
import re
import time
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st

# ============================================================================
# CONFIGURATION
# ============================================================================

# Set to True to show debug columns (Price Type, Source)
DEBUG_MODE = True

st.set_page_config(
    page_title="Unified Game Pricing Tool v1.6",
    page_icon="🎮",
    layout="wide"
)

# Country display names
COUNTRY_NAMES: Dict[str, str] = {
    "US": "United States", "CA": "Canada", "MX": "Mexico", "BR": "Brazil",
    "AR": "Argentina", "CL": "Chile", "CO": "Colombia", "PE": "Peru",
    "UY": "Uruguay", "CR": "Costa Rica", "GB": "United Kingdom", "IE": "Ireland",
    "FR": "France", "DE": "Germany", "IT": "Italy", "ES": "Spain", "PT": "Portugal",
    "NL": "Netherlands", "BE": "Belgium", "AT": "Austria", "CH": "Switzerland",
    "DK": "Denmark", "SE": "Sweden", "NO": "Norway", "FI": "Finland", "PL": "Poland",
    "CZ": "Czechia", "SK": "Slovakia", "HU": "Hungary", "GR": "Greece",
    "TR": "Turkey", "IL": "Israel", "SA": "Saudi Arabia", "AE": "United Arab Emirates",
    "QA": "Qatar", "KW": "Kuwait", "JP": "Japan", "KR": "South Korea", "TW": "Taiwan",
    "HK": "Hong Kong", "SG": "Singapore", "MY": "Malaysia", "TH": "Thailand",
    "ID": "Indonesia", "PH": "Philippines", "VN": "Vietnam", "IN": "India",
    "AU": "Australia", "NZ": "New Zealand", "KZ": "Kazakhstan", "UA": "Ukraine",
    "CN": "China", "ZA": "South Africa", "RU": "Russia"
}

# Steam country code mappings
STEAM_MARKETS = {
    "US": "US", "CA": "CA", "MX": "MX", "BR": "BR", "AR": "AR", "CL": "CL",
    "CO": "CO", "PE": "PE", "UY": "UY", "CR": "CR", "GB": "GB", "FR": "FR",
    "DE": "FR", "IT": "FR", "ES": "FR", "PT": "FR", "NL": "FR", "BE": "FR",
    "AT": "FR", "CH": "CH", "DK": "FR", "SE": "FR", "NO": "NO", "FI": "FR",
    "PL": "PL", "CZ": "FR", "SK": "FR", "HU": "FR", "GR": "FR", "TR": "TR",
    "IL": "IL", "SA": "SA", "AE": "AE", "QA": "QA", "KW": "KW", "JP": "JP",
    "KR": "KR", "TW": "TW", "HK": "HK", "SG": "SG", "MY": "MY", "TH": "TH",
    "ID": "ID", "PH": "PH", "VN": "VN", "IN": "IN", "AU": "AU", "NZ": "NZ",
    "KZ": "KZ", "UA": "UA", "CN": "CN", "ZA": "ZA", "RU": "RU"
}

# Xbox market mappings
XBOX_MARKETS = {
    "US": "en-us", "CA": "en-ca", "MX": "es-mx", "BR": "pt-br", "AR": "es-ar",
    "CL": "es-cl", "CO": "es-co", "PE": "es-pe", "CR": "es-cr", "GB": "en-gb",
    "IE": "en-ie", "FR": "fr-fr", "DE": "de-de", "IT": "it-it", "ES": "es-es",
    "PT": "pt-pt", "NL": "nl-nl", "BE": "fr-fr", "AT": "de-at", "CH": "de-ch",
    "SE": "sv-se", "NO": "nb-no", "FI": "fi-fi", "PL": "pl-pl", "CZ": "cs-cz",
    "SK": "sk-sk", "HU": "hu-hu", "GR": "el-gr", "TR": "tr-tr", "IL": "he-il",
    "SA": "ar-sa", "AE": "ar-ae", "QA": "ar-qa", "KW": "ar-kw", "JP": "ja-jp",
    "KR": "ko-kr", "TW": "zh-tw", "HK": "zh-hk", "SG": "en-sg", "MY": "en-my",
    "TH": "th-th", "ID": "id-id", "PH": "en-ph", "VN": "vi-vn", "IN": "en-in",
    "AU": "en-au", "NZ": "en-nz", "ZA": "en-za", "UA": "uk-ua", "KZ": "kk-kz",
    "RU": "ru-ru"
}

# PlayStation locale mappings
PS_MARKETS = {
    "US": "en-us", "CA": "en-ca", "MX": "es-mx", "BR": "pt-br", "AR": "es-ar",
    "CL": "es-cl", "CO": "es-co", "PE": "es-pe", "UY": "es-uy", "CR": "es-cr",
    "GB": "en-gb", "IE": "en-ie", "FR": "fr-fr", "DE": "de-de", "IT": "it-it",
    "ES": "es-es", "PT": "pt-pt", "NL": "nl-nl", "BE": "fr-be", "AT": "de-at",
    "CH": "de-ch", "DK": "da-dk", "SE": "sv-se", "NO": "no-no", "FI": "fi-fi",
    "PL": "pl-pl", "CZ": "cs-cz", "SK": "sk-sk", "HU": "hu-hu", "GR": "el-gr",
    "TR": "tr-tr", "IL": "he-il", "SA": "ar-sa", "AE": "ar-ae", "JP": "ja-jp",
    "KR": "ko-kr", "TW": "zh-tw", "HK": "zh-hk", "SG": "en-sg", "MY": "en-my",
    "TH": "th-th", "ID": "id-id", "PH": "en-ph", "VN": "vi-vn", "IN": "en-in",
    "AU": "au-en", "NZ": "en-nz", "ZA": "en-za", "UA": "uk-ua"
}

# Currency mappings by platform and country
PLATFORM_CURRENCIES = {
    "Steam": {
        "US": "USD", "CA": "CAD", "MX": "MXN", "BR": "BRL", "AR": "USD",
        "CL": "CLP", "CO": "COP", "PE": "PEN", "UY": "UYU", "CR": "CRC",
        "GB": "GBP", "FR": "EUR", "DE": "EUR", "IT": "EUR", "ES": "EUR",
        "PT": "EUR", "NL": "EUR", "BE": "EUR", "AT": "EUR", "CH": "CHF",
        "DK": "EUR", "SE": "EUR", "NO": "NOK", "FI": "EUR", "PL": "PLN",
        "CZ": "EUR", "SK": "EUR", "HU": "EUR", "GR": "EUR", "TR": "USD",
        "IL": "ILS", "SA": "SAR", "AE": "AED", "QA": "QAR", "KW": "KWD",
        "JP": "JPY", "KR": "KRW", "TW": "TWD", "HK": "HKD", "SG": "SGD",
        "MY": "MYR", "TH": "THB", "ID": "IDR", "PH": "PHP", "VN": "VND",
        "IN": "INR", "AU": "AUD", "NZ": "NZD", "KZ": "KZT", "UA": "UAH",
        "CN": "CNY", "ZA": "ZAR", "RU": "RUB"
    },
    "Xbox": {
        "US": "USD", "CA": "CAD", "MX": "MXN", "BR": "BRL", "AR": "ARS",
        "CL": "CLP", "CO": "COP", "PE": "PEN", "CR": "CRC", "GB": "GBP",
        "IE": "EUR", "FR": "EUR", "DE": "EUR", "IT": "EUR", "ES": "EUR",
        "PT": "EUR", "NL": "EUR", "BE": "EUR", "AT": "EUR", "CH": "CHF",
        "SE": "SEK", "NO": "NOK", "FI": "EUR", "PL": "PLN", "CZ": "CZK",
        "SK": "EUR", "HU": "HUF", "GR": "EUR", "TR": "TRY", "IL": "ILS",
        "SA": "SAR", "AE": "AED", "QA": "QAR", "KW": "KWD", "JP": "JPY",
        "KR": "KRW", "TW": "TWD", "HK": "HKD", "SG": "SGD", "MY": "MYR",
        "TH": "THB", "ID": "IDR", "PH": "PHP", "VN": "VND", "IN": "INR",
        "AU": "AUD", "NZ": "NZD", "ZA": "ZAR", "UA": "UAH", "KZ": "KZT",
        "RU": "RUB"
    },
    "PlayStation": {
        "US": "USD", "CA": "CAD", "MX": "MXN", "BR": "BRL", "AR": "ARS",
        "CL": "CLP", "CO": "COP", "PE": "PEN", "UY": "UYU", "CR": "CRC",
        "GB": "GBP", "IE": "EUR", "FR": "EUR", "DE": "EUR", "IT": "EUR",
        "ES": "EUR", "PT": "EUR", "NL": "EUR", "BE": "EUR", "AT": "EUR",
        "CH": "CHF", "DK": "DKK", "SE": "SEK", "NO": "NOK", "FI": "EUR",
        "PL": "PLN", "CZ": "CZK", "SK": "EUR", "HU": "HUF", "GR": "EUR",
        "TR": "TRY", "IL": "ILS", "SA": "SAR", "AE": "AED", "JP": "JPY",
        "KR": "KRW", "TW": "TWD", "HK": "HKD", "SG": "SGD", "MY": "MYR",
        "TH": "THB", "ID": "IDR", "PH": "PHP", "VN": "VND", "IN": "INR",
        "AU": "AUD", "NZ": "NZD", "ZA": "ZAR", "UA": "UAH"
    }
}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

PS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
}

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class PriceData:
    platform: str
    title: str
    country: str
    currency: str
    price: Optional[float]
    price_usd: Optional[float]
    diff_vs_us: Optional[str]
    price_type: Optional[str] = "API"
    source: Optional[str] = None

# ============================================================================
# CURRENCY CONVERSION
# ============================================================================

def fetch_exchange_rates() -> Dict[str, float]:
    """Fetch current exchange rates with USD as base"""
    if "exchange_rates" in st.session_state:
        cache_time = st.session_state.get("rates_timestamp", 0)
        if time.time() - cache_time < 7200:
            return st.session_state["exchange_rates"]
    
    rates = {"USD": 1.0}
    try:
        resp = requests.get("https://api.exchangerate.host/latest", 
                          params={"base": "USD"}, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if "rates" in data:
                rates.update({k.upper(): float(v) for k, v in data["rates"].items()})
    except Exception:
        pass
    
    st.session_state["exchange_rates"] = rates
    st.session_state["rates_timestamp"] = time.time()
    return rates

def convert_to_usd(amount: Optional[float], currency: str, rates: Dict[str, float]) -> Optional[float]:
    """Convert amount to USD"""
    if amount is None or currency not in rates:
        return None
    rate = rates.get(currency, 1.0)
    if rate <= 0:
        return None
    return round(amount / rate, 2)

# ============================================================================
# STEAM PRICE PULLER
# ============================================================================

def extract_steam_appid(input_str: str) -> Optional[str]:
    """Extract Steam AppID from URL or return as-is if numeric"""
    input_str = input_str.strip()
    if input_str.isdigit():
        return input_str
    match = re.search(r'/app/(\d+)', input_str)
    if match:
        return match.group(1)
    return None

def fetch_steam_price(appid: str, country: str, title: str) -> Optional[PriceData]:
    """Fetch Steam price for a specific country"""
    if country not in STEAM_MARKETS:
        return None
    
    cc = STEAM_MARKETS[country]
    currency = PLATFORM_CURRENCIES["Steam"].get(country, "USD")
    
    try:
        url = "https://store.steampowered.com/api/appdetails"
        params = {"appids": appid, "cc": cc, "l": "en"}
        resp = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=30)
        data = resp.json().get(str(appid), {})
        
        if not data.get("success"):
            return PriceData("Steam", title, country, currency, None, None, None, "API", "steam_api")
        
        game_data = data.get("data", {})
        price_overview = game_data.get("price_overview", {})
        
        price_cents = price_overview.get("initial") or price_overview.get("final")
        if price_cents and isinstance(price_cents, int) and price_cents > 0:
            price = round(price_cents / 100.0, 2)
            return PriceData("Steam", title, country, currency, price, None, None, "API", "steam_api")
        
    except Exception:
        pass
    
    return PriceData("Steam", title, country, currency, None, None, None, "API", "steam_api")

# ============================================================================
# XBOX PRICE PULLER
# ============================================================================

def extract_xbox_store_id(input_str: str) -> Optional[str]:
    """Extract Xbox Store ID from URL or return as-is"""
    input_str = input_str.strip()
    if len(input_str) == 12 and input_str[0] == '9':
        return input_str
    match = re.search(r'/([9][A-Z0-9]{11})', input_str, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None

def fetch_xbox_price(store_id: str, country: str, title: str) -> Optional[PriceData]:
    """Fetch Xbox price for a specific country"""
    if country not in XBOX_MARKETS:
        return None
    
    locale = XBOX_MARKETS[country]
    currency = PLATFORM_CURRENCIES["Xbox"].get(country, "USD")
    
    def _ms_cv():
        return ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=24))
    
    headers = {"MS-CV": _ms_cv(), "Accept": "application/json"}
    
    try:
        url = "https://storeedgefd.dsx.mp.microsoft.com/v9.0/sdk/products"
        params = {"bigIds": store_id, "market": country, "locale": locale}
        resp = requests.get(url, params=params, headers=headers, timeout=25)
        
        if resp.status_code == 200:
            payload = resp.json()
            products = payload.get("Products") or payload.get("products")
            if products and len(products) > 0:
                p0 = products[0]
                skus = p0.get("DisplaySkuAvailabilities") or p0.get("displaySkuAvailabilities") or []
                for sku in skus:
                    avails = sku.get("Availabilities") or sku.get("availabilities") or []
                    for av in avails:
                        omd = av.get("OrderManagementData") or av.get("orderManagementData") or {}
                        price_obj = omd.get("Price") or omd.get("price") or {}
                        amt = price_obj.get("MSRP") or price_obj.get("msrp") or price_obj.get("ListPrice") or price_obj.get("listPrice")
                        if amt:
                            return PriceData("Xbox", title, country, currency, float(amt), None, None, "API", "xbox_api")
    except Exception:
        pass
    
    try:
        url = "https://displaycatalog.mp.microsoft.com/v7.0/products"
        params = {"bigIds": store_id, "market": country, "languages": "en-US", "fieldsTemplate": "Details"}
        resp = requests.get(url, params=params, headers=headers, timeout=25)
        
        if resp.status_code == 200:
            payload = resp.json()
            products = payload.get("Products") or payload.get("products")
            if products and len(products) > 0:
                p0 = products[0]
                skus = p0.get("DisplaySkuAvailabilities") or p0.get("displaySkuAvailabilities") or []
                for sku in skus:
                    avails = sku.get("Availabilities") or sku.get("availabilities") or []
                    for av in avails:
                        omd = av.get("OrderManagementData") or av.get("orderManagementData") or {}
                        price_obj = omd.get("Price") or omd.get("price") or {}
                        amt = price_obj.get("MSRP") or price_obj.get("msrp") or price_obj.get("ListPrice") or price_obj.get("listPrice")
                        if amt:
                            return PriceData("Xbox", title, country, currency, float(amt), None, None, "API", "xbox_api")
    except Exception:
        pass
    
    return PriceData("Xbox", title, country, currency, None, None, None, "API", "xbox_api")

# ============================================================================
# PLAYSTATION PRICE PULLER - v1.6 WITH ENHANCED basePrice PRIORITY
# ============================================================================

def extract_ps_product_id(input_str: str) -> Optional[str]:
    """Extract PlayStation Product ID from URL or return as-is"""
    input_str = input_str.strip()
    if not input_str.startswith("http"):
        return input_str
    match = re.search(r'/product/([^/?#]+)', input_str)
    if match:
        return match.group(1)
    return None

def _num(x: Any) -> Optional[float]:
    """Convert to number safely"""
    try:
        if x is None:
            return None
        s = str(x).strip().replace(",", "")
        return float(s)
    except Exception:
        return None

def parse_next_json(html: str) -> Optional[dict]:
    """Parse PlayStation Next.js JSON"""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except Exception:
        return None

def extract_price_with_type(price_dict: dict, debug_prefix: str = "") -> Tuple[Optional[float], str]:
    """
    Extract price from PlayStation price object with ENHANCED basePrice priority
    Returns: (price, price_type)
    
    v1.6 Fix: ALWAYS use basePrice (MSRP) when available, even if discountedPrice exists
    This fixes NBA 2K26 Spain showing €55.99 (sale) instead of €79.99 (MSRP)
    """
    if not isinstance(price_dict, dict):
        return None, "Unknown"
    
    # Extract ALL price fields for debugging
    base = _num(price_dict.get("basePrice"))
    disc = _num(price_dict.get("discountedPrice"))
    final = _num(price_dict.get("finalPrice"))
    current = _num(price_dict.get("current"))
    value = _num(price_dict.get("value"))
    
    if DEBUG_MODE and debug_prefix:
        print(f"{debug_prefix} Price fields: base={base}, disc={disc}, final={final}, current={current}, value={value}")
    
    # PRIORITY 1: basePrice (MSRP) - THE MOST IMPORTANT
    # This is the fix: always use basePrice when it exists
    if base and base > 0:
        # Check if item is on sale (discounted < base)
        if disc and disc > 0 and disc < base:
            if DEBUG_MODE and debug_prefix:
                print(f"{debug_prefix} ✓ Using basePrice {base} (on sale, ignoring disc {disc})")
            return base, "MSRP"
        if DEBUG_MODE and debug_prefix:
            print(f"{debug_prefix} ✓ Using basePrice {base}")
        return base, "MSRP"
    
    # PRIORITY 2: finalPrice
    if final and final > 0:
        if DEBUG_MODE and debug_prefix:
            print(f"{debug_prefix} Using finalPrice {final}")
        return final, "Current"
    
    # PRIORITY 3: discountedPrice (ONLY if basePrice missing)
    if disc and disc > 0:
        if DEBUG_MODE and debug_prefix:
            print(f"{debug_prefix} ⚠ Using discountedPrice {disc} (basePrice unavailable)")
        return disc, "Sale Price"
    
    # PRIORITY 4: Other fields
    if current and current > 0:
        return current, "Current"
    if value and value > 0:
        return value, "Current"
    
    return None, "Unknown"

def from_next_json(next_json: dict, product_id: str = "") -> Tuple[Optional[str], Optional[str], Optional[float], Optional[str], Optional[str]]:
    """Extract price data from PlayStation Next.js JSON with enhanced debugging"""
    try:
        props = next_json.get("props", {})
        page_props = props.get("pageProps", {})
        product = page_props.get("product") or page_props.get("pageData") or page_props.get("telemetryData") or {}

        title = product.get("name") or product.get("title") or page_props.get("title")
        pid = product.get("id") or product.get("productId") or product.get("slug") or page_props.get("productId")

        debug_prefix = f"[PSN {product_id}]" if DEBUG_MODE else ""

        # Location 1: Direct product.price
        p = product.get("price") if isinstance(product, dict) else None
        if isinstance(p, dict):
            price, price_type = extract_price_with_type(p, f"{debug_prefix} product.price")
            currency = p.get("currency")
            if price and price > 0:
                return title, pid, price, price_type, currency

        # Location 2: defaultSku.price
        default_sku = product.get("defaultSku") if isinstance(product, dict) else None
        if isinstance(default_sku, dict):
            p2 = default_sku.get("price")
            if isinstance(p2, dict):
                price, price_type = extract_price_with_type(p2, f"{debug_prefix} defaultSku.price")
                currency = p2.get("currency")
                if price and price > 0:
                    return title, pid, price, price_type, currency

        # Location 3: skus array
        skus = product.get("skus") if isinstance(product, dict) else None
        if isinstance(skus, list):
            for sku in skus:
                p3 = sku.get("price")
                if isinstance(p3, dict):
                    price, price_type = extract_price_with_type(p3, f"{debug_prefix} skus.price")
                    currency = p3.get("currency")
                    if price and price > 0:
                        return title, pid, price, price_type, currency

        # Location 4: pageProps.price
        pp = page_props.get("price") or page_props.get("store", {}).get("price")
        if isinstance(pp, dict):
            price, price_type = extract_price_with_type(pp, f"{debug_prefix} pageProps.price")
            currency = pp.get("currency")
            if price and price > 0:
                return title, pid, price, price_type, currency

        return title, pid, None, "Unknown", None
    except Exception as e:
        if DEBUG_MODE:
            print(f"[PSN] from_next_json error: {e}")
        return None, None, None, "Error", None

def parse_json_ld(html: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
    """Parse JSON-LD structured data"""
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

def parse_meta_tags(html: str) -> Tuple[Optional[float], Optional[str]]:
    """Parse meta tags for price"""
    soup = BeautifulSoup(html, "html.parser")
    meta_amt = soup.find("meta", property="og:price:amount")
    meta_cur = soup.find("meta", property="og:price:currency")
    if meta_amt and meta_amt.get("content"):
        price = _num(meta_amt.get("content"))
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

def choose_currency(parsed: Optional[str], expected: Optional[str]) -> Optional[str]:
    """Choose currency with preference for expected"""
    if expected:
        return expected.upper()
    return parsed.upper() if parsed else None

def fetch_ps_price(product_id: str, country: str, title: str) -> Optional[PriceData]:
    """Fetch PlayStation price with enhanced MSRP priority and debugging"""
    if country not in PS_MARKETS:
        return None
    
    locale = PS_MARKETS[country]
    currency = PLATFORM_CURRENCIES["PlayStation"].get(country, "USD")
    
    headers = dict(PS_HEADERS)
    if locale:
        lang = locale.split("-")[0]
        headers["Accept-Language"] = f"{lang}-{locale.split('-')[-1].upper()},{lang};q=0.8"
    
    try:
        url = f"https://store.playstation.com/{locale}/product/{product_id}"
        resp = requests.get(url, headers=headers, timeout=30)
        
        if resp.status_code == 200:
            html = resp.text
            
            # Try Next.js JSON first
            nxt = parse_next_json(html)
            if nxt:
                t, _, price, price_type, pcurr = from_next_json(nxt, product_id)
                if price is not None and price > 0:
                    final_currency = choose_currency(pcurr, currency)
                    if DEBUG_MODE:
                        print(f"[PSN {product_id} {country}] SUCCESS: {price} {final_currency} ({price_type})")
                    return PriceData("PlayStation", title, country, final_currency, price, None, None, price_type, "next_json")
            
            # Fallback to JSON-LD
            t2, price2, pcurr2 = parse_json_ld(html)
            if price2 is not None and price2 > 0:
                final_currency = choose_currency(pcurr2, currency)
                return PriceData("PlayStation", title, country, final_currency, price2, None, None, "Current", "json_ld")
            
            # Fallback to meta tags
            price3, pcurr3 = parse_meta_tags(html)
            if price3 is not None and price3 > 0:
                final_currency = choose_currency(pcurr3, currency)
                return PriceData("PlayStation", title, country, final_currency, price3, None, None, "Current", "meta_tags")
        
        if DEBUG_MODE:
            print(f"[PSN {product_id} {country}] FAILED: HTTP {resp.status_code}")
                
    except Exception as e:
        if DEBUG_MODE:
            print(f"[PSN {product_id} {country}] ERROR: {e}")
    
    return PriceData("PlayStation", title, country, currency, None, None, None, "N/A", None)

# ============================================================================
# MAIN PULL ORCHESTRATION
# ============================================================================

def pull_all_prices(steam_games: List[Tuple[str, str]], 
                   xbox_games: List[Tuple[str, str]], 
                   ps_games: List[Tuple[str, str]],
                   max_workers: int = 20) -> Tuple[List[PriceData], List[PriceData], List[PriceData]]:
    """Pull prices for all games across all platforms and regions"""
    
    steam_results = []
    xbox_results = []
    ps_results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        
        # Submit Steam jobs
        for appid, title in steam_games:
            for country in STEAM_MARKETS.keys():
                futures.append((executor.submit(fetch_steam_price, appid, country, title), "steam"))
        
        # Submit Xbox jobs
        for store_id, title in xbox_games:
            for country in XBOX_MARKETS.keys():
                futures.append((executor.submit(fetch_xbox_price, store_id, country, title), "xbox"))
        
        # Submit PlayStation jobs
        for product_id, title in ps_games:
            for country in PS_MARKETS.keys():
                futures.append((executor.submit(fetch_ps_price, product_id, country, title), "ps"))
        
        # Collect results
        for future_tuple in futures:
            future, platform = future_tuple
            try:
                result = future.result()
                if result:
                    if platform == "steam":
                        steam_results.append(result)
                    elif platform == "xbox":
                        xbox_results.append(result)
                    elif platform == "ps":
                        ps_results.append(result)
            except Exception:
                pass
    
    return steam_results, xbox_results, ps_results

def process_results(results: List[PriceData], rates: Dict[str, float]) -> pd.DataFrame:
    """Process results into DataFrame with USD conversion and variance"""
    if not results:
        return pd.DataFrame()
    
    # Convert to USD
    for r in results:
        r.price_usd = convert_to_usd(r.price, r.currency, rates)
    
    # Find US baseline
    us_prices = {}
    for r in results:
        if r.country == "US" and r.price_usd:
            us_prices[r.title] = r.price_usd
    
    # Calculate variance
    for r in results:
        if r.price_usd and r.title in us_prices:
            us_price = us_prices[r.title]
            if us_price > 0:
                pct = ((r.price_usd / us_price) - 1) * 100
                r.diff_vs_us = f"{pct:+.1f}%"
    
    # Convert to DataFrame
    df_data = []
    for r in results:
        row = {
            "Title": r.title,
            "Country": COUNTRY_NAMES.get(r.country, r.country),
            "Currency": r.currency,
            "Local Price": r.price if r.price is not None else None,
            "USD Price": r.price_usd if r.price_usd is not None else None,
            "% Diff vs US": r.diff_vs_us if r.diff_vs_us else None
        }
        
        # Add debug columns if enabled
        if DEBUG_MODE:
            row["Price Type"] = r.price_type
            row["Source"] = r.source
        
        df_data.append(row)
    
    df = pd.DataFrame(df_data)
    return df.sort_values(["Title", "Country"]).reset_index(drop=True)

# ============================================================================
# STREAMLIT UI
# ============================================================================

st.title("🎮 Unified Multi-Platform Game Pricing Tool v1.6")
st.caption("✅ FIXED: PlayStation basePrice Priority + Enhanced Call of Duty Bundle Debugging")

if DEBUG_MODE:
    st.info("🔍 **Debug Mode Active** - Console will show detailed PlayStation price extraction logs")

st.markdown("---")

# Steam Basket
st.subheader("🎮 Steam Games")
st.caption("Add games one per line: Title | AppID or URL")
col1, col2 = st.columns([3, 1])
with col1:
    steam_input = st.text_area(
        "Format: Game Title | AppID or URL",
        height=150,
        placeholder="The Outer Worlds 2 | 1449110\nBorderlands 4 | 1285190"
    )
with col2:
    st.markdown("**Examples:**")
    st.code("Borderlands 4 | 1285190", language="text")
    st.code("NBA 2K26 | 3472040", language="text")

# Xbox Basket
st.subheader("🎮 Xbox Games")
st.caption("Add games one per line: Title | Store ID or URL")
col3, col4 = st.columns([3, 1])
with col3:
    xbox_input = st.text_area(
        "Format: Game Title | Store ID or URL",
        height=150,
        placeholder="The Outer Worlds 2 | 9NSPRSXXZZLG\nBorderlands 4 | 9MX6HKF5647G"
    )
with col4:
    st.markdown("**Examples:**")
    st.code("Borderlands 4 | 9MX6HKF5647G", language="text")
    st.code("NBA 2K26 | 9PJ2RVRC0L1X", language="text")

# PlayStation Basket
st.subheader("🎮 PlayStation Games")
st.caption("Add games one per line: Title | Product ID or URL")
col5, col6 = st.columns([3, 1])
with col5:
    ps_input = st.text_area(
        "Format: Game Title | Product ID or URL",
        height=150,
        placeholder="Borderlands 4 | UP1001-PPSA01494_00-000000000000OAK2\nCall of Duty: Black Ops 6 | UP0002-PPSA01649_00-CODBO6CROSSGEN01"
    )
with col6:
    st.markdown("**Examples:**")
    st.code("Borderlands 4 | UP1001-PPSA01494_00-...", language="text")
    st.code("COD BO6 | UP0002-PPSA01649_00-...", language="text")

st.markdown("---")

if st.button("🚀 Pull Prices", type="primary", use_container_width=True):
    # Parse inputs with manual titles
    steam_games = []
    xbox_games = []
    ps_games = []
    
    # Process Steam
    for line in steam_input.strip().split("\n"):
        if "|" in line:
            parts = line.split("|", 1)
            title = parts[0].strip()
            id_part = parts[1].strip()
            appid = extract_steam_appid(id_part)
            if appid:
                steam_games.append((appid, title))
        elif line.strip():
            appid = extract_steam_appid(line)
            if appid:
                steam_games.append((appid, f"Steam Game {appid}"))
    
    # Process Xbox
    for line in xbox_input.strip().split("\n"):
        if "|" in line:
            parts = line.split("|", 1)
            title = parts[0].strip()
            id_part = parts[1].strip()
            store_id = extract_xbox_store_id(id_part)
            if store_id:
                xbox_games.append((store_id, title))
        elif line.strip():
            store_id = extract_xbox_store_id(line)
            if store_id:
                xbox_games.append((store_id, f"Xbox Game {store_id}"))
    
    # Process PlayStation
    for line in ps_input.strip().split("\n"):
        if "|" in line:
            parts = line.split("|", 1)
            title = parts[0].strip()
            id_part = parts[1].strip()
            product_id = extract_ps_product_id(id_part)
            if product_id:
                ps_games.append((product_id, title))
        elif line.strip():
            product_id = extract_ps_product_id(line)
            if product_id:
                ps_games.append((product_id, f"PS Game {product_id}"))
    
    if not steam_games and not xbox_games and not ps_games:
        st.error("Please enter at least one game for any platform.")
    else:
        st.info(f"🎮 Pulling prices for: {len(steam_games)} Steam, {len(xbox_games)} Xbox, {len(ps_games)} PlayStation games")
        
        with st.spinner("Fetching prices across all regions..."):
            rates = fetch_exchange_rates()
            steam_results, xbox_results, ps_results = pull_all_prices(
                steam_games, xbox_games, ps_games
            )
        
        st.success(f"✅ Price pull complete! Found {len(steam_results)} Steam, {len(xbox_results)} Xbox, {len(ps_results)} PlayStation prices")
        
        # Display Steam results
        if steam_results:
            st.markdown("### 🎮 Steam Regional Pricing")
            steam_df = process_results(steam_results, rates)
            st.dataframe(steam_df, use_container_width=True, height=400)
            st.download_button(
                "⬇️ Download Steam CSV",
                steam_df.to_csv(index=False).encode("utf-8"),
                "steam_prices.csv",
                "text/csv"
            )
        
        # Display Xbox results
        if xbox_results:
            st.markdown("### 🎮 Xbox Regional Pricing")
            xbox_df = process_results(xbox_results, rates)
            st.dataframe(xbox_df, use_container_width=True, height=400)
            st.download_button(
                "⬇️ Download Xbox CSV",
                xbox_df.to_csv(index=False).encode("utf-8"),
                "xbox_prices.csv",
                "text/csv"
            )
        
        # Display PlayStation results
        if ps_results:
            st.markdown("### 🎮 PlayStation Regional Pricing")
            ps_df = process_results(ps_results, rates)
            st.dataframe(ps_df, use_container_width=True, height=400)
            
            if DEBUG_MODE:
                # Show summary of price types
                price_type_counts = ps_df['Price Type'].value_counts()
                st.markdown("**Price Type Summary:**")
                st.write(price_type_counts)
                st.caption("Check your console/terminal for detailed debugging logs showing exact price extraction logic")
            
            st.download_button(
                "⬇️ Download PlayStation CSV",
                ps_df.to_csv(index=False).encode("utf-8"),
                "playstation_prices.csv",
                "text/csv"
            )