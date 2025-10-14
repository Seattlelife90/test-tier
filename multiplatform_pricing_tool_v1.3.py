# streamlit_app.py
# Unified Multi-Platform Game Pricing Tool
# Pulls prices from Steam, Xbox, and PlayStation stores across all regions
# 
# To use:
# 1. Download this file
# 2. Drag it into your GitHub repository (replace your old streamlit_app.py)
# 3. Streamlit will automatically detect and deploy it

import json
import re
import time
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st

# ============================================================================
# CONFIGURATION & MAPPINGS
# ============================================================================

st.set_page_config(
    page_title="Unified Game Pricing Tool",
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
        "US": "USD", "CA": "CAD", "MX": "USD", "BR": "BRL", "AR": "USD",
        "CL": "USD", "CO": "USD", "PE": "USD", "UY": "USD", "CR": "USD",
        "GB": "GBP", "IE": "EUR", "FR": "EUR", "DE": "EUR", "IT": "EUR",
        "ES": "EUR", "PT": "EUR", "NL": "EUR", "BE": "EUR", "AT": "EUR",
        "CH": "CHF", "DK": "DKK", "SE": "SEK", "NO": "NOK", "FI": "EUR",
        "PL": "PLN", "CZ": "CZK", "SK": "USD", "HU": "HUF", "GR": "EUR",
        "TR": "TRY", "IL": "ILS", "SA": "USD", "AE": "USD", "JP": "JPY",
        "KR": "KRW", "TW": "TWD", "HK": "HKD", "SG": "SGD", "MY": "MYR",
        "TH": "THB", "ID": "IDR", "PH": "PHP", "VN": "USD", "IN": "INR",
        "AU": "AUD", "NZ": "NZD", "ZA": "ZAR", "UA": "UAH"
    }
}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
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

# ============================================================================
# CURRENCY CONVERSION
# ============================================================================

def fetch_exchange_rates() -> Dict[str, float]:
    """Fetch current exchange rates with USD as base"""
    if "exchange_rates" in st.session_state:
        cache_time = st.session_state.get("rates_timestamp", 0)
        if time.time() - cache_time < 7200:  # 2 hour cache
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
            return PriceData("Steam", title, country, currency, None, None, None)
        
        game_data = data.get("data", {})
        price_overview = game_data.get("price_overview", {})
        
        price_cents = price_overview.get("initial") or price_overview.get("final")
        if price_cents and isinstance(price_cents, int) and price_cents > 0:
            price = round(price_cents / 100.0, 2)
            return PriceData("Steam", title, country, currency, price, None, None)
        
    except Exception:
        pass
    
    return PriceData("Steam", title, country, currency, None, None, None)

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
    
    # Try StorEdge SDK API (like your working tool)
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
                            return PriceData("Xbox", title, country, currency, float(amt), None, None)
    except Exception:
        pass
    
    # Fallback to DisplayCatalog
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
                            return PriceData("Xbox", title, country, currency, float(amt), None, None)
    except Exception:
        pass
    
    return PriceData("Xbox", title, country, currency, None, None, None)

# ============================================================================
# PLAYSTATION PRICE PULLER
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

def parse_ps_next_json(html: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
    """Parse PlayStation Next.js JSON data"""
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not script or not script.string:
        return None, None, None
    
    try:
        data = json.loads(script.string)
        props = data.get("props", {}).get("pageProps", {})
        product = props.get("product") or props.get("pageData") or props.get("telemetryData") or {}
        
        title = product.get("name") or product.get("title") or props.get("title")
        
        # Try multiple price locations
        price = None
        currency = None
        
        # Location 1: Direct product.price
        p = product.get("price") if isinstance(product, dict) else None
        if isinstance(p, dict):
            price = p.get("basePrice") or p.get("discountedPrice") or p.get("finalPrice") or p.get("current") or p.get("value")
            currency = p.get("currency")
        
        # Location 2: defaultSku.price
        if price is None:
            default_sku = product.get("defaultSku") if isinstance(product, dict) else None
            if isinstance(default_sku, dict):
                p2 = default_sku.get("price") if isinstance(default_sku.get("price"), dict) else None
                if p2:
                    price = p2.get("basePrice") or p2.get("discountedPrice") or p2.get("finalPrice") or p2.get("current") or p2.get("value")
                    currency = p2.get("currency") or currency
        
        # Location 3: skus array
        if price is None:
            skus = product.get("skus") if isinstance(product, dict) else None
            if isinstance(skus, list):
                for sku in skus:
                    p3 = sku.get("price") if isinstance(sku.get("price"), dict) else None
                    if p3:
                        price = p3.get("basePrice") or p3.get("discountedPrice") or p3.get("finalPrice") or p3.get("current") or p3.get("value")
                        currency = p3.get("currency") or currency
                        if price is not None:
                            break
        
        # Location 4: pageProps.price
        if price is None:
            pp = props.get("price") or props.get("store", {}).get("price")
            if isinstance(pp, dict):
                price = pp.get("basePrice") or pp.get("discountedPrice") or pp.get("finalPrice") or pp.get("current")
                currency = pp.get("currency") or currency
        
        # Convert price to float
        if price is not None:
            try:
                price = float(str(price).strip().replace(",", ""))
            except:
                price = None
        
        return title, price, currency
    except Exception:
        return None, None, None

def fetch_ps_price(product_id: str, country: str, title: str) -> Optional[PriceData]:
    """Fetch PlayStation price for a specific country"""
    if country not in PS_MARKETS:
        return None
    
    locale = PS_MARKETS[country]
    currency = PLATFORM_CURRENCIES["PlayStation"].get(country, "USD")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
    }
    
    try:
        url = f"https://store.playstation.com/{locale}/product/{product_id}"
        resp = requests.get(url, headers=headers, timeout=30)
        
        if resp.status_code == 200:
            _, price, parsed_currency = parse_ps_next_json(resp.text)
            if price and price > 0:
                final_currency = parsed_currency.upper() if parsed_currency else currency
                return PriceData("PlayStation", title, country, final_currency, price, None, None)
    except Exception:
        pass
    
    return PriceData("PlayStation", title, country, currency, None, None, None)

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
            except Exception as e:
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
    df = pd.DataFrame([{
        "Title": r.title,
        "Country": COUNTRY_NAMES.get(r.country, r.country),
        "Currency": r.currency,
        "Local Price": r.price if r.price is not None else None,
        "USD Price": r.price_usd if r.price_usd is not None else None,
        "% Diff vs US": r.diff_vs_us if r.diff_vs_us else None
    } for r in results])
    
    return df.sort_values(["Title", "Country"]).reset_index(drop=True)

# ============================================================================
# STREAMLIT UI
# ============================================================================

st.title("🎮 Unified Multi-Platform Game Pricing Tool")
st.caption("Pull prices from Steam, Xbox, and PlayStation across all global markets")

st.markdown("---")

# Steam Basket
st.subheader("🎮 Steam Games")
st.caption("Add games one per line: Title | AppID or URL")
col1, col2 = st.columns([3, 1])
with col1:
    steam_input = st.text_area(
        "Format: Game Title | AppID or URL",
        height=150,
        placeholder="The Outer Worlds 2 | 1449110\nMadden NFL 26 | https://store.steampowered.com/app/3230400/"
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
        placeholder="The Outer Worlds 2 | 9NSPRSXXZZLG\nMadden NFL 26 | https://www.xbox.com/en-US/games/store/game/9NVD16NP4J8T"
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
        placeholder="The Outer Worlds 2 | UP6312-PPSA24588_00-0872768154966924\nMadden NFL 26 | https://store.playstation.com/en-us/product/UP0006-PPSA26127_00-MADDENNFL26GAME0"
    )
with col6:
    st.markdown("**Examples:**")
    st.code("Borderlands 4 | UP1001-PPSA01494_00-...", language="text")
    st.code("NBA 2K26 | UP1001-PPSA28420_00-...", language="text")

st.markdown("---")

if st.button("🚀 Pull Prices", type="primary", width='stretch'):
    # Parse inputs with manual titles
    steam_games = []
    xbox_games = []
    ps_games = []
    
    # Process Steam
    for line in steam_input.strip().split("\n"):
        if "|" in line:
            parts = line.split("|")
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
            parts = line.split("|")
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
            parts = line.split("|")
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
        # Show what we're pulling
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
            st.dataframe(steam_df, width='stretch', height=400)
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
            st.dataframe(xbox_df, width='stretch', height=400)
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
            st.dataframe(ps_df, width='stretch', height=400)
            st.download_button(
                "⬇️ Download PlayStation CSV",
                ps_df.to_csv(index=False).encode("utf-8"),
                "playstation_prices.csv",
                "text/csv"
            )
