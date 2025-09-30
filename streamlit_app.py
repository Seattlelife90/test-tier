# streamlit_app.py
# ------------------------------------------------------------
# AAA Pricing Tier Composer (Xbox + Steam)
# (see previous message for feature list)
# ------------------------------------------------------------

import random
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="AAA Tier Pricing Composer (Xbox + Steam)", page_icon="🎮", layout="wide")
st.title("🎮 AAA Tier Pricing Composer — Xbox + Steam")
st.caption("Platform-true pulls: Steam uses Steam cc; Xbox uses Xbox locale. HELLDIVERS 2 scaled by (price/4)*7.")

COUNTRY_NAMES: Dict[str, str] = {
    "US":"United States","CA":"Canada","MX":"Mexico","BR":"Brazil","AR":"Argentina","CL":"Chile","CO":"Colombia",
    "PE":"Peru","UY":"Uruguay","PY":"Paraguay","EC":"Ecuador","CR":"Costa Rica","PA":"Panama","DO":"Dominican Republic",
    "GT":"Guatemala","HN":"Honduras","NI":"Nicaragua","SV":"El Salvador",
    "GB":"United Kingdom","IE":"Ireland","FR":"France","DE":"Germany","IT":"Italy","ES":"Spain","PT":"Portugal",
    "NL":"Netherlands","BE":"Belgium","LU":"Luxembourg","AT":"Austria","CH":"Switzerland","DK":"Denmark","SE":"Sweden",
    "NO":"Norway","FI":"Finland","PL":"Poland","CZ":"Czechia","SK":"Slovakia","HU":"Hungary","RO":"Romania",
    "BG":"Bulgaria","GR":"Greece","EE":"Estonia","LV":"Latvia","LT":"Lithuania","MT":"Malta","CY":"Cyprus","UA":"Ukraine",
    "TR":"Türkiye","IL":"Israel","SA":"Saudi Arabia","AE":"United Arab Emirates","QA":"Qatar","KW":"Kuwait","BH":"Bahrain",
    "OM":"Oman","JO":"Jordan","EG":"Egypt","MA":"Morocco","ZA":"South Africa",
    "JP":"Japan","KR":"South Korea","TW":"Taiwan","HK":"Hong Kong","SG":"Singapore","MY":"Malaysia",
    "TH":"Thailand","ID":"Indonesia","PH":"Philippines","VN":"Vietnam","IN":"India","AU":"Australia","NZ":"New Zealand",
    "KZ":"Kazakhstan","CN":"China",
}
def country_name(code: str) -> str:
    return COUNTRY_NAMES.get(code.upper(), code.upper())

STEAM_CC_MAP: Dict[str, str] = {
    "US":"US","KZ":"KZ","CN":"CN","UA":"UA","ID":"ID","AR":"AR","TR":"TR","BR":"BR","CL":"CL","IN":"IN","KR":"KR","PH":"PH",
    "JP":"JP","VN":"VN","CO":"CO","NZ":"NZ","CR":"CR","SA":"SA","TW":"TW","SK":"SK","PE":"PE","PL":"PL","SG":"SG","ZA":"ZA",
    "HK":"HK","MX":"MX","GB":"GB","CA":"CA","AU":"AU","MY":"MY","FR":"FR","DE":"FR","AT":"FR","BE":"FR","DK":"FR","FI":"FR",
    "IE":"FR","NL":"FR","PT":"FR","ES":"FR","CZ":"FR","GR":"FR","HU":"FR","TH":"TH","UY":"UY","QA":"QA","KW":"KW","AE":"AE",
    "SV":"SV","PK":"PK","AM":"AM","CH":"CH","IL":"IL","RU":"RU",
}
def steam_cc_for(market: str) -> str:
    return STEAM_CC_MAP.get(market.upper(), market.upper())

XBOX_LOCALE_MAP: Dict[str, str] = {
    "US":"en-us","KZ":None,"CN":"zh-CN","UA":"uk-ua","ID":"id-id","AR":"es-ar","TR":"tr-tr","BR":"pt-br","CL":"es-cl",
    "IN":"en-in","KR":"ko-kr","PH":"en-ph","JP":"ja-jp","VN":"vi-vn","CO":"es-co","NZ":"en-nz","CR":"es-cr","SA":"ar-sa",
    "SE":None,"TW":"zh-tw","SK":"sk-sk","PE":"es-pe","PL":"pl-pl","SG":"en-sg","ZA":"en-za","HK":"zh-hk","MX":"es-mx",
    "GB":"en-gb","CA":"en-ca","AU":"en-au","MY":"en-my","FR":"fr-fr","DE":"de-de","AT":"de-at","BE":"fr-fr","DK":None,
    "FI":"fi-fi","IE":"en-ie","NL":"nl-nl","PT":"pt-pt","ES":"es-es","CZ":"cs-cz","GR":"el-gr","HU":"hu-hu","TH":"th-th",
    "UY":None,"QA":"ar-qa","KW":"ar-kw","AE":"ar-ae","SV":None,"PK":None,"AM":None,"CH":"de-ch","IL":"he-il","RU":"ru-ru",
}
def xbox_locale_for(market: str) -> str:
    code = XBOX_LOCALE_MAP.get(market.upper())
    if code: return code
    fallback = {"US":"en-us","CA":"en-ca","GB":"en-gb","AU":"en-au","NZ":"en-nz","IE":"en-ie","ZA":"en-za",
        "MX":"es-mx","AR":"es-ar","CL":"es-cl","CO":"es-co","ES":"es-es","PE":"es-pe","CR":"es-cr",
        "BR":"pt-br","PT":"pt-pt","FR":"fr-fr","DE":"de-de","AT":"de-at","NL":"nl-nl","IT":"it-it",
        "JP":"ja-jp","KR":"ko-kr","TW":"zh-tw","HK":"zh-hk","CN":"zh-cn",
        "PL":"pl-pl","CZ":"cs-cz","SK":"sk-sk","HU":"hu-hu","GR":"el-gr","FI":"fi-fi","DK":"da-dk","SE":"sv-se",
        "TR":"tr-tr","IL":"he-il","AE":"ar-ae","QA":"ar-qa","KW":"ar-kw","SA":"ar-sa","RU":"ru-ru",
        "IN":"en-in","SG":"en-sg","MY":"en-my","PH":"en-ph","TH":"th-th","VN":"vi-vn","ID":"id-id"}
    return fallback.get(market.upper(), "en-us")

STEAM_APPIDS={"The Outer Worlds 2":"1449110","Madden NFL 26":"3230400","Call of Duty: Black Ops 6":"2933620","NBA 2K26":"3472040","Borderlands 4":"1285190","HELLDIVERS 2":"553850"}
XBOX_PRODUCT_IDS={"The Outer Worlds 2":"9NSPRSXXZZLG","Madden NFL 26":"9NVD16NP4J8T","Call of Duty: Black Ops 6":"9PNCL2R6G8D0","NBA 2K26":"9PJ2RVRC0L1X","Borderlands 4":"9MX6HKF5647G","HELLDIVERS 2":"9P3PT7PQJD0M"}
XBOX_PRODUCT_ALIASES={"Madden NFL 26":["9NVD16NP4J8T","9PGVZ5XPQ9SP"],"Call of Duty: Black Ops 6":["9PNCL2R6G8D0"],"NBA 2K26":["9PJ2RVRC0L1X"],"The Outer Worlds 2":["9NSPRSXXZZLG"]}

ZERO_DEC_CURRENCIES={"JPY","KRW","VND","CLP","ISK"}
VANITY_RULES={"AU":{"suffix":0.95,"nines":True},"NZ":{"suffix":0.95,"nines":True},"CA":{"suffix":0.99,"nines":True}}

@dataclass
class PriceRow:
    platform: str; title: str; country: str; currency: Optional[str]; price: Optional[float]; source_url: Optional[str]
@dataclass
class MissRow:
    platform: str; title: str; country: str; reason: str

def _nearest_x9_suffix(price: float, cents_suffix: float) -> float:
    base_tens=int(price//10); cand=[10*k+9+cents_suffix for k in range(base_tens-2,base_tens+3) if 10*k+9+cents_suffix>0]
    return round(min(cand,key=lambda v:(abs(v-price),-v)),2)
def apply_vanity(country: str, price: float) -> float:
    r=VANITY_RULES.get(country.upper()); 
    return _nearest_x9_suffix(float(price),float(r["suffix"])) if r and r.get("nines") else round(price,2)

STEAM_APPDETAILS="https://store.steampowered.com/api/appdetails"
STEAM_PACKAGEDETAILS="https://store.steampowered.com/api/packagedetails"
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

def _steam_appdetails(appid: str, cc: str)->Optional[dict]:
    try:
        r=requests.get(STEAM_APPDETAILS,params={"appids":appid,"cc":cc,"l":"en"},headers=UA,timeout=25)
        data=r.json().get(str(appid),{}); 
        if not data or not data.get("success"): return None
        return data.get("data") or {}
    except Exception: return None

def _steam_packagedetails(ids: List[int], cc: str)->Dict[int,dict]:
    out={}
    try:
        pid_str=",".join(str(i) for i in ids)
        r=requests.get(STEAM_PACKAGEDETAILS,params={"packageids":pid_str,"cc":cc,"l":"en"},headers=UA,timeout=25)
        data=r.json() if r.status_code==200 else {}
        for pid,obj in (data or {}).items():
            if isinstance(obj,dict) and obj.get("success") and isinstance(obj.get("data"),dict):
                out[int(pid)]=obj["data"]
    except Exception: pass
    return out

def fetch_steam_price(appid: str, cc_iso: str, forced_title: Optional[str]=None):
    cc=steam_cc_for(cc_iso)
    data=_steam_appdetails(appid,cc)
    if not data: return None, MissRow("Steam",forced_title or appid,cc_iso,"appdetails_no_data")
    pov=data.get("price_overview") or {}
    cents=None
    if isinstance(pov.get("initial"),int) and pov.get("initial")>0: cents=pov.get("initial")
    elif isinstance(pov.get("final"),int) and pov.get("final")>0: cents=pov.get("final")
    if cents:
        price=round(cents/100.0,2); currency=(pov.get("currency") or "").upper() or None; name=forced_title or data.get("name") or f"Steam App {appid}"
        return PriceRow("Steam",name,cc_iso.upper(),currency,price,f"https://store.steampowered.com/app/{appid}"), None
    sub_ids=[]
    if isinstance(data.get("packages"),list): sub_ids+=[int(x) for x in data.get("packages") if isinstance(x,int)]
    for grp in data.get("package_groups",[]):
        for sub in grp.get("subs",[]): 
            sid=sub.get("packageid"); 
            if isinstance(sid,int): sub_ids.append(sid)
    sub_ids=list(dict.fromkeys(sub_ids))
    if not sub_ids: return None, MissRow("Steam",forced_title or data.get("name") or appid,cc_iso,"no_price_overview_no_packages")
    packs=_steam_packagedetails(sub_ids,cc=cc)
    for pid,p in packs.items():
        price_obj=(p.get("price") or {})
        cents=price_obj.get("initial") if isinstance(price_obj.get("initial"),int) and price_obj.get("initial")>0 else price_obj.get("final")
        if isinstance(cents,int) and cents>0:
            price=round(cents/100.0,2); currency=(price_obj.get("currency") or "").upper() or None; name=forced_title or data.get("name") or f"Steam App {appid}"
            return PriceRow("Steam",name,cc_iso.upper(),currency,price,f"https://store.steampowered.com/app/{appid}"), None
    return None, MissRow("Steam",forced_title or data.get("name") or appid,cc_iso,"packagedetails_no_price")

STORESDK_URL="https://storeedgefd.dsx.mp.microsoft.com/v9.0/sdk/products"
DISPLAYCATALOG_URL="https://displaycatalog.mp.microsoft.com/v7.0/products"
def _ms_cv():
    import string; return "".join(random.choice(string.ascii_letters+string.digits) for _ in range(24))
def _parse_xbox_price_from_products(payload: dict):
    try:
        products=payload.get("Products") or payload.get("products")
        if not products: return None,None
        dsa=products[0].get("DisplaySkuAvailabilities") or products[0].get("displaySkuAvailabilities") or []
        for sku in dsa:
            for av in sku.get("Availabilities") or sku.get("availabilities") or []:
                price=(av.get("OrderManagementData") or av.get("orderManagementData") or {}).get("Price") or {}
                amount=price.get("MSRP") or price.get("msrp") or price.get("ListPrice") or price.get("listPrice")
                ccy=price.get("CurrencyCode") or price.get("currencyCode")
                if amount:
                    try: return float(amount),(str(ccy).upper() if ccy else None)
                    except: pass
        return None,None
    except Exception: return None,None
def fetch_xbox_price_one_market(pid,market_iso,locale):
    h={"MS-CV":_ms_cv(),"Accept":"application/json"}
    try:
        r=requests.get(STORESDK_URL,params={"bigIds":pid,"market":market_iso.upper(),"locale":locale},headers=h,timeout=25)
        if r.status_code==200:
            a,c=_parse_xbox_price_from_products(r.json()); 
            if a: return a,c,None
    except Exception: pass
    try:
        r=requests.get(DISPLAYCATALOG_URL,params={"bigIds":pid,"market":market_iso.upper(),"languages":locale,"fieldsTemplate":"Details"},headers=h,timeout=25)
        if r.status_code==200:
            a,c=_parse_xbox_price_from_products(r.json()); 
            if a: return a,c,None
    except Exception: pass
    return None,None,"no_price_entries"
def fetch_xbox_price(product_name,pid,market_iso,alt_ids: List[str]):
    loc=xbox_locale_for(market_iso); ids=[pid]+[i for i in alt_ids if i and i!=pid]+XBOX_PRODUCT_ALIASES.get(product_name,[])[1:]
    tried=False
    for id_ in ids:
        tried=True
        a,c,err=fetch_xbox_price_one_market(id_,market_iso,loc)
        if a: return PriceRow("Xbox",product_name,market_iso.upper(),c.upper() if c else None,float(a),f"https://www.xbox.com/{loc.split('-')[0]}/games/store/placeholder/{id_}"), None
    for id_ in ids:
        a,c,err=fetch_xbox_price_one_market(id_,market_iso,"en-US")
        if a: return PriceRow("Xbox",product_name,market_iso.upper(),c.upper() if c else None,float(a),f"https://www.xbox.com/en-US/games/store/placeholder/{id_}"), None
    return None, MissRow("Xbox",product_name,market_iso,"tried_alt_ids_no_price" if tried else "no_ids")

BASKET_TITLES=["The Outer Worlds 2","Madden NFL 26","Call of Duty: Black Ops 6","NBA 2K26","Borderlands 4","HELLDIVERS 2"]
def normalize_row(row:PriceRow)->PriceRow:
    return PriceRow(row.platform,row.title+" (scaled)",row.country,row.currency,round((row.price/4.0)*7.0,2),row.source_url) if row.title.lower().startswith("helldivers 2") and row.price is not None else row

with st.sidebar:
    st.header("Controls")
    default_markets=",".join(sorted(COUNTRY_NAMES.keys()))
    markets=[m.strip().upper() for m in st.text_area("Markets (comma-separated ISO country codes)",value=default_markets,height=140).split(",") if m.strip()]
    st.subheader("Game IDs (override if needed)")
    st.caption("Steam AppIDs")
    for k,v in list(STEAM_APPIDS.items()): STEAM_APPIDS[k]=st.text_input(f"Steam — {k}",value=v)
    st.caption("Xbox Product IDs (StoreId)")
    for k,v in list(XBOX_PRODUCT_IDS.items()): XBOX_PRODUCT_IDS[k]=st.text_input(f"Xbox — {k}",value=v)
    st.caption("Alt Store IDs (comma-separated; optional)")
    alt_ow2=st.text_input("Xbox ALT IDs — The Outer Worlds 2",value="")
    alt_2k =st.text_input("Xbox ALT IDs — NBA 2K26",value="")
    st.divider(); run=st.button("Run Pricing Pull",type="primary")

if run:
    rows=[]; misses=[]
    with st.status("Pulling prices across markets…",expanded=False) as status:
        futures=[]
        with ThreadPoolExecutor(max_workers=18) as ex:
            for cc in markets:
                for t in BASKET_TITLES:
                    a=STEAM_APPIDS.get(t); 
                    if a: futures.append(ex.submit(fetch_steam_price,a,cc,t))
            for cc in markets:
                for t in BASKET_TITLES:
                    pid=XBOX_PRODUCT_IDS.get(t); 
                    if pid:
                        alts = [x.strip() for x in (alt_ow2 if t=="The Outer Worlds 2" else alt_2k if t=="NBA 2K26" else "").split(",") if x.strip()]
                        futures.append(ex.submit(fetch_xbox_price,t,pid,cc,alts))
            for f in as_completed(futures):
                try: res=f.result()
                except Exception: res=(None, MissRow("unknown","unknown","unknown","exception"))
                row,miss=res
                if row: rows.append(normalize_row(row))
                if miss: misses.append(miss)
        if not rows and not misses: status.update(label="No data returned — check IDs or try fewer markets.",state="error"); st.stop()
        status.update(label="Done!",state="complete")
    raw_df=pd.DataFrame([asdict(r) for r in rows])
    if not raw_df.empty: raw_df.insert(2,"country_name",raw_df["country"].map(country_name))
    if not raw_df.empty:
        reco=(raw_df.groupby(["platform","country","currency"],dropna=False)["price"].mean().reset_index().rename(columns={"price":"RecommendedPrice"}))
        reco.insert(1,"country_name",reco["country"].map(country_name))
        rx=reco[reco["platform"]=="Xbox"][["country_name","country","currency","RecommendedPrice"]].reset_index(drop=True)
        rs=reco[reco["platform"]=="Steam"][["country_name","country","currency","RecommendedPrice"]].reset_index(drop=True)
        if not rx.empty: rx["RecommendedPrice"]=[apply_vanity(c,p) for c,p in zip(rx["country"],rx["RecommendedPrice"])]
        if not rs.empty: rs["RecommendedPrice"]=[apply_vanity(c,p) for c,p in zip(rs["country"],rs["RecommendedPrice"])]
        st.subheader("Raw Basket Rows (after normalization)"); st.dataframe(raw_df)
        st.subheader("Price Recommendations — Xbox (per country)"); st.dataframe(rx)
        st.subheader("Price Recommendations — Steam (per country)"); st.dataframe(rs)
        merged=pd.merge(rx.rename(columns={"RecommendedPrice":"XboxRecommended"}), rs.rename(columns={"RecommendedPrice":"SteamRecommended"}), on=["country_name","country","currency"], how="outer").sort_values(["country"]).reset_index(drop=True)
        st.subheader("Combined Recommendations (Xbox + Steam)"); st.dataframe(merged)
        csv=merged.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV (combined recommendations)", data=csv, file_name="aaa_tier_recommendations_xbox_steam.csv", mime="text/csv")
    if misses:
        miss_df=pd.DataFrame([asdict(m) for m in misses]).sort_values(["platform","title","country"]).reset_index(drop=True)
        st.subheader("Diagnostics (no price found)"); st.dataframe(miss_df)
else:
    st.info("Configure IDs/markets in the sidebar, then click **Run Pricing Pull** to generate recommendations.",icon="🛠️")
