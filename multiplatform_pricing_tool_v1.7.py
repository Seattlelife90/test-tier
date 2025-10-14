# multiplatform_pricing_tool_v1.7.py
# MAJOR FIX: Robust basePrice extraction + Better JSON-LD parsing + Debug column shows parse method
# Fixes: Australia locale, sale price issues, missing Call of Duty prices

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
    page_title="Unified Game Pricing Tool v1.7",
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

# PlayStation locale mappings - FIXED Australia
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
    debug_info: Optional[str] = None  # NEW: Store debug information

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
# PLAYSTATION PRICE PULLER - v1.7 ROBUST PARSING
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
    """Parse PlayStation Next.js JSON with multiple fallback strategies"""
    soup = BeautifulSoup(html, "html.parser")
    
    # Strategy 1: Standard __NEXT_DATA__
    tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if tag and tag.string:
        try:
            return json.loads(tag.string)
        except Exception:
            pass
    
    # Strategy 2: Look for any script with __NEXT_DATA__
    all_scripts = soup.find_all("script")
    for script in all_scripts:
        if script.string and "__NEXT_DATA__" in script.string:
            try:
                # Extract JSON from script
                match = re.search(r'({.*})', script.string, re.DOTALL)
                if match:
                    return json.loads(match.group(1))
            except Exception:
                continue
    
    # Strategy 3: Look for data in script without ID
    for script in all_scripts:
        if script.string and "pageProps" in script.string and "product" in script.string:
            try:
                return json.loads(script.string)
            except Exception:
                continue
    
    return None

def extract_price_with_type(price_dict: dict) -> Tuple[Optional[float], str, str]:
    """
    Extract price from PlayStation price object with MAXIMUM basePrice priority
    Returns: (price, price_type, debug_info)
    
    v1.7: Even more aggressive basePrice extraction
    """
    if not isinstance(price_dict, dict):
        return None, "Unknown", "not_dict"
    
    # Extract ALL possible price fields
    base = _num(price_dict.get("basePrice"))
    disc = _num(price_dict.get("discountedPrice"))
    final = _num(price_dict.get("finalPrice"))
    current = _num(price_dict.get("current"))
    value = _num(price_dict.get("value"))
    actual = _num(price_dict.get("actualPrice"))
    
    debug = f"base={base},disc={disc},final={final},curr={current},val={value},act={actual}"
    
    # CRITICAL: ALWAYS use basePrice when it exists (this is MSRP)
    if base and base > 0:
        # If there's a discount active, basePrice is STILL the correct MSRP
        if disc and disc > 0 and disc < base:
            return base, "MSRP", f"{debug}|used_base_over_disc"
        return base, "MSRP", f"{debug}|used_base"
    
    # If basePrice missing, try to infer MSRP from other fields
    # Some regions put MSRP in finalPrice when no discount active
    if final and final > 0:
        # If discount exists and is less than final, final might be MSRP
        if disc and disc > 0 and disc < final:
            return final, "MSRP", f"{debug}|used_final_as_msrp"
        return final, "Current", f"{debug}|used_final"
    
    # actualPrice might be MSRP in some regions
    if actual and actual > 0:
        if disc and disc > 0 and disc < actual:
            return actual, "MSRP", f"{debug}|used_actual_as_msrp"
        return actual, "Current", f"{debug}|used_actual"
    
    # Last resort: discounted price (this is a SALE price, not ideal)
    if disc and disc > 0:
        return disc, "Sale Price", f"{debug}|used_disc_only"
    
    # Fallback to any available field
    if current and current > 0:
        return current, "Current", f"{debug}|used_current"
    if value and value > 0:
        return value, "Current", f"{debug}|used_value"
    
    return None, "Unknown", f"{debug}|no_price_found"

def from_next_json(next_json: dict) -> Tuple[Optional[str], Optional[str], Optional[float], str, Optional[str], str]:
    """
    Extract price from Next.js JSON with comprehensive debugging
    Returns: (title, product_id, price, price_type, currency, debug_info)
    """
    try:
        props = next_json.get("props", {})
        page_props = props.get("pageProps", {})
        product = page_props.get("product") or page_props.get("pageData") or page_props.get("telemetryData") or {}

        title = product.get("name") or product.get("title") or page_props.get("title")
        pid = product.get("id") or product.get("productId") or product.get("slug") or page_props.get("productId")

        # Try multiple locations for price data
        locations = [
            ("product.price", product.get("price") if isinstance(product, dict) else None),
            ("defaultSku.price", product.get("defaultSku", {}).get("price") if isinstance(product.get("defaultSku"), dict) else None),
            ("pageProps.price", page_props.get("price")),
            ("store.price", page_props.get("store", {}).get("price"))
        ]
        
        # Also check skus array
        skus = product.get("skus") if isinstance(product, dict) else None
        if isinstance(skus, list) and len(skus) > 0:
            for idx, sku in enumerate(skus):
                locations.append((f"skus[{idx}].price", sku.get("price")))
        
        # Try each location
        for location_name, price_obj in locations:
            if isinstance(price_obj, dict):
                price, price_type, debug = extract_price_with_type(price_obj)
                currency = price_obj.get("currency")
                if price and price > 0:
                    full_debug = f"{location_name}|{debug}"
                    return title, pid, price, price_type, currency, full_debug
        
        return title, pid, None, "Unknown", None, "no_valid_price_location"
    except Exception as e:
        return None, None, None, "Error", None, f"exception:{str(e)}"

def parse_json_ld_enhanced(html: str) -> Tuple[Optional[str], Optional[float], Optional[str], str]:
    """
    Enhanced JSON-LD parsing that tries to find basePrice/MSRP
    Returns: (title, price, currency, debug_info)
    """
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
                
                # Try to extract MSRP from offers
                if isinstance(offers, dict):
                    # Look for price and priceValidUntil (might indicate it's base price)
                    price = _num(offers.get("price"))
                    currency = offers.get("priceCurrency")
                    
                    # Check if there's a "highPrice" which might be MSRP
                    high_price = _num(offers.get("highPrice"))
                    if high_price and high_price > 0:
                        return title, high_price, currency, f"{debug_info}|script{idx}|used_highPrice"
                    
                    if price is not None and price > 0:
                        return title, price, currency, f"{debug_info}|script{idx}|used_price"
                
                elif isinstance(offers, list):
                    # Try each offer, prefer ones with highPrice
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
    """Parse meta tags for price with debug info"""
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
    """Choose currency with preference for expected"""
    if expected:
        return expected.upper()
    return parsed.upper() if parsed else None

def fetch_ps_price(product_id: str, country: str, title: str) -> Optional[PriceData]:
    """Fetch PlayStation price with robust MSRP extraction and debugging"""
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
        
        # Try Next.js JSON first
        nxt = parse_next_json(html)
        if nxt:
            debug_log.append("nextjs_found")
            t, _, price, price_type, pcurr, parse_debug = from_next_json(nxt)
            if price is not None and price > 0:
                final_currency = choose_currency(pcurr, currency)
                full_debug = "|".join(debug_log + ["next_json", parse_debug])
                print(f"[PSN {country}] {title}: {price} {final_currency} ({price_type}) - {full_debug}")
                return PriceData("PlayStation", title, country, final_currency, price, None, None, price_type, "next_json", full_debug)
            else:
                debug_log.append(f"nextjs_no_price:{parse_debug}")
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
        
        # All methods failed
        full_debug = "|".join(debug_log + ["all_failed"])
        print(f"[PSN {country}] {title}: FAILED - {full_debug}")
        return PriceData("PlayStation", title, country, currency, None, None, None, "N/A", None, full_debug)
                
    except Exception as e:
        debug_log.append(f"exception:{str(e)[:50]}")
        full_debug = "|".join(debug_log)
        print(f"[PSN {country}] {title}: ERROR - {full_debug}")
        return PriceData("PlayStation", title, country, currency, None, None, None, "N/A", None, full_debug)

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
            row["Debug Info"] = r.debug_info  # NEW: Full debug trail
        
        df_data.append(row)
    
    df = pd.DataFrame(df_data)
    return df.sort_values(["Title", "Country"]).reset_index(drop=True)

# ============================================================================
# STREAMLIT UI
# ============================================================================

st.title("🎮 Unified Multi-Platform Game Pricing Tool v1.7")
st.caption("✅ MAJOR FIX: Robust basePrice extraction + Enhanced debugging + Australia locale fixed")

if DEBUG_MODE:
    st.info("🔍 **Debug Mode Active** - Results include 'Debug Info' column showing exact parse path")

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
        placeholder="Borderlands 4 | UP1001-PPSA01494_00-000000000000OAK2\nNBA 2K26 | UP1001-PPSA28420_00-NBA2K26000000000"
    )
with col6:
    st.markdown("**Examples:**")
    st.code("Borderlands 4 | UP1001-PPSA01494_00-...", language="text")
    st.code("NBA 2K26 | UP1001-PPSA28420_00-...", language="text")

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
                st.markdown("**Price Type Summary:**")
                price_type_counts = ps_df['Price Type'].value_counts()
                st.write(price_type_counts)
                
                # Show parse method distribution
                st.markdown("**Parse Method Summary:**")
                source_counts = ps_df['Source'].value_counts()
                st.write(source_counts)
                
                st.caption("📊 Check 'Debug Info' column for detailed parse path. Console may show additional logs.")
            
            st.download_button(
                "⬇️ Download PlayStation CSV",
                ps_df.to_csv(index=False).encode("utf-8"),
                "playstation_prices.csv",
                "text/csv"
            )