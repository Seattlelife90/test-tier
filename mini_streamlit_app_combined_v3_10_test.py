
# mini_streamlit_app_combined_v3_10_test.py
# Minimal test app for Xbox · Steam · PlayStation price pulling
# - 2 titles only
# - 3 markets only
# - Progress bar + diagnostics
# - Uses the same core fetchers (Steam market mapping, Xbox fallback headers,
#   PlayStation MSRP + standard/cross-gen selection via page JSON and link hop).

import re, json, time, random, string
from dataclasses import dataclass, asdict
from typing import Optional, Tuple
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Game Pricing – Mini Test v3.10", page_icon="🎮", layout="centered")
st.title("🎮 Game Pricing – Mini Test v3.10 (Xbox · Steam · PlayStation)")

# ----------------- HTTP basics -----------------
SESSION = requests.Session()
ADAPTER = requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=32)
SESSION.mount("https://", ADAPTER); SESSION.mount("http://", ADAPTER)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

def http_get(url, params=None, headers=None, timeout=12, retries=1, backoff=0.35):
    last = None
    headers = {**UA, **(headers or {})}
    for i in range(retries+1):
        try:
            r = SESSION.get(url, params=params, headers=headers, timeout=timeout)
            if getattr(r, "status_code", 0) == 200:
                return r
            last = r
        except Exception as e:
            last = e
        time.sleep(backoff * (i+1))
    return last

def _ms_cv():
    import random, string
    return "".join(random.choice(string.ascii_letters+string.digits) for _ in range(28))

# ----------------- Small helpers -----------------
@dataclass
class PriceRow:
    platform: str
    title: str
    country: str
    currency: Optional[str]
    price: Optional[float]
    source_url: Optional[str]
    identity: str
    edition: Optional[str]

@dataclass
class MissRow:
    platform: str
    title: str
    country: str
    reason: str

def cname(cc: str) -> str:
    N = {"US":"United States","AU":"Australia","DE":"Germany"}
    return N.get(cc, cc)

# ----------------- Steam -----------------
STEAM_CC_MAP = {
    "US":"US","AU":"AU",
    # Most EUR markets map well to FR for EUR pricing via appdetails
    "DE":"FR"
}

def fetch_steam_price(appid: str, cc_iso: str, title: str) -> Tuple[Optional[PriceRow], Optional[MissRow]]:
    cc_eff = STEAM_CC_MAP.get(cc_iso.upper(), cc_iso.upper())
    try:
        r = http_get("https://store.steampowered.com/api/appdetails",
                     params={"appids": appid, "cc": cc_eff, "l": "en"}, timeout=10, retries=1)
        j = r.json()
        node = j.get(str(appid), {})
        if not node.get("success"):
            return None, MissRow("Steam", title, cc_iso, "no_data")
        pov = (node.get("data") or {}).get("price_overview") or {}
        cents = pov.get("initial") or pov.get("final")
        if cents:
            price = round(cents/100.0, 2)
            ccy = (pov.get("currency") or "").upper() or None
            return PriceRow("Steam", title, cc_iso.upper(), ccy, price,
                            f"https://store.steampowered.com/app/{appid}", f"steam:{appid}", "Standard"), None
        return None, MissRow("Steam", title, cc_iso, "no_price")
    except Exception:
        return None, MissRow("Steam", title, cc_iso, "exception")

# ----------------- Xbox -----------------
XBOX_LOCALE = {"US":"en-us","AU":"en-au","DE":"de-de"}
def xbox_locale(cc): return XBOX_LOCALE.get(cc.upper(),"en-us")

def parse_xbox_price(payload):
    try:
        prods = payload.get("Products") or payload.get("products") or []
        if not prods: return None, None
        p0 = prods[0]
        for sku in p0.get("DisplaySkuAvailabilities",[]) or p0.get("displaySkuAvailabilities",[]):
            for av in sku.get("Availabilities",[]) or sku.get("availabilities",[]):
                pr = (av.get("OrderManagementData") or av.get("orderManagementData") or {}).get("Price") or {}
                amt = pr.get("MSRP") or pr.get("ListPrice") or pr.get("msrp") or pr.get("listPrice")
                ccy = pr.get("CurrencyCode") or pr.get("currencyCode")
                if amt: return float(amt), (ccy and str(ccy).upper())
    except Exception:
        pass
    return None, None

def fetch_xbox_price(title: str, store_id: str, cc_iso: str):
    loc = xbox_locale(cc_iso)
    headers = {"MS-CV": _ms_cv(), "Accept":"application/json", "Referer":"https://www.xbox.com"}
    # primary
    r = http_get("https://storeedgefd.dsx.mp.microsoft.com/v9.0/sdk/products",
                 params={"bigIds":store_id,"market":cc_iso.upper(),"locale":loc},
                 headers=headers, timeout=10, retries=1)
    try:
        if hasattr(r, "json"):
            amt, ccy = parse_xbox_price(r.json())
            if amt:
                return PriceRow("Xbox", title, cc_iso.upper(), ccy, float(amt),
                                f"https://www.xbox.com/{loc.split('-')[0]}/games/store/x/{store_id}", f"xbox:{store_id}", "Standard"), None
    except Exception:
        pass
    return None, MissRow("Xbox", title, cc_iso, "no_price")

# ----------------- PlayStation -----------------
PRODUCT_ID_RE = re.compile(r"/product/([^/?#]+)")
CROSSED_RE = re.compile(r"<del[^>]*>(.*?)</del>", re.I|re.S)

NEGATIVE_EDITIONS = ["deluxe","ultimate","premium","super","vault","gold","mvp","champion","bundle"]
PREFER_EDITIONS  = ["standard","standard edition","cross-gen","cross gen","crossgen","base game"]

def _html(url, locale=None):
    h = {"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "User-Agent": UA["User-Agent"]}
    if locale:
        lang = locale.split("-")[0]
        h["Accept-Language"] = f"{lang}-{locale.split('-')[-1].upper()},{lang};q=0.8"
    r = http_get(url, headers=h, timeout=10, retries=1)
    try: return r.text if hasattr(r,'text') and r.status_code==200 else None
    except Exception: return None

def _next_json(html):
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not tag or not tag.string: return None
    try: return json.loads(tag.string)
    except Exception: return None

def _num(x):
    try:
        if x is None: return None
        s = str(x).replace("\xa0","").replace(" ","").replace(",",".")
        return float(re.sub(r"[^\d.]", "", s)) if s else None
    except Exception: return None

def _score_edition(text:str)->int:
    t=(text or "").lower()
    score=0
    if any(k in t for k in ["cross-gen","cross gen","crossgen"]): score += 200
    if any(k in t for k in ["standard","standard edition","base game"]): score += 150
    if score==0 and any(k in t for k in NEGATIVE_EDITIONS): score -= 100
    return score

def _find_preferred_product_link(html:str, locale:str)->Tuple[Optional[str], Optional[str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    best=(None,None,-999)
    for a in soup.find_all("a", href=True):
        href=a["href"]
        if "/product/" not in href: continue
        label=a.get_text(" ", strip=True) or a.get("aria-label","")
        s=_score_edition(label)
        if s>best[2]:
            full = f"https://store.playstation.com/{locale}{href}" if href.startswith("/") else href
            best=(full, label, s)
    if best[0] and best[2] >= 0:
        return best[0], best[1]
    return None, None

PS_CCY_MAP={"US":"USD","AU":"AUD","DE":"EUR"}
PS_LOCALE={"US":"en-us","AU":"en-au","DE":"de-de"}

def fetch_playstation_price(ps_url: str, cc_iso: str, title: str, prefer_msrp=True):
    loc = PS_LOCALE.get(cc_iso.upper(),"en-us")
    url = ps_url

    # Load page
    html = _html(url, loc)
    if not html:
        return None, MissRow("PlayStation", title, cc_iso, "no_html")

    j = _next_json(html)
    msrp=price=curr=None; edition_label=None
    if j:
        try:
            props=j.get("props",{}).get("pageProps",{}); product=props.get("product") or {}
            edition_label=product.get("edition") or product.get("badge") or ""
            pb=product.get("price") or {}
            msrp=_num(pb.get("basePrice") or pb.get("regularPrice") or pb.get("originalPrice"))
            price=_num(pb.get("discountedPrice") or pb.get("finalPrice") or pb.get("current") or pb.get("value") or pb.get("priceValue"))
            curr=(pb.get("currency") or pb.get("priceCurrency"))
            if isinstance(curr,str): curr=curr.upper()
        except Exception: pass

    # If landed on Deluxe/Ultimate, hop to Standard/Cross-Gen
    label_for_score = (edition_label or title or "")
    if ("deluxe" in label_for_score.lower() or "ultimate" in label_for_score.lower() or "bundle" in label_for_score.lower()) or (edition_label=="" and "productList" in (j or {})):
        href, lab = _find_preferred_product_link(html, loc)
        if href and href!=url:
            html2=_html(href, loc)
            if html2:
                j2=_next_json(html2)
                if j2:
                    try:
                        props=j2.get("props",{}).get("pageProps",{}); product=props.get("product") or {}
                        edition_label=product.get("edition") or product.get("badge") or lab or "Standard"
                        pb=product.get("price") or {}
                        msrp=_num(pb.get("basePrice") or pb.get("regularPrice") or pb.get("originalPrice")) or msrp
                        price=_num(pb.get("discountedPrice") or pb.get("finalPrice") or pb.get("current") or pb.get("value") or pb.get("priceValue")) or price
                        curr=(pb.get("currency") or pb.get("priceCurrency") or curr)
                        if isinstance(curr,str): curr=curr.upper()
                        url=href
                    except Exception: pass

    # MSRP from <del> if needed
    if (msrp is None) and prefer_msrp:
        for raw in CROSSED_RE.findall(html or ""):
            v=_num(raw)
            if v:
                msrp = max(msrp or 0.0, v)

    chosen_currency = (curr or PS_CCY_MAP.get(cc_iso.upper(), "USD"))
    chosen_amount   = msrp if prefer_msrp and msrp is not None else (price if price is not None else msrp)
    if chosen_amount is not None:
        return PriceRow("PlayStation", title, cc_iso.upper(), chosen_currency, float(chosen_amount), url, f"ps:{title}", edition_label or "Standard"), None
    return None, MissRow("PlayStation", title, cc_iso, "no_price")

# ----------------- Mini basket -----------------
MARKETS = ["US","AU","DE"]

# Two titles — one Activision & one 2K to test edition/MSRP logic
STEAM_ITEMS = [
    ("Borderlands 4", "1285190"),
    ("HELLDIVERS 2", "553850")
]
XBOX_ITEMS = [
    ("Madden NFL 26", "9NVD16NP4J8T"),
    ("Borderlands 4", "9MX6HKF5647G"),
]
PS_ITEMS = [
    ("Madden NFL 26", "https://store.playstation.com/en-us/product/UP0006-PPSA26127_00-MADDENNFL26GAME0"),
    ("Borderlands 4", "https://store.playstation.com/en-us/product/UP1001-PPSA01494_00-0000000000000AK2"),
]

with st.sidebar:
    st.markdown("**Markets**: US, AU, DE")
    prefer_msrp = st.checkbox("Prefer MSRP (ignore discounts)", value=True)
    st.caption("If enabled, PS pulls use crossed-out MSRP or basePrice instead of discounted price.")
    run = st.button("Run mini test", type="primary")

if not run:
    st.caption("Click **Run mini test** to fetch prices for 2 games × 3 markets (Steam, Xbox, PlayStation).")
else:
    all_jobs = []
    for cc in MARKETS:
        for t,appid in STEAM_ITEMS: all_jobs.append(("Steam", cc, t, appid))
        for t,store in XBOX_ITEMS:  all_jobs.append(("Xbox", cc, t, store))
        for t,url in PS_ITEMS:      all_jobs.append(("PS",    cc, t, url))

    prog = st.progress(0.0)
    rows=[]; misses=[]
    with ThreadPoolExecutor(max_workers=9) as ex:
        futs=[]
        for plat, cc, title, ident in all_jobs:
            if plat=="Steam": futs.append(ex.submit(fetch_steam_price, ident, cc, title))
            elif plat=="Xbox": futs.append(ex.submit(fetch_xbox_price, title, ident, cc))
            else: futs.append(ex.submit(fetch_playstation_price, ident, cc, title, prefer_msrp))
        total=len(futs)
        done=0
        for f in as_completed(futs):
            try:
                pr, ms = f.result()
            except Exception:
                pr, ms = None, MissRow("unknown","unknown","unknown","exception")
            if pr: rows.append(pr)
            if ms: misses.append(ms)
            done+=1; prog.progress(done/total)

    df = pd.DataFrame([asdict(r) for r in rows])
    st.subheader("Results (raw)")
    st.dataframe(df, use_container_width=True)

    st.subheader("Diagnostics")
    if not df.empty:
        st.write("Success counts by platform:")
        st.write(df.groupby("platform")["country"].count().rename("rows").reset_index())
    if misses:
        md = pd.DataFrame([asdict(m) for m in misses])
        st.write("First reasons by platform:")
        st.write(md.groupby(["platform","reason"]).size().rename("count").reset_index())
    else:
        st.write("No misses 🎉")

    st.download_button("⬇️ Download CSV (raw results)",
                       df.to_csv(index=False).encode("utf-8"),
                       file_name="mini_test_results_v3_10.csv",
                       mime="text/csv")
