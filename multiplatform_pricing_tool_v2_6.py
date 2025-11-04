# multiplatform_pricing_tool_v2.6.py
# MAJOR UPDATE - COMPETITIVE INTELLIGENCE SYSTEM:
# - ✅ TIER SYSTEM: AAA, AA, Indie with predefined comp sets
# - ✅ EDITABLE COMP SETS: Add/remove games, adjust scale factors & weights
# - ✅ SCALE FACTORS: Adjust competitor prices to target price point
# - ✅ WEIGHTING: Control influence of each game (must sum to 100%)
# - ✅ RECOMMENDATIONS: Weighted average pricing per platform/country
# - ✅ PROGRESS BAR: Real-time tracking
# - ✅ USD CONVERSION: Working exchange rates

import json
import re
import time
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st

# ============================================================================
# CONFIGURATION
# ============================================================================

DEBUG_MODE = True

st.set_page_config(
    page_title="Game Pricing Recommendation Tool v2.6",
    page_icon="🎮",
    layout="wide"
)

# ============================================================================
# PREDEFINED COMPETITIVE SETS
# ============================================================================

DEFAULT_TIERS = {
    "AAA Tier": {
        "steam": [
            {"title": "Black Myth: Wukong", "id": "2358720", "scale": 1.0, "weight": 16.67},
            {"title": "Helldivers 2", "id": "553850", "scale": 1.0, "weight": 16.67},
            {"title": "A Plague Tale: Requiem", "id": "1182900", "scale": 1.0, "weight": 16.67},
            {"title": "Remnant 2", "id": "1282100", "scale": 1.0, "weight": 16.67},
            {"title": "Stellar Blade", "id": "3489700", "scale": 1.0, "weight": 16.67},
            {"title": "Clair Obscur: Expedition 33", "id": "1903340", "scale": 1.0, "weight": 16.65},
        ],
        "xbox": [
            {"title": "Black Myth: Wukong", "id": "9NWQ1Q1F80C9", "scale": 1.0, "weight": 16.67},
            {"title": "Helldivers 2", "id": "9NDWGPM8GMQV", "scale": 1.0, "weight": 16.67},
            {"title": "A Plague Tale: Requiem", "id": "9nd0jxlb184t", "scale": 1.0, "weight": 16.67},
            {"title": "Remnant 2", "id": "9P2P1KQZKM5Q", "scale": 1.0, "weight": 16.67},
            {"title": "Stellar Blade", "id": "9npp8k6gzghr", "scale": 1.0, "weight": 16.67},
            {"title": "Clair Obscur: Expedition 33", "id": "9P92762M4GQU", "scale": 1.0, "weight": 16.65},
        ],
        "playstation": [
            {"title": "Black Myth: Wukong", "id": "HP6545-PPSA23206_00-GAME000000000000", "scale": 1.0, "weight": 16.67},
            {"title": "Helldivers 2", "id": "PPSA16127_00-HELLDIVERS2TRIAL", "scale": 1.0, "weight": 16.67},
            {"title": "A Plague Tale: Requiem", "id": "UP4133-PPSA05366_00-APLAQUEOUTBURST0", "scale": 1.0, "weight": 16.67},
            {"title": "Remnant 2", "id": "UP4040-PPSA10199_00-remnan2x-ashne00", "scale": 1.0, "weight": 16.67},
            {"title": "Stellar Blade", "id": "10006891", "scale": 1.0, "weight": 16.67},
            {"title": "Clair Obscur: Expedition 33", "id": "10006904", "scale": 1.0, "weight": 16.65},
        ]
    },
    "AA Tier": {
        "steam": [
            {"title": "Kena: Bridge of Spirits", "id": "1954200", "scale": 1.0, "weight": 20.0},
            {"title": "A Plague Tale: Innocence", "id": "752590", "scale": 1.0, "weight": 20.0},
            {"title": "Grounded", "id": "962130", "scale": 1.0, "weight": 20.0},
            {"title": "The Pathless", "id": "1280780", "scale": 1.0, "weight": 20.0},
            {"title": "Immortals Fenyx Rising", "id": "2221920", "scale": 1.0, "weight": 20.0},
        ],
        "xbox": [
            {"title": "Kena: Bridge of Spirits", "id": "9N1W76N0FC0B", "scale": 1.0, "weight": 20.0},
            {"title": "A Plague Tale: Innocence", "id": "BNNRKT8DTXPR", "scale": 1.0, "weight": 20.0},
            {"title": "Grounded", "id": "9NF3B94V2NRL", "scale": 1.0, "weight": 20.0},
            {"title": "The Pathless", "id": "9P5TQCD72TKR", "scale": 1.0, "weight": 20.0},
            {"title": "Immortals Fenyx Rising", "id": "9PGTW51Z5MDV", "scale": 1.0, "weight": 20.0},
        ],
        "playstation": [
            {"title": "Kena: Bridge of Spirits", "id": "UP2225-PPSA02862_00-KENABASEGAMEPS5A", "scale": 1.0, "weight": 20.0},
            {"title": "A Plague Tale: Innocence", "id": "UP4133-CUSA11032_00-APLAGUETALEGAME0", "scale": 1.0, "weight": 20.0},
            {"title": "Grounded", "id": "UP4412-PPSA03787_00-5518013010085695", "scale": 1.0, "weight": 20.0},
            {"title": "The Pathless", "id": "UP2470-PPSA01928_00-THEPATHLESS00000", "scale": 1.0, "weight": 20.0},
            {"title": "Immortals Fenyx Rising", "id": "UP0001-PPSA01534_00-ORPHEUSGAMEFULL0", "scale": 1.0, "weight": 20.0},
        ]
    },
    "Indie Tier": {
        "steam": [
            {"title": "Hollow Knight: Silksong", "id": "1030300", "scale": 1.0, "weight": 14.29},
            {"title": "Hades", "id": "1145360", "scale": 1.0, "weight": 14.29},
            {"title": "Hades II", "id": "1145350", "scale": 1.0, "weight": 14.29},
            {"title": "Blue Prince", "id": "1569590", "scale": 1.0, "weight": 14.29},
            {"title": "Split Fiction", "id": "2001120", "scale": 1.0, "weight": 14.29},
            {"title": "Animal Well", "id": "813230", "scale": 1.0, "weight": 14.29},
            {"title": "UFO 50", "id": "1514570", "scale": 1.0, "weight": 14.26},
        ],
        "xbox": [
            {"title": "Hollow Knight: Silksong", "id": "9n116v0589hb", "scale": 1.0, "weight": 14.29},
            {"title": "Hades", "id": "9PFT5B9N68T2", "scale": 1.0, "weight": 14.29},
            {"title": "Hades II", "id": "9PCZGQP5K6BM", "scale": 1.0, "weight": 14.29},
            {"title": "Blue Prince", "id": "9prfrrq569g", "scale": 1.0, "weight": 14.29},
            {"title": "Split Fiction", "id": "9n1wxd1r8d", "scale": 1.0, "weight": 14.29},
            {"title": "Animal Well", "id": "9NFPLMC3S42NV", "scale": 1.0, "weight": 14.29},
            {"title": "UFO 50", "id": "9p3stg4kj6n", "scale": 1.0, "weight": 14.26},
        ],
        "playstation": [
            {"title": "Hollow Knight: Silksong", "id": "10003908", "scale": 1.0, "weight": 14.29},
            {"title": "Hades", "id": "10002368", "scale": 1.0, "weight": 14.29},
            {"title": "Hades II", "id": "10008036", "scale": 1.0, "weight": 14.29},
            {"title": "Blue Prince", "id": "UP8015-PPSA25099_00-BLUEPRINCE000000", "scale": 1.0, "weight": 14.29},
            {"title": "Split Fiction", "id": "10008768", "scale": 1.0, "weight": 14.29},
            {"title": "Animal Well", "id": "10008402", "scale": 1.0, "weight": 14.29},
            {"title": "UFO 50", "id": "10008402", "scale": 1.0, "weight": 14.26},
        ]
    }
}

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
    "CO": "CO", "PE": "PE", "UY": "UY", "CR": "CR", 
    "GB": "GB", "IE": "IE", "FR": "FR", "DE": "DE", "IT": "IT", "ES": "ES", 
    "PT": "PT", "NL": "NL", "BE": "BE", "AT": "AT", "CH": "CH", 
    "DK": "DK", "SE": "SE", "NO": "NO", "FI": "FI", "PL": "PL",
    "CZ": "CZ", "SK": "SK", "HU": "HU", "GR": "GR", "TR": "TR",
    "IL": "IL", "SA": "SA", "AE": "AE", "QA": "QA", "KW": "KW", 
    "JP": "JP", "KR": "KR", "TW": "TW", "HK": "HK", "SG": "SG", 
    "MY": "MY", "TH": "TH", "ID": "ID", "PH": "PH", "VN": "VN", 
    "IN": "IN", "AU": "AU", "NZ": "NZ", "KZ": "KZ", "UA": "UA", 
    "CN": "CN", "ZA": "ZA", "RU": "RU"
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
        "GB": "GBP", "IE": "EUR", "FR": "EUR", "DE": "EUR", "IT": "EUR", "ES": "EUR",
        "PT": "EUR", "NL": "EUR", "BE": "EUR", "AT": "EUR", "CH": "CHF",
        "DK": "DKK", "SE": "SEK", "NO": "NOK", "FI": "EUR", "PL": "PLN",
        "CZ": "CZK", "SK": "EUR", "HU": "HUF", "GR": "EUR", "TR": "USD",
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
        "US": "USD", "CA": "CAD", "MX": "USD", "BR": "BRL", "AR": "USD",
        "CL": "USD", "CO": "USD", "PE": "USD", "UY": "USD", "CR": "USD",
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

DECIMAL_CURRENCIES = {"EUR", "USD", "GBP", "CAD", "AUD", "NZD", "CHF", "SGD", "ZAR", "MYR", "BRL", "PLN", "SEK", "NOK", "DKK", "TRY"}

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
    scale_factor: Optional[float] = None
    weight: Optional[float] = None

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

def init_session_state():
    """Initialize session state with default tiers"""
    if "tiers" not in st.session_state:
        st.session_state.tiers = deepcopy(DEFAULT_TIERS)
    if "current_tier" not in st.session_state:
        st.session_state.current_tier = "AAA Tier"
    if "results_cache" not in st.session_state:
        st.session_state.results_cache = {}

# ============================================================================
# UTILITY FUNCTIONS (from v2.5)
# ============================================================================

def fetch_exchange_rates() -> Dict[str, float]:
    """Fetch exchange rates with proper error handling"""
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
                st.session_state["exchange_rates"] = rates
                st.session_state["rates_timestamp"] = time.time()
                return rates
    except Exception as e:
        print(f"Exchange rate fetch failed: {e}")
    
    # Fallback rates
    rates.update({
        "EUR": 0.92, "GBP": 0.79, "CAD": 1.36, "AUD": 1.52, "NZD": 1.67,
        "JPY": 149.50, "KRW": 1320.0, "CNY": 7.24, "INR": 83.12,
        "BRL": 4.97, "MXN": 17.08, "ARS": 350.0, "CLP": 910.0,
        "COP": 3950.0, "PEN": 3.73, "CRC": 510.0, "UYU": 39.0,
        "CHF": 0.88, "SEK": 10.58, "NOK": 10.78, "DKK": 6.87,
        "PLN": 4.01, "CZK": 23.15, "HUF": 363.0, "TRY": 32.0,
        "ZAR": 18.50, "ILS": 3.73, "SAR": 3.75, "AED": 3.67,
        "THB": 34.50, "MYR": 4.47, "SGD": 1.34, "HKD": 7.83,
        "TWD": 31.50, "PHP": 56.50, "IDR": 15600.0, "VND": 24500.0,
        "UAH": 37.0, "RUB": 92.0, "KZT": 450.0
    })
    
    st.session_state["exchange_rates"] = rates
    st.session_state["rates_timestamp"] = time.time()
    return rates

def convert_to_usd(amount: Optional[float], currency: str, rates: Dict[str, float]) -> Optional[float]:
    """Convert local currency to USD"""
    if amount is None or amount <= 0:
        return None
    if currency == "USD":
        return round(amount, 2)
    if currency not in rates:
        return None
    rate = rates.get(currency, 1.0)
    if rate <= 0:
        return None
    return round(amount / rate, 2)

def parse_price_string(raw_value: Any, currency: str) -> Optional[float]:
    """Parse price string with EU comma format handling"""
    try:
        if raw_value is None:
            return None
        
        original_str = str(raw_value).strip()
        s = original_str.replace("$", "").replace("€", "").replace("£", "").replace("¥", "")
        s = s.replace("₹", "").replace("R$", "").replace("R", "").replace(" ", "").strip()
        
        if not s:
            return None
        
        has_comma = ',' in s
        has_dot = '.' in s
        
        if has_comma and has_dot:
            s = s.replace(',', '')
            value = float(s)
        elif has_comma and not has_dot:
            s = s.replace(',', '.')
            value = float(s)
        elif has_dot and not has_comma:
            parts = s.split('.')
            if len(parts) == 2 and len(parts[1]) >= 3:
                s = s.replace('.', '')
                value = float(s)
            else:
                value = float(s)
        else:
            value = float(s)
        
        if value <= 0:
            return None
        
        if currency in DECIMAL_CURRENCIES:
            if value >= 1000 and '.' not in original_str and ',' not in original_str:
                value = value / 100.0
        
        return round(value, 2)
        
    except Exception:
        return None

def retry_with_backoff(func, max_retries=3, initial_delay=1.0):
    """Exponential backoff with jitter"""
    for attempt in range(max_retries):
        try:
            result = func()
            return result
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            delay = initial_delay * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(delay)
    return None

# ============================================================================
# PLATFORM FETCHERS (from v2.5 - unchanged)
# ============================================================================

def extract_steam_appid(input_str: str) -> Optional[str]:
    input_str = input_str.strip()
    if input_str.isdigit():
        return input_str
    match = re.search(r'/app/(\d+)', input_str)
    if match:
        return match.group(1)
    return None

def fetch_steam_price(appid: str, country: str, title: str, scale: float = 1.0, weight: float = 1.0) -> Optional[PriceData]:
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
            result = PriceData("Steam", title, country, currency, None, None, None, "API", "steam_api")
            result.scale_factor = scale
            result.weight = weight
            return result
        game_data = data.get("data", {})
        price_overview = game_data.get("price_overview", {})
        price_cents = price_overview.get("initial") or price_overview.get("final")
        if price_cents and isinstance(price_cents, int) and price_cents > 0:
            price = round(price_cents / 100.0, 2)
            result = PriceData("Steam", title, country, currency, price, None, None, "API", "steam_api")
            result.scale_factor = scale
            result.weight = weight
            return result
    except Exception:
        pass
    result = PriceData("Steam", title, country, currency, None, None, None, "API", "steam_api")
    result.scale_factor = scale
    result.weight = weight
    return result

def extract_xbox_store_id(input_str: str) -> Optional[str]:
    input_str = input_str.strip()
    if len(input_str) == 12 and input_str[0] == '9':
        return input_str
    match = re.search(r'/([9][A-Z0-9]{11})', input_str, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None

def fetch_xbox_price(store_id: str, country: str, title: str, scale: float = 1.0, weight: float = 1.0) -> Optional[PriceData]:
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
                            result = PriceData("Xbox", title, country, currency, float(amt), None, None, "API", "xbox_api")
                            result.scale_factor = scale
                            result.weight = weight
                            return result
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
                            result = PriceData("Xbox", title, country, currency, float(amt), None, None, "API", "xbox_api")
                            result.scale_factor = scale
                            result.weight = weight
                            return result
    except Exception:
        pass
    result = PriceData("Xbox", title, country, currency, None, None, None, "API", "xbox_api")
    result.scale_factor = scale
    result.weight = weight
    return result

def extract_ps_product_id(input_str: str) -> Optional[str]:
    input_str = input_str.strip()
    if not input_str.startswith("http"):
        return input_str
    match = re.search(r'/product/([^/?#]+)', input_str)
    if match:
        return match.group(1)
    return None

def hunt_prices_in_html(html: str, currency: str) -> List[Dict[str, Any]]:
    """Search for basePrice/discountedPrice"""
    findings = []
    
    base_pattern = r'basePrice["\s:]+(["\$€£¥₹R\s]*)([\d,.]+)'
    base_matches = re.findall(base_pattern, html, re.IGNORECASE)
    
    disc_pattern = r'discountedPrice["\s:]+(["\$€£¥₹R\s]*)([\d,.]+)'
    disc_matches = re.findall(disc_pattern, html, re.IGNORECASE)
    
    json_pattern = r'\{[^}]*basePrice[^}]*\}'
    json_matches = re.findall(json_pattern, html, re.IGNORECASE)
    
    for match in json_matches:
        try:
            base_search = re.search(r'basePrice["\s:]+(["\$€£¥₹R\s]*)([\d,.]+)', match)
            disc_search = re.search(r'discountedPrice["\s:]+(["\$€£¥₹R\s]*)([\d,.]+)', match)
            curr_search = re.search(r'currencyCode["\s:]+["\']*([A-Z]{3})', match)
            
            if base_search or disc_search:
                raw_base = base_search.group(2) if base_search else None
                raw_disc = disc_search.group(2) if disc_search else None
                detected_currency = curr_search.group(1) if curr_search else currency
                
                finding = {
                    'basePrice': parse_price_string(raw_base, detected_currency) if raw_base else None,
                    'discountedPrice': parse_price_string(raw_disc, detected_currency) if raw_disc else None,
                    'currencyCode': detected_currency,
                    'source': 'regex_json_object',
                    'raw_base': raw_base,
                    'raw_disc': raw_disc
                }
                findings.append(finding)
        except Exception:
            continue
    
    if findings:
        return findings
    
    if base_matches or disc_matches:
        raw_base = base_matches[0][1] if base_matches else None
        raw_disc = disc_matches[0][1] if disc_matches else None
        
        finding = {
            'basePrice': parse_price_string(raw_base, currency) if raw_base else None,
            'discountedPrice': parse_price_string(raw_disc, currency) if raw_disc else None,
            'currencyCode': currency,
            'source': 'regex_separate',
            'raw_base': raw_base,
            'raw_disc': raw_disc
        }
        findings.append(finding)
    
    return findings

def search_all_scripts_for_prices(html: str, currency: str) -> List[Dict[str, Any]]:
    """Search ALL script tags"""
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script")
    
    all_findings = []
    for script in scripts:
        if script.string:
            findings = hunt_prices_in_html(script.string, currency)
            all_findings.extend(findings)
    
    return all_findings

def parse_json_ld(html: str, currency: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
    """Parse JSON-LD"""
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
                    high_price = parse_price_string(offers.get("highPrice"), currency)
                    if high_price and high_price > 0:
                        detected_currency = offers.get("priceCurrency") or currency
                        return title, high_price, detected_currency
                    
                    price = parse_price_string(offers.get("price"), currency)
                    detected_currency = offers.get("priceCurrency") or currency
                    if price is not None and price > 0:
                        return title, price, detected_currency
                
                elif isinstance(offers, list):
                    for off in offers:
                        if isinstance(off, dict):
                            high_price = parse_price_string(off.get("highPrice"), currency)
                            if high_price and high_price > 0:
                                detected_currency = off.get("priceCurrency") or currency
                                return title, high_price, detected_currency
                            
                            price = parse_price_string(off.get("price"), currency)
                            detected_currency = off.get("priceCurrency") or currency
                            if price is not None and price > 0:
                                return title, price, detected_currency
    
    return None, None, None

def fetch_ps_price_attempt(product_id: str, country: str, title: str, currency_code: str) -> Optional[PriceData]:
    """Single attempt to fetch PlayStation price"""
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
    
    html_findings = hunt_prices_in_html(html, currency_code)
    if html_findings:
        debug_log.append(f"regex_found_{len(html_findings)}")
        for finding in html_findings:
            base = finding.get('basePrice')
            disc = finding.get('discountedPrice')
            curr = finding.get('currencyCode', currency_code)
            
            if base and base > 0:
                debug_log.append(f"base={base}|raw={finding.get('raw_base')}|curr={curr}")
                full_debug = "|".join(debug_log)
                return PriceData("PlayStation", title, country, curr, base, None, None, "MSRP", "regex_hunt", full_debug)
            
            if disc and disc > 0:
                debug_log.append(f"disc={disc}|raw={finding.get('raw_disc')}")
                full_debug = "|".join(debug_log)
                return PriceData("PlayStation", title, country, curr, disc, None, None, "Sale Price", "regex_hunt", full_debug)
    
    script_findings = search_all_scripts_for_prices(html, currency_code)
    if script_findings:
        debug_log.append(f"scripts_found_{len(script_findings)}")
        for finding in script_findings:
            base = finding.get('basePrice')
            if base and base > 0:
                curr = finding.get('currencyCode', currency_code)
                debug_log.append(f"base={base}|script")
                full_debug = "|".join(debug_log)
                return PriceData("PlayStation", title, country, curr, base, None, None, "MSRP", "script_hunt", full_debug)
    
    t2, price2, curr2 = parse_json_ld(html, currency_code)
    if price2 is not None and price2 > 0:
        debug_log.append("json_ld_fallback")
        full_debug = "|".join(debug_log)
        return PriceData("PlayStation", title, country, curr2 or currency_code, price2, None, None, "Current", "json_ld", full_debug)
    
    debug_log.append("all_methods_failed")
    full_debug = "|".join(debug_log)
    raise Exception(f"No price found: {full_debug}")

def fetch_ps_price(product_id: str, country: str, title: str, scale: float = 1.0, weight: float = 1.0) -> Optional[PriceData]:
    """PlayStation with retry"""
    if country not in PS_MARKETS:
        return None
    
    currency_code = PLATFORM_CURRENCIES["PlayStation"].get(country, "USD")
    
    try:
        result = retry_with_backoff(
            lambda: fetch_ps_price_attempt(product_id, country, title, currency_code),
            max_retries=3,
            initial_delay=1.0
        )
        if result:
            result.scale_factor = scale
            result.weight = weight
        return result
    except Exception as e:
        debug_info = f"all_retries_failed|{str(e)[:100]}"
        result = PriceData("PlayStation", title, country, currency_code, None, None, None, "N/A", None, debug_info)
        result.scale_factor = scale
        result.weight = weight
        return result

# ============================================================================
# ORCHESTRATION WITH PROGRESS
# ============================================================================

def pull_tier_prices(tier_name: str, max_workers: int = 20) -> Tuple[List[PriceData], List[PriceData], List[PriceData]]:
    """Pull prices for all games in a tier"""
    tier = st.session_state.tiers[tier_name]
    
    steam_games = [(g["id"], g["title"], g["scale"], g["weight"]) for g in tier["steam"]]
    xbox_games = [(g["id"], g["title"], g["scale"], g["weight"]) for g in tier["xbox"]]
    ps_games = [(g["id"], g["title"], g["scale"], g["weight"]) for g in tier["playstation"]]
    
    steam_results = []
    xbox_results = []
    ps_results = []
    
    total_tasks = (
        len(steam_games) * len(STEAM_MARKETS) +
        len(xbox_games) * len(XBOX_MARKETS) +
        len(ps_games) * len(PS_MARKETS)
    )
    
    if total_tasks == 0:
        return [], [], []
    
    progress_bar = st.progress(0)
    progress_text = st.empty()
    completed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for appid, title, scale, weight in steam_games:
            for country in STEAM_MARKETS.keys():
                futures.append((executor.submit(fetch_steam_price, appid, country, title, scale, weight), "steam"))
        for store_id, title, scale, weight in xbox_games:
            for country in XBOX_MARKETS.keys():
                futures.append((executor.submit(fetch_xbox_price, store_id, country, title, scale, weight), "xbox"))
        for product_id, title, scale, weight in ps_games:
            for country in PS_MARKETS.keys():
                futures.append((executor.submit(fetch_ps_price, product_id, country, title, scale, weight), "ps"))
        
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
            
            completed += 1
            progress = completed / total_tasks
            progress_bar.progress(progress)
            progress_text.text(f"Progress: {completed}/{total_tasks} ({progress*100:.1f}%)")
    
    progress_bar.progress(1.0)
    progress_text.text(f"✅ Complete! Processed {total_tasks} price checks")
    
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
            "% Diff vs US": r.diff_vs_us if r.diff_vs_us else None,
            "Scale Factor": r.scale_factor,
            "Weight (%)": r.weight
        }
        if DEBUG_MODE:
            row["Price Type"] = r.price_type
            row["Source"] = r.source
        df_data.append(row)
    
    df = pd.DataFrame(df_data)
    return df.sort_values(["Title", "Country"]).reset_index(drop=True)

def calculate_recommendations(results: List[PriceData], rates: Dict[str, float]) -> pd.DataFrame:
    """Calculate weighted recommendations per platform/country"""
    if not results:
        return pd.DataFrame()
    
    # Convert all prices to USD
    for r in results:
        r.price_usd = convert_to_usd(r.price, r.currency, rates)
    
    # Group by platform and country
    recommendations = []
    
    platforms = set(r.platform for r in results)
    countries = set(r.country for r in results)
    
    for platform in platforms:
        for country in countries:
            # Get all results for this platform/country
            country_results = [r for r in results if r.platform == platform and r.country == country and r.price_usd is not None]
            
            if not country_results:
                continue
            
            # Calculate weighted average
            weighted_sum = 0
            weight_sum = 0
            
            for r in country_results:
                if r.price_usd and r.scale_factor and r.weight:
                    scaled_price = r.price_usd * r.scale_factor
                    weighted_sum += scaled_price * r.weight
                    weight_sum += r.weight
            
            if weight_sum > 0:
                recommended_usd = weighted_sum / weight_sum
                
                # Convert back to local currency
                currency = country_results[0].currency
                if currency == "USD":
                    recommended_local = recommended_usd
                elif currency in rates:
                    rate = rates[currency]
                    recommended_local = recommended_usd * rate
                else:
                    recommended_local = None
                
                recommendations.append({
                    "Platform": platform,
                    "Country": COUNTRY_NAMES.get(country, country),
                    "Currency": currency,
                    "Recommended Price (USD)": round(recommended_usd, 2),
                    "Recommended Price (Local)": round(recommended_local, 2) if recommended_local else None,
                    "Num Games": len(country_results)
                })
    
    df = pd.DataFrame(recommendations)
    if not df.empty:
        df = df.sort_values(["Platform", "Country"]).reset_index(drop=True)
    return df

# ============================================================================
# STREAMLIT UI
# ============================================================================

init_session_state()

st.title("🎮 Game Pricing Recommendation Tool v2.6")
st.caption("🎯 Competitive Intelligence System: Tier-based pricing with scale factors & weighting")

st.markdown("---")

# Tier Selection
col1, col2 = st.columns([3, 1])
with col1:
    selected_tier = st.selectbox(
        "Select Tier:",
        options=list(DEFAULT_TIERS.keys()),
        index=list(DEFAULT_TIERS.keys()).index(st.session_state.current_tier)
    )
    st.session_state.current_tier = selected_tier

with col2:
    if st.button("🔄 Reset to Defaults", help="Reset current tier to default games"):
        st.session_state.tiers[selected_tier] = deepcopy(DEFAULT_TIERS[selected_tier])
        st.rerun()

st.markdown("---")

# Editable Competitive Set
st.subheader(f"📋 {selected_tier} Competitive Set")

tier_data = st.session_state.tiers[selected_tier]

# Calculate total weights
steam_weight_total = sum(g["weight"] for g in tier_data["steam"])
xbox_weight_total = sum(g["weight"] for g in tier_data["xbox"])
ps_weight_total = sum(g["weight"] for g in tier_data["playstation"])

# Show weight status
col_s, col_x, col_p = st.columns(3)
with col_s:
    if abs(steam_weight_total - 100.0) < 0.1:
        st.success(f"✅ Steam Weight: {steam_weight_total:.1f}%")
    else:
        st.error(f"❌ Steam Weight: {steam_weight_total:.1f}% (Must = 100%)")
with col_x:
    if abs(xbox_weight_total - 100.0) < 0.1:
        st.success(f"✅ Xbox Weight: {xbox_weight_total:.1f}%")
    else:
        st.error(f"❌ Xbox Weight: {xbox_weight_total:.1f}% (Must = 100%)")
with col_p:
    if abs(ps_weight_total - 100.0) < 0.1:
        st.success(f"✅ PlayStation Weight: {ps_weight_total:.1f}%")
    else:
        st.error(f"❌ PlayStation Weight: {ps_weight_total:.1f}% (Must = 100%)")

# Display editable tables for each platform
tab1, tab2, tab3 = st.tabs(["🎮 Steam", "🎮 Xbox", "🎮 PlayStation"])

with tab1:
    st.markdown("**Steam Games:**")
    for idx, game in enumerate(tier_data["steam"]):
        col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 1, 0.5])
        with col1:
            st.text(f"☑ {game['title']}")
        with col2:
            st.text(f"ID: {game['id']}")
        with col3:
            new_scale = st.number_input(f"Scale##steam{idx}", value=game["scale"], min_value=0.1, max_value=5.0, step=0.05, key=f"steam_scale_{idx}", label_visibility="collapsed")
            game["scale"] = new_scale
        with col4:
            new_weight = st.number_input(f"Weight##steam{idx}", value=game["weight"], min_value=0.0, max_value=100.0, step=0.1, key=f"steam_weight_{idx}", label_visibility="collapsed")
            game["weight"] = new_weight
        with col5:
            if st.button("🗑️", key=f"del_steam_{idx}", help="Delete game"):
                tier_data["steam"].pop(idx)
                st.rerun()

with tab2:
    st.markdown("**Xbox Games:**")
    for idx, game in enumerate(tier_data["xbox"]):
        col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 1, 0.5])
        with col1:
            st.text(f"☑ {game['title']}")
        with col2:
            st.text(f"ID: {game['id']}")
        with col3:
            new_scale = st.number_input(f"Scale##xbox{idx}", value=game["scale"], min_value=0.1, max_value=5.0, step=0.05, key=f"xbox_scale_{idx}", label_visibility="collapsed")
            game["scale"] = new_scale
        with col4:
            new_weight = st.number_input(f"Weight##xbox{idx}", value=game["weight"], min_value=0.0, max_value=100.0, step=0.1, key=f"xbox_weight_{idx}", label_visibility="collapsed")
            game["weight"] = new_weight
        with col5:
            if st.button("🗑️", key=f"del_xbox_{idx}", help="Delete game"):
                tier_data["xbox"].pop(idx)
                st.rerun()

with tab3:
    st.markdown("**PlayStation Games:**")
    for idx, game in enumerate(tier_data["playstation"]):
        col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 1, 0.5])
        with col1:
            st.text(f"☑ {game['title']}")
        with col2:
            st.text(f"ID: {game['id']}")
        with col3:
            new_scale = st.number_input(f"Scale##ps{idx}", value=game["scale"], min_value=0.1, max_value=5.0, step=0.05, key=f"ps_scale_{idx}", label_visibility="collapsed")
            game["scale"] = new_scale
        with col4:
            new_weight = st.number_input(f"Weight##ps{idx}", value=game["weight"], min_value=0.0, max_value=100.0, step=0.1, key=f"ps_weight_{idx}", label_visibility="collapsed")
            game["weight"] = new_weight
        with col5:
            if st.button("🗑️", key=f"del_ps_{idx}", help="Delete game"):
                tier_data["playstation"].pop(idx)
                st.rerun()

st.markdown("---")

# Pull Prices Button
weights_valid = (
    abs(steam_weight_total - 100.0) < 0.1 and
    abs(xbox_weight_total - 100.0) < 0.1 and
    abs(ps_weight_total - 100.0) < 0.1
)

if not weights_valid:
    st.warning("⚠️ Weights must sum to 100% for each platform before pulling prices!")

if st.button("🚀 Pull Prices", type="primary", use_container_width=True, disabled=not weights_valid):
    st.info(f"🎮 Pulling prices for {selected_tier}...")
    
    rates = fetch_exchange_rates()
    
    with st.spinner("Fetching prices across all regions..."):
        steam_results, xbox_results, ps_results = pull_tier_prices(selected_tier)
    
    st.session_state.results_cache = {
        "tier": selected_tier,
        "steam": steam_results,
        "xbox": xbox_results,
        "playstation": ps_results,
        "rates": rates
    }
    
    st.success(f"✅ Price pull complete!")

# Display Results
if "results_cache" in st.session_state and st.session_state.results_cache:
    cache = st.session_state.results_cache
    
    if cache.get("tier") == selected_tier:
        steam_results = cache.get("steam", [])
        xbox_results = cache.get("xbox", [])
        ps_results = cache.get("playstation", [])
        rates = cache.get("rates", {})
        
        result_tabs = st.tabs(["📊 Steam Prices", "📊 Xbox Prices", "📊 PlayStation Prices", "🎯 Recommendations"])
        
        with result_tabs[0]:
            if steam_results:
                steam_df = process_results(steam_results, rates)
                st.dataframe(steam_df, use_container_width=True, height=400)
                st.download_button("⬇️ Download Steam CSV", steam_df.to_csv(index=False).encode("utf-8"),
                                 f"steam_{selected_tier.lower().replace(' ', '_')}.csv", "text/csv")
        
        with result_tabs[1]:
            if xbox_results:
                xbox_df = process_results(xbox_results, rates)
                st.dataframe(xbox_df, use_container_width=True, height=400)
                st.download_button("⬇️ Download Xbox CSV", xbox_df.to_csv(index=False).encode("utf-8"),
                                 f"xbox_{selected_tier.lower().replace(' ', '_')}.csv", "text/csv")
        
        with result_tabs[2]:
            if ps_results:
                ps_df = process_results(ps_results, rates)
                st.dataframe(ps_df, use_container_width=True, height=400)
                st.download_button("⬇️ Download PlayStation CSV", ps_df.to_csv(index=False).encode("utf-8"),
                                 f"playstation_{selected_tier.lower().replace(' ', '_')}.csv", "text/csv")
        
        with result_tabs[3]:
            st.markdown("### 🎯 Pricing Recommendations")
            st.caption("Weighted average prices per platform/country (using scale factors & weights)")
            
            all_results = steam_results + xbox_results + ps_results
            
            if all_results:
                recs_df = calculate_recommendations(all_results, rates)
                
                if not recs_df.empty:
                    st.dataframe(recs_df, use_container_width=True, height=600)
                    st.download_button("⬇️ Download Recommendations CSV", recs_df.to_csv(index=False).encode("utf-8"),
                                     f"recommendations_{selected_tier.lower().replace(' ', '_')}.csv", "text/csv")
                else:
                    st.warning("No recommendations generated - insufficient price data")
            else:
                st.info("Pull prices first to generate recommendations")
