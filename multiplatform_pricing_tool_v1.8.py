# multiplatform_pricing_tool_v1.8.py
# DEEP FIX: Comprehensive Next.js JSON inspection + Alternative price field extraction
# Fixes: NBA 2K26 sale prices, Call of Duty missing countries, Next.js parse failures

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

DEBUG_MODE = True

st.set_page_config(
    page_title="Unified Game Pricing Tool v1.8",
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
    "AU": "en-au", "NZ": "en-nz", "ZA": "en-za", "UA": "uk-ua"
}

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
    debug_info: Optional[str] = None

# ============================================================================
# CURRENCY & UTILITY
# ============================================================================

def fetch_exchange_rates() -> Dict[str, float]:
    if "exchange_rates" in st.session_state:
        cache_time = st.session_state.get("rates_timestamp", 0)
        if time.time() - cache_time < 7200:
            return st.session_state["exchange_rates"]
    rates = {"USD": 1.0}
    try:
        resp = requests.get("https://api.exchangerate.host/latest", params={"base": "USD"}, timeout=15)
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
    if amount is None or currency not in rates:
        return None
    rate = rates.get(currency, 1.0)
    if rate <= 0:
        return None
    return round(amount / rate, 2)

def _num(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        s = str(x).strip().replace(",", "")
        return float(s)
    except Exception:
        return None

# ============================================================================
# STEAM
# ============================================================================

def extract_steam_appid(input_str: str) -> Optional[str]:
    input_str = input_str.strip()
    if input_str.isdigit():
        return input_str
    match = re.search(r'/app/(\d+)', input_str)
    if match:
        return match.group(1)
    return None

def fetch_steam_price(appid: str, country: str, title: str) -> Optional[PriceData]:
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
# XBOX
# ============================================================================

def extract_xbox_store_id(input_str: str) -> Optional[str]:
    input_str = input_str.strip()
    if len(input_str) == 12 and input_str[0] == '9':
        return input_str
    match = re.search(r'/([9][A-Z0-9]{11})', input_str, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None

def fetch_xbox_price(store_id: str, country: str, title: str) -> Optional[PriceData]:
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
# PLAYSTATION - v1.8 DEEP INSPECTION
# ============================================================================

def extract_ps_product_id(input_str: str) -> Optional[str]:
    input_str = input_str.strip()
    if not input_str.startswith("http"):
        return input_str
    match = re.search(r'/product/([^/?#]+)', input_str)
    if match:
        return match.group(1)
    return None

def parse_next_json(html: str) -> Optional[dict]:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if tag and tag.string:
        try:
            return json.loads(tag.string)
        except Exception:
            pass
    all_scripts = soup.find_all("script")
    for script in all_scripts:
        if script.string and "__NEXT_DATA__" in script.string:
            try:
                match = re.search(r'({.*})', script.string, re.DOTALL)
                if match:
                    return json.loads(match.group(1))
            except Exception:
                continue
    for script in all_scripts:
        if script.string and "pageProps" in script.string and "product" in script.string:
            try:
                return json.loads(script.string)
            except Exception:
                continue
    return None

def deep_search_for_prices(obj: Any, path: str = "root") -> List[Tuple[str, dict]]:
    """
    Recursively search through JSON for ANY object containing price-like fields
    Returns list of (path, price_object) tuples
    """
    results = []
    
    if isinstance(obj, dict):
        # Check if this object itself contains price fields
        price_fields = {"basePrice", "discountedPrice", "finalPrice", "price", "msrp", "retailPrice", 
                       "listPrice", "actualPrice", "current", "value"}
        if any(key in obj for key in price_fields):
            results.append((path, obj))
        
        # Recurse into nested objects
        for key, value in obj.items():
            new_path = f"{path}.{key}"
            results.extend(deep_search_for_prices(value, new_path))
    
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            new_path = f"{path}[{idx}]"
            results.extend(deep_search_for_prices(item, new_path))
    
    return results

def extract_price_from_object(price_obj: dict) -> Tuple[Optional[float], str, str]:
    """
    Extract price with MAXIMUM MSRP priority checking ALL possible field names
    Returns: (price, price_type, debug_info)
    """
    if not isinstance(price_obj, dict):
        return None, "Unknown", "not_dict"
    
    # Try ALL possible MSRP field names first
    msrp_fields = ["basePrice", "msrp", "MSRP", "retailPrice", "listPrice", "originalPrice"]
    for field in msrp_fields:
        val = _num(price_obj.get(field))
        if val and val > 0:
            fields_str = ",".join([f"{k}={price_obj.get(k)}" for k in price_obj.keys() if k in msrp_fields or "price" in k.lower()])
            return val, "MSRP", f"used_{field}|{fields_str}"
    
    # Try standard price fields
    standard_fields = ["finalPrice", "actualPrice", "price"]
    for field in standard_fields:
        val = _num(price_obj.get(field))
        if val and val > 0:
            fields_str = ",".join([f"{k}={price_obj.get(k)}" for k in price_obj.keys() if "price" in k.lower()])
            return val, "Current", f"used_{field}|{fields_str}"
    
    # Try discounted/sale fields (least preferred)
    sale_fields = ["discountedPrice", "salePrice", "current", "value"]
    for field in sale_fields:
        val = _num(price_obj.get(field))
        if val and val > 0:
            fields_str = ",".join([f"{k}={price_obj.get(k)}" for k in price_obj.keys() if "price" in k.lower()])
            return val, "Sale Price", f"used_{field}|{fields_str}"
    
    return None, "Unknown", f"no_valid_price|keys={list(price_obj.keys())}"

def from_next_json_deep(next_json: dict) -> Tuple[Optional[str], Optional[str], Optional[float], str, Optional[str], str]:
    """
    DEEP extraction from Next.js JSON - searches ENTIRE structure for price data
    Returns: (title, product_id, price, price_type, currency, debug_info)
    """
    try:
        props = next_json.get("props", {})
        page_props = props.get("pageProps", {})
        product = page_props.get("product") or page_props.get("pageData") or page_props.get("telemetryData") or {}

        title = product.get("name") or product.get("title") or page_props.get("title")
        pid = product.get("id") or product.get("productId") or product.get("slug") or page_props.get("productId")

        # DEEP SEARCH: Find ALL price objects in the entire JSON structure
        price_candidates = deep_search_for_prices(next_json)
        
        if not price_candidates:
            return title, pid, None, "Unknown", None, "deep_search_found_no_price_objects"
        
        # Try each price object found, prioritizing by path depth (shallower = more likely to be correct)
        price_candidates.sort(key=lambda x: x[0].count('.'))
        
        for path, price_obj in price_candidates:
            price, price_type, extract_debug = extract_price_from_object(price_obj)
            if price and price > 0:
                currency = price_obj.get("currency") or price_obj.get("currencyCode")
                full_debug = f"deep_search|path={path}|{extract_debug}"
                return title, pid, price, price_type, currency, full_debug
        
        # Found price objects but couldn't extract valid prices
        paths = [p[0] for p in price_candidates[:3]]
        return title, pid, None, "Unknown", None, f"deep_search_found_{len(price_candidates)}_objects|tried={','.join(paths)}"
        
    except Exception as e:
        return None, None, None, "Error", None, f"exception:{str(e)[:100]}"

def parse_json_ld_enhanced(html: str) -> Tuple[Optional[str], Optional[float], Optional[str], str]:
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")
    debug_info = f"found_{len(scripts)}_ld_scripts"
    
    for idx, s in enumerate(scripts):
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
                    high_price = _num(offers.get("highPrice"))
                    if high_price and high_price > 0:
                        currency = offers.get("priceCurrency")
                        return title, high_price, currency, f"{debug_info}|script{idx}|used_highPrice"
                    price = _num(offers.get("price"))
                    currency = offers.get("priceCurrency")
                    if price is not None and price > 0:
                        return title, price, currency, f"{debug_info}|script{idx}|used_price"
                
                elif isinstance(offers, list):
                    for off_idx, off in enumerate(offers):
                        if isinstance(off, dict):
                            high_price = _num(off.get("highPrice"))
                            if high_price and high_price > 0:
                                currency = off.get("priceCurrency")
                                return title, high_price, currency, f"{debug_info}|script{idx}|offer{off_idx}|highPrice"
                            price = _num(off.get("price"))
                            currency = off.get("priceCurrency")
                            if price is not None and price > 0:
                                return title, price, currency, f"{debug_info}|script{idx}|offer{off_idx}|price"
    
    return None, None, None, f"{debug_info}|no_valid_offers"

def parse_meta_tags(html: str) -> Tuple[Optional[float], Optional[str], str]:
    soup = BeautifulSoup(html, "html.parser")
    meta_amt = soup.find("meta", property="og:price:amount")
    meta_cur = soup.find("meta", property="og:price:currency")
    if meta_amt and meta_amt.get("content"):
        price = _num(meta_amt.get("content"))
        currency = meta_cur.get("content") if meta_cur and meta_cur.get("content") else None
        if price is not None:
            return price, currency, "og_price_amount"
    ip = soup.find(attrs={"itemprop":"price"})
    ipcur = soup.find(attrs={"itemprop":"priceCurrency"})
    if ip and ip.get("content"):
        price = _num(ip.get("content"))
        currency = ipcur.get("content") if ipcur and ipcur.get("content") else None
        if price is not None:
            return price, currency, "itemprop_price"
    return None, None, "no_meta_tags"

def choose_currency(parsed: Optional[str], expected: Optional[str]) -> Optional[str]:
    if expected:
        return expected.upper()
    return parsed.upper() if parsed else None

def fetch_ps_price(product_id: str, country: str, title: str) -> Optional[PriceData]:
    """Fetch PlayStation price with DEEP JSON inspection"""
    if country not in PS_MARKETS:
        return None
    
    locale = PS_MARKETS[country]
    currency = PLATFORM_CURRENCIES["PlayStation"].get(country, "USD")
    
    headers = dict(PS_HEADERS)
    if locale:
        lang = locale.split("-")[0]
        headers["Accept-Language"] = f"{lang}-{locale.split('-')[-1].upper()},{lang};q=0.8"
    
    debug_log = []
    
    try:
        url = f"https://store.playstation.com/{locale}/product/{product_id}"
        resp = requests.get(url, headers=headers, timeout=30)
        
        if resp.status_code != 200:
            debug_log.append(f"http_{resp.status_code}")
            return PriceData("PlayStation", title, country, currency, None, None, None, "N/A", None, "|".join(debug_log))
        
        html = resp.text
        debug_log.append("html_ok")
        
        # Try DEEP Next.js JSON extraction
        nxt = parse_next_json(html)
        if nxt:
            debug_log.append("nextjs_found")
            t, _, price, price_type, pcurr, parse_debug = from_next_json_deep(nxt)
            if price is not None and price > 0:
                final_currency = choose_currency(pcurr, currency)
                full_debug = "|".join(debug_log + ["next_json_deep", parse_debug])
                print(f"[PSN {country}] {title}: {price} {final_currency} ({price_type}) - {full_debug}")
                return PriceData("PlayStation", title, country, final_currency, price, None, None, price_type, "next_json", full_debug)
            else:
                debug_log.append(f"nextjs_deep_no_price:{parse_debug}")
        else:
            debug_log.append("nextjs_not_found")
        
        # Fallback to JSON-LD
        t2, price2, pcurr2, ld_debug = parse_json_ld_enhanced(html)
        if price2 is not None and price2 > 0:
            final_currency = choose_currency(pcurr2, currency)
            full_debug = "|".join(debug_log + ["json_ld", ld_debug])
            print(f"[PSN {country}] {title}: {price2} {final_currency} (JSON-LD) - {full_debug}")
            return PriceData("PlayStation", title, country, final_currency, price2, None, None, "Current", "json_ld", full_debug)
        else:
            debug_log.append(f"json_ld_no_price:{ld_debug}")
        
        # Fallback to meta tags
        price3, pcurr3, meta_debug = parse_meta_tags(html)
        if price3 is not None and price3 > 0:
            final_currency = choose_currency(pcurr3, currency)
            full_debug = "|".join(debug_log + ["meta", meta_debug])
            return PriceData("PlayStation", title, country, final_currency, price3, None, None, "Current", "meta_tags", full_debug)
        else:
            debug_log.append(f"meta_no_price:{meta_debug}")
        
        full_debug = "|".join(debug_log + ["all_failed"])
        print(f"[PSN {country}] {title}: FAILED - {full_debug}")
        return PriceData("PlayStation", title, country, currency, None, None, None, "N/A", None, full_debug)
                
    except Exception as e:
        debug_log.append(f"exception:{str(e)[:50]}")
        full_debug = "|".join(debug_log)
        print(f"[PSN {country}] {title}: ERROR - {full_debug}")
        return PriceData("PlayStation", title, country, currency, None, None, None, "N/A", None, full_debug)

# ============================================================================
# ORCHESTRATION
# ============================================================================

def pull_all_prices(steam_games: List[Tuple[str, str]], 
                   xbox_games: List[Tuple[str, str]], 
                   ps_games: List[Tuple[str, str]],
                   max_workers: int = 20) -> Tuple[List[PriceData], List[PriceData], List[PriceData]]:
    steam_results = []
    xbox_results = []
    ps_results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for appid, title in steam_games:
            for country in STEAM_MARKETS.keys():
                futures.append((executor.submit(fetch_steam_price, appid, country, title), "steam"))
        for store_id, title in xbox_games:
            for country in XBOX_MARKETS.keys():
                futures.append((executor.submit(fetch_xbox_price, store_id, country, title), "xbox"))
        for product_id, title in ps_games:
            for country in PS_MARKETS.keys():
                futures.append((executor.submit(fetch_ps_price, product_id, country, title), "ps"))
        
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
    if not results:
        return pd.DataFrame()
    
    for r in results:
        r.price_usd = convert_to_usd(r.price, r.currency, rates)
    
    us_prices = {}
    for r in results:
        if r.country == "US" and r.price_usd:
            us_prices[r.title] = r.price_usd
    
    for r in results:
        if r.price_usd and r.title in us_prices:
            us_price = us_prices[r.title]
            if us_price > 0:
                pct = ((r.price_usd / us_price) - 1) * 100
                r.diff_vs_us = f"{pct:+.1f}%"
    
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
        if DEBUG_MODE:
            row["Price Type"] = r.price_type
            row["Source"] = r.source
            row["Debug Info"] = r.debug_info
        df_data.append(row)
    
    df = pd.DataFrame(df_data)
    return df.sort_values(["Title", "Country"]).reset_index(drop=True)

# ============================================================================
# STREAMLIT UI
# ============================================================================

st.title("🎮 Unified Multi-Platform Game Pricing Tool v1.8")
st.caption("✅ DEEP FIX: Recursive JSON inspection finds prices anywhere in structure + MSRP priority")

if DEBUG_MODE:
    st.info("🔍 **Deep Search Active** - Recursively searches entire Next.js JSON for price objects")

st.markdown("---")

st.subheader("🎮 Steam Games")
st.caption("Add games one per line: Title | AppID or URL")
col1, col2 = st.columns([3, 1])
with col1:
    steam_input = st.text_area("Format: Game Title | AppID or URL", height=150, 
                               placeholder="The Outer Worlds 2 | 1449110\nBorderlands 4 | 1285190")
with col2:
    st.markdown("**Examples:**")
    st.code("Borderlands 4 | 1285190", language="text")
    st.code("NBA 2K26 | 3472040", language="text")

st.subheader("🎮 Xbox Games")
st.caption("Add games one per line: Title | Store ID or URL")
col3, col4 = st.columns([3, 1])
with col3:
    xbox_input = st.text_area("Format: Game Title | Store ID or URL", height=150,
                             placeholder="The Outer Worlds 2 | 9NSPRSXXZZLG\nBorderlands 4 | 9MX6HKF5647G")
with col4:
    st.markdown("**Examples:**")
    st.code("Borderlands 4 | 9MX6HKF5647G", language="text")
    st.code("NBA 2K26 | 9PJ2RVRC0L1X", language="text")

st.subheader("🎮 PlayStation Games")
st.caption("Add games one per line: Title | Product ID or URL")
col5, col6 = st.columns([3, 1])
with col5:
    ps_input = st.text_area("Format: Game Title | Product ID or URL", height=150,
                           placeholder="Borderlands 4 | UP1001-PPSA01494_00-000000000000OAK2\nNBA 2K26 | UP1001-PPSA28420_00-NBA2K26000000000")
with col6:
    st.markdown("**Examples:**")
    st.code("Borderlands 4 | UP1001-PPSA01494_00-...", language="text")
    st.code("NBA 2K26 | UP1001-PPSA28420_00-...", language="text")

st.markdown("---")

if st.button("🚀 Pull Prices", type="primary", use_container_width=True):
    steam_games = []
    xbox_games = []
    ps_games = []
    
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
            steam_results, xbox_results, ps_results = pull_all_prices(steam_games, xbox_games, ps_games)
        
        st.success(f"✅ Price pull complete! Found {len(steam_results)} Steam, {len(xbox_results)} Xbox, {len(ps_results)} PlayStation prices")
        
        if steam_results:
            st.markdown("### 🎮 Steam Regional Pricing")
            steam_df = process_results(steam_results, rates)
            st.dataframe(steam_df, use_container_width=True, height=400)
            st.download_button("⬇️ Download Steam CSV", steam_df.to_csv(index=False).encode("utf-8"),
                             "steam_prices.csv", "text/csv")
        
        if xbox_results:
            st.markdown("### 🎮 Xbox Regional Pricing")
            xbox_df = process_results(xbox_results, rates)
            st.dataframe(xbox_df, use_container_width=True, height=400)
            st.download_button("⬇️ Download Xbox CSV", xbox_df.to_csv(index=False).encode("utf-8"),
                             "xbox_prices.csv", "text/csv")
        
        if ps_results:
            st.markdown("### 🎮 PlayStation Regional Pricing")
            ps_df = process_results(ps_results, rates)
            st.dataframe(ps_df, use_container_width=True, height=400)
            
            if DEBUG_MODE:
                st.markdown("**Price Type Summary:**")
                st.write(ps_df['Price Type'].value_counts())
                st.markdown("**Parse Method Summary:**")
                st.write(ps_df['Source'].value_counts())
                st.caption("📊 'Debug Info' column shows exact parse path including deep search results")
            
            st.download_button("⬇️ Download PlayStation CSV", ps_df.to_csv(index=False).encode("utf-8"),
                             "playstation_prices.csv", "text/csv")