
# streamlit_app_combined_v3_6_minitest_hotfix_ps.py
# v3.6 (mini-test hotfix): faster run + PlayStation Standard/Cross-Gen preference + MSRP option

import re, json, time, random
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------- Page ----------
st.set_page_config(page_title="Game Pricing Recommendation Tool — v3.6 (Mini Hotfix)", page_icon="🎮", layout="wide")
st.title("🎮 Game Pricing Recommendation Tool — v3.6 Mini (Xbox · Steam · PlayStation)")

# ---------- HTTP helpers ----------
UA = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
def _ms_cv():
    import string
    return "".join(random.choice(string.ascii_letters+string.digits) for _ in range(24))

def http_get(url, params=None, headers=None, timeout=16, retries=1, backoff=0.4):
    last=None
    headers = {**UA, **(headers or {})}
    for i in range(retries+1):
        try:
            r=requests.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code==200:
                return r
            last=r
        except Exception as e:
            last=e
        time.sleep(backoff*(i+1))
    return last

# ---------- Static data ----------
COUNTRY_NAMES = {
    "US":"United States","CA":"Canada","MX":"Mexico","CL":"Chile","CO":"Colombia","PE":"Peru","CR":"Costa Rica","AR":"Argentina","UY":"Uruguay",
    "BO":"Bolivia","EC":"Ecuador","SV":"El Salvador","GT":"Guatemala","HN":"Honduras","NI":"Nicaragua","PA":"Panama","PY":"Paraguay","BR":"Brazil",
    "GB":"United Kingdom","IE":"Ireland","FR":"France","DE":"Germany","ES":"Spain","IT":"Italy","PT":"Portugal","NL":"Netherlands","BE":"Belgium","AT":"Austria",
    "CH":"Switzerland","LU":"Luxembourg","MT":"Malta","GR":"Greece","HR":"Croatia","HU":"Hungary","CZ":"Czech Republic","SK":"Slovakia","RO":"Romania","PL":"Poland",
    "BG":"Bulgaria","SI":"Slovenia","IS":"Iceland","SE":"Sweden","DK":"Denmark","NO":"Norway","FI":"Finland","AU":"Australia","NZ":"New Zealand",
    "JP":"Japan","KR":"Korea","SG":"Singapore","MY":"Malaysia","TH":"Thailand","ID":"Indonesia","TW":"Taiwan","HK":"Hong Kong","IN":"India","TR":"Türkiye","IL":"Israel",
    "SA":"Saudi Arabia","AE":"United Arab Emirates","ZA":"South Africa","UA":"Ukraine","RU":"Russia","CY":"Cyprus"}
def cname(code): return COUNTRY_NAMES.get(code.upper(), code.upper())

XBOX_LOCALE = {"US":"en-us","GB":"en-gb","CA":"en-ca","AU":"en-au","NZ":"en-nz","FR":"fr-fr","DE":"de-de","ES":"es-es","IT":"it-it","JP":"ja-jp",
               "BR":"pt-br","MX":"es-mx","AE":"ar-ae","SA":"ar-sa","PL":"pl-pl","PT":"pt-pt","NL":"nl-nl","SE":"sv-se","NO":"no-no","DK":"da-dk","FI":"fi-fi"}
def xbox_locale(cc): return XBOX_LOCALE.get(cc.upper(),"en-us")

# Verified PS currency mapping (based on provided spreadsheet + fixes)
PS_CCY_MAP: Dict[str,str] = {
    # Americas
    "US":"USD","CA":"CAD","MX":"MXN","BR":"BRL","AR":"ARS","CL":"CLP","CO":"COP","PE":"PEN","UY":"UYU",
    "CR":"CRC","GT":"GTQ","HN":"HNL","NI":"NIO","PA":"USD","PY":"PYG","SV":"USD","DO":"DOP","BO":"BOB",
    # Europe
    "GB":"GBP","IE":"EUR","FR":"EUR","DE":"EUR","ES":"EUR","IT":"EUR","PT":"EUR","NL":"EUR","BE":"EUR","AT":"EUR","CH":"CHF","LU":"EUR",
    "GR":"EUR","HR":"EUR","HU":"HUF","CZ":"CZK","SK":"EUR","RO":"RON","PL":"PLN","BG":"BGN","SI":"EUR","CY":"EUR",
    "IS":"ISK","SE":"SEK","DK":"DKK","NO":"NOK","FI":"EUR","UA":"UAH",
    # APAC / MEA
    "AU":"AUD","NZ":"NZD","JP":"JPY","KR":"KRW","SG":"SGD","MY":"MYR","TH":"THB","ID":"IDR","TW":"TWD","HK":"HKD","IN":"INR",
    "TR":"TRY","IL":"ILS","SA":"SAR","AE":"AED","ZA":"ZAR"
}
def ps_meta(cc):
    loc_by_cc = {"US":"en-us","GB":"en-gb","CA":"en-ca","AU":"en-au","NZ":"en-nz","IE":"en-ie","SG":"en-sg","MY":"en-my",
        "HK":"en-hk","IN":"en-in","AE":"en-ae","SA":"ar-sa","TR":"tr-tr","IL":"en-il","JP":"ja-jp","KR":"ko-kr","TW":"zh-tw",
        "FR":"fr-fr","DE":"de-de","ES":"es-es","IT":"it-it","PT":"pt-pt","NL":"nl-nl","BE":"nl-be","AT":"de-at","CH":"de-ch",
        "DK":"da-dk","NO":"no-no","SE":"sv-se","FI":"fi-fi","PL":"pl-pl","CZ":"cs-cz","HU":"hu-hu","RO":"ro-ro","GR":"el-gr",
        "BG":"bg-bg","SI":"sl-si","SK":"sk-sk","HR":"hr-hr","LU":"fr-lu","MT":"en-mt","CY":"en-cy","IS":"is-is",
        "AR":"es-ar","CL":"es-cl","CO":"es-co","PE":"es-pe","UY":"es-uy","CR":"es-cr","GT":"es-gt","SV":"es-sv","HN":"es-hn","NI":"es-ni","PA":"es-pa","PY":"es-py",
        "MX":"es-mx","BR":"pt-br","UA":"uk-ua","ZA":"en-za"}
    return loc_by_cc.get(cc.upper(),"en-us"), PS_CCY_MAP.get(cc.upper(),"USD")

# Vanity rules
ZERO_DECIMAL={"JPY","KRW","HUF","ISK","CLP"}
HUNDRED_STEP={"IDR","VND"}
NEAREST5={"BRL","RUB","INR"}
SUFFIX_99={"USD","EUR","GBP","CAD","SEK","NOK","DKK","CZK","PLN","CHF"}
SUFFIX_95={"AUD","NZD"}
def _force_suffix(p,s): w=int(p); return (w+s) if (w+s)>p else (w+1+s)
def apply_vanity_currency(cur, val):
    if val is None: return None
    c=(cur or "").upper(); p=float(val)
    if c in ZERO_DECIMAL: return float(int(round(p)))
    if c in HUNDRED_STEP: return float(int(round(p/100.0))*100)
    if c in NEAREST5: return float(int(round(p/5.0))*5)
    if c in SUFFIX_95: return round(_force_suffix(p,0.95),2)
    if c in SUFFIX_99: return round(_force_suffix(p,0.99),2)
    return round(p,2)

# FX
def fx_rates():
    if "fx" in st.session_state and time.time()-st.session_state.get("fx_ts",0)<7200:
        return st.session_state["fx"]
    out={"USD":1.0}
    for url in ["https://api.exchangerate.host/latest?base=USD","https://open.er-api.com/v6/latest/USD"]:
        try:
            r=http_get(url, timeout=12, retries=1).json()
            rates=r.get("rates")
            if rates:
                for k,v in rates.items():
                    if isinstance(v,(int,float)) and v>0: out[k.upper()]=float(v)
                break
        except Exception: pass
    st.session_state["fx"]=out; st.session_state["fx_ts"]=time.time(); return out

def to_usd(amount, currency, rates):
    if amount is None or not currency: return None
    r=rates.get(str(currency).upper())
    return round(float(amount)/r,2) if r else None

# ---------- Data classes ----------
@dataclass
class PriceRow:
    platform:str; title:str; country:str; currency:Optional[str]; price:Optional[float]; source_url:Optional[str]; identity:str; currency_source:str="page"
@dataclass
class MissRow:
    platform:str; title:str; country:str; reason:str

# ---------- Steam ----------
def fetch_steam_price(appid, cc_iso, title=None):
    try:
        j=http_get("https://store.steampowered.com/api/appdetails",
                   params={"appids":appid,"cc":cc_iso,"l":"en"}, timeout=12).json()
        node=j.get(str(appid),{})
        if not node.get("success"): return None, MissRow("Steam", title or appid, cc_iso, "no_data")
        pov=(node.get("data") or {}).get("price_overview") or {}
        cents=pov.get("initial") or pov.get("final")
        if cents:
            price=round(cents/100.0,2); ccy=(pov.get("currency") or "").upper() or None
            return PriceRow("Steam", title or "Steam App", cc_iso.upper(), ccy, price, f"https://store.steampowered.com/app/{appid}", f"steam:{appid}"), None
        return None, MissRow("Steam", title or appid, cc_iso, "no_price")
    except Exception:
        return None, MissRow("Steam", title or appid, cc_iso, "exception")

# ---------- Xbox ----------
def parse_xbox_price(payload: Dict[str,Any]):
    try:
        prods=payload.get("Products") or payload.get("products") or []
        if not prods: return None, None
        p0=prods[0]
        for sku in p0.get("DisplaySkuAvailabilities",[]) or p0.get("displaySkuAvailabilities",[]):
            for av in sku.get("Availabilities",[]) or sku.get("availabilities",[]):
                pr=(av.get("OrderManagementData") or av.get("orderManagementData") or {}).get("Price") or {}
                amt=pr.get("MSRP") or pr.get("ListPrice") or pr.get("msrp") or pr.get("listPrice")
                ccy=pr.get("CurrencyCode") or pr.get("currencyCode")
                if amt: return float(amt), (ccy and str(ccy).upper())
    except Exception:
        pass
    return None, None

def fetch_xbox_price(title, store_id, cc_iso):
    loc=xbox_locale(cc_iso); headers={"MS-CV":_ms_cv(),"Accept":"application/json"}
    r=http_get("https://storeedgefd.dsx.mp.microsoft.com/v9.0/sdk/products",
               params={"bigIds":store_id,"market":cc_iso,"locale":loc}, headers=headers, timeout=12, retries=1)
    try:
        if hasattr(r,"json"):
            amt,ccy=parse_xbox_price(r.json())
            if amt:
                return PriceRow("Xbox", title or "Xbox Product", cc_iso.upper(), ccy, float(amt),
                                f"https://www.xbox.com/{loc.split('-')[0]}/games/store/x/{store_id}", f"xbox:{store_id}"), None
    except Exception:
        pass
    r2=http_get("https://displaycatalog.mp.microsoft.com/v7.0/products",
                params={"bigIds":store_id,"market":cc_iso,"languages":"en-US","fieldsTemplate":"Details"},
                headers=headers, timeout=12, retries=1)
    try:
        if hasattr(r2,"json"):
            amt,ccy=parse_xbox_price(r2.json())
            if amt:
                return PriceRow("Xbox", title or "Xbox Product", cc_iso.upper(), ccy, float(amt),
                                f"https://www.xbox.com/en-us/games/store/x/{store_id}", f"xbox:{store_id}"), None
    except Exception:
        pass
    return None, MissRow("Xbox", title or store_id, cc_iso, "no_price")

# ---------- PlayStation (hotfix) ----------
PRODUCT_ID_RE=re.compile(r"/product/([^/?#]+)")
PRICE_RE=re.compile(r'"(?:basePrice|regularPrice|originalPrice|discountedPrice|finalPrice|current|value|priceValue)"\s*:\s*("?)([0-9]+(?:[.,][0-9]+)?)\1', re.I)
CROSSED_RE=re.compile(r"<del[^>]*>([^<]+)</del>", re.I)

NEGATIVE_EDITIONS=[ "deluxe","ultimate","premium","super","vault","gold","mvp","champion","bundle","edition bundle"]
PREFER_EDITIONS=[ "standard","standard edition","cross-gen","cross gen","crossgen","base game","online" ]

CUR_HINTS={"$":"USD","CAD$":"CAD","A$":"AUD","NZ$":"NZD","R$":"BRL","€":"EUR","£":"GBP","₺":"TRY","zł":"PLN","kr":"SEK","CHF":"CHF",
"HK$":"HKD","NT$":"TWD","₩":"KRW","¥":"JPY","₪":"ILS","AED":"AED","SAR":"SAR","MXN":"MXN","ARS":"ARS","CLP":"CLP","COP":"COP","PEN":"PEN",
"UYU":"UYU","CRC":"CRC","GTQ":"GTQ","HNL":"HNL","NIO":"NIO","PYG":"PYG","DOP":"DOP","BOB":"BOB","ZAR":"ZAR","MYR":"MYR","THB":"THB",
"IDR":"IDR","PHP":"PHP","VND":"VND","INR":"INR","NOK":"NOK","DKK":"DKK","RUB":"RUB","UAH":"UAH","QAR":"QAR","KWD":"KWD","OMR":"OMR","BHD":"BHD","JOD":"JOD","EGP":"EGP","ISK":"ISK","ILS":"ILS"}

def _html(url, locale=None):
    h={"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","User-Agent":UA["User-Agent"]}
    if locale:
        lang=locale.split("-")[0]; h["Accept-Language"]=f"{lang}-{locale.split('-')[-1].upper()},{lang};q=0.8"
    r=http_get(url, headers=h, timeout=12, retries=1)
    try: return r.text if hasattr(r,"text") and r.status_code==200 else None
    except Exception: return None

def _next_json(html):
    soup=BeautifulSoup(html,"html.parser")
    tag=soup.find("script",id="__NEXT_DATA__",type="application/json")
    if not tag or not tag.string: return None
    try:
        return json.loads(tag.string)
    except Exception:
        return None

def _num(x):
    try:
        if x is None: return None
        s=str(x).replace("\xa0","").replace(" ","").replace(",",".")
        return float(re.sub(r"[^\d.]", "", s)) if s else None
    except Exception: return None

def _scan_json_ld(html):
    soup=BeautifulSoup(html,"html.parser")
    scripts=soup.find_all("script", type="application/ld+json")
    title=None; price=None; curr=None; msrp=None
    for s in scripts:
        try: data=json.loads(s.string) if s.string else None
        except Exception: continue
        if not data: continue
        items=data if isinstance(data,list) else [data]
        for obj in items:
            if not isinstance(obj,dict): continue
            if not title: title=obj.get("name") or obj.get("headline")
            offers=obj.get("offers")
            if isinstance(offers, dict):
                if not curr: curr=(offers.get("priceCurrency") or offers.get("currency"))
                if not price: price=_num(offers.get("price"))
            elif isinstance(offers, list):
                for off in offers:
                    if not isinstance(off, dict): continue
                    if not curr: curr=(off.get("priceCurrency") or off.get("currency"))
                    if not price: price=_num(off.get("price"))
                    if price is not None: break
    return title, msrp, price, (curr and str(curr).upper())

def _fallback_prices(html):
    msrp=price=curr=None
    cross=CROSSED_RE.findall(html or "") or []
    cross_vals=[_num(x) for x in cross if _num(x)]
    # current/discount
    for m in PRICE_RE.finditer(html or ""):
        val=_num(m.group(2))
        ctx=(html or "")[max(0,m.start()-60):m.start()].lower()
        if any(k in ctx for k in ["baseprice","regularprice","originalprice"]) and msrp is None: msrp=val
        if any(k in ctx for k in ["discountedprice","finalprice","current","value","pricevalue"]) and price is None: price=val
    if msrp is None and cross_vals: msrp=max(cross_vals)
    if price is None and msrp is None and cross_vals: price=min(cross_vals)
    if curr is None:
        soup=BeautifulSoup(html or "","html.parser")
        token=(soup.find(attrs={"data-qa":"mfeCtaMain#offer0#displayPrice"}) or {}).get_text("",strip=True) if soup else ""
        for hint,c in CUR_HINTS.items():
            if token and hint in token: curr=c; break
    return msrp, price, curr

def _resolve_concept(concept_url, locale):
    html=_html(concept_url, locale)
    if not html: return None
    soup=BeautifulSoup(html,"html.parser")
    def score(a):
        t=a.get_text(" ",strip=True).lower()
        s=0
        if any(k in t for k in PREFER_EDITIONS): s+=100
        if any(k in t for k in NEGATIVE_EDITIONS): s-=100
        return s
    best=("","-inf")
    for a in soup.find_all("a",href=True):
        if "/product/" not in a["href"]: continue
        sc=score(a)
        if sc>best[1]:
            href=a["href"]
            url=f"https://store.playstation.com/{locale}{href}" if href.startswith("/") else href
            best=(url,sc)
    return best[0] or None

def _ps_candidates(pid):
    cands=[pid]
    if pid.startswith("UP"): cands.append("EP"+pid[2:])
    elif pid.startswith("EP"): cands.append("UP"+pid[2:])
    return list(dict.fromkeys(cands))

def fetch_playstation_price(ps_ref, cc_iso, title=None, prefer_msrp=True):
    base_locale, cur_fb = ps_meta(cc_iso)
    ref=(ps_ref or "").strip()
    if ref.startswith("http") and "/concept/" in ref:
        r=_resolve_concept(ref, base_locale)
        if r: ref=r
    pid=None
    if ref:
        if ref.startswith("http"):
            m=PRODUCT_ID_RE.search(ref); pid=m and m.group(1)
        else: pid=ref
    if not pid: return None, MissRow("PlayStation", title or "unknown", cc_iso, "no_id")
    locales_try=[base_locale,"en-us","en-gb"]
    pids_try=_ps_candidates(pid)

    name=None; msrp=price=curr=None; best_url=None; currency_source="mapped"
    for loc in locales_try:
        for cand in pids_try:
            url=f"https://store.playstation.com/{loc}/product/{cand}"
            html=_html(url, loc)
            if not html: continue

            low = html.lower()
            if any(k in low for k in NEGATIVE_EDITIONS):
                sibling=_resolve_concept(url.replace("/product/","/concept/"), loc)
                if sibling and sibling!=url:
                    html=_html(sibling, loc) or html
                    url=sibling

            j=_next_json(html)
            if j:
                props=j.get("props",{}).get("pageProps",{})
                product=props.get("product") or {}
                if not name: name=product.get("name") or props.get("title")
                pb=product.get("price") or {}
                base=_num(pb.get("basePrice") or pb.get("regularPrice") or pb.get("originalPrice"))
                disc=_num(pb.get("discountedPrice") or pb.get("finalPrice") or pb.get("current") or pb.get("value") or pb.get("priceValue"))
                cur=(pb.get("currency") or pb.get("priceCurrency"))
                if isinstance(cur,str): cur=cur.upper()
                if base is not None: msrp=base
                if disc is not None and price is None: price=disc
                if cur and not curr: curr=cur; currency_source="page"

            t2,m2,p2,c2=_scan_json_ld(html)
            if t2 and not name: name=t2
            if m2 is not None and msrp is None: msrp=m2
            if p2 is not None and price is None: price=p2
            if c2 and not curr: curr=c2; currency_source="page"

            m3,p3,c3=_fallback_prices(html)
            if m3 is not None and msrp is None: msrp=m3
            if p3 is not None and price is None: price=p3
            if c3 and not curr: curr=c3; currency_source="page"

            if msrp is not None or price is not None:
                best_url=url; break
        if best_url: break

    if not curr: curr=PS_CCY_MAP.get(cc_iso.upper(), cur_fb); currency_source="mapped"

    if prefer_msrp and msrp is None and price is not None:
        msrp=max(price, msrp or 0.0)

    amt = msrp if prefer_msrp and msrp is not None else (msrp if msrp is not None else price)
    if amt is None:
        return None, MissRow("PlayStation", title or (name or f"PS {pid}"), cc_iso, "no_price")
    return PriceRow("PlayStation", title or (name or f"PS {pid}"), cc_iso.upper(), curr, float(amt), best_url or ref, f"ps:{ref or pid}", currency_source), None

# ---------- Default baskets ----------
DEFAULT_STEAM=[
    {"include":True,"title":"The Outer Worlds 2","appid":"1449110","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"Madden NFL 26","appid":"3230400","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"Call of Duty: Black Ops 6","appid":"2933620","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"NBA 2K26","appid":"3472040","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"Borderlands 4","appid":"1285190","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"HELLDIVERS 2","appid":"553850","scale_factor":1.75,"weight":1.0},
]
DEFAULT_XBOX=[
    {"include":True,"title":"The Outer Worlds 2","store_id":"9NSPRSXXZZLG","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"Madden NFL 26","store_id":"9NVD16NP4J8T","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"Call of Duty: Black Ops 6","store_id":"9PNCL2R6G8D0","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"NBA 2K26","store_id":"9PJ2RVRC0L1X","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"Borderlands 4","store_id":"9MX6HKF5647G","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"HELLDIVERS 2","store_id":"9P3PT7PQJD0M","scale_factor":1.75,"weight":1.0},
]
DEFAULT_PS=[
    {"include":True,"title":"The Outer Worlds 2","ps_ref":"https://store.playstation.com/en-us/product/UP6312-PPSA16483_00-OW2STANDARDPS5US","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"Madden NFL 26","ps_ref":"https://store.playstation.com/en-ca/product/UP0006-PPSA26127_00-MADDENNFL26GAME0","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"Call of Duty: Black Ops 6","ps_ref":"https://store.playstation.com/en-us/product/UP0002-PPSA17544_00-BO6CROSSGENBUNDLE","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"NBA 2K26","ps_ref":"https://store.playstation.com/en-hk/product/UP1001-PPSA28420_00-NBA2K260000000000","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"Borderlands 4","ps_ref":"https://store.playstation.com/en-us/concept/10000819","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"HELLDIVERS 2","ps_ref":"https://store.playstation.com/en-us/product/UP9000-PPSA14719_00-ARROWHEADGAAS000","scale_factor":1.75,"weight":1.0},
]

# ---------- Sidebar / Controls ----------
with st.sidebar:
    st.header("Controls")
    default_markets=",".join(sorted(COUNTRY_NAMES.keys()))
    user_markets=st.text_area("Markets (comma-separated ISO country codes)", value=default_markets, height=120)
    markets=[m.strip().upper() for m in user_markets.split(",") if m.strip()]

    quick = st.checkbox("Quick run (top 10 markets)", value=True,
                        help="US, CA, GB, FR, DE, AU, NZ, BR, JP, KR")
    if quick:
        preferred = ["US","CA","GB","FR","DE","AU","NZ","BR","JP","KR"]
        markets = [m for m in preferred if m in markets][:10]

    prefer_msrp=st.checkbox("Prefer MSRP (ignore discounts)", value=True)

    if "steam_rows" not in st.session_state: st.session_state.steam_rows=DEFAULT_STEAM.copy()
    if "xbox_rows"  not in st.session_state: st.session_state.xbox_rows=DEFAULT_XBOX.copy()
    if "ps_rows"    not in st.session_state: st.session_state.ps_rows=DEFAULT_PS.copy()

    st.subheader("Steam basket")
    st.session_state.steam_rows = st.data_editor(pd.DataFrame(st.session_state.steam_rows), key="steam_editor", num_rows="dynamic", use_container_width=True).to_dict("records")
    st.subheader("Xbox basket")
    st.session_state.xbox_rows  = st.data_editor(pd.DataFrame(st.session_state.xbox_rows), key="xbox_editor",  num_rows="dynamic", use_container_width=True).to_dict("records")
    st.subheader("PlayStation basket")
    st.session_state.ps_rows    = st.data_editor(pd.DataFrame(st.session_state.ps_rows), key="ps_editor",   num_rows="dynamic", use_container_width=True).to_dict("records")

    run = st.button("Run Pricing Pull", type="primary")

# ---------- Helpers ----------
def fx_view(df, label):
    rates=fx_rates()
    if df.empty:
        return pd.DataFrame(columns=["platform","country_name","country","currency","RecommendedPrice","USDPrice","DiffUSD"])
    us=df.loc[df["country"]=="US"]
    out=df[["country","currency","RecommendedPrice"]].copy()
    out["USDPrice"]=[to_usd(p,c,rates) for p,c in zip(out["RecommendedPrice"],out["currency"])]
    if not us.empty:
        us_usd=to_usd(float(us["RecommendedPrice"].iloc[0]), str(us["currency"].iloc[0]), rates)
        out["DiffUSD"]=[None if pd.isna(v) else round(v-us_usd,2) for v in out["USDPrice"]]
    else:
        out["DiffUSD"]=None
    out.insert(0,"platform",label); out.insert(1,"country_name",out["country"].map(cname))
    return out.sort_values("country_name").reset_index(drop=True)

# ---------- Run ----------
if run:
    steam_rows=[r for r in st.session_state.steam_rows if r.get("include") and r.get("appid")]
    xbox_rows=[r for r in st.session_state.xbox_rows if r.get("include") and r.get("store_id")]
    ps_rows=[r for r in st.session_state.ps_rows if r.get("include") and (r.get("ps_ref") or r.get("title"))]

    rows=[]; misses=[]
    with st.status("Pulling prices across markets…"):
        futs=[]
        with ThreadPoolExecutor(max_workers=12) as ex:
            for cc in markets:
                for r in steam_rows: futs.append(ex.submit(fetch_steam_price, r["appid"], cc, r.get("title")))
                for r in xbox_rows:  futs.append(ex.submit(fetch_xbox_price,  r.get("title"), r["store_id"], cc))
                for r in ps_rows:    futs.append(ex.submit(fetch_playstation_price, r.get("ps_ref",""), cc, r.get("title"), prefer_msrp))
            for f in as_completed(futs):
                try: pr, miss = f.result()
                except Exception: pr, miss = None, MissRow("unknown","unknown","unknown","exception")
                if pr: rows.append(pr)
                if miss: misses.append(miss)

    raw=pd.DataFrame([asdict(r) for r in rows])
    if not raw.empty:
        meta={}
        for r in steam_rows: meta[f"steam:{r['appid']}"]={"scale":float(r.get("scale_factor",1.0)),"weight":float(r.get("weight",1.0))}
        for r in xbox_rows:  meta[f"xbox:{r['store_id']}"]={"scale":float(r.get("scale_factor",1.0)),"weight":float(r.get("weight",1.0))}
        for r in ps_rows:    meta[f"ps:{(r.get('ps_ref') or r.get('title'))}"]={"scale":float(r.get("scale_factor",1.0)),"weight":float(r.get("weight",1.0))}

        raw.insert(2,"country_name",raw["country"].map(cname))
        raw["scale"]=raw["identity"].map(lambda i: meta.get(i,{}).get("scale",1.0))
        raw["weight"]=raw["identity"].map(lambda i: meta.get(i,{}).get("weight",1.0))
        raw["price"]=raw["price"]*raw["scale"]

        st.subheader("Raw Basket Rows (after scaling)")
        st.dataframe(raw, use_container_width=True)

        grp=raw.groupby(["platform","country","currency"], dropna=False)
        sums=grp.apply(lambda g:(g["price"]*g["weight"]).sum()).rename("weighted_sum")
        wts=grp["weight"].sum().rename("weight_total")
        reco=pd.concat([sums,wts],axis=1).reset_index()
        reco["RecommendedPrice"]=reco.apply(lambda r:(r["weighted_sum"]/r["weight_total"]) if r["weight_total"]>0 else None, axis=1)
        reco=reco[["platform","country","currency","RecommendedPrice"]]
        reco["RecommendedPrice"]=[apply_vanity_currency(cur, val) if pd.notna(val) else val for cur,val in zip(reco["currency"],reco["RecommendedPrice"])]

        xdf=reco[reco["platform"]=="Xbox"].copy();    xdf.insert(1,"country_name",xdf["country"].map(cname))
        sdf=reco[reco["platform"]=="Steam"].copy();   sdf.insert(1,"country_name",sdf["country"].map(cname))
        pdf=reco[reco["platform"]=="PlayStation"].copy(); pdf.insert(1,"country_name",pdf["country"].map(cname))

        st.subheader("Xbox Regional Pricing Recommendation");   st.dataframe(fx_view(xdf, "Xbox"), use_container_width=True)
        st.subheader("Steam Regional Pricing Recommendation");  st.dataframe(fx_view(sdf, "Steam"), use_container_width=True)
        st.subheader("PlayStation Regional Pricing Recommendation"); st.dataframe(fx_view(pdf, "PlayStation"), use_container_width=True)

        merged=xdf.rename(columns={"RecommendedPrice":"XboxRecommended"})
        merged=pd.merge(merged, sdf.rename(columns={"RecommendedPrice":"SteamRecommended"}), on=["country_name","country","currency"], how="outer")
        merged=pd.merge(merged, pdf.rename(columns={"RecommendedPrice":"PSRecommended"}), on=["country_name","country","currency"], how="outer")
        merged=merged.sort_values("country_name").reset_index(drop=True)
        st.subheader("Combined Recommendations (Xbox + Steam + PlayStation)")
        st.dataframe(merged, use_container_width=True)

        st.download_button("⬇️ Download CSV (combined recommendations)",
                           merged.to_csv(index=False).encode("utf-8"),
                           file_name="aaa_tier_recommendations_xsx_steam_ps_v3_6_minitest_hotfix.csv",
                           mime="text/csv")

    if misses:
        st.subheader("Diagnostics (no price found)")
        st.dataframe(pd.DataFrame([asdict(m) for m in misses]), use_container_width=True)
else:
    st.caption("Tip: use Quick run (top 10) while we validate PlayStation pulls for OW2, BO6, NBA 2K26, and HELLDIVERS 2.")
