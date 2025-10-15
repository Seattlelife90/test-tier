# multiplatform_pricing_tool_v2.0.py
# REVOLUTIONARY: Direct PlayStation GraphQL API integration
# - Bypasses HTML scraping for PlayStation
# - Calls the same GraphQL API that PlayStation's website uses
# - Gets complete price object with basePrice (MSRP) and discountedPrice
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
    page_title="Unified Game Pricing Tool v2.0",
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
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
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
    """Convert PlayStation's string prices to numbers: "$79.99" → 79.99"""
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        s = s.replace("$", "").replace("€", "").replace("£", "").replace("¥", "")
        s = s.replace("₹", "").replace("R$", "").replace(",", "").strip()
        if not s:
            return None
        return float(s)
    except Exception:
        return None

# ============================================================================
# STEAM (Unchanged from v1.9)
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
# XBOX (Unchanged from v1.9)
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
# PLAYSTATION - v2.0 GRAPHQL API APPROACH
# ============================================================================

def extract_ps_product_id(input_str: str) -> Optional[str]:
    input_str = input_str.strip()
    if not input_str.startswith("http"):
        return input_str
    match = re.search(r'/product/([^/?#]+)', input_str)
    if match:
        return match.group(1)
    return None

def fetch_ps_price_graphql(product_id: str, country: str, title: str) -> Optional[PriceData]:
    """
    v2.0 Revolutionary approach: Call PlayStation's GraphQL API directly
    This is the same API the website uses to fetch pricing data
    """
    if country not in PS_MARKETS:
        return None
    
    locale = PS_MARKETS[country]
    currency_code = PLATFORM_CURRENCIES["PlayStation"].get(country, "USD")
    
    # PlayStation's GraphQL endpoint (discovered from network traffic)
    graphql_url = "https://web-commerce-anywhere.playstation.com/"
    
    # GraphQL query structure (based on network inspection)
    graphql_payload = {
        "operationName": "queryRetrieveTelemetryDataPDPConc",
        "variables": {
            "productId": product_id,
            "country": country,
            "language": locale.split("-")[0]
        },
        "query": """
            query queryRetrieveTelemetryDataPDPConc($productId: String!) {
                product(id: $productId) {
                    id
                    name
                    price {
                        basePrice
                        discountedPrice
                        currencyCode
                        campaignId
                        applicability
                    }
                }
            }
        """
    }
    
    headers = dict(PS_HEADERS)
    headers["Origin"] = "https://store.playstation.com"
    headers["Referer"] = f"https://store.playstation.com/{locale}/product/{product_id}"
    
    debug_log = []
    
    try:
        # Make GraphQL API call
        resp = requests.post(graphql_url, json=graphql_payload, headers=headers, timeout=30)
        
        if resp.status_code != 200:
            debug_log.append(f"graphql_http_{resp.status_code}")
            return PriceData("PlayStation", title, country, currency_code, None, None, None, "N/A", "graphql_api", "|".join(debug_log))
        
        data = resp.json()
        debug_log.append("graphql_ok")
        
        # Extract price from GraphQL response
        if "data" in data and "product" in data["data"]:
            product_data = data["data"]["product"]
            price_obj = product_data.get("price", {})
            
            if not price_obj:
                debug_log.append("no_price_object")
                return PriceData("PlayStation", title, country, currency_code, None, None, None, "N/A", "graphql_api", "|".join(debug_log))
            
            # Extract prices using correct nomenclature
            base_price_str = price_obj.get("basePrice")
            disc_price_str = price_obj.get("discountedPrice")
            currency = price_obj.get("currencyCode", currency_code)
            
            debug_log.append(f"basePrice={base_price_str}")
            debug_log.append(f"discountedPrice={disc_price_str}")
            
            # PRIORITY: Use basePrice (MSRP) if available
            base_price = _num(base_price_str)
            if base_price and base_price > 0:
                debug_log.append("✓used_basePrice_MSRP")
                full_debug = "|".join(debug_log)
                print(f"[PSN GraphQL {country}] {title}: {base_price} {currency} (MSRP)")
                return PriceData("PlayStation", title, country, currency, base_price, None, None, "MSRP", "graphql_api", full_debug)
            
            # Fallback: Use discountedPrice if basePrice missing
            disc_price = _num(disc_price_str)
            if disc_price and disc_price > 0:
                debug_log.append("⚠used_discountedPrice_NO_BASE")
                full_debug = "|".join(debug_log)
                print(f"[PSN GraphQL {country}] {title}: {disc_price} {currency} (Sale - no base)")
                return PriceData("PlayStation", title, country, currency, disc_price, None, None, "Sale Price", "graphql_api", full_debug)
            
            debug_log.append("no_valid_prices")
        else:
            debug_log.append("no_product_data")
        
        full_debug = "|".join(debug_log)
        print(f"[PSN GraphQL {country}] {title}: FAILED - {full_debug}")
        return PriceData("PlayStation", title, country, currency_code, None, None, None, "N/A", "graphql_api", full_debug)
                
    except Exception as e:
        debug_log.append(f"exception:{str(e)[:50]}")
        full_debug = "|".join(debug_log)
        print(f"[PSN GraphQL {country}] {title}: ERROR - {full_debug}")
        return PriceData("PlayStation", title, country, currency_code, None, None, None, "N/A", "graphql_api", full_debug)

# Alias for compatibility
fetch_ps_price = fetch_ps_price_graphql

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

st.title("🎮 Unified Multi-Platform Game Pricing Tool v2.0")
st.caption("🚀 REVOLUTIONARY: Direct PlayStation GraphQL API - Gets MSRP directly from the same API the website uses!")

if DEBUG_MODE:
    st.info("⚡ **v2.0 Game Changer:** PlayStation now uses GraphQL API instead of HTML scraping. Should get basePrice (MSRP) correctly!")

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
        st.caption("⚡ PlayStation v2.0: Using GraphQL API for direct MSRP access")
        
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
                st.markdown("**📊 v2.0 GraphQL API Results:**")
                
                # Price Type breakdown
                price_type_counts = ps_df['Price Type'].value_counts()
                st.write("**Price Types:**")
                st.write(price_type_counts)
                
                # MSRP vs Sale count
                msrp_count = (ps_df['Price Type'] == 'MSRP').sum()
                sale_count = (ps_df['Price Type'] == 'Sale Price').sum()
                na_count = (ps_df['Price Type'] == 'N/A').sum()
                
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("✅ MSRP Prices", msrp_count)
                with col_b:
                    st.metric("⚠️ Sale Prices", sale_count)
                with col_c:
                    st.metric("❌ Failed", na_count)
                
                if msrp_count > 0:
                    st.success(f"🎉 GraphQL API successfully retrieved {msrp_count} MSRP prices!")
                else:
                    st.warning("⚠️ No MSRP prices found - GraphQL API may need adjustment")
                
                st.caption("📝 Check 'Debug Info' column for detailed API response analysis")
            
            st.download_button("⬇️ Download PlayStation CSV", ps_df.to_csv(index=False).encode("utf-8"),
                             "playstation_prices.csv", "text/csv")