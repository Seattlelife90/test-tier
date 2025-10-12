
import re
import time
import json
import logging
from typing import Dict, List, Optional, Tuple

import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="Game Pricing – vSilos (Xbox • Steam • PlayStation)", layout="wide")

log = logging.getLogger("app")
logging.basicConfig(level=logging.INFO)

# -----------------------------
# Helpers
# -----------------------------

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

def _get(url: str, timeout: float = 20.0) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return r.text

def _num_from_text(text: str) -> Optional[float]:
    if not text:
        return None
    m = re.search(r'(\d{1,3}(?:[\.,]\d{3})*(?:[\.,]\d{2}))', text)
    if not m:
        return None
    val = m.group(1).replace(',', '').replace(' ', '')
    val = val.replace('٬', '').replace('．','.')  # odd separators
    if val.count('.') > 1:
        # fallback: last dot is decimal
        head, _, tail = val.rpartition('.')
        val = head.replace('.','') + '.' + tail
    try:
        return float(val)
    except Exception:
        return None

# Very small silo map for currencies by locale (extend as needed)
PS_LOCALE_TO_CCY = {
    "en-us": "USD", "en-ca": "CAD", "en-gb": "GBP", "en-au": "AUD",
    "en-nz": "NZD", "en-hk": "HKD", "zh-hk": "HKD", "de-de": "EUR",
    "fr-fr": "EUR", "es-es": "EUR", "it-it": "EUR", "pt-br": "BRL",
    "ja-jp": "JPY", "ko-kr": "KRW",
}

def _locale_from_url(url: str) -> Optional[str]:
    # https://store.playstation.com/en-us/product/UP1001-PPSA01494_00-0000000000000AK2
    m = re.search(r'store\.playstation\.com/([a-z]{2}-[a-z]{2})/', url, re.I)
    return m.group(1).lower() if m else None

def parse_ps_mspp(html: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Return (msrp, sale) from a PS Store HTML.
    Strategy:
      1) If there's a <del> (struck-through), treat it as MSRP and the nearby number as sale.
      2) Else, if two prices appear in the primary buy block, treat the larger as MSRP.
      3) Else, if only one number, treat it as MSRP.
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1) explicit strike-through tags
    strike = None
    for tagname in ("del", "s"):
        t = soup.find(tagname)
        if t and _num_from_text(t.get_text(strip=True)) is not None:
            strike = _num_from_text(t.get_text(" ", strip=True))
            break

    # 2) collect visible prices in the buy section
    text_blob = " ".join(x.get_text(" ", strip=True) for x in soup.find_all(["div","span","p"]))
    # Fixed regex (the previous build had a mismatched bracket). This finds numbers like 69.99 or 1,299.00, etc.
    nums = [ _num_from_text(m.group(0)) for m in re.finditer(r'(\d{1,3}(?:[\.,]\d{3})*(?:[\.,]\d{2}))', text_blob) ]
    nums = [n for n in nums if n is not None]

    msrp = None
    sale = None

    if strike is not None:
        msrp = strike
        # try to find a number smaller than MSRP near by (heuristic)
        smaller = [n for n in nums if n < msrp * 0.999]
        sale = min(smaller) if smaller else None
    elif len(nums) >= 2:
        msrp = max(nums)
        sale = min(nums)
    elif len(nums) == 1:
        msrp = nums[0]

    return msrp, sale

def fetch_ps_one(url: str) -> Dict[str, Optional[str]]:
    try:
        html = _get(url, timeout=25)
    except Exception as e:
        return {"platform":"PlayStation", "currency":None, "price":None, "msrp":None, "sale":None, "source_url":url, "reason":f"fetch_error: {e}"}

    msrp, sale = parse_ps_mspp(html)

    loc = _locale_from_url(url)
    ccy = PS_LOCALE_TO_CCY.get(loc or "", None)

    return {"platform":"PlayStation", "currency": ccy, "price": msrp or sale, "msrp": msrp, "sale": sale, "source_url": url, "reason": None if (msrp or sale) else "no_price"}

# -----------------------------
# UI
# -----------------------------

st.title("🎮 Game Pricing – vSilos (Xbox • Steam • PlayStation)")

st.caption("This build hotfixes the PlayStation MSRP regex syntax error and keeps MSRP > sale when both appear.")

with st.expander("PlayStation basket (PS silo)", expanded=True):
    st.write("Enter up to 6 PS product URLs (one per line):")
    default_urls = "\n".join([
        "https://store.playstation.com/en-us/product/UP1001-PPSA01494_00-0000000000000AK2",  # Borderlands 4 (example)
    ])
    ps_urls = st.text_area("PS URLs", value=default_urls, height=120)
    run = st.button("Run Pricing Pull")

if run:
    urls = [u.strip() for u in ps_urls.splitlines() if u.strip()]
    rows = [fetch_ps_one(u) for u in urls]
    df = pd.DataFrame(rows)
    st.subheader("Raw results")
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv, file_name="ps_results.csv", mime="text/csv")
else:
    st.info("Add URLs and click **Run Pricing Pull**.")
