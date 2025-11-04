import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time
from typing import Dict, List, Optional, Tuple
import json

# ==========================================
# CONFIGURATION
# ==========================================

# Tier configurations with URLs for all platforms
TIER_CONFIGS = {
    "AAA": {
        "Steam": [
            ("The Outer Worlds 2", "https://store.steampowered.com/app/1449110/The_Outer_Worlds_2/", 1.0, 1.0),
            ("Madden NFL 26", "https://store.steampowered.com/app/3230400/Madden_NFL_26/", 1.0, 1.0),
            ("Call of Duty: Black Ops 6", "https://store.steampowered.com/app/2933620/Call_of_Duty_Black_Ops_6/", 1.0, 1.0),
            ("Borderlands 4", "https://store.steampowered.com/app/1285190/Borderlands_4/", 1.0, 1.0),
            ("NBA 2K26", "https://store.steampowered.com/app/3472040/NBA_2K26/", 1.0, 1.0),
        ],
        "Xbox": [
            ("The Outer Worlds 2", "https://www.xbox.com/en-US/games/store/the-outer-worlds-2/9NSPRSXXZZLG", 1.0, 1.0),
            ("Madden NFL 26", "https://www.xbox.com/en-US/games/store/madden-nfl-26/9nvd16np48t", 1.0, 1.0),
            ("Call of Duty: Black Ops 6", "https://www.xbox.com/en-US/games/store/call-of-duty-black-ops-6/9pfz8m6crhq", 1.0, 1.0),
            ("Borderlands 4", "https://www.xbox.com/en-US/games/store/borderlands-4/9m6bh5647g", 1.0, 1.0),
            ("NBA 2K26", "https://www.xbox.com/en-US/games/store/nba-2k26/9p2vrc01x", 1.0, 1.0),
        ],
        "PlayStation": [
            ("The Outer Worlds 2", "https://store.playstation.com/en-us/product/UP6312-PPSA24588_00-0872768154966924", 1.0, 1.0),
            ("Madden NFL 26", "https://store.playstation.com/en-us/product/UP0006-PPSA26127_00-MADDENNFL26GAME0", 1.0, 1.0),
            ("Call of Duty: Black Ops 6", "https://store.playstation.com/en-us/product/UP0002-PPSA01649_00-CODBO6CROSSGEN01", 1.0, 1.0),
            ("Borderlands 4", "https://store.playstation.com/en-us/product/UP1001-PPSA01494_00-000000000000OAK2", 1.0, 1.0),
            ("NBA 2K26", "https://store.playstation.com/en-us/product/UP1001-PPSA28420_00-NBA2K26000000000", 1.0, 1.0),
        ],
    },
    "AA": {
        "Steam": [
            ("Black Myth: Wukong", "https://store.steampowered.com/app/2358720/Black_Myth_Wukong/", 1.0, 1.0),
            ("Helldivers 2", "https://store.steampowered.com/app/553850/HELLDIVERS_2/", 1.0, 1.0),
            ("A Plague Tale: Requiem", "https://store.steampowered.com/app/1182900/A_Plague_Tale_Requiem/", 1.0, 1.0),
            ("Remnant II", "https://store.steampowered.com/app/1282100/REMNANT_II/", 1.0, 1.0),
            ("Stellar Blade", "https://store.steampowered.com/app/3489700/Stellar_Blade/", 1.0, 1.0),
            ("Clair Obscur: Expedition 33", "https://store.steampowered.com/app/1903340/Clair_Obscur_Expedition_33/", 1.0, 1.0),
            ("Banishers: Ghosts of New Eden", "https://store.steampowered.com/app/1493640/Banishers_Ghosts_of_New_Eden/", 1.0, 1.0),
        ],
        "Xbox": [
            ("Black Myth: Wukong", "https://www.xbox.com/en-US/games/store/black-myth-wukong/9NWQ1Q1FR0C9", 1.0, 1.0),
            ("Helldivers 2", "https://www.xbox.com/en-us/games/store/helldivers-2/9p3pt7pqjd0m", 1.0, 1.0),
            ("A Plague Tale: Requiem", "https://www.xbox.com/en-us/games/store/a-plague-tale-requiem/9nd0jxlb184t", 1.0, 1.0),
            ("Remnant II", "https://www.xbox.com/en-us/games/store/remnant-ii-standard-edition/9P92782MJGQIJ", 1.0, 1.0),
            ("Stellar Blade", "https://www.xbox.com/en-us/games/store/stellar-blade/9npp8k6gzghrz", 1.0, 1.0),
            ("Clair Obscur: Expedition 33", "https://www.xbox.com/en-US/games/store/clair-obscur-expedition-33/9P92762M4GQU", 1.0, 1.0),
            ("Banishers: Ghosts of New Eden", "https://www.xbox.com/en-us/games/store/banishers-ghosts-of-new-eden/9NKFS43DLFFL", 1.0, 1.0),
        ],
        "PlayStation": [
            ("Black Myth: Wukong", "https://store.playstation.com/en-us/product/HP6545-PPSA23206_00-GAME000000000000", 1.0, 1.0),
            ("Helldivers 2", "https://store.playstation.com/en-us/product/UP9000-PPSA01413_00-HELLDIVERS00000", 1.0, 1.0),
            ("A Plague Tale: Requiem", "https://store.playstation.com/en-us/product/UP4133-PPSA05366_00-APLAQUEOUTBURST0", 1.0, 1.0),
            ("Remnant II", "https://store.playstation.com/en-us/product/UP1980-PPSA06693_00-REM2STDPREORDER0", 1.0, 1.0),
            ("Stellar Blade", "https://store.playstation.com/en-us/concept/10006891", 1.0, 1.0),
            ("Clair Obscur: Expedition 33", "https://store.playstation.com/en-us/concept/10008503", 1.0, 1.0),
            ("Banishers: Ghosts of New Eden", "https://store.playstation.com/en-us/product/UP4133-PPSA10054_00-NEWWORLDGAME0000", 1.0, 1.0),
        ],
    },
    "Indie": {
        "Steam": [
            ("Hollow Knight: Silksong", "https://store.steampowered.com/app/1030300/Hollow_Knight_Silksong/", 1.0, 1.0),
            ("Hades", "https://store.steampowered.com/app/1145360/Hades/", 1.0, 1.0),
            ("Hades II", "https://store.steampowered.com/app/1145350/Hades_II/", 1.0, 1.0),
            ("Blue Prince", "https://store.steampowered.com/app/1569590/Blue_Prince/", 1.0, 1.0),
            ("Split Fiction", "https://store.steampowered.com/app/2001120/Split_Fiction/", 1.0, 1.0),
            ("Animal Well", "https://store.steampowered.com/app/813230/Animal_Well/", 1.0, 1.0),
            ("UFO 50", "https://store.steampowered.com/app/1514570/UFO_50/", 1.0, 1.0),
        ],
        "Xbox": [
            ("Hollow Knight: Silksong", "https://www.xbox.com/games/store/hollow-knight-silksong/9n116v0599hb", 1.0, 1.0),
            ("Hades", "https://www.xbox.com/en-us/games/store/hades/9P8DL6W3FG2W", 1.0, 1.0),
            ("Hades II", "https://www.xbox.com/en-us/games/store/hades-ii/9N2W7KQ3KS0F", 1.0, 1.0),
            ("Blue Prince", "https://www.xbox.com/en-US/games/store/blue-prince/9prfrrq569g", 1.0, 1.0),
            ("Split Fiction", "https://www.xbox.com/en-US/games/store/split-fiction/9n1wxd1r8d", 1.0, 1.0),
            ("Animal Well", "https://www.xbox.com/en-US/games/store/animal-well/9NFPLMC3S42NV", 1.0, 1.0),
            ("UFO 50", "https://www.xbox.com/en-US/games/store/ufo-50/9p3stq4kj6n", 1.0, 1.0),
        ],
        "PlayStation": [
            ("Hollow Knight: Silksong", "https://store.playstation.com/en-us/concept/10005908", 1.0, 1.0),
            ("Hades", "https://store.playstation.com/en-ca/concept/10002648", 1.0, 1.0),
            ("Hades II", "https://store.playstation.com/en-us/concept/10008036", 1.0, 1.0),
            ("Blue Prince", "https://store.playstation.com/en-us/product/EP2187-PPSA25009_00-BLUEPRINCE000000", 1.0, 1.0),
            ("Split Fiction", "https://store.playstation.com/en-us/product/UP0006-PPSA08360_00-SPLITSTANDARDED0", 1.0, 1.0),
            ("Animal Well", "https://store.playstation.com/en-us/product/UP7425-PPSA06799_00-9351926314516028", 1.0, 1.0),
            ("UFO 50", "https://store.playstation.com/en-us/concept/10008402", 1.0, 1.0),
        ],
    },
}

# Currency symbols
CURRENCY_SYMBOLS = {
    'USD': '$', 'CAD': 'CA$', 'EUR': '€', 'GBP': '£', 'AUD': 'A$', 'NZD': 'NZ$',
    'JPY': '¥', 'KRW': '₩', 'CNY': '¥', 'HKD': 'HK$', 'TWD': 'NT$', 'SGD': 'S$',
    'THB': '฿', 'MYR': 'RM', 'IDR': 'Rp', 'PHP': '₱', 'VND': '₫', 'INR': '₹',
    'AED': 'AED', 'SAR': 'SAR', 'ZAR': 'R', 'BRL': 'R$', 'ARS': 'ARS$',
    'CLP': 'CLP$', 'COP': 'COL$', 'MXN': 'Mex$', 'PEN': 'S/', 'UYU': '$U',
    'RUB': '₽', 'TRY': '₺', 'UAH': '₴', 'PLN': 'zł', 'CHF': 'CHF', 'SEK': 'kr',
    'NOK': 'kr', 'DKK': 'kr.', 'CZK': 'Kč', 'HUF': 'Ft', 'RON': 'lei', 'BGN': 'лв',
    'HRK': 'kn', 'ILS': '₪', 'QAR': 'QR', 'KWD': 'KD', 'BHD': 'BD'
}

# Country to currency mapping (simplified)
COUNTRY_CURRENCIES = {
    'us': 'USD', 'ca': 'CAD', 'gb': 'GBP', 'au': 'AUD', 'nz': 'NZD',
    'de': 'EUR', 'fr': 'EUR', 'it': 'EUR', 'es': 'EUR', 'nl': 'EUR', 'be': 'EUR',
    'at': 'EUR', 'pt': 'EUR', 'ie': 'EUR', 'fi': 'EUR', 'gr': 'EUR',
    'jp': 'JPY', 'kr': 'KRW', 'cn': 'CNY', 'hk': 'HKD', 'tw': 'TWD', 'sg': 'SGD',
    'th': 'THB', 'my': 'MYR', 'id': 'IDR', 'ph': 'PHP', 'vn': 'VND', 'in': 'INR',
    'ae': 'AED', 'sa': 'SAR', 'za': 'ZAR', 'br': 'BRL', 'ar': 'ARS',
    'cl': 'CLP', 'co': 'COP', 'mx': 'MXN', 'pe': 'PEN', 'uy': 'UYU',
    'ru': 'RUB', 'tr': 'TRY', 'ua': 'UAH', 'pl': 'PLN', 'ch': 'CHF', 'se': 'SEK',
    'no': 'NOK', 'dk': 'DKK', 'cz': 'CZK', 'hu': 'HUF', 'ro': 'RON', 'bg': 'BGN',
    'hr': 'HRK', 'il': 'ILS', 'qa': 'QAR', 'kw': 'KWD', 'bh': 'BHD'
}

# USD conversion rates (approximate - these should be updated regularly)
USD_RATES = {
    'USD': 1.0, 'CAD': 1.36, 'EUR': 0.92, 'GBP': 0.79, 'AUD': 1.53, 'NZD': 1.67,
    'JPY': 149.0, 'KRW': 1320.0, 'CNY': 7.24, 'HKD': 7.83, 'TWD': 31.5, 'SGD': 1.34,
    'THB': 34.5, 'MYR': 4.47, 'IDR': 15700.0, 'PHP': 55.5, 'VND': 24500.0, 'INR': 83.0,
    'AED': 3.67, 'SAR': 3.75, 'ZAR': 18.2, 'BRL': 5.0, 'ARS': 350.0,
    'CLP': 920.0, 'COP': 3950.0, 'MXN': 17.0, 'PEN': 3.75, 'UYU': 39.0,
    'RUB': 92.0, 'TRY': 32.0, 'UAH': 36.5, 'PLN': 3.95, 'CHF': 0.86, 'SEK': 10.4,
    'NOK': 10.6, 'DKK': 6.85, 'CZK': 22.5, 'HUF': 355.0, 'RON': 4.57, 'BGN': 1.80,
    'HRK': 6.93, 'ILS': 3.65, 'QAR': 3.64, 'KWD': 0.31, 'BHD': 0.38
}

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def extract_steam_appid(url: str) -> Optional[str]:
    """Extract Steam App ID from URL"""
    match = re.search(r'/app/(\d+)', url)
    return match.group(1) if match else None

def extract_xbox_id(url: str) -> Optional[str]:
    """Extract Xbox Store ID from URL"""
    match = re.search(r'/store/[^/]+/([A-Z0-9]+)', url, re.IGNORECASE)
    return match.group(1) if match else None

def extract_playstation_id(url: str) -> Optional[str]:
    """Extract PlayStation Product ID from URL"""
    # Try product ID format first
    match = re.search(r'/product/([A-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    # Try concept ID format
    match = re.search(r'/concept/(\d+)', url)
    if match:
        return f"concept_{match.group(1)}"
    return None

def convert_to_usd(price: float, currency: str) -> float:
    """Convert price to USD"""
    if currency == 'USD':
        return price
    rate = USD_RATES.get(currency, 1.0)
    return round(price / rate, 2)

def normalize_weights(weights: List[float]) -> List[float]:
    """Auto-normalize weights to percentages"""
    total = sum(weights)
    if total == 0:
        return [0.0] * len(weights)
    return [w / total for w in weights]

# ==========================================
# STEAM SCRAPER
# ==========================================

def fetch_steam_prices(app_id: str) -> Dict[str, Dict]:
    """Fetch Steam prices for all regions"""
    countries = ['us', 'ca', 'gb', 'de', 'au', 'jp', 'br', 'ru', 'cn', 'tr']
    prices = {}
    
    for country in countries:
        try:
            url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc={country}"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if data.get(app_id, {}).get('success'):
                price_data = data[app_id]['data'].get('price_overview', {})
                if price_data:
                    currency = price_data['currency']
                    price = price_data['final'] / 100
                    usd_price = convert_to_usd(price, currency)
                    
                    prices[country.upper()] = {
                        'price': price,
                        'currency': currency,
                        'usd': usd_price,
                        'formatted': f"{CURRENCY_SYMBOLS.get(currency, '')}{price:.2f}"
                    }
            time.sleep(0.5)
        except Exception as e:
            st.warning(f"Steam {country.upper()}: {str(e)}")
            continue
    
    return prices

# ==========================================
# XBOX SCRAPER
# ==========================================

def fetch_xbox_prices(store_id: str) -> Dict[str, Dict]:
    """Fetch Xbox prices for all regions"""
    countries = ['us', 'ca', 'gb', 'de', 'au', 'jp', 'br', 'mx', 'fr', 'it']
    prices = {}
    
    for country in countries:
        try:
            url = f"https://www.xbox.com/en-{country}/games/store/product/{store_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try multiple price patterns
            price_text = None
            price_patterns = [
                soup.find('span', {'itemprop': 'price'}),
                soup.find('div', {'class': re.compile(r'Price')}),
                soup.find(string=re.compile(r'[\$£€¥]\s*\d+'))
            ]
            
            for pattern in price_patterns:
                if pattern:
                    price_text = pattern.get_text() if hasattr(pattern, 'get_text') else str(pattern)
                    break
            
            if price_text:
                # Extract price and currency
                price_match = re.search(r'([\$£€¥₹])?\s*([\d,]+\.?\d*)', price_text)
                if price_match:
                    price = float(price_match.group(2).replace(',', ''))
                    currency = COUNTRY_CURRENCIES.get(country.lower(), 'USD')
                    usd_price = convert_to_usd(price, currency)
                    
                    prices[country.upper()] = {
                        'price': price,
                        'currency': currency,
                        'usd': usd_price,
                        'formatted': f"{CURRENCY_SYMBOLS.get(currency, '')}{price:.2f}"
                    }
            time.sleep(1)
        except Exception as e:
            st.warning(f"Xbox {country.upper()}: {str(e)}")
            continue
    
    return prices

# ==========================================
# PLAYSTATION SCRAPER
# ==========================================

def fetch_playstation_prices(product_id: str) -> Dict[str, Dict]:
    """Fetch PlayStation prices for all regions"""
    countries = ['us', 'ca', 'gb', 'de', 'au', 'jp', 'br', 'mx', 'fr', 'it']
    prices = {}
    
    for country in countries:
        try:
            # Handle concept IDs differently
            if product_id.startswith('concept_'):
                concept_id = product_id.replace('concept_', '')
                url = f"https://store.playstation.com/en-{country}/concept/{concept_id}"
            else:
                url = f"https://store.playstation.com/en-{country}/product/{product_id}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try multiple price patterns
            price_text = None
            price_patterns = [
                soup.find('span', {'data-qa': 'mfeCtaMain#offer0#finalPrice'}),
                soup.find('span', {'class': re.compile(r'price')}),
                soup.find(string=re.compile(r'[\$£€¥]\s*\d+'))
            ]
            
            for pattern in price_patterns:
                if pattern:
                    price_text = pattern.get_text() if hasattr(pattern, 'get_text') else str(pattern)
                    break
            
            if price_text:
                # Extract price and currency
                price_match = re.search(r'([\$£€¥₹])?\s*([\d,]+\.?\d*)', price_text)
                if price_match:
                    price = float(price_match.group(2).replace(',', ''))
                    currency = COUNTRY_CURRENCIES.get(country.lower(), 'USD')
                    usd_price = convert_to_usd(price, currency)
                    
                    prices[country.upper()] = {
                        'price': price,
                        'currency': currency,
                        'usd': usd_price,
                        'formatted': f"{CURRENCY_SYMBOLS.get(currency, '')}{price:.2f}"
                    }
            time.sleep(1)
        except Exception as e:
            st.warning(f"PlayStation {country.upper()}: {str(e)}")
            continue
    
    return prices

# ==========================================
# RECOMMENDATION ENGINE
# ==========================================

def calculate_weighted_recommendations(pricing_data: Dict, tier_config: Dict) -> pd.DataFrame:
    """Calculate weighted pricing recommendations"""
    recommendations = []
    
    for platform in ['Steam', 'Xbox', 'PlayStation']:
        if platform not in pricing_data or not pricing_data[platform]:
            continue
        
        # Get scale factors and weights for this platform
        games_config = tier_config[platform]
        scales = [game[2] for game in games_config]
        weights = [game[3] for game in games_config]
        normalized_weights = normalize_weights(weights)
        
        # Group by country
        countries = set()
        for game_prices in pricing_data[platform].values():
            countries.update(game_prices.keys())
        
        for country in countries:
            weighted_sum = 0
            total_weight = 0
            count = 0
            local_currency = None
            
            for idx, (game_name, _, scale, weight) in enumerate(games_config):
                if game_name in pricing_data[platform]:
                    game_prices = pricing_data[platform][game_name]
                    if country in game_prices:
                        price_data = game_prices[country]
                        usd_price = price_data['usd']
                        
                        # Apply scale factor and weight
                        weighted_price = usd_price * scale * normalized_weights[idx]
                        weighted_sum += weighted_price
                        total_weight += normalized_weights[idx]
                        count += 1
                        
                        if local_currency is None:
                            local_currency = price_data['currency']
            
            if count > 0 and total_weight > 0:
                # Calculate recommendation in USD
                rec_usd = weighted_sum / total_weight
                
                # Convert back to local currency
                rate = USD_RATES.get(local_currency, 1.0)
                rec_local = rec_usd * rate
                
                recommendations.append({
                    'Platform': platform,
                    'Country': country,
                    'Currency': local_currency,
                    'Recommended (USD)': f"${rec_usd:.2f}",
                    'Recommended (Local)': f"{CURRENCY_SYMBOLS.get(local_currency, '')}{rec_local:.2f}",
                    'Games Included': count
                })
    
    return pd.DataFrame(recommendations)

# ==========================================
# STREAMLIT UI
# ==========================================

st.set_page_config(page_title="Video Game Pricing Tool v4.0", layout="wide")
st.title("🎮 Video Game Pricing Tool v4.0")
st.caption("Multi-platform pricing with tier system, scale factors, and weighted recommendations")

# Initialize session state
if 'tier_configs' not in st.session_state:
    st.session_state.tier_configs = TIER_CONFIGS.copy()
if 'pricing_data' not in st.session_state:
    st.session_state.pricing_data = {}

# Tier selector
tier = st.selectbox("Select Tier", ["AAA", "AA", "Indie"], key="tier_selector")

st.divider()

# ==========================================
# COMPETITIVE SET EDITOR
# ==========================================

st.subheader(f"📝 {tier} Tier - Competitive Set")

for platform in ['Steam', 'Xbox', 'PlayStation']:
    with st.expander(f"{platform} Games", expanded=False):
        games = st.session_state.tier_configs[tier][platform]
        
        # Display games in a table format
        cols = st.columns([3, 2, 1, 1, 1])
        cols[0].write("**Game Title**")
        cols[1].write("**URL**")
        cols[2].write("**Scale Factor**")
        cols[3].write("**Weight**")
        cols[4].write("**Action**")
        
        games_to_remove = []
        updated_games = []
        
        for idx, game in enumerate(games):
            cols = st.columns([3, 2, 1, 1, 1])
            
            name = cols[0].text_input(f"Name {idx}", value=game[0], key=f"{tier}_{platform}_name_{idx}", label_visibility="collapsed")
            url = cols[1].text_input(f"URL {idx}", value=game[1], key=f"{tier}_{platform}_url_{idx}", label_visibility="collapsed")
            scale = cols[2].number_input(f"Scale {idx}", value=float(game[2]), min_value=0.1, max_value=5.0, step=0.05, key=f"{tier}_{platform}_scale_{idx}", label_visibility="collapsed")
            weight = cols[3].number_input(f"Weight {idx}", value=float(game[3]), min_value=0.0, step=0.1, key=f"{tier}_{platform}_weight_{idx}", label_visibility="collapsed")
            
            if cols[4].button("🗑️", key=f"{tier}_{platform}_delete_{idx}"):
                games_to_remove.append(idx)
            else:
                updated_games.append((name, url, scale, weight))
        
        # Update games list
        st.session_state.tier_configs[tier][platform] = updated_games
        
        # Add new game button
        if st.button(f"➕ Add {platform} Game", key=f"{tier}_{platform}_add"):
            st.session_state.tier_configs[tier][platform].append(("New Game", "", 1.0, 1.0))
            st.rerun()

st.divider()

# ==========================================
# PRICE PULLER
# ==========================================

if st.button("🚀 Pull Prices", type="primary", use_container_width=True):
    st.session_state.pricing_data = {tier: {'Steam': {}, 'Xbox': {}, 'PlayStation': {}}}
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_games = sum(len(st.session_state.tier_configs[tier][p]) for p in ['Steam', 'Xbox', 'PlayStation'])
    current = 0
    
    # Fetch Steam prices
    for game in st.session_state.tier_configs[tier]['Steam']:
        name, url, _, _ = game
        status_text.text(f"Fetching Steam: {name}...")
        app_id = extract_steam_appid(url)
        if app_id:
            prices = fetch_steam_prices(app_id)
            if prices:
                st.session_state.pricing_data[tier]['Steam'][name] = prices
        current += 1
        progress_bar.progress(current / total_games)
    
    # Fetch Xbox prices
    for game in st.session_state.tier_configs[tier]['Xbox']:
        name, url, _, _ = game
        status_text.text(f"Fetching Xbox: {name}...")
        store_id = extract_xbox_id(url)
        if store_id:
            prices = fetch_xbox_prices(store_id)
            if prices:
                st.session_state.pricing_data[tier]['Xbox'][name] = prices
        current += 1
        progress_bar.progress(current / total_games)
    
    # Fetch PlayStation prices
    for game in st.session_state.tier_configs[tier]['PlayStation']:
        name, url, _, _ = game
        status_text.text(f"Fetching PlayStation: {name}...")
        product_id = extract_playstation_id(url)
        if product_id:
            prices = fetch_playstation_prices(product_id)
            if prices:
                st.session_state.pricing_data[tier]['PlayStation'][name] = prices
        current += 1
        progress_bar.progress(current / total_games)
    
    progress_bar.empty()
    status_text.success("✅ Price pull complete!")

st.divider()

# ==========================================
# RESULTS TABS
# ==========================================

if tier in st.session_state.pricing_data and st.session_state.pricing_data[tier]:
    tabs = st.tabs(["Steam Pricing", "Xbox Pricing", "PlayStation Pricing", "💡 Recommendations"])
    
    # Steam Tab
    with tabs[0]:
        if st.session_state.pricing_data[tier].get('Steam'):
            steam_data = []
            for game_name, prices in st.session_state.pricing_data[tier]['Steam'].items():
                for country, data in prices.items():
                    steam_data.append({
                        'Game': game_name,
                        'Country': country,
                        'Currency': data['currency'],
                        'Price': data['formatted'],
                        'USD': f"${data['usd']:.2f}"
                    })
            if steam_data:
                df = pd.DataFrame(steam_data)
                st.dataframe(df, use_container_width=True)
                st.download_button("⬇️ Download Steam CSV", df.to_csv(index=False).encode("utf-8"),
                                 "steam_prices.csv", "text/csv")
        else:
            st.info("No Steam pricing data available")
    
    # Xbox Tab
    with tabs[1]:
        if st.session_state.pricing_data[tier].get('Xbox'):
            xbox_data = []
            for game_name, prices in st.session_state.pricing_data[tier]['Xbox'].items():
                for country, data in prices.items():
                    xbox_data.append({
                        'Game': game_name,
                        'Country': country,
                        'Currency': data['currency'],
                        'Price': data['formatted'],
                        'USD': f"${data['usd']:.2f}"
                    })
            if xbox_data:
                df = pd.DataFrame(xbox_data)
                st.dataframe(df, use_container_width=True)
                st.download_button("⬇️ Download Xbox CSV", df.to_csv(index=False).encode("utf-8"),
                                 "xbox_prices.csv", "text/csv")
        else:
            st.info("No Xbox pricing data available")
    
    # PlayStation Tab
    with tabs[2]:
        if st.session_state.pricing_data[tier].get('PlayStation'):
            ps_data = []
            for game_name, prices in st.session_state.pricing_data[tier]['PlayStation'].items():
                for country, data in prices.items():
                    ps_data.append({
                        'Game': game_name,
                        'Country': country,
                        'Currency': data['currency'],
                        'Price': data['formatted'],
                        'USD': f"${data['usd']:.2f}"
                    })
            if ps_data:
                df = pd.DataFrame(ps_data)
                st.dataframe(df, use_container_width=True)
                st.download_button("⬇️ Download PlayStation CSV", df.to_csv(index=False).encode("utf-8"),
                                 "playstation_prices.csv", "text/csv")
        else:
            st.info("No PlayStation pricing data available")
    
    # Recommendations Tab
    with tabs[3]:
        st.subheader("💡 Weighted Pricing Recommendations")
        st.caption("Calculated using: (Game1_USD × Scale1 × Weight1 + ...) / Total_Weight")
        st.caption("Note: Currency-specific vanity rounding (e.g., £69.99, ¥9,800) will be added in v4.1")
        
        rec_df = calculate_weighted_recommendations(
            st.session_state.pricing_data[tier],
            st.session_state.tier_configs[tier]
        )
        
        if not rec_df.empty:
            st.dataframe(rec_df, use_container_width=True)
            st.download_button("⬇️ Download Recommendations CSV", rec_df.to_csv(index=False).encode("utf-8"),
                             "recommendations.csv", "text/csv")
        else:
            st.warning("No recommendations generated - insufficient price data")
else:
    st.info("Pull prices first to see results")
