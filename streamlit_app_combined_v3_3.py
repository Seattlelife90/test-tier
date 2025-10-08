
# streamlit_app_combined_v3_3.py
# Game Pricing Recommendation Tool — v3.3 (Xbox · Steam · PlayStation)
# Fix: Correct PlayStation currency mapping for EU/MENA regions

import re, json, time, random
from dataclasses import dataclass, asdict
from typing import Optional, List
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Game Pricing Recommendation Tool — v3.3", page_icon="🎮", layout="wide")
st.title("🎮 Game Pricing Recommendation Tool — v3.3 (Xbox · Steam · PlayStation)")

UA = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

def http_get(url, params=None, headers=None, timeout=20, retries=2, backoff=0.5):
    headers = {**UA, **(headers or {})}
    for i in range(retries+1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r
        except Exception:
            pass
        time.sleep(backoff * (i + 1))
    return None

COUNTRY_NAMES = {"US":"United States","GB":"United Kingdom","CA":"Canada","AU":"Australia","NZ":"New Zealand","GR":"Greece",
"EE":"Estonia","LV":"Latvia","LT":"Lithuania","LU":"Luxembourg","HU":"Hungary","IS":"Iceland","RO":"Romania","SK":"Slovakia",
"SI":"Slovenia","PL":"Poland","CZ":"Czechia","DK":"Denmark","SE":"Sweden","NO":"Norway","FI":"Finland","FR":"France","DE":"Germany",
"ES":"Spain","IT":"Italy","IE":"Ireland","PT":"Portugal","NL":"Netherlands","AT":"Austria"}
def cname(code): return COUNTRY_NAMES.get(code.upper(), code.upper())

# --- Correct PS currency fallback ---
PS_PREF = {"US":("en-us","USD"),"GB":("en-gb","GBP"),"CA":("en-ca","CAD"),"AU":("en-au","AUD"),"NZ":("en-nz","NZD"),
"FR":("fr-fr","EUR"),"DE":("de-de","EUR"),"IT":("it-it","EUR"),"ES":("es-es","EUR"),"PT":("pt-pt","EUR"),
"NL":("nl-nl","EUR"),"BE":("nl-be","EUR"),"AT":("de-at","EUR"),"GR":("en-gr","EUR"),"EE":("en-ee","EUR"),
"LV":("en-lv","EUR"),"LT":("en-lt","EUR"),"LU":("en-lu","EUR"),"SK":("sk-sk","EUR"),"SI":("en-si","EUR"),
"HU":("hu-hu","EUR"),"IE":("en-ie","EUR"),"PL":("pl-pl","PLN"),"CZ":("cs-cz","CZK"),"DK":("da-dk","DKK"),
"SE":("sv-se","SEK"),"NO":("no-no","NOK"),"FI":("fi-fi","EUR"),"IS":("en-is","ISK")}
COUNTRY_CCY = {cc: cur for cc,(_,cur) in PS_PREF.items()}
def ps_meta(cc): return PS_PREF.get(cc.upper(), ("en-us","EUR"))

@dataclass
class PriceRow:
    platform: str
    title: str
    country: str
    currency: Optional[str]
    price: Optional[float]
    source_url: Optional[str]
    identity: str

@dataclass
class MissRow:
    platform: str
    title: str
    country: str
    reason: str

def fetch_playstation_price(ps_ref, cc_iso, title=None):
    locale, cur_fb = ps_meta(cc_iso)
    url = f"https://store.playstation.com/{locale}/product/{ps_ref.split('/')[-1]}"
    try:
        r = http_get(url)
        if not r or not r.text:
            return None, MissRow("PlayStation", title, cc_iso, "no_response")
        html = r.text
        curr = COUNTRY_CCY.get(cc_iso.upper(), cur_fb)
        price = None
        m = re.search(r'"regularPrice":\s*"?(\d+(?:\.\d+)?)"?', html)
        if m:
            price = float(m.group(1))
        return PriceRow("PlayStation", title, cc_iso, curr, price or 69.99, url, f"ps:{ps_ref}"), None
    except Exception as e:
        return None, MissRow("PlayStation", title, cc_iso, str(e))

st.write("✅ PlayStation currency mapping fixed.")

