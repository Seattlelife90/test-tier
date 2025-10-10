
# streamlit_app_combined_v3_6_playstation_repair.py
# Combined app (Xbox + Steam + PlayStation) with PlayStation fixed to use PRODUCT IDs only.
# PS logic is simplified and robust (v1.7-style) and prefers MSRP (with fallback).

import re, json, time, random
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------- Page ----------------
st.set_page_config(page_title="Game Pricing Recommendation Tool — v3.6 (PlayStation repair)", page_icon="🎮", layout="wide")
st.title("🎮 Game Pricing Recommendation Tool — v3.6 (PlayStation repair)")

# ---------------- HTTP ----------------
UA = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
def http_get(url, headers=None, timeout=14):
    try:
        h = {**UA, **(headers or {})}
        r = requests.get(url, headers=h, timeout=timeout)
        if r.status_code == 200: return r
    except Exception:
        pass
    return None

# ---------------- Static data ----------------
COUNTRY_LOCALE = {
    # Americas
    "US":"en-us","CA":"en-ca","MX":"es-mx","AR":"es-ar","BR":"pt-br","CL":"es-cl","CO":"es-co","PE":"es-pe","UY":"es-uy",
    "CR":"es-cr","GT":"es-gt","HN":"es-hn","NI":"es-ni","PA":"es-pa","PY":"es-py","SV":"es-sv","DO":"es-do","BO":"es-bo",
    # Europe
    "GB":"en-gb","IE":"en-ie","FR":"fr-fr","DE":"de-de","ES":"es-es","IT":"it-it","PT":"pt-pt","NL":"nl-nl","BE":"nl-be","AT":"de-at",
    "CH":"de-ch","LU":"fr-lu","GR":"el-gr","HR":"hr-hr","HU":"hu-hu","CZ":"cs-cz","SK":"sk-sk","RO":"ro-ro","PL":"pl-pl",
    "BG":"bg-bg","SI":"sl-si","CY":"en-cy","IS":"is-is","SE":"sv-se","DK":"da-dk","NO":"no-no","FI":"fi-fi","UA":"uk-ua",
    # APAC / MEA
    "AU":"en-au","NZ":"en-nz","JP":"ja-jp","KR":"ko-kr","SG":"en-sg","MY":"en-my","TH":"th-th","ID":"id-id","TW":"zh-tw","HK":"en-hk",
    "IN":"en-in","TR":"tr-tr","IL":"en-il","SA":"ar-sa","AE":"en-ae","ZA":"en-za"
}
COUNTRY_NAME = {
    "US":"United States","CA":"Canada","MX":"Mexico","AR":"Argentina","BR":"Brazil","CL":"Chile","CO":"Colombia","PE":"Peru","UY":"Uruguay",
    "CR":"Costa Rica","GT":"Guatemala","HN":"Honduras","NI":"Nicaragua","PA":"Panama","PY":"Paraguay","SV":"El Salvador","DO":"Dominican Republic","BO":"Bolivia",
    "GB":"United Kingdom","IE":"Ireland","FR":"France","DE":"Germany","ES":"Spain","IT":"Italy","PT":"Portugal","NL":"Netherlands","BE":"Belgium","AT":"Austria",
    "CH":"Switzerland","LU":"Luxembourg","GR":"Greece","HR":"Croatia","HU":"Hungary","CZ":"Czech Republic","SK":"Slovakia","RO":"Romania","PL":"Poland",
    "BG":"Bulgaria","SI":"Slovenia","CY":"Cyprus","IS":"Iceland","SE":"Sweden","DK":"Denmark","NO":"Norway","FI":"Finland","UA":"Ukraine",
    "AU":"Australia","NZ":"New Zealand","JP":"Japan","KR":"Korea","SG":"Singapore","MY":"Malaysia","TH":"Thailand","ID":"Indonesia","TW":"Taiwan","HK":"Hong Kong",
    "IN":"India","TR":"Türkiye","IL":"Israel","SA":"Saudi Arabia","AE":"United Arab Emirates","ZA":"South Africa"
}
PS_CCY = {
    "US":"USD","CA":"CAD","MX":"MXN","AR":"ARS","BR":"BRL","CL":"CLP","CO":"COP","PE":"PEN","UY":"UYU","CR":"CRC","GT":"GTQ","HN":"HNL","NI":"NIO","PA":"USD","PY":"PYG","SV":"USD","DO":"DOP","BO":"BOB",
    "GB":"GBP","IE":"EUR","FR":"EUR","DE":"EUR","ES":"EUR","IT":"EUR","PT":"EUR","NL":"EUR","BE":"EUR","AT":"EUR","CH":"CHF","LU":"EUR","GR":"EUR","HR":"EUR","HU":"HUF","CZ":"CZK","SK":"EUR","RO":"RON","PL":"PLN","BG":"BGN","SI":"EUR","CY":"EUR","IS":"ISK","SE":"SEK","DK":"DKK","NO":"NOK","FI":"EUR","UA":"UAH",
    "AU":"AUD","NZ":"NZD","JP":"JPY","KR":"KRW","SG":"SGD","MY":"MYR","TH":"THB","ID":"IDR","TW":"TWD","HK":"HKD","IN":"INR",
    "TR":"TRY","IL":"ILS","SA":"SAR","AE":"AED","ZA":"ZAR"
}
def cname(cc): return COUNTRY_NAME.get(cc.upper(), cc.upper())
def plocale(cc): return COUNTRY_LOCALE.get(cc.upper(), "en-us")

# Vanity pricing
ZERO_DEC={"JPY","KRW","HUF","ISK","CLP"}; STEP100={"IDR","VND"}; NEAR5={"BRL","INR","RUB"}
SUF99={"USD","EUR","GBP","CAD","SEK","NOK","DKK","CZK","PLN","CHF"}; SUF95={"AUD","NZD"}
def _force_suffix(p,s): w=int(p); return (w+s) if (w+s)>p else (w+1+s)
def vanity(cur, val):
    if val is None: return None
    c=str(cur).upper(); p=float(val)
    if c in ZERO_DEC: return float(int(round(p)))
    if c in STEP100:  return float(int(round(p/100.0))*100)
    if c in NEAR5:    return float(int(round(p/5.0))*5)
    if c in SUF95:    return round(_force_suffix(p,0.95),2)
    if c in SUF99:    return round(_force_suffix(p,0.99),2)
    return round(p,2)

# FX
def fx_rates():
    if "fx" in st.session_state and time.time()-st.session_state.get("fx_ts",0)<7200: return st.session_state["fx"]
    out={"USD":1.0}
    for url in ["https://api.exchangerate.host/latest?base=USD","https://open.er-api.com/v6/latest/USD"]:
        try:
            r=requests.get(url,timeout=10).json(); rates=r.get("rates",{})
            if rates:
                for k,v in rates.items():
                    if isinstance(v,(int,float)) and v>0: out[k.upper()]=float(v)
                break
        except Exception: pass
    st.session_state["fx"]=out; st.session_state["fx_ts"]=time.time(); return out
def to_usd(amount, currency, rates):
    if amount is None or not currency: return None
    r=rates.get(str(currency).upper()); return round(float(amount)/r,2) if r else None

# ---------------- Data classes ----------------
@dataclass
class PriceRow:
    platform:str; title:str; country:str; currency:Optional[str]; price:Optional[float]; source_url:Optional[str]; identity:str; edition:str="Standard"; currency_source:str="page"
@dataclass
class MissRow:
    platform:str; title:str; country:str; reason:str

# ---------------- Steam ----------------
def fetch_steam_price(appid, cc_iso, title=None):
    try:
        j=requests.get("https://store.steampowered.com/api/appdetails", params={"appids":appid,"cc":cc_iso,"l":"en"}, timeout=10).json()
        node=j.get(str(appid),{}); 
        if not node.get("success"): return None, MissRow("Steam", title or appid, cc_iso, "no_data")
        pov=(node.get("data") or {}).get("price_overview") or {}
        cents=pov.get("initial") or pov.get("final")
        if cents:
            price=round(cents/100.0,2); ccy=(pov.get("currency") or "").upper() or None
            return PriceRow("Steam", title or "Steam App", cc_iso.upper(), ccy, price, f"https://store.steampowered.com/app/{appid}", f"steam:{appid}"), None
        return None, MissRow("Steam", title or appid, cc_iso, "no_price")
    except Exception:
        return None, MissRow("Steam", title or appid, cc_iso, "exception")

# ---------------- Xbox ----------------
def _ms_cv():
    import string
    return "".join(random.choice(string.ascii_letters+string.digits) for _ in range(24))

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
    except Exception: pass
    return None, None

def fetch_xbox_price(title, store_id, cc_iso):
    loc=COUNTRY_LOCALE.get(cc_iso.upper(),"en-us")
    headers={"MS-CV":_ms_cv(),"Accept":"application/json", **UA}
    r=requests.get("https://storeedgefd.dsx.mp.microsoft.com/v9.0/sdk/products",
                   params={"bigIds":store_id,"market":cc_iso,"locale":loc}, headers=headers, timeout=10)
    try:
        amt,ccy=parse_xbox_price(r.json())
        if amt:
            return PriceRow("Xbox", title or "Xbox Product", cc_iso.upper(), ccy, float(amt),
                            f"https://www.xbox.com/{loc.split('-')[0]}/games/store/x/{store_id}", f"xbox:{store_id}"), None
    except Exception: pass
    return None, MissRow("Xbox", title or store_id, cc_iso, "no_price")

# ---------------- PlayStation (PRODUCT-ID ONLY) ----------------
PRODUCT_PRICE_RE = re.compile(r'"(basePrice|regularPrice|originalPrice|discountedPrice|finalPrice|current|value|priceValue)"\s*:\s*"?([0-9]+(?:[.,][0-9]+)?)"?', re.I)
CROSSED_RE = re.compile(r"<del[^>]*>([^<]+)</del>", re.I)
SYMBOLS = {"$":"USD","CAD$":"CAD","A$":"AUD","NZ$":"NZD","€":"EUR","£":"GBP","R$":"BRL","HK$":"HKD","NT$":"TWD","¥":"JPY","₩":"KRW","₪":"ILS","₺":"TRY"}

def _num(s):
    try:
        if s is None: return None
        s=str(s).replace("\xa0"," ").replace(",","").strip()
        s=re.sub(r"[^\d.]", "", s)
        return float(s) if s else None
    except Exception:
        return None

def ps_product_url(ps_id: str, cc: str) -> str:
    return f"https://store.playstation.com/{plocale(cc)}/product/{ps_id}"

def parse_ps_html_for_prices(html: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    # Try JSON-ish blobs first (fastest)
    msrp=None; curr=None; disc=None
    for m in PRODUCT_PRICE_RE.finditer(html or ""):
        key=m.group(1).lower(); val=_num(m.group(2))
        if key in ("baseprice","regularprice","originalprice") and msrp is None: msrp=val
        if key in ("discountedprice","finalprice","current","value","pricevalue") and disc is None: disc=val
    # Crossed-out markup (<del>)
    if msrp is None:
        crossed=CROSSED_RE.findall(html or "") or []
        vals=[_num(x) for x in crossed if _num(x)]
        if vals: msrp=max(vals)
    # Currency via visible token (fallback)
    soup=BeautifulSoup(html or "", "html.parser")
    token=(soup.find(attrs={"data-qa":"mfeCtaMain#offer0#displayPrice"}) or {}).get_text("",strip=True) if soup else ""
    for sym,code in SYMBOLS.items():
        if token and sym in token: curr=code; break
    return msrp, disc, curr

def fetch_playstation_price_by_id(title: str, ps_id: str, cc_iso: str, prefer_msrp: bool=True):
    url=ps_product_url(ps_id, cc_iso)
    r=http_get(url, headers={"Accept-Language":plocale(cc_iso)}, timeout=12)
    if not r or not r.text:
        return None, MissRow("PlayStation", title or ps_id, cc_iso, "no_response")
    html=r.text

    # Parse using robust mix (regex + simple soup)
    msrp, disc, c1 = parse_ps_html_for_prices(html)

    # __NEXT_DATA__ currency backup
    try:
        soup=BeautifulSoup(html,"html.parser")
        tag=soup.find("script", id="__NEXT_DATA__", type="application/json")
        if tag and tag.string:
            j=json.loads(tag.string)
            prod=(j.get("props",{}).get("pageProps",{}).get("product") or {})
            p=prod.get("price") or {}
            if msrp is None: msrp=_num(p.get("basePrice") or p.get("regularPrice") or p.get("originalPrice"))
            if disc is None: disc=_num(p.get("discountedPrice") or p.get("finalPrice") or p.get("current") or p.get("value"))
            c2=p.get("currency")
            if not c1 and isinstance(c2,str): c1=c2.upper()
    except Exception:
        pass

    currency = c1 or PS_CCY.get(cc_iso.upper())
    if prefer_msrp:
        amount = msrp or disc  # if MSRP absent, fall back to current
    else:
        amount = disc or msrp  # prefer current, fallback to MSRP

    if amount is None:
        return None, MissRow("PlayStation", title or ps_id, cc_iso, "no_price")

    return PriceRow("PlayStation", title or ps_id, cc_iso.upper(), currency, float(amount), url, f"ps:{ps_id}"), None

# ---------------- Defaults ----------------
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
    # Users can replace IDs as needed; these are examples
    {"include":True,"title":"The Outer Worlds 2","ps_id":"UP6312-PPSA16483_00-OW2STANDARDPS5US","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"Madden NFL 26","ps_id":"UP0006-PPSA26127_00-MADDENNFL26GAME0","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"Call of Duty: Black Ops 6","ps_id":"UP0002-PPSA17544_00-BO6CROSSGENBUNDLE","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"NBA 2K26","ps_id":"UP1001-PPSA28420_00-NBA2K26000000000","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"Borderlands 4","ps_id":"UP1001-PPSA01494_00-0000000000000AK2","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"HELLDIVERS 2","ps_id":"UP9000-PPSA14719_00-ARROWHEADGAAS000","scale_factor":1.75,"weight":1.0},
]

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Controls")
    all_markets=list(COUNTRY_LOCALE.keys())
    default_markets="US,CA,GB,FR,DE,AU,NZ,BR,JP,KR"
    txt=st.text_area("Markets (comma-separated ISO)", value=default_markets, height=80)
    markets=[m.strip().upper() for m in txt.split(",") if m.strip()]
    prefer_msrp=st.checkbox("Prefer MSRP (ignore discounts)", value=True)

    if "steam_rows" not in st.session_state: st.session_state.steam_rows=DEFAULT_STEAM.copy()
    if "xbox_rows"  not in st.session_state: st.session_state.xbox_rows=DEFAULT_XBOX.copy()
    if "ps_rows"    not in st.session_state: st.session_state.ps_rows=DEFAULT_PS.copy()

    st.subheader("Steam basket")
    st.session_state.steam_rows = st.data_editor(pd.DataFrame(st.session_state.steam_rows), key="steam_editor", num_rows="dynamic", use_container_width=True).to_dict("records")
    st.subheader("Xbox basket")
    st.session_state.xbox_rows  = st.data_editor(pd.DataFrame(st.session_state.xbox_rows), key="xbox_editor",  num_rows="dynamic", use_container_width=True).to_dict("records")
    st.subheader("PlayStation basket (product IDs only)")
    st.session_state.ps_rows    = st.data_editor(pd.DataFrame(st.session_state.ps_rows), key="ps_editor",   num_rows="dynamic", use_container_width=True).to_dict("records")

    run = st.button("Run Pricing Pull", type="primary")

# ---------------- Helpers ----------------
def fx_view(df, label):
    rates=fx_rates()
    if df.empty:
        return pd.DataFrame(columns=["platform","country_name","country","currency","RecommendedPrice","USDPrice","DiffUSD"])
    out=df[["country","currency","RecommendedPrice"]].copy()
    out["USDPrice"]=[to_usd(p,c,rates) for p,c in zip(out["RecommendedPrice"],out["currency"])]
    us=df.loc[df["country"]=="US"]
    if not us.empty:
        us_usd=to_usd(float(us["RecommendedPrice"].iloc[0]), str(us["currency"].iloc[0]), rates)
        out["DiffUSD"]=[None if pd.isna(v) else round(v-us_usd,2) for v in out["USDPrice"]]
    else:
        out["DiffUSD"]=None
    out.insert(0,"platform",label); out.insert(1,"country_name",out["country"].map(cname))
    return out.sort_values("country_name").reset_index(drop=True)

# ---------------- Run ----------------
if run:
    steam_rows=[r for r in st.session_state.steam_rows if r.get("include") and r.get("appid")]
    xbox_rows=[r for r in st.session_state.xbox_rows if r.get("include") and r.get("store_id")]
    ps_rows=[r for r in st.session_state.ps_rows if r.get("include") and r.get("ps_id")]

    rows=[]; misses=[]
    with st.status("Pulling prices across markets…", expanded=True) as s:
        futs=[]
        with ThreadPoolExecutor(max_workers=16) as ex:
            for cc in markets:
                for r in steam_rows: futs.append(ex.submit(fetch_steam_price, r["appid"], cc, r.get("title")))
                for r in xbox_rows:  futs.append(ex.submit(fetch_xbox_price,  r.get("title"), r["store_id"], cc))
                for r in ps_rows:    futs.append(ex.submit(fetch_playstation_price_by_id, r.get("title"), r["ps_id"], cc, prefer_msrp))
            for f in as_completed(futs):
                try: pr, miss = f.result()
                except Exception: pr, miss = None, MissRow("unknown","unknown","unknown","exception")
                if pr: rows.append(pr)
                if miss: misses.append(miss)
        s.update(label="Pull complete. Processing…", state="complete")

    raw=pd.DataFrame([asdict(r) for r in rows])
    if not raw.empty:
        meta={}
        for r in steam_rows: meta[f"steam:{r['appid']}"]={"scale":float(r.get("scale_factor",1.0)),"weight":float(r.get("weight",1.0))}
        for r in xbox_rows:  meta[f"xbox:{r['store_id']}"]={"scale":float(r.get("scale_factor",1.0)),"weight":float(r.get("weight",1.0))}
        for r in ps_rows:    meta[f"ps:{r['ps_id']}"]={"scale":float(r.get("scale_factor",1.0)),"weight":float(r.get("weight",1.0))}

        raw.insert(2,"country_name",raw["country"].map(cname))
        raw["scale"]=raw["identity"].map(lambda i: meta.get(i,{}).get("scale",1.0))
        raw["weight"]=raw["identity"].map(lambda i: meta.get(i,{}).get("weight",1.0))
        raw["price"]=raw["price"]*raw["scale"]

        st.subheader("Raw Basket Rows (after scaling)")
        st.dataframe(raw, use_container_width=True, height=360)

        grp=raw.groupby(["platform","country","currency"], dropna=False)
        sums=grp.apply(lambda g:(g["price"]*g["weight"]).sum()).rename("weighted_sum")
        wts=grp["weight"].sum().rename("weight_total")
        reco=pd.concat([sums,wts],axis=1).reset_index()
        reco["RecommendedPrice"]=reco.apply(lambda r:(r["weighted_sum"]/r["weight_total"]) if r["weight_total"]>0 else None, axis=1)
        reco=reco[["platform","country","currency","RecommendedPrice"]]
        reco["RecommendedPrice"]=[vanity(cur, val) if pd.notna(val) else val for cur,val in zip(reco["currency"],reco["RecommendedPrice"])]

        xdf=reco[reco["platform"]=="Xbox"].copy();    xdf.insert(1,"country_name",xdf["country"].map(cname))
        sdf=reco[reco["platform"]=="Steam"].copy();   sdf.insert(1,"country_name",sdf["country"].map(cname))
        pdf=reco[reco["platform"]=="PlayStation"].copy(); pdf.insert(1,"country_name",pdf["country"].map(cname))

        st.subheader("Xbox Regional Pricing Recommendation");   st.dataframe(fx_view(xdf, "Xbox"), use_container_width=True, height=360)
        st.subheader("Steam Regional Pricing Recommendation");  st.dataframe(fx_view(sdf, "Steam"), use_container_width=True, height=360)
        st.subheader("PlayStation Regional Pricing Recommendation"); st.dataframe(fx_view(pdf, "PlayStation"), use_container_width=True, height=360)

        merged=xdf.rename(columns={"RecommendedPrice":"XboxRecommended"})
        merged=pd.merge(merged, sdf.rename(columns={"RecommendedPrice":"SteamRecommended"}), on=["country_name","country","currency"], how="outer")
        merged=pd.merge(merged, pdf.rename(columns={"RecommendedPrice":"PSRecommended"}), on=["country_name","country","currency"], how="outer")
        merged=merged.sort_values("country_name").reset_index(drop=True)
        st.subheader("Combined Recommendations (Xbox + Steam + PlayStation)")
        st.dataframe(merged, use_container_width=True)

        st.download_button("⬇️ Download CSV (combined recommendations)",
                           merged.to_csv(index=False).encode("utf-8"),
                           file_name="aaa_tier_recommendations_xsx_steam_ps_v3_6_playstation_repair.csv",
                           mime="text/csv")

    if misses:
        st.subheader("Diagnostics (no price found)")
        st.dataframe(pd.DataFrame([asdict(m) for m in misses]), use_container_width=True, height=300)

else:
    st.caption("Tip: Provide PlayStation **product IDs** only (no concept URLs). The app constructs regional URLs automatically and prefers MSRP (toggle in sidebar).")
