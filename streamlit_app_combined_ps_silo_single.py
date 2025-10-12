
# streamlit_app_combined_ps_silo_single.py
# v1.0 — Steam & Xbox kept separate; PlayStation in its own silo
# Dependencies: streamlit, requests, pandas, beautifulsoup4
# (requirements.txt should include: streamlit==1.38.0, requests, pandas, beautifulsoup4)

from __future__ import annotations
import re, json, time, math
from typing import Dict, List, Optional, Tuple
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})

# -----------------------------
# Steam (kept as you had it)
# -----------------------------
STEAM_MARKETS = ["AE","AR","AT","AU","BE","BG","BH","BR","CA","CH","CL","CN","CO","CR","CY","CZ","DE","DK","DO",
                 "EC","EE","EG","ES","FI","FR","GB","GR","GT","HK","HN","HU","ID","IE","IL","IN","IS","IT","JP",
                 "KR","KW","LB","LU","LV","MA","MT","MX","MY","NI","NL","NO","NZ","OM","PA","PE","PH","PL","PR",
                 "PT","PY","QA","RO","RS","RU","SA","SE","SG","SI","SK","SV","TH","TR","TW","UA","US","UY","ZA"]

def steam_price_from_page(appid: str, country: str) -> Optional[Tuple[str, float, str]]:
    url = f"https://store.steampowered.com/app/{appid}"
    try:
        r = SESSION.get(url, timeout=25)
        if r.status_code != 200:
            return None
        html = r.text
        m = re.search(r'"final_price":\s*?(\d+)', html)
        cur = "USD"
        if m:
            cents = int(m.group(1))
            return (url, round(cents/100.0, 2), cur)
        m2 = re.search(r'(\$|USD)\s?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', html)
        if m2:
            amt = m2.group(2).replace(",", "")
            return (url, float(amt), "USD")
    except Exception:
        return None
    return None

# -----------------------------
# Xbox (kept as you had it)
# -----------------------------
XBOX_MARKETS = STEAM_MARKETS

def xbox_price_from_page(store_id: str, country: str) -> Optional[Tuple[str, float, str]]:
    url = f"https://www.xbox.com/{country.lower()}/games/store/_/{store_id}"
    try:
        r = SESSION.get(url, timeout=25)
        if r.status_code != 200:
            return None
        html = r.text
        m_sr = re.search(r'aria-label="(?:Original price|Full price) .*?(\$|\€|\£)?\s?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', html)
        m_now = re.search(r'itemprop="price".*?content="(\d+(?:\.\d{2})?)"', html)
        cur = "USD"
        if m_sr:
            amt = m_sr.group(2).replace(",", "")
            return (url, float(amt), cur)
        if m_now:
            return (url, float(m_now.group(1)), cur)
    except Exception:
        return None
    return None

# -----------------------------
# PlayStation SILO
# -----------------------------
PS_MARKETS = [
    ("US", "en-us", "USD"),
    ("CA", "en-ca", "CAD"),
    ("AR", "es-ar", "USD"),
    ("CL", "es-cl", "USD"),
    ("BR", "pt-br", "BRL"),
    ("GB", "en-gb", "GBP"),
    ("DE", "de-de", "EUR"),
    ("FR", "fr-fr", "EUR"),
    ("AU", "en-au", "AUD"),
    ("NZ", "en-nz", "NZD"),
    ("HK", "en-hk", "HKD"),
    ("JP", "ja-jp", "JPY"),
]

def _norm_ps_url(ps_ref: str, locale: str) -> str:
    if ps_ref.startswith("http"):
        return re.sub(r"store.playstation.com/([a-z]{2}-[a-z]{2})/", f"store.playstation.com/{locale}/", ps_ref)
    return f"https://store.playstation.com/{locale}/product/{ps_ref}"

def ps_fetch_one(ps_ref: str, country: str, locale: str) -> Optional[Tuple[str, float, str, str]]:
    url = _norm_ps_url(ps_ref, locale)
    try:
        r = SESSION.get(url, timeout=30)
        if r.status_code != 200:
            return None
        html = r.text
        m_strike = re.search(r'(?:was|original|strikethrough)["']?:?\s?\$?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))', html, re.I)
        if m_strike:
            amt = m_strike.group(1).replace(",", "")
            return (url, float(amt), "USD", "MSRP")
        m = re.findall(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))', html)
        vals = [float(x.replace(",", "")) for x in m if x]
        if vals:
            return (url, max(vals), "USD", "Largest")
    except Exception:
        return None
    return None

# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="Game Pricing – vSilos (Xbox • Steam • PlayStation)", layout="wide")
st.title("🎮 Game Pricing – vSilos (Xbox • Steam • PlayStation)")

st.caption("Steam & Xbox keep their working logic. PlayStation uses its own silo.")

colL, colR = st.columns([1,3])
with colL:
    st.subheader("Controls")
    quick = st.toggle("⚡ Quick run (first 10 markets)", value=True)
    prefer_msrp = st.toggle("Prefer MSRP", value=True)

steam_basket = [
    {"include": True,  "title":"The Outer Worlds 2", "appid":"1449110", "scale":1.0, "weight":1},
    {"include": True,  "title":"Madden NFL 26",      "appid":"3230400", "scale":1.0, "weight":1},
]

xbox_basket = [
    {"include": True, "title":"The Outer Worlds 2", "store_id":"9NSPRSXXZZLG", "scale":1.0,"weight":1},
]

ps_basket = [
    {"include": True, "title":"The Outer Worlds 2", "ps_ref":"UP1001-PPSA01494_00-0000000000000AK2"},
]

st.info("Pulling prices across markets…")

rows = []

for g in steam_basket:
    if not g["include"]: continue
    for c in STEAM_MARKETS[:10 if quick else len(STEAM_MARKETS)]:
        got = steam_price_from_page(g["appid"], c)
        if got:
            url, price, cur = got
            rows.append({"platform":"Steam","title":g["title"],"country":c,"currency":cur,"price":price,"source_url":url})
        time.sleep(0.1)

for g in xbox_basket:
    if not g["include"]: continue
    for c in XBOX_MARKETS[:10 if quick else len(XBOX_MARKETS)]:
        got = xbox_price_from_page(g["store_id"], c)
        if got:
            url, price, cur = got
            rows.append({"platform":"Xbox","title":g["title"],"country":c,"currency":cur,"price":price,"source_url":url})
        time.sleep(0.1)

for g in ps_basket:
    if not g["include"]: continue
    for (cc, locale, cur) in PS_MARKETS[:10 if quick else len(PS_MARKETS)]:
        got = ps_fetch_one(g["ps_ref"], cc, locale)
        if got:
            url, price, cur2, note = got
            rows.append({"platform":"PlayStation","title":g["title"],"country":cc,"currency":cur2,"price":price,"source_url":url,"note":note})
        time.sleep(0.2)

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True)
