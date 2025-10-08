
# streamlit_app_combined_v3_9.py
# Changes from v3.8 -> v3.9
# - PlayStation: robust edition targeting. Cross‑Gen counts as "standard".
# - PlayStation: when "Prefer MSRP" is ON, ONLY take JSON base/regular/original OR <del> (crossed) values.
#                This prevents the "$99.99 everywhere" fallback.
# - Xbox: add fallback to displaycatalog v7.0 if storeedgefd v9.0 fails.
# - Keep progress bar + Quick Run; show 'edition' column in Raw rows.

import re, json, time, random, string
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Tuple
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Game Pricing Recommendation Tool — v3.9", page_icon="🎮", layout="wide")
st.title("🎮 Game Pricing Recommendation Tool — v3.9 (Xbox · Steam · PlayStation)")

# ---------- HTTP session (pooled) ----------
SESSION = requests.Session()
ADAPTER = requests.adapters.HTTPAdapter(pool_connections=64, pool_maxsize=64)
SESSION.mount("https://", ADAPTER); SESSION.mount("http://", ADAPTER)
UA = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

def _ms_cv():
    return "".join(random.choice(string.ascii_letters+string.digits) for _ in range(28))

def http_get(url, params=None, headers=None, timeout=12, retries=1, backoff=0.35):
    last=None
    headers = headers or {}
    headers = {**UA, **headers}
    for i in range(retries+1):
        try:
            r=SESSION.get(url, params=params, headers=headers, timeout=timeout)
            if getattr(r,"status_code",0)==200:
                return r
            last=r
        except Exception as e:
            last=e
        time.sleep(backoff*(i+1))
    return last

# ------------- Shared data / helpers -------------
COUNTRY_NAMES = {"US":"United States","CA":"Canada","MX":"Mexico","CL":"Chile","CO":"Colombia","PE":"Peru","CR":"Costa Rica","AR":"Argentina","UY":"Uruguay",
"BO":"Bolivia","EC":"Ecuador","SV":"El Salvador","GT":"Guatemala","HN":"Honduras","NI":"Nicaragua","PA":"Panama","PY":"Paraguay","BR":"Brazil",
"GB":"United Kingdom","IE":"Ireland","FR":"France","DE":"Germany","ES":"Spain","IT":"Italy","PT":"Portugal","NL":"Netherlands","BE":"Belgium","AT":"Austria",
"CH":"Switzerland","LU":"Luxembourg","MT":"Malta","GR":"Greece","HR":"Croatia","HU":"Hungary","CZ":"Czech Republic","SK":"Slovakia","RO":"Romania","PL":"Poland",
"BG":"Bulgaria","SI":"Slovenia","IS":"Iceland","SE":"Sweden","DK":"Denmark","NO":"Norway","FI":"Finland","AU":"Australia","NZ":"New Zealand",
"JP":"Japan","KR":"Korea","SG":"Singapore","MY":"Malaysia","TH":"Thailand","ID":"Indonesia","TW":"Taiwan","HK":"Hong Kong","IN":"India","TR":"Türkiye","IL":"Israel",
"SA":"Saudi Arabia","AE":"United Arab Emirates","ZA":"South Africa","UA":"Ukraine","RU":"Russia","CY":"Cyprus"}
def cname(code): return COUNTRY_NAMES.get(code.upper(), code.upper())

XBOX_LOCALE={"US":"en-us","GB":"en-gb","CA":"en-ca","AU":"en-au","NZ":"en-nz","FR":"fr-fr","DE":"de-de","ES":"es-es","IT":"it-it","JP":"ja-jp",
             "BR":"pt-br","MX":"es-mx","AE":"ar-ae","SA":"ar-sa","PL":"pl-pl","PT":"pt-pt","NL":"nl-nl","SE":"sv-se","NO":"no-no","DK":"da-dk","FI":"fi-fi"}
def xbox_locale(cc): return XBOX_LOCALE.get(cc.upper(),"en-us")

PS_CCY_MAP={
    "US":"USD","CA":"CAD","MX":"USD","CL":"USD","CO":"USD","PE":"USD","CR":"USD","AR":"USD","UY":"USD","BO":"USD","EC":"USD",
    "SV":"USD","GT":"USD","HN":"USD","NI":"USD","PA":"USD","PY":"USD","BR":"BRL",
    "GB":"GBP","IE":"EUR","FR":"EUR","DE":"EUR","ES":"EUR","IT":"EUR","PT":"EUR","NL":"EUR","BE":"EUR","AT":"EUR","CH":"CHF","LU":"EUR","MT":"EUR",
    "GR":"EUR","HR":"EUR","HU":"HUF","CZ":"CZK","SK":"EUR","RO":"RON","PL":"PLN","BG":"BGN","SI":"EUR","CY":"EUR",
    "IS":"EUR","SE":"SEK","DK":"DKK","NO":"NOK","FI":"EUR",
    "AU":"AUD","NZ":"NZD",
    "JP":"JPY","KR":"KRW","SG":"SGD","MY":"MYR","TH":"THB","ID":"IDR","TW":"TWD","HK":"HKD","IN":"INR",
    "TR":"TRY","IL":"ILS","SA":"SAR","AE":"AED","ZA":"ZAR","UA":"UAH","RU":"RUB"
}
def ps_meta(cc):
    loc_by_cc={"US":"en-us","GB":"en-gb","CA":"en-ca","AU":"en-au","NZ":"en-nz","IE":"en-ie","SG":"en-sg","MY":"en-my",
        "HK":"en-hk","IN":"en-in","AE":"en-ae","SA":"ar-sa","TR":"tr-tr","IL":"en-il","JP":"ja-jp","KR":"ko-kr","TW":"zh-tw",
        "FR":"fr-fr","DE":"de-de","ES":"es-es","IT":"it-it","PT":"pt-pt","NL":"nl-nl","BE":"nl-be","AT":"de-at","CH":"de-ch",
        "DK":"da-dk","NO":"no-no","SE":"sv-se","FI":"fi-fi","PL":"pl-pl","CZ":"cs-cz","HU":"hu-hu","RO":"en-ro","GR":"en-gr",
        "BG":"en-bg","SI":"en-si","SK":"sk-sk","HR":"en-hr","LU":"en-lu","MT":"en-mt","CY":"en-cy","IS":"en-is",
        "AR":"es-ar","CL":"es-cl","CO":"es-co","PE":"es-pe","CR":"es-cr","UY":"es-uy","GT":"es-gt","SV":"es-sv","HN":"es-hn","NI":"es-ni","PA":"es-pa","PY":"es-py",
        "MX":"es-mx","BR":"pt-br","UA":"uk-ua","RU":"ru-ru","ZA":"en-za"}
    return loc_by_cc.get(cc.upper(),"en-us"), PS_CCY_MAP.get(cc.upper(),"USD")

# Vanity pricing
ZERO_DECIMAL={"JPY","KRW","HUF","ISK","CLP"}
HUNDRED_STEP={"IDR","VND"}
NEAREST5={"BRL","RUB","INR"}
SUFFIX_99={"USD","EUR","GBP","CAD","SEK","NOK","DKK","CZK","PLN","CHF"}
SUFFIX_95={"AUD","NZD"}
def _force_suffix(p,s): w=int(p); return (w+s) if (w+s)>p else (w+1+s)
def apply_vanity_currency(cur, val):
    if val is None: return None
    c=(cur or '').upper(); p=float(val)
    if c in ZERO_DECIMAL: return float(int(round(p)))
    if c in HUNDRED_STEP: return float(int(round(p/100.0))*100)
    if c in NEAREST5: return float(int(round(p/5.0))*5)
    if c in SUFFIX_95: return round(_force_suffix(p,0.95),2)
    if c in SUFFIX_99: return round(_force_suffix(p,0.99),2)
    return round(p,2)

def fx_rates():
    if "fx" in st.session_state and time.time()-st.session_state.get("fx_ts",0)<7200:
        return st.session_state["fx"]
    out={"USD":1.0}
    for url in ["https://api.exchangerate.host/latest?base=USD","https://open.er-api.com/v6/latest/USD"]:
        try:
            r=http_get(url, timeout=8, retries=0).json()
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

@dataclass
class PriceRow:
    platform:str; title:str; country:str; currency:Optional[str]; price:Optional[float]; source_url:Optional[str]; identity:str; edition:Optional[str]

@dataclass
class MissRow:
    platform:str; title:str; country:str; reason:str

# ---- Default baskets ----
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
    {"include":True,"title":"Madden NFL 26","ps_ref":"https://store.playstation.com/en-us/product/UP0006-PPSA26127_00-MADDENNFL26GAME0","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"Call of Duty: Black Ops 6","ps_ref":"https://store.playstation.com/en-us/product/UP0002-PPSA17544_00-BO6CROSSGENBUNDLE","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"NBA 2K26","ps_ref":"https://store.playstation.com/en-us/product/UP1001-PPSA28420_00-NBA2K260000000000","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"Borderlands 4","ps_ref":"https://store.playstation.com/en-us/product/UP1001-PPSA01494_00-0000000000000AK2","scale_factor":1.0,"weight":1.0},
    {"include":True,"title":"HELLDIVERS 2","ps_ref":"https://store.playstation.com/en-us/product/UP9000-PPSA14719_00-ARROWHEADGAAS000","scale_factor":1.75,"weight":1.0},
]

# ---- Steam fetch ----
def fetch_steam_price(appid, cc_iso, title=None):
    try:
        j=http_get("https://store.steampowered.com/api/appdetails",
                   params={"appids":appid,"cc":cc_iso,"l":"en"}, timeout=10, retries=1).json()
        node=j.get(str(appid),{})
        if not node.get("success"): return None, MissRow("Steam", title or appid, cc_iso, "no_data")
        pov=(node.get("data") or {}).get("price_overview") or {}
        cents=pov.get("initial") or pov.get("final")
        if cents:
            price=round(cents/100.0,2); ccy=(pov.get("currency") or "").upper() or None
            return PriceRow("Steam", title or "Steam App", cc_iso.upper(), ccy, price, f"https://store.steampowered.com/app/{appid}", f"steam:{appid}", "Standard"), None
        return None, MissRow("Steam", title or appid, cc_iso, "no_price")
    except Exception:
        return None, MissRow("Steam", title or appid, cc_iso, "exception")

# ---- Xbox fetch (with fallback) ----
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
    except Exception:
        pass
    return None, None

def fetch_xbox_price(title, store_id, cc_iso):
    loc=xbox_locale(cc_iso)
    headers={"MS-CV":_ms_cv(),"Accept":"application/json","X-Client-Id":"pricing-tool/1.0"}
    # primary endpoint
    r=http_get("https://storeedgefd.dsx.mp.microsoft.com/v9.0/sdk/products",
               params={"bigIds":store_id,"market":cc_iso.upper(),"locale":loc},
               headers=headers, timeout=10, retries=1)
    try:
        if hasattr(r,"json"):
            amt,ccy=parse_xbox_price(r.json())
            if amt:
                return PriceRow("Xbox", title or "Xbox Product", cc_iso.upper(), ccy, float(amt),
                                f"https://www.xbox.com/{loc.split('-')[0]}/games/store/x/{store_id}", f"xbox:{store_id}", "Standard"), None
    except Exception:
        pass
    # fallback endpoint
    r2=http_get("https://displaycatalog.mp.microsoft.com/v7.0/products",
                params={"bigIds":store_id,"market":cc_iso.upper(),"languages":loc,"fieldsTemplate":"Store","deviceFamily":"Windows.Xbox"},
                headers=headers, timeout=12, retries=1)
    try:
        if hasattr(r2,"json"):
            amt,ccy=parse_xbox_price(r2.json())
            if amt:
                return PriceRow("Xbox", title or "Xbox Product", cc_iso.upper(), ccy, float(amt),
                                f"https://www.xbox.com/{loc.split('-')[0]}/games/store/x/{store_id}", f"xbox:{store_id}", "Standard"), None
    except Exception:
        pass
    return None, MissRow("Xbox", title or store_id, cc_iso, "no_price")

# ---- PlayStation fetch ----
PRODUCT_ID_RE=re.compile(r"/product/([^/?#]+)")

# Only rely on <del> MSRP when prefer_msrp is True
CROSSED_RE=re.compile(r"<del[^>]*>(.*?)</del>", re.I|re.S)

NEGATIVE_EDITIONS = ["deluxe","ultimate","premium","super","vault","gold","mvp","champion","bundle"]
PREFER_EDITIONS  = ["standard","standard edition","cross-gen","cross gen","crossgen","base game"]

def _html(url, locale=None):
    h={"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "User-Agent":UA["User-Agent"]}
    if locale:
        lang=locale.split("-")[0]; h["Accept-Language"]=f"{lang}-{locale.split('-')[-1].upper()},{lang};q=0.8"
    r=http_get(url, headers=h, timeout=10, retries=1)
    try: return r.text if hasattr(r,'text') and r.status_code==200 else None
    except Exception: return None

def _next_json(html):
    soup=BeautifulSoup(html,"html.parser")
    tag=soup.find("script",id="__NEXT_DATA__",type="application/json")
    if not tag or not tag.string: return None
    try: return json.loads(tag.string)
    except Exception: return None

def _num(x):
    try:
        if x is None: return None
        s=str(x).replace("\xa0","").replace(" ","").replace(",",".")
        return float(re.sub(r"[^\d.]", "", s)) if s else None
    except Exception: return None

def _resolve_concept(concept_url, locale):
    html=_html(concept_url, locale)
    if not html: return None
    soup=BeautifulSoup(html,"html.parser")
    for a in soup.find_all("a",href=True):
        href=a["href"]
        if "/product/" in href:
            if href.startswith("/"):
                return f"https://store.playstation.com/{locale}{href}"
            return href
    return None

def _ps_candidates(pid):
    cands=[pid]
    if pid.startswith("UP"): cands.append("EP"+pid[2:])
    elif pid.startswith("EP"): cands.append("UP"+pid[2:])
    return list(dict.fromkeys(cands))

def _score_edition(text:str)->int:
    t=(text or "").lower()
    # strong positive for preferred terms
    score = 0
    if any(k in t for k in ["cross-gen","cross gen","crossgen"]):
        score += 200  # treat cross‑gen as standard
    if any(k in t for k in ["standard","standard edition","base game"]):
        score += 150
    if score == 0 and any(k in t for k in NEGATIVE_EDITIONS):
        score -= 100
    return score

def _find_preferred_product_link(html:str, locale:str)->Tuple[Optional[str], Optional[str]]:
    soup=BeautifulSoup(html or "", "html.parser")
    best=(None, None, -999)
    for a in soup.find_all("a", href=True):
        href=a["href"]
        if "/product/" not in href: 
            continue
        label=a.get_text(" ", strip=True) or a.get("aria-label","")
        s=_score_edition(label)
        if s>best[2]:
            full = f"https://store.playstation.com/{locale}{href}" if href.startswith("/") else href
            best=(full, label, s)
    if best[0] and best[2] >= 0:
        return best[0], best[1]
    return None, None

def _extract_prices_from_next_data(j) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    try:
        props=j.get("props",{}).get("pageProps",{})
        product=props.get("product") or {}
        name=product.get("name") or props.get("title")
        edition=product.get("edition") or product.get("badge") or ""
        pb=product.get("price") or {}
        base=_num(pb.get("basePrice") or pb.get("regularPrice") or pb.get("originalPrice"))
        disc=_num(pb.get("discountedPrice") or pb.get("finalPrice") or pb.get("current") or pb.get("value") or pb.get("priceValue"))
        cur=(pb.get("currency") or pb.get("priceCurrency"))
        if isinstance(cur,str): cur=cur.upper()
        return base, disc, cur, edition or name
    except Exception:
        return None, None, None, None

def _extract_msrp_from_del(html)->Optional[float]:
    msrp_vals=[]
    for raw in CROSSED_RE.findall(html or ""):
        v=_num(raw)
        if v: msrp_vals.append(v)
    if msrp_vals:
        return max(msrp_vals)
    return None

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

    final_row=None
    for loc in locales_try:
        for cand in pids_try:
            url=f"https://store.playstation.com/{loc}/product/{cand}"
            html=_html(url, loc)
            if not html: 
                time.sleep(0.1); 
                continue

            j=_next_json(html)
            msrp=price=curr=None; edition_label=None
            if j:
                b,d,curr0,ed=_extract_prices_from_next_data(j)
                if b is not None: msrp=b
                if d is not None: price=d
                if curr0: curr=curr0
                edition_label = ed

            # If this looks like non-standard, hop to preferred edition if we can find one
            label_for_score = (edition_label or title or "")
            if _score_edition(label_for_score) < 0:
                target_href, target_label = _find_preferred_product_link(html, loc)
                if target_href and target_href != url:
                    html2=_html(target_href, loc)
                    if html2:
                        j2=_next_json(html2)
                        b2=d2=curr2=lab2=None
                        if j2:
                            b2,d2,curr2,lab2=_extract_prices_from_next_data(j2)
                        msrp = b2 if b2 is not None else msrp
                        price = d2 if d2 is not None else price
                        curr  = curr2 or curr
                        edition_label = lab2 or target_label or "Standard"
                        url = target_href

            # MSRP-only fallback from <del> when toggle is on
            if prefer_msrp and (msrp is None):
                msrp = _extract_msrp_from_del(html)

            chosen_currency = (curr or PS_CCY_MAP.get(cc_iso.upper(), cur_fb))
            chosen_amount = msrp if prefer_msrp and msrp is not None else (price if price is not None else msrp)

            if chosen_amount is not None:
                final_row = PriceRow("PlayStation", title or (edition_label or f"PS {pid}"), cc_iso.upper(), chosen_currency, float(chosen_amount), url, f"ps:{ref or pid}", edition_label or "Standard")
                break
        if final_row: break

    if final_row: 
        return final_row, None
    return None, MissRow("PlayStation", title or f"PS {pid}", cc_iso, "no_price")

# ------------- UI -------------
with st.sidebar:
    st.header("Controls")
    default_markets=",".join(sorted(COUNTRY_NAMES.keys()))
    user_markets=st.text_area("Markets (comma-separated ISO country codes)", value=default_markets, height=120)
    markets=[m.strip().upper() for m in user_markets.split(",") if m.strip()]
    quick = st.checkbox("Quick run (top 25 markets)", value=True)
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

if run:
    steam_rows=[r for r in st.session_state.steam_rows if r.get("include") and r.get("appid")]
    xbox_rows=[r for r in st.session_state.xbox_rows if r.get("include") and r.get("store_id")]
    ps_rows=[r for r in st.session_state.ps_rows if r.get("include") and (r.get("ps_ref") or r.get("title"))]

    if quick and len(markets)>25:
        markets=sorted(markets)[:25]
        st.info(f"Quick run enabled: limiting to {len(markets)} markets.")

    total = len(markets)*(len(steam_rows)+len(xbox_rows)+len(ps_rows))
    prog = st.progress(0.0)
    done = 0

    rows=[]; misses=[]
    with st.status("Pulling prices across markets…"):
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs=[]
            for cc in markets:
                for r in steam_rows: futs.append(ex.submit(fetch_steam_price, r['appid'], cc, r.get('title')))
                for r in xbox_rows:  futs.append(ex.submit(fetch_xbox_price,  r.get('title'), r['store_id'], cc))
                for r in ps_rows:    futs.append(ex.submit(fetch_playstation_price, r.get('ps_ref',''), cc, r.get('title'), prefer_msrp))
            for f in as_completed(futs):
                try: pr, miss = f.result()
                except Exception: pr, miss = None, MissRow('unknown','unknown','unknown','exception')
                if pr: rows.append(pr)
                if miss: misses.append(miss)
                done += 1
                prog.progress(min(1.0, done/total if total>0 else 1.0))

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
        st.subheader("Raw Basket Rows (after scaling)"); st.dataframe(raw, use_container_width=True)

        grp=raw.groupby(["platform","country","currency"], dropna=False)
        sums=grp.apply(lambda g:(g["price"]*g["weight"]).sum()).rename("weighted_sum")
        wts=grp["weight"].sum().rename("weight_total")
        reco=pd.concat([sums,wts],axis=1).reset_index()
        reco["RecommendedPrice"]=reco.apply(lambda r:(r["weighted_sum"]/r["weight_total"]) if r["weight_total"]>0 else None, axis=1)
        reco=reco[["platform","country","currency","RecommendedPrice"]]

        # Vanity rounding
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
        st.download_button("⬇️ Download CSV (combined recommendations)", merged.to_csv(index=False).encode("utf-8"),
                           file_name="aaa_tier_recommendations_xsx_steam_ps_v3_9.csv", mime="text/csv")

    if misses:
        st.subheader("Diagnostics (no price found)")
        st.dataframe(pd.DataFrame([asdict(m) for m in misses]), use_container_width=True)
else:
    st.caption("Tip: enable Quick run for a fast sanity check; then disable it to run all markets.")
