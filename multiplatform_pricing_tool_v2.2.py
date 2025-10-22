# multiplatform_pricing_tool_v2.2.py
# ENHANCED HYBRID APPROACH: HTML scraping + aggressive regex price hunting + DECIMAL FIXES
# NEW IN v2.2:
# - ✅ DECIMAL CONVERSION: Converts 7999 → 79.99 for EUR prices
# - ✅ RETRY LOGIC: Exponential backoff with 3 retries on failures
# - ✅ IMPROVED CURRENCY DETECTION: Better handling of currency symbols
# - ✅ ROBUST PRICE PARSING: Handles more edge cases
# - Steam and Xbox unchanged (working perfectly)

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
    page_title="Unified Game Pricing Tool v2.2",
    page_icon="🎮",
    layout="wide"
)

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

# Currencies that typically use 2 decimal places
DECIMAL_CURRENCIES = {
    "USD", "CAD", "EUR", "GBP", "AUD", "NZD", "SGD", "HKD", "MYR", "THB",
    "PHP", "BRL", "ARS", "MXN", "CLP", "COP", "PEN", "UYU", "CRC", "CHF",
    "NOK", "SEK", "DKK", "PLN", "CZK", "HUF", "TRY", "ILS", "SAR", "AED",
    "QAR", "KWD", "ZAR", "UAH", "KZT", "RUB", "INR", "CNY", "TWD"
}

# Currencies that typically DON'T use decimals (yen-like currencies)
NO_DECIMAL_CURRENCIES = {"JPY", "KRW", "VND", "IDR"}

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
# UTILITY FUNCTIONS
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

def smart_price_conversion(raw_value: Any, currency: str) -> Optional[float]:
    """
    v2.2 SMART CONVERSION: Intelligently converts price strings to floats
    - Handles 7999 → 79.99 for decimal currencies (EUR, USD, etc.)
    - Keeps 7999 → 7999 for non-decimal currencies (JPY, KRW, etc.)
    - Handles currency symbols and formatting
    """
    try:
        if raw_value is None:
            return None
        
        # Already a number
        if isinstance(raw_value, (int, float)):
            value = float(raw_value)
        else:
            # Clean string: remove currency symbols and commas
            s = str(raw_value).strip()
            s = s.replace("$", "").replace("€", "").replace("£", "").replace("¥", "")
            s = s.replace("₹", "").replace("R$", "").replace(",", "").replace(" ", "").strip()
            
            if not s:
                return None
            
            value = float(s)
        
        # If value is zero or negative, return None
        if value <= 0:
            return None
        
        # Check if this currency uses decimals
        if currency in NO_DECIMAL_CURRENCIES:
            # Currencies like JPY, KRW - no decimal conversion needed
            return round(value, 0)
        
        elif currency in DECIMAL_CURRENCIES:
            # Currencies like EUR, USD - need decimal conversion
            # If the value is > 100 and has no decimal point in original string
            if value >= 100 and '.' not in str(raw_value):
                # Likely missing decimal: 7999 → 79.99
                value = value / 100.0
                return round(value, 2)
            else:
                # Already has decimal or is small value
                return round(value, 2)
        
        else:
            # Unknown currency - assume it uses decimals
            if value >= 100 and '.' not in str(raw_value):
                value = value / 100.0
            return round(value, 2)
            
    except Exception:
        return None

def _num(x: Any, currency: str = "USD") -> Optional[float]:
    """Legacy wrapper that uses smart_price_conversion"""
    return smart_price_conversion(x, currency)

# ============================================================================
# RETRY LOGIC
# ============================================================================

def retry_with_backoff(func, max_retries=3, initial_delay=1.0):
    """
    v2.2 RETRY LOGIC: Exponential backoff with jitter
    Retries failed requests up to max_retries times with increasing delays
    """
    for attempt in range(max_retries):
        try:
            result = func()
            return result
        except Exception as e:
            if attempt == max_retries - 1:
                # Last attempt failed, raise the exception
                raise e
            
            # Calculate delay with exponential backoff and jitter
            delay = initial_delay * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(delay)
    
    return None

# ============================================================================
# STEAM (Unchanged)
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
# XBOX (Unchanged)
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
# PLAYSTATION - v2.2 WITH DECIMAL CONVERSION + RETRY LOGIC
# ============================================================================

def extract_ps_product_id(input_str: str) -> Optional[str]:
    input_str = input_str.strip()
    if not input_str.startswith("http"):
        return input_str
    match = re.search(r'/product/([^/?#]+)', input_str)
    if match:
        return match.group(1)
    return None

def hunt_prices_in_html(html: str, currency: str) -> List[Dict[str, Any]]:
    """
    v2.2 ENHANCED: Aggressively search entire HTML for price patterns
    Now uses smart_price_conversion for decimal handling
    Looking for: basePrice, discountedPrice in any format
    Returns list of {basePrice, discountedPrice, currencyCode, source}
    """
    findings = []
    
    # Pattern 1: Search for basePrice:"$XX.XX" or basePrice:"€XX.XX" or basePrice:7999
    base_pattern = r'basePrice["\s:]+(["\$€£¥₹R\s]*)([\d,]+\.?\d{0,2})'
    base_matches = re.findall(base_pattern, html, re.IGNORECASE)
    
    # Pattern 2: Search for discountedPrice:"$XX.XX"
    disc_pattern = r'discountedPrice["\s:]+(["\$€£¥₹R\s]*)([\d,]+\.?\d{0,2})'
    disc_matches = re.findall(disc_pattern, html, re.IGNORECASE)
    
    # Pattern 3: Search for price objects in JSON format
    # Looking for: {"basePrice":"$79.99","discountedPrice":"$55.99"}
    # OR: {"basePrice":7999,"discountedPrice":5599}
    json_pattern = r'\{[^}]*basePrice[^}]*\}'
    json_matches = re.findall(json_pattern, html, re.IGNORECASE)
    
    for match in json_matches:
        try:
            # Try to extract structured price data
            base_search = re.search(r'basePrice["\s:]+(["\$€£¥₹R\s]*)?([\d,]+\.?\d{0,2})', match)
            disc_search = re.search(r'discountedPrice["\s:]+(["\$€£¥₹R\s]*)?([\d,]+\.?\d{0,2})', match)
            curr_search = re.search(r'currencyCode["\s:]+["\']*([A-Z]{3})', match)
            
            if base_search or disc_search:
                raw_base = base_search.group(2) if base_search else None
                raw_disc = disc_search.group(2) if disc_search else None
                detected_currency = curr_search.group(1) if curr_search else currency
                
                finding = {
                    'basePrice': smart_price_conversion(raw_base, detected_currency),
                    'discountedPrice': smart_price_conversion(raw_disc, detected_currency),
                    'currencyCode': detected_currency,
                    'source': 'regex_json_object',
                    'raw_base': raw_base,
                    'raw_disc': raw_disc
                }
                findings.append(finding)
        except Exception:
            continue
    
    # If we found structured objects, return those
    if findings:
        return findings
    
    # Otherwise, try to pair basePrice and discountedPrice from separate matches
    if base_matches or disc_matches:
        raw_base = base_matches[0][1] if base_matches else None
        raw_disc = disc_matches[0][1] if disc_matches else None
        
        finding = {
            'basePrice': smart_price_conversion(raw_base, currency),
            'discountedPrice': smart_price_conversion(raw_disc, currency),
            'currencyCode': currency,
            'source': 'regex_separate',
            'raw_base': raw_base,
            'raw_disc': raw_disc
        }
        findings.append(finding)
    
    return findings

def parse_next_json(html: str) -> Optional[dict]:
    """Parse Next.js JSON from script tags"""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if tag and tag.string:
        try:
            return json.loads(tag.string)
        except Exception:
            pass
    return None

def search_all_scripts_for_prices(html: str, currency: str) -> List[Dict[str, Any]]:
    """v2.2: Search ALL script tags for price data with smart conversion"""
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script")
    
    all_findings = []
    for script in scripts:
        if script.string:
            findings = hunt_prices_in_html(script.string, currency)
            all_findings.extend(findings)
    
    return all_findings

def parse_json_ld(html: str, currency: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
    """v2.2: Parse JSON-LD structured data (fallback) with smart conversion"""
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
                    high_price = smart_price_conversion(offers.get("highPrice"), currency)
                    if high_price and high_price > 0:
                        detected_currency = offers.get("priceCurrency") or currency
                        return title, high_price, detected_currency
                    price = smart_price_conversion(offers.get("price"), currency)
                    detected_currency = offers.get("priceCurrency") or currency
                    if price is not None and price > 0:
                        return title, price, detected_currency
                
                elif isinstance(offers, list):
                    for off in offers:
                        if isinstance(off, dict):
                            high_price = smart_price_conversion(off.get("highPrice"), currency)
                            if high_price and high_price > 0:
                                detected_currency = off.get("priceCurrency") or currency
                                return title, high_price, detected_currency
                            price = smart_price_conversion(off.get("price"), currency)
                            detected_currency = off.get("priceCurrency") or currency
                            if price is not None and price > 0:
                                return title, price, detected_currency
    
    return None, None, None

def fetch_ps_price_attempt(product_id: str, country: str, title: str, currency_code: str) -> Optional[PriceData]:
    """Single attempt to fetch PlayStation price - used by retry wrapper"""
    locale = PS_MARKETS[country]
    
    headers = dict(PS_HEADERS)
    if locale:
        lang = locale.split("-")[0]
        headers["Accept-Language"] = f"{lang}-{locale.split('-')[-1].upper()},{lang};q=0.8"
    
    debug_log = []
    
    url = f"https://store.playstation.com/{locale}/product/{product_id}"
    resp = requests.get(url, headers=headers, timeout=30)
    
    if resp.status_code != 200:
        debug_log.append(f"http_{resp.status_code}")
        raise Exception(f"HTTP {resp.status_code}")
    
    html = resp.text
    debug_log.append("html_ok")
    
    # METHOD 1: Hunt for prices in entire HTML with regex
    html_findings = hunt_prices_in_html(html, currency_code)
    if html_findings:
        debug_log.append(f"regex_found_{len(html_findings)}_patterns")
        # Use first finding with basePrice
        for finding in html_findings:
            base = finding.get('basePrice')
            disc = finding.get('discountedPrice')
            curr = finding.get('currencyCode', currency_code)
            
            if base and base > 0:
                debug_log.append(f"base={base}|raw={finding.get('raw_base')}|disc={disc}|src={finding['source']}")
                debug_log.append("✓used_basePrice_regex")
                full_debug = "|".join(debug_log)
                print(f"[PSN v2.2 Regex {country}] {title}: {base} {curr} (MSRP from {finding['source']})")
                return PriceData("PlayStation", title, country, curr, base, None, None, "MSRP", "regex_hunt", full_debug)
            
            if disc and disc > 0:
                debug_log.append(f"disc={disc}|raw={finding.get('raw_disc')}|src={finding['source']}")
                debug_log.append("⚠used_discountedPrice_regex")
                full_debug = "|".join(debug_log)
                return PriceData("PlayStation", title, country, curr, disc, None, None, "Sale Price", "regex_hunt", full_debug)
    
    # METHOD 2: Search all script tags
    script_findings = search_all_scripts_for_prices(html, currency_code)
    if script_findings:
        debug_log.append(f"scripts_found_{len(script_findings)}_patterns")
        for finding in script_findings:
            base = finding.get('basePrice')
            if base and base > 0:
                curr = finding.get('currencyCode', currency_code)
                debug_log.append(f"base={base}|raw={finding.get('raw_base')}✓script")
                full_debug = "|".join(debug_log)
                print(f"[PSN v2.2 Script {country}] {title}: {base} {curr} (MSRP)")
                return PriceData("PlayStation", title, country, curr, base, None, None, "MSRP", "script_hunt", full_debug)
    
    # METHOD 3: Fallback to JSON-LD (will have sale prices)
    t2, price2, curr2 = parse_json_ld(html, currency_code)
    if price2 is not None and price2 > 0:
        debug_log.append("json_ld_fallback")
        full_debug = "|".join(debug_log)
        print(f"[PSN v2.2 JSON-LD {country}] {title}: {price2} {curr2 or currency_code} (fallback)")
        return PriceData("PlayStation", title, country, curr2 or currency_code, price2, None, None, "Current", "json_ld", full_debug)
    
    # All methods failed
    debug_log.append("all_methods_failed")
    full_debug = "|".join(debug_log)
    raise Exception(f"No price found: {full_debug}")

def fetch_ps_price(product_id: str, country: str, title: str) -> Optional[PriceData]:
    """v2.2: PlayStation price fetcher with RETRY LOGIC and DECIMAL CONVERSION"""
    if country not in PS_MARKETS:
        return None
    
    currency_code = PLATFORM_CURRENCIES["PlayStation"].get(country, "USD")
    
    try:
        # Wrap the fetch attempt with retry logic
        result = retry_with_backoff(
            lambda: fetch_ps_price_attempt(product_id, country, title, currency_code),
            max_retries=3,
            initial_delay=1.0
        )
        return result
    except Exception as e:
        # All retries failed
        debug_info = f"all_retries_failed|{str(e)[:100]}"
        print(f"[PSN v2.2 {country}] {title}: FAILED after retries - {debug_info}")
        return PriceData("PlayStation", title, country, currency_code, None, None, None, "N/A", None, debug_info)

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

st.title("🎮 Unified Multi-Platform Game Pricing Tool v2.2")
st.caption("✨ NEW: Smart decimal conversion (7999→79.99) + Retry logic with exponential backoff!")

if DEBUG_MODE:
    st.info("🚀 **v2.2 Enhancements:** Decimal conversion for EUR prices + 3-retry system + Better price parsing")

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
        st.caption("✨ PlayStation v2.2: Smart decimal conversion + 3-attempt retry logic")
        
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
                st.markdown("**📊 v2.2 Smart Conversion Results:**")
                
                # Price Type breakdown
                price_type_counts = ps_df['Price Type'].value_counts()
                st.write("**Price Types:**")
                st.write(price_type_counts)
                
                # Source breakdown
                source_counts = ps_df['Source'].value_counts()
                st.write("**Sources:**")
                st.write(source_counts)
                
                # MSRP vs Sale count
                msrp_count = (ps_df['Price Type'] == 'MSRP').sum()
                sale_count = (ps_df['Price Type'] == 'Sale Price').sum()
                current_count = (ps_df['Price Type'] == 'Current').sum()
                na_count = (ps_df['Price Type'] == 'N/A').sum()
                
                col_a, col_b, col_c, col_d = st.columns(4)
                with col_a:
                    st.metric("✅ MSRP", msrp_count)
                with col_b:
                    st.metric("⚠️ Sale", sale_count)
                with col_c:
                    st.metric("📊 Current", current_count)
                with col_d:
                    st.metric("❌ Failed", na_count)
                
                if msrp_count > 0:
                    st.success(f"🎉 v2.2 successfully found {msrp_count} MSRP prices with smart decimal conversion!")
                elif current_count > 0:
                    st.warning(f"⚠️ Found {current_count} prices via JSON-LD fallback (may be sale prices)")
                else:
                    st.error("❌ Price extraction failed - may need manual inspection")
                
                st.caption("📝 Check 'Debug Info' for conversion details (raw→converted) and 'Source' for extraction method")
            
            st.download_button("⬇️ Download PlayStation CSV", ps_df.to_csv(index=False).encode("utf-8"),
                             "playstation_prices.csv", "text/csv")
