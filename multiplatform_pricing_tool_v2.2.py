# multiplatform_pricing_tool_v2.2.py
# FIXES: Decimal conversion (7999 → 79.99) + Retry logic for connection errors
# - Converts cent values to proper decimals
# - Retries failed requests up to 3 times with backoff
# - Increased timeout to reduce connection failures
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

def _num(x: Any) -> Optional[float]:
    """
    Convert PlayStation's prices to numbers with smart decimal handling
    "$79.99" → 79.99
    "7999" (cents) → 79.99
    """
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            val = float(x)
            # Smart decimal conversion: if >= 100 and no decimal, likely cents
            if val >= 100 and val == int(val):
                return round(val / 100, 2)
            return val
        
        s = str(x).strip()
        s = s.replace("$", "").replace("€", "").replace("£", "").replace("¥", "")
        s = s.replace("₹", "").replace("R$", "").replace(",", "").strip()
        
        if not s:
            return None
        
        val = float(s)
        
        # Smart decimal conversion for values like "7999" (should be 79.99)
        # Only apply if >= 100 and has no decimal point in original string
        if val >= 100 and val == int(val) and '.' not in str(x):
            return round(val / 100, 2)
            
        return val
    except Exception:
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
# PLAYSTATION - v2.2 WITH DECIMAL FIX + RETRY LOGIC
# ============================================================================

def extract_ps_product_id(input_str: str) -> Optional[str]:
    input_str = input_str.strip()
    if not input_str.startswith("http"):
        return input_str
    match = re.search(r'/product/([^/?#]+)', input_str)
    if match:
        return match.group(1)
    return None

def hunt_prices_in_html(html: str) -> List[Dict[str, Any]]:
    """Aggressively search entire HTML for price patterns"""
    findings = []
    
    # Pattern for JSON objects containing basePrice
    json_pattern = r'\{[^}]*basePrice[^}]*\}'
    json_matches = re.findall(json_pattern, html, re.IGNORECASE)
    
    for match in json_matches:
        try:
            base_search = re.search(r'basePrice["\s:]+(["\$€£¥₹R\s]*)?([\d,]+\.?\d{0,2})', match)
            disc_search = re.search(r'discountedPrice["\s:]+(["\$€£¥₹R\s]*)?([\d,]+\.?\d{0,2})', match)
            curr_search = re.search(r'currencyCode["\s:]+["\']*([A-Z]{3})', match)
            
            if base_search or disc_search:
                finding = {
                    'basePrice': base_search.group(2) if base_search else None,
                    'discountedPrice': disc_search.group(2) if disc_search else None,
                    'currencyCode': curr_search.group(1) if curr_search else None,
                    'source': 'regex_json_object'
                }
                findings.append(finding)
        except Exception:
            continue
    
    if findings:
        return findings
    
    # Fallback: separate pattern matching
    base_pattern = r'basePrice["\s:]+(["\$€£¥₹R\s]*)([\d,]+\.?\d{0,2})'
    disc_pattern = r'discountedPrice["\s:]+(["\$€£¥₹R\s]*)([\d,]+\.?\d{0,2})'
    
    base_matches = re.findall(base_pattern, html, re.IGNORECASE)
    disc_matches = re.findall(disc_pattern, html, re.IGNORECASE)
    
    if base_matches or disc_matches:
        finding = {
            'basePrice': base_matches[0][1] if base_matches else None,
            'discountedPrice': disc_matches[0][1] if disc_matches else None,
            'currencyCode': None,
            'source': 'regex_separate'
        }
        findings.append(finding)
    
    return findings

def search_all_scripts_for_prices(html: str) -> List[Dict[str, Any]]:
    """Search ALL script tags for price data"""
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script")
    
    all_findings = []
    for script in scripts:
        if script.string:
            findings = hunt_prices_in_html(script.string)
            all_findings.extend(findings)
    
    return all_findings

def parse_json_ld(html: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
    """Parse JSON-LD structured data (fallback)"""
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
                    high_price = _num(offers.get("highPrice"))
                    if high_price and high_price > 0:
                        currency = offers.get("priceCurrency")
                        return title, high_price, currency
                    price = _num(offers.get("price"))
                    currency = offers.get("priceCurrency")
                    if price is not None and price > 0:
                        return title, price, currency
                
                elif isinstance(offers, list):
                    for off in offers:
                        if isinstance(off, dict):
                            high_price = _num(off.get("highPrice"))
                            if high_price and high_price > 0:
                                currency = off.get("priceCurrency")
                                return title, high_price, currency
                            price = _num(off.get("price"))
                            currency = off.get("priceCurrency")
                            if price is not None and price > 0:
                                return title, price, currency
    
    return None, None, None

def fetch_ps_price_with_retry(product_id: str, country: str, title: str, max_retries: int = 3) -> Optional[PriceData