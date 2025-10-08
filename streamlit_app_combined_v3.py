
# streamlit_app_combined_v3.py
import re, json, time, random
from dataclasses import dataclass, asdict
from typing import Optional, Tuple, Dict, List, Any

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Game Pricing Recommendation Tool v3", page_icon="🎮", layout="wide")
st.title("🎮 Game Pricing Recommendation Tool — v3 (Xbox · Steam · PlayStation)")

UA = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
JSON_HEADERS={"Accept":"application/json", **UA}

def _ms_cv():
    import string
    return "".join(random.choice(string.ascii_letters+string.digits) for _ in range(24))

def http_get(url, params=None, headers=None, timeout=20, retries=2, backoff=0.6):
    last=None
    for i in range(retries+1):
        try:
            r=requests.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code==200: return r
            last=r
        except Exception as e:
            last=e
        time.sleep(backoff*(i+1))
    return last

COUNTRY_NAMES={
    "US":"United States","GB":"United Kingdom","CA":"Canada","AU":"Australia","NZ":"New Zealand","AE":"United Arab Emirates",
    "AR":"Argentina","AT":"Austria","BE":"Belgium","BG":"Bulgaria","BH":"Bahrain","BR":"Brazil","CH":"Switzerland","CL":"Chile","CN":"China",
    "CO":"Colombia","CR":"Costa Rica","CY":"Cyprus","CZ":"Czechia","DE":"Germany","DK":"Denmark","DO":"Dominican Republic","EC":"Ecuador",
    "EE":"Estonia","EG":"Egypt","ES":"Spain","FI":"Finland","FR":"France","GR":"Greece","GT":"Guatemala","HK":"Hong Kong","HN":"Honduras",
    "HR":"Croatia","HU":"Hungary","ID":"Indonesia","IE":"Ireland","IL":"Israel","IN":"India","IS":"Iceland","IT":"Italy","JP":"Japan","JO":"Jordan",
    "KR":"South Korea","KW":"Kuwait","LU":"Luxembourg","LV":"Latvia","LT":"Lithuania","MA":"Morocco","MT":"Malta","MX":"Mexico","MY":"Malaysia",
    "NL":"Netherlands","NI":"Nicaragua","NO":"Norway","OM":"Oman","PA":"Panama","PE":"Peru","PH":"Philippines","PL":"Poland","PT":"Portugal",
    "PY":"Paraguay","QA":"Qatar","RO":"Romania","RS":"Serbia","RU":"Russia","SA":"Saudi Arabia","SE":"Sweden","SG":"Singapore","SI":"Slovenia",
    "SK":"Slovakia","SV":"El Salvador","TH":"Thailand","TR":"Türkiye","TW":"Taiwan","UA":"Ukraine","UY":"Uruguay","VN":"Vietnam","ZA":"South Africa"
}
def cname(code): return COUNTRY_NAMES.get(code.upper(), code.upper())

XBOX_LOCALE={"US":"en-us","GB":"en-gb","CA":"en-ca","AU":"en-au","NZ":"en-nz","FR":"fr-fr","DE":"de-de","ES":"es-es","IT":"it-it","JP":"ja-jp",
             "BR":"pt-br","MX":"es-mx","AE":"ar-ae","SA":"ar-sa","PL":"pl-pl","PT":"pt-pt","NL":"nl-nl","SE":"sv-se","NO":"no-no","DK":"da-dk","FI":"fi-fi"}
def xbox_locale(cc): return XBOX_LOCALE.get(cc.upper(),"en-us")

PS_PREF={"US":("en-us","USD"),"GB":("en-gb","GBP"),"CA":("en-ca","CAD"),"AU":("en-au","AUD"),"NZ":("en-nz","NZD"),
"AE":("en-ae","AED"),"SA":("ar-sa","SAR"),"IE":("en-ie","EUR"),"FR":("fr-fr","EUR"),"DE":("de-de","EUR"),"ES":("es-es","EUR"),
"PT":("pt-pt","EUR"),"IT":("it-it","EUR"),"NL":("nl-nl","EUR"),"PL":("pl-pl","PLN"),"CZ":("cs-cz","CZK"),"SE":("sv-se","SEK"),
"NO":("no-no","NOK"),"DK":("da-dk","DKK"),"FI":("fi-fi","EUR"),"JP":("ja-jp","JPY"),"KR":("ko-kr","KRW"),"TW":("zh-tw","TWD"),
"BR":("pt-br","BRL"),"MX":("es-mx","MXN"),"AR":("es-ar","ARS"),"CL":("es-cl","CLP"),"CO":("es-co","COP"),"PE":("es-pe","PEN"),
"UY":("es-uy","UYU"),"SG":("en-sg","SGD"),"MY":("en-my","MYR"),"PH":("en-ph","PHP"),"HK":("en-hk","HKD"),"ZA":("en-za","ZAR")}
def ps_meta(cc): return PS_PREF.get(cc.upper(),("en-us","USD"))

VANITY={"AU":{"suffix":0.95,"nines":True},"NZ":{"suffix":0.95,"nines":True},"CA":{"suffix":0.99,"nines":True}}
def _nearest_x9(price,sfx):
    k=int(price//10); cand=[10*i+9+sfx for i in range(k-2,k+4) if 10*i+9+sfx>0]
    return round(min(cand,key=lambda v:(abs(v-price),-v)),2) if cand else round(price,2)
def apply_vanity(cc,p):
    r=VANITY.get(cc.upper()); 
    return _nearest_x9(float(p), r["suffix"]) if r and r.get("nines") else round(float(p),2)

def fx_rates():
    if "fx" in st.session_state and time.time()-st.session_state.get("fx_ts",0)<7200:
        return st.session_state["fx"]
    out={"USD":1.0}
    for url in ["https://api.exchangerate.host/latest?base=USD","https://open.er-api.com/v6/latest/USD"]:
        r=http_get(url, headers=JSON_HEADERS, timeout=15, retries=1)
        try:
            j=r.json() if hasattr(r,"json") else {}
            if j.get("rates"):
                for k,v in j["rates"].items():
                    if isinstance(v,(int,float)) and v>0: out[k.upper()]=float(v)
                break
            if j.get("result")=="success" and j.get("rates"):
                for k,v in j["rates"].items():
                    if isinstance(v,(int,float)) and v>0: out[k.upper()]=float(v)
                break
        except Exception: pass
    st.session_state["fx"]=out; st.session_state["fx_ts"]=time.time(); return out
def to_usd(amount, currency, rates):
    if amount is None or not currency: return None
    r=rates.get(str(currency).upper()); 
    return round(float(amount)/r,2) if r else None

@dataclass
class PriceRow:
    platform:str; title:str; country:str; currency:Optional[str]; price:Optional[float]; source_url:Optional[str]; identity:str
@dataclass
class MissRow:
    platform:str; title:str; country:str; reason:str

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
 {"include":True,"title":"The Outer Worlds 2","ps_ref":"https://store.playstation.com/en-us/product/UP6312-PPSA16483_00-OW2STANDARDPS5US","edition_hint":"Standard","scale_factor":1.0,"weight":1.0},
 {"include":True,"title":"Madden NFL 26","ps_ref":"https://store.playstation.com/en-us/product/UP0006-PPSA26127_00-MADDENNFL26GAME0","edition_hint":"Standard","scale_factor":1.0,"weight":1.0},
 {"include":True,"title":"Call of Duty: Black Ops 6","ps_ref":"https://store.playstation.com/en-us/product/UP0002-PPSA17544_00-BO6CROSSGENBUNDLE","edition_hint":"Standard","scale_factor":1.0,"weight":1.0},
 {"include":True,"title":"NBA 2K26","ps_ref":"https://store.playstation.com/en-us/concept/10014149","edition_hint":"Standard","scale_factor":1.0,"weight":1.0},
 {"include":True,"title":"Borderlands 4","ps_ref":"https://store.playstation.com/en-us/concept/10000819","edition_hint":"Standard","scale_factor":1.0,"weight":1.0},
 {"include":True,"title":"HELLDIVERS 2","ps_ref":"https://store.playstation.com/en-us/product/UP9000-PPSA14719_00-ARROWHEADGAAS000","edition_hint":"","scale_factor":1.75,"weight":1.0},
]

def fetch_steam_price(appid, cc_iso, title=None):
    r=http_get("https://store.steampowered.com/api/appdetails", params={"appids":appid,"cc":cc_iso,"l":"en"}, headers=JSON_HEADERS, timeout=20)
    try:
        j=r.json().get(str(appid),{})
        if not j.get("success"): return None, MissRow("Steam", title or appid, cc_iso, "appdetails_no_data")
        d=j.get("data") or {}
        pov=d.get("price_overview") or {}
        cents=pov.get("initial") or pov.get("final")
        if cents:
            price=round(cents/100.0,2); ccy=(pov.get("currency") or "").upper() or None
            return PriceRow("Steam", title or d.get("name") or f"Steam App {appid}", cc_iso.upper(), ccy, price, f"https://store.steampowered.com/app/{appid}", f"steam:{appid}"), None
        return None, MissRow("Steam", title or d.get("name") or appid, cc_iso, "no_price")
    except Exception:
        return None, MissRow("Steam", title or appid, cc_iso, "exception")

def parse_xbox_price(payload):
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
        return None, None
    except Exception:
        return None, None

def fetch_xbox_price(title, store_id, cc_iso):
    loc=xbox_locale(cc_iso); headers={"MS-CV":_ms_cv(),"Accept":"application/json"}
    r=http_get("https://storeedgefd.dsx.mp.microsoft.com/v9.0/sdk/products", params={"bigIds":store_id,"market":cc_iso,"locale":loc}, headers=headers, timeout=20, retries=2)
    try:
        if hasattr(r,"json"):
            amt,ccy=parse_xbox_price(r.json())
            if amt: return PriceRow("Xbox", title or "Xbox Product", cc_iso.upper(), ccy, float(amt), f"https://www.xbox.com/{loc.split('-')[0]}/games/store/x/{store_id}", f"xbox:{store_id}"), None
    except Exception: pass
    r2=http_get("https://displaycatalog.mp.microsoft.com/v7.0/products", params={"bigIds":store_id,"market":cc_iso,"languages":"en-US","fieldsTemplate":"Details"}, headers=headers, timeout=20, retries=1)
    try:
        if hasattr(r2,"json"):
            amt,ccy=parse_xbox_price(r2.json())
            if amt: return PriceRow("Xbox", title or "Xbox Product", cc_iso.upper(), ccy, float(amt), f"https://www.xbox.com/en-us/games/store/x/{store_id}", f"xbox:{store_id}"), None
    except Exception: pass
    return None, MissRow("Xbox", title or store_id, cc_iso, "no_price_entries")

PRODUCT_ID_RE=re.compile(r"/product/([^/?#]+)")
PRICE_RE=re.compile(r'"(?:basePrice|strikethroughPrice|regularPrice|originalPrice|discountedPrice|finalPrice|current|value)"\s*:\s*("?)([0-9]+(?:\.[0-9]+)?)\1', re.I)
CUR_RE=re.compile(r'"currency"\s*:\s*"([A-Z]{3})"')
DISPLAY_RE=re.compile(r'data-qa="mfeCtaMain#offer0#displayPrice"[^>]*>([^<]+)<', re.I)
CUR_HINTS={"$":"USD","CAD$":"CAD","A$":"AUD","NZ$":"NZD","R$":"BRL","€":"EUR","£":"GBP","₺":"TRY","zł":"PLN","kr":"SEK","CHF":"CHF",
"HK$":"HKD","NT$":"TWD","₩":"KRW","¥":"JPY","₪":"ILS","AED":"AED","SAR":"SAR","MXN":"MXN","ARS":"ARS","CLP":"CLP","COP":"COP","PEN":"PEN",
"UYU":"UYU","CRC":"CRC","GTQ":"GTQ","HNL":"HNL","NIO":"NIO","PYG":"PYG","DOP":"DOP","BOB":"BOB","ZAR":"ZAR","MYR":"MYR","THB":"THB",
"IDR":"IDR","PHP":"PHP","VND":"VND","INR":"INR","NOK":"NOK","DKK":"DKK"}

def _html(url, locale=None, timeout=20):
    h={"User-Agent":UA["User-Agent"],"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
    if locale:
        lang=locale.split("-")[0]; h["Accept-Language"]=f"{lang}-{locale.split('-')[-1].upper()},{lang};q=0.8"
    r=http_get(url, headers=h, timeout=timeout, retries=1)
    try: return r.text if hasattr(r,"text") and r.status_code==200 else None
    except Exception: return None

def _next_json(html):
    soup=BeautifulSoup(html,"html.parser")
    tag=soup.find("script",id="__NEXT_DATA__",type="application/json")
    if not tag or not tag.string: return None
    try: return json.loads(tag.string)
    except Exception: return None

def _fallback_prices(html):
    msrp=price=curr=None
    for m in PRICE_RE.finditer(html):
        val=float(m.group(2))
        ctx=html[max(0,m.start()-30):m.start()]
        if any(k in ctx for k in ["basePrice","strikethroughPrice","regularPrice","originalPrice"]) and msrp is None: msrp=val
        if any(k in ctx for k in ["discountedPrice","finalPrice","current","value"]) and price is None: price=val
    mcur=CUR_RE.search(html)
    if mcur: curr=mcur.group(1)
    if not curr:
        mdisp=DISPLAY_RE.search(html)
        if mdisp:
            token=mdisp.group(1)
            for hint,c in CUR_HINTS.items():
                if hint in token: curr=c; break
    return msrp, price, curr

def _resolve_concept(concept_url, locale):
    html=_html(concept_url, locale)
    if not html: return None
    soup=BeautifulSoup(html,"html.parser")
    candidates=[]
    for a in soup.find_all("a",href=True):
        href=a["href"]
        if "/product/" in href:
            if href.startswith("/"):
                href=f"https://store.playstation.com/{locale}{href}"
            t=(a.get("title") or a.get("aria-label") or a.text or "").lower()
            candidates.append((href,t))
    if not candidates: return None
    candidates.sort(key=lambda x:(("standard" in x[1])*2)+("/product/" in x[0]), reverse=True)
    return candidates[0][0]

def fetch_playstation_price(ps_ref, cc_iso, title=None, prefer_msrp=True):
    locale, cur_fb = ps_meta(cc_iso)
    ref=(ps_ref or "").strip()

    if ref.startswith("http") and "/concept/" in ref:
        us_loc,_ = ps_meta("US")
        r=_resolve_concept(ref, us_loc)
        if r: ref=r

    pid=None
    if ref:
        if ref.startswith("http"):
            m=PRODUCT_ID_RE.search(ref); pid=m and m.group(1)
        else: pid=ref
    if not pid:
        return None, MissRow("PlayStation", title or "unknown", cc_iso, "cannot_resolve_ps_id")

    url=f"https://store.playstation.com/{locale}/product/{pid}"
    html=_html(url, locale)
    name=None; msrp=price=curr=None
    if html:
        j=_next_json(html)
        if j:
            props=j.get("props",{}).get("pageProps",{})
            product=props.get("product") or {}
            name=product.get("name") or props.get("title")
            pb=product.get("price") or {}
            msrp = pb.get("basePrice") or pb.get("regularPrice") or pb.get("originalPrice")
            price = pb.get("discountedPrice") or pb.get("finalPrice") or pb.get("current")
            curr = pb.get("currency")
        if msrp is None and price is None:
            m2,p2,c2=_fallback_prices(html); msrp=m2 or msrp; price=p2 or price; curr=c2 or curr

    if curr is None: curr=cur_fb
    amt = msrp if prefer_msrp and msrp else (msrp if msrp is not None else price)
    if amt is None:
        return None, MissRow("PlayStation", title or (name or f"PS {pid}"), cc_iso, "no_price_found")
    return PriceRow("PlayStation", title or (name or f"PS {pid}"), cc_iso.upper(), curr, float(amt), url, f"ps:{ref or pid}"), None

with st.sidebar:
    st.header("Controls")
    default_markets = ",".join(sorted(COUNTRY_NAMES.keys()))
    user_markets = st.text_area("Markets (comma-separated ISO country codes)", value=default_markets, height=120)
    markets=[m.strip().upper() for m in user_markets.split(",") if m.strip()]
    prefer_msrp = st.checkbox("Prefer MSRP (ignore discounts)", value=True)

    if "steam_rows" not in st.session_state: st.session_state.steam_rows = DEFAULT_STEAM.copy()
    if "xbox_rows"  not in st.session_state: st.session_state.xbox_rows  = DEFAULT_XBOX.copy()
    if "ps_rows"    not in st.session_state: st.session_state.ps_rows    = DEFAULT_PS.copy()

    st.subheader("Steam basket")
    st.session_state.steam_rows = st.data_editor(pd.DataFrame(st.session_state.steam_rows), key="steam_editor", num_rows="dynamic", use_container_width=True).to_dict("records")
    st.subheader("Xbox basket")
    st.session_state.xbox_rows  = st.data_editor(pd.DataFrame(st.session_state.xbox_rows), key="xbox_editor",  num_rows="dynamic", use_container_width=True).to_dict("records")
    st.subheader("PlayStation basket")
    st.session_state.ps_rows    = st.data_editor(pd.DataFrame(st.session_state.ps_rows), key="ps_editor",   num_rows="dynamic", use_container_width=True).to_dict("records")

    run = st.button("Run Pricing Pull", type="primary")

def fx_view(df, label):
    if df.empty: return pd.DataFrame()
    rates=fx_rates()
    us=df.loc[df["country"]=="US"]
    if us.empty: return pd.DataFrame()
    us_local=float(us["RecommendedPrice"].iloc[0]); us_ccy=str(us["currency"].iloc[0])
    us_usd=to_usd(us_local, us_ccy, rates)
    out=df[["country","currency","RecommendedPrice"]].copy()
    out["USDPrice"]=[to_usd(p,c,rates) for p,c in zip(out["RecommendedPrice"],out["currency"])]
    out["DiffUSD"]=[None if pd.isna(v) else round(v-us_usd,2) for v in out["USDPrice"]]
    out.insert(0,"platform",label)
    out.insert(1,"country_name",out["country"].map(cname))
    return out.sort_values("country_name").reset_index(drop=True)

if run:
    steam_rows=[r for r in st.session_state.steam_rows if r.get("include") and r.get("appid")]
    xbox_rows=[r for r in st.session_state.xbox_rows if r.get("include") and r.get("store_id")]
    ps_rows=[r for r in st.session_state.ps_rows if r.get("include") and (r.get("ps_ref") or r.get("title"))]

    rows=[]; misses=[]
    with st.status("Pulling prices across markets…"):
        futs=[]
        with ThreadPoolExecutor(max_workers=16) as ex:
            for cc in markets:
                for r in steam_rows: futs.append(ex.submit(fetch_steam_price, r["appid"], cc, r.get("title")))
                for r in xbox_rows:  futs.append(ex.submit(fetch_xbox_price, r.get("title"), r["store_id"], cc))
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
        st.subheader("Raw Basket Rows (after scaling)"); st.dataframe(raw,use_container_width=True)

        grp=raw.groupby(["platform","country","currency"], dropna=False)
        sums=grp.apply(lambda g:(g["price"]*g["weight"]).sum()).rename("weighted_sum")
        wts=grp["weight"].sum().rename("weight_total")
        reco=pd.concat([sums,wts],axis=1).reset_index()
        reco["RecommendedPrice"]=reco.apply(lambda r:(r["weighted_sum"]/r["weight_total"]) if r["weight_total"]>0 else None, axis=1)
        reco=reco[["platform","country","currency","RecommendedPrice"]]

        for plat in ["Xbox","Steam","PlayStation"]:
            mask=reco["platform"]==plat
            reco.loc[mask,"RecommendedPrice"]=[apply_vanity(c,p) for c,p in zip(reco.loc[mask,"country"], reco.loc[mask,"RecommendedPrice"])]

        xdf=reco[reco["platform"]=="Xbox"].copy(); xdf.insert(1,"country_name",xdf["country"].map(cname))
        sdf=reco[reco["platform"]=="Steam"].copy(); sdf.insert(1,"country_name",sdf["country"].map(cname))
        pdf=reco[reco["platform"]=="PlayStation"].copy(); pdf.insert(1,"country_name",pdf["country"].map(cname))

        rates=fx_rates()
        for df in (xdf,sdf,pdf):
            if not df.empty:
                df["RecommendedPriceUSD"]=[to_usd(p,cur,rates) for p,cur in zip(df["RecommendedPrice"], df["currency"])]

        if not xdf.empty: st.subheader("Xbox Regional Pricing Recommendation"); st.dataframe(fx_view(xdf, "Xbox"), use_container_width=True)
        if not sdf.empty: st.subheader("Steam Regional Pricing Recommendation"); st.dataframe(fx_view(sdf, "Steam"), use_container_width=True)
        if not pdf.empty: st.subheader("PlayStation Regional Pricing Recommendation"); st.dataframe(fx_view(pdf, "PlayStation"), use_container_width=True)

        merged=xdf.rename(columns={"RecommendedPrice":"XboxRecommended","RecommendedPriceUSD":"XboxRecommendedUSD"})
        merged=pd.merge(merged, sdf.rename(columns={"RecommendedPrice":"SteamRecommended","RecommendedPriceUSD":"SteamRecommendedUSD"}), on=["country_name","country","currency"], how="outer")
        merged=pd.merge(merged, pdf.rename(columns={"RecommendedPrice":"PSRecommended","RecommendedPriceUSD":"PSRecommendedUSD"}), on=["country_name","country","currency"], how="outer")
        merged=merged.sort_values("country_name").reset_index(drop=True)
        st.subheader("Combined Recommendations (Xbox + Steam + PlayStation)")
        st.dataframe(merged, use_container_width=True)
        st.download_button("⬇️ Download CSV (combined recommendations)", merged.to_csv(index=False).encode("utf-8"),
                           file_name="aaa_tier_recommendations_xsx_steam_ps_v3.csv", mime="text/csv")

    if misses:
        st.subheader("Diagnostics (no price found)"); st.dataframe(pd.DataFrame([asdict(m) for m in misses]), use_container_width=True)
else:
    st.caption("Edit baskets, set markets, then Run Pricing Pull.")
