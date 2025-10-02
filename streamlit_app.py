# streamlit_app.py
# Canonical titles + validators + scaling by identity
import random
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import pandas as pd
import requests
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="AAA Tier Pricing Composer (Xbox + Steam)", page_icon="🎮", layout="wide")
st.title("🎮 AAA Tier Pricing Composer — Xbox + Steam")
st.caption("Editable basket · Per-row scale factor · Weighted means · Platform-true pulls · Canonical titles")

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

XBOX_LOCALE_MAP: Dict[str, Optional[str]] = {
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
    return "en-us"

DEFAULT_STEAM_ROWS = [
    {"include": True, "title": "The Outer Worlds 2", "appid": "1449110", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""},
    {"include": True, "title": "Madden NFL 26",       "appid": "3230400", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""},
    {"include": True, "title": "Call of Duty: Black Ops 6", "appid": "2933620", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""},
    {"include": True, "title": "NBA 2K26",            "appid": "3472040", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""},
    {"include": True, "title": "Borderlands 4",       "appid": "1285190", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""},
    {"include": True, "title": "HELLDIVERS 2",        "appid": "553850",  "scale_factor": 1.75, "weight": 1.0, "_steam_error": ""},
]
DEFAULT_XBOX_ROWS = [
    {"include": True, "title": "The Outer Worlds 2", "store_id": "9NSPRSXXZZLG", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""},
    {"include": True, "title": "Madden NFL 26",      "store_id": "9NVD16NP4J8T", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""},
    {"include": True, "title": "Call of Duty: Black Ops 6", "store_id": "9PNCL2R6G8D0", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""},
    {"include": True, "title": "NBA 2K26",           "store_id": "9PJ2RVRC0L1X", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""},
    {"include": True, "title": "Borderlands 4",      "store_id": "9MX6HKF5647G", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""},
    {"include": True, "title": "HELLDIVERS 2",       "store_id": "9P3PT7PQJD0M", "scale_factor": 1.75, "weight": 1.0, "_xbox_error": ""},
]

VANITY_RULES = {"AU":{"suffix":0.95,"nines":True},"NZ":{"suffix":0.95,"nines":True},"CA":{"suffix":0.99,"nines":True}}
UA = {"User-Agent": "Mozilla/5.0"}

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

def _nearest_x9_suffix(price: float, cents_suffix: float) -> float:
    base_tens = int(price // 10)
    cand = []
    for k in range(base_tens-2, base_tens+4):
        x = 10*k + 9 + cents_suffix
        if x > 0: cand.append(x)
    return round(min(cand, key=lambda v: (abs(v-price), -v)), 2)

def apply_vanity(country: str, price: float) -> float:
    rule = VANITY_RULES.get(country.upper())
    if rule and rule.get("nines"):
        return _nearest_x9_suffix(float(price), float(rule["suffix"]))
    return round(price, 2)

STEAM_APPDETAILS = "https://store.steampowered.com/api/appdetails"
STEAM_PACKAGEDETAILS = "https://store.steampowered.com/api/packagedetails"

def _steam_appdetails(appid: str, cc: str) -> Optional[dict]:
    try:
        r = requests.get(STEAM_APPDETAILS, params={"appids": appid, "cc": cc, "l":"en"}, headers=UA, timeout=25)
        data = r.json().get(str(appid), {})
        if not data or not data.get("success"): return None
        return data.get("data") or {}
    except Exception:
        return None

def _steam_packagedetails(ids: List[int], cc: str) -> Dict[int, dict]:
    out: Dict[int, dict] = {}
    try:
        pid_str = ",".join(str(i) for i in ids)
        r = requests.get(STEAM_PACKAGEDETAILS, params={"packageids": pid_str, "cc": cc, "l":"en"}, headers=UA, timeout=25)
        data = r.json() if r.status_code == 200 else {}
        for pid, obj in (data or {}).items():
            if isinstance(obj, dict) and obj.get("success") and isinstance(obj.get("data"), dict):
                out[int(pid)] = obj["data"]
    except Exception:
        pass
    return out

def fetch_steam_price(appid: str, cc_iso: str, forced_title: Optional[str]) -> Tuple[Optional[PriceRow], Optional[MissRow]]:
    cc = steam_cc_for(cc_iso)
    data = _steam_appdetails(appid, cc)
    if not data:
        return None, MissRow("Steam", forced_title or appid, cc_iso, "appdetails_no_data")
    pov = data.get("price_overview") or {}
    cents = None
    if isinstance(pov.get("initial"), int) and pov.get("initial") > 0:
        cents = pov.get("initial")
    elif isinstance(pov.get("final"), int) and pov.get("final") > 0:
        cents = pov.get("final")
    if cents:
        price = round(cents/100.0, 2)
        currency = (pov.get("currency") or "").upper() or None
        name = forced_title or data.get("name") or f"Steam App {appid}"
        return PriceRow("Steam", name, cc_iso.upper(), currency, price, f"https://store.steampowered.com/app/{appid}", f"steam:{appid}"), None
    sub_ids = []
    if isinstance(data.get("packages"), list):
        sub_ids += [int(x) for x in data.get("packages") if isinstance(x, int)]
    for grp in data.get("package_groups", []):
        for sub in grp.get("subs", []):
            sid = sub.get("packageid")
            if isinstance(sid, int): sub_ids.append(sid)
    sub_ids = list(dict.fromkeys(sub_ids))
    if not sub_ids:
        return None, MissRow("Steam", forced_title or data.get("name") or appid, cc_iso, "packagedetails_no_price")
    packs = _steam_packagedetails(sub_ids, cc=cc)
    for _, p in packs.items():
        price_obj = (p.get("price") or {})
        cents = price_obj.get("initial") if isinstance(price_obj.get("initial"), int) and price_obj.get("initial")>0 else price_obj.get("final")
        if isinstance(cents, int) and cents > 0:
            price = round(cents/100.0, 2)
            currency = (price_obj.get("currency") or "").upper() or None
            name = forced_title or data.get("name") or f"Steam App {appid}"
            return PriceRow("Steam", name, cc_iso.upper(), currency, price, f"https://store.steampowered.com/app/{appid}", f"steam:{appid}"), None
    return None, MissRow("Steam", forced_title or data.get("name") or appid, cc_iso, "packagedetails_no_price")

STORESDK_URL = "https://storeedgefd.dsx.mp.microsoft.com/v9.0/sdk/products"
DISPLAYCATALOG_URL = "https://displaycatalog.mp.microsoft.com/v7.0/products"

def _ms_cv() -> str:
    import string
    return "".join(random.choice(string.ascii_letters+string.digits) for _ in range(24))

def _parse_xbox_price_from_products(payload: dict) -> Tuple[Optional[float], Optional[str]]:
    try:
        products = payload.get("Products") or payload.get("products")
        if not products: return None, None
        p0 = products[0]
        dsa = p0.get("DisplaySkuAvailabilities") or p0.get("displaySkuAvailabilities") or []
        for sku in dsa:
            avs = sku.get("Availabilities") or sku.get("availabilities") or []
            for av in avs:
                omd = av.get("OrderManagementData") or av.get("orderManagementData") or {}
                price = omd.get("Price") or omd.get("price") or {}
                amount = price.get("MSRP") or price.get("msrp") or price.get("ListPrice") or price.get("listPrice")
                currency = price.get("CurrencyCode") or price.get("currencyCode")
                if amount:
                    return float(amount), (str(currency).upper() if currency else None)
        return None, None
    except Exception:
        return None, None

def fetch_xbox_price(product_name: str, product_id: str, market_iso: str) -> Tuple[Optional[PriceRow], Optional[MissRow]]:
    headers = {"MS-CV": _ms_cv(), "Accept": "application/json"}
    loc = xbox_locale_for(market_iso)
    try:
        r = requests.get(STORESDK_URL, params={"bigIds": product_id, "market": market_iso.upper(), "locale": loc}, headers=headers, timeout=25)
        if r.status_code == 200:
            amt, ccy = _parse_xbox_price_from_products(r.json())
            if amt:
                return PriceRow("Xbox", product_name or "Xbox Product", market_iso.upper(), ccy.upper() if ccy else None, float(amt),
                                f"https://www.xbox.com/{loc.split('-')[0]}/games/store/placeholder/{product_id}", f"xbox:{product_id}"), None
    except Exception:
        pass
    try:
        r = requests.get(DISPLAYCATALOG_URL, params={"bigIds": product_id, "market": market_iso.upper(), "languages": "en-US", "fieldsTemplate": "Details"}, headers=headers, timeout=25)
        if r.status_code == 200:
            amt, ccy = _parse_xbox_price_from_products(r.json())
            if amt:
                return PriceRow("Xbox", product_name or "Xbox Product", market_iso.upper(), ccy.upper() if ccy else None, float(amt),
                                f"https://www.xbox.com/en-US/games/store/placeholder/{product_id}", f"xbox:{product_id}"), None
    except Exception:
        pass
    return None, MissRow("Xbox", product_name or product_id, market_iso, "no_price_entries")

def validate_and_fill_steam_rows(rows: List[dict]) -> List[dict]:
    updated = []
    for r in rows:
        appid = str(r.get("appid") or "").strip()
        if not appid.isdigit():
            r["_steam_error"] = "appid must be numeric"; updated.append(r); continue
        data = _steam_appdetails(appid, cc="US")
        if not data:
            r["_steam_error"] = "not found on Steam API"
        else:
            r["_steam_error"] = ""
            if not r.get("title"):
                r["title"] = data.get("name") or r.get("title")
        updated.append(r)
    return updated

def validate_and_fill_xbox_rows(rows: List[dict]) -> List[dict]:
    updated = []
    headers = {"MS-CV": _ms_cv(), "Accept": "application/json"}
    for r in rows:
        store_id = str(r.get("store_id") or "").strip()
        if len(store_id) != 12 or not store_id.upper().startswith("9"):
            r["_xbox_error"] = "store_id should be 12 chars (usually starts with 9)"; updated.append(r); continue
        try:
            resp = requests.get(DISPLAYCATALOG_URL, params={"bigIds": store_id, "market": "US", "languages": "en-US", "fieldsTemplate": "Details"}, headers=headers, timeout=12)
            j = resp.json() if resp.status_code == 200 else {}
            products = j.get("Products") or j.get("products") or []
            if not products:
                r["_xbox_error"] = "not found on Xbox catalog"
            else:
                r["_xbox_error"] = ""
                if not r.get("title"):
                    lp = (products[0].get("LocalizedProperties") or products[0].get("localizedProperties") or [])
                    if lp and lp[0].get("ProductTitle"):
                        r["title"] = lp[0]["ProductTitle"]
        except Exception:
            r["_xbox_error"] = "lookup error"
        updated.append(r)
    return updated

with st.sidebar:
    st.header("Controls")
    default_markets = ",".join(sorted(COUNTRY_NAMES.keys()))
    user_markets = st.text_area("Markets (comma-separated ISO country codes)", value=default_markets, height=120)
    markets = [m.strip().upper() for m in user_markets.split(",") if m.strip()]

    st.markdown("**Scale factor help**\n- Leave 1.0 for no scaling.\n- 39.99 -> 69.99 = 1.75 (7/4)\n- 49.99 -> 69.99 = 1.40 (7/5)\n- 29.99 -> 69.99 = 2.33\nGeneral rule: scale_factor = target_price / source_price.")

    if "steam_rows" not in st.session_state:
        st.session_state.steam_rows = DEFAULT_STEAM_ROWS.copy()
    if "xbox_rows" not in st.session_state:
        st.session_state.xbox_rows = DEFAULT_XBOX_ROWS.copy()

    st.subheader("Steam basket")
    steam_df = st.data_editor(
        pd.DataFrame(st.session_state.steam_rows),
        key="steam_editor",
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "include": st.column_config.CheckboxColumn(default=True),
            "title":   st.column_config.TextColumn(),
            "appid":   st.column_config.TextColumn(),
            "scale_factor": st.column_config.NumberColumn(step=0.05, min_value=0.0, max_value=10.0, format="%.2f"),
            "weight":  st.column_config.NumberColumn(step=0.1, min_value=0.0, max_value=10.0, format="%.2f"),
            "_steam_error": st.column_config.TextColumn("error", disabled=True),
        },
    )
    st.session_state.steam_rows = steam_df.to_dict(orient="records")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔎 Validate & auto-fill (Steam)"):
            st.session_state.steam_rows = validate_and_fill_steam_rows(st.session_state.steam_rows)
            st.rerun()
    with c2:
        if st.button("➕ Add Steam row"):
            st.session_state.steam_rows.append({"include": True, "title": "", "appid": "", "scale_factor": 1.0, "weight": 1.0, "_steam_error": ""})
            st.rerun()

    st.subheader("Xbox basket")
    xbox_df = st.data_editor(
        pd.DataFrame(st.session_state.xbox_rows),
        key="xbox_editor",
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "include": st.column_config.CheckboxColumn(default=True),
            "title":   st.column_config.TextColumn(),
            "store_id": st.column_config.TextColumn(),
            "scale_factor": st.column_config.NumberColumn(step=0.05, min_value=0.0, max_value=10.0, format="%.2f"),
            "weight":  st.column_config.NumberColumn(step=0.1, min_value=0.0, max_value=10.0, format="%.2f"),
            "_xbox_error": st.column_config.TextColumn("error", disabled=True),
        },
    )
    st.session_state.xbox_rows = xbox_df.to_dict(orient="records")

    d1, d2 = st.columns(2)
    with d1:
        if st.button("🔎 Validate & auto-fill (Xbox)"):
            st.session_state.xbox_rows = validate_and_fill_xbox_rows(st.session_state.xbox_rows)
            st.rerun()
    with d2:
        if st.button("➕ Add Xbox row"):
            st.session_state.xbox_rows.append({"include": True, "title": "", "store_id": "", "scale_factor": 1.0, "weight": 1.0, "_xbox_error": ""})
            st.rerun()

    st.divider()
    run = st.button("Run Pricing Pull", type="primary")

if run:
    steam_rows = [r for r in st.session_state.steam_rows if r.get("include") and r.get("appid")]
    xbox_rows  = [r for r in st.session_state.xbox_rows  if r.get("include") and r.get("store_id")]

    steam_meta   = { f"steam:{str(r['appid']).strip()}": {"weight": float(r.get("weight",1.0)), "scale": float(r.get("scale_factor",1.0))} for r in steam_rows }
    xbox_meta    = { f"xbox:{str(r['store_id']).strip()}": {"weight": float(r.get("weight",1.0)), "scale": float(r.get("scale_factor",1.0))} for r in xbox_rows }
    steam_title  = { f"steam:{str(r['appid']).strip()}": (r.get("title") or f"Steam App {r['appid']}") for r in steam_rows }
    xbox_title   = { f"xbox:{str(r['store_id']).strip()}": (r.get("title") or f"Xbox Product {r['store_id']}") for r in xbox_rows }
    TITLE_MAP = {**steam_title, **xbox_title}

    rows: List[PriceRow] = []
    misses: List[MissRow] = []
    with st.status("Pulling prices across markets…", expanded=False) as status:
        futures = []
        with ThreadPoolExecutor(max_workers=20) as ex:
            for cc in markets:
                for r in steam_rows:
                    futures.append(ex.submit(fetch_steam_price, str(r["appid"]).strip(), cc, TITLE_MAP[f"steam:{str(r['appid']).strip()}"]))
            for cc in markets:
                for r in xbox_rows:
                    futures.append(ex.submit(fetch_xbox_price, TITLE_MAP[f"xbox:{str(r['store_id']).strip()}"], str(r["store_id"]).strip(), cc))

            for f in as_completed(futures):
                try:
                    result = f.result()
                except Exception:
                    result = (None, MissRow("unknown","unknown","unknown","exception"))
                row, miss = result
                if row: rows.append(row)
                if miss: misses.append(miss)

        if not rows and not misses:
            status.update(label="No data returned — check IDs or try fewer markets.", state="error")
            st.stop()
        status.update(label="Done!", state="complete")

    raw_df = pd.DataFrame([asdict(r) for r in rows])
    if not raw_df.empty:
        raw_df.insert(2, "country_name", raw_df["country"].map(country_name))
        def _meta(identity):
            return (steam_meta if identity.startswith("steam:") else xbox_meta).get(identity, {"weight":1.0, "scale":1.0})
        meta_df = pd.DataFrame(list(raw_df["identity"].map(lambda i: _meta(i))))
        raw_df = pd.concat([raw_df, meta_df], axis=1)
        raw_df["title"] = raw_df["identity"].map(lambda i: TITLE_MAP.get(i, "Unknown"))
        raw_df["price"] = raw_df["price"] * raw_df["scale"]
        raw_df["title"] = raw_df.apply(lambda r: f"{r['title']} (scaled)" if r["scale"] and abs(r["scale"]-1.0) > 1e-6 else r["title"], axis=1)

        grp = raw_df.groupby(["platform","country","currency"], dropna=False)
        sums = grp.apply(lambda g: (g["price"] * g["weight"]).sum()).rename("weighted_sum")
        wts  = grp["weight"].sum().rename("weight_total")
        reco = pd.concat([sums, wts], axis=1).reset_index()
        reco["RecommendedPrice"] = reco.apply(lambda r: (r["weighted_sum"]/r["weight_total"]) if r["weight_total"]>0 else None, axis=1)
        reco = reco[["platform","country","currency","RecommendedPrice"]]
        reco.insert(1, "country_name", reco["country"].map(country_name))

        reco_xbox  = reco[reco["platform"]=="Xbox"][["country_name","country","currency","RecommendedPrice"]].reset_index(drop=True)
        reco_steam = reco[reco["platform"]=="Steam"][["country_name","country","currency","RecommendedPrice"]].reset_index(drop=True)

        if not reco_xbox.empty:
            reco_xbox["RecommendedPrice"]  = [apply_vanity(c,p) for c,p in zip(reco_xbox["country"],  reco_xbox["RecommendedPrice"])]
        if not reco_steam.empty:
            reco_steam["RecommendedPrice"] = [apply_vanity(c,p) for c,p in zip(reco_steam["country"], reco_steam["RecommendedPrice"])]

        st.subheader("Raw Basket Rows (after scaling)")
        st.dataframe(raw_df)

        st.subheader("Price Recommendations — Xbox (weighted per country)")
        st.dataframe(reco_xbox)

        st.subheader("Price Recommendations — Steam (weighted per country)")
        st.dataframe(reco_steam)

        merged = pd.merge(
            reco_xbox.rename(columns={"RecommendedPrice":"XboxRecommended"}),
            reco_steam.rename(columns={"RecommendedPrice":"SteamRecommended"}),
            on=["country_name","country","currency"],
            how="outer",
        ).sort_values(["country"]).reset_index(drop=True)

        st.subheader("Combined Recommendations (Xbox + Steam)")
        st.dataframe(merged)

        csv = merged.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV (combined recommendations)", data=csv, file_name="aaa_tier_recommendations_xbox_steam.csv", mime="text/csv")

    if misses:
        miss_df = pd.DataFrame([asdict(m) for m in misses]).sort_values(["platform","title","country"]).reset_index(drop=True)
        st.subheader("Diagnostics (no price found)")
        st.dataframe(miss_df)

else:
    st.info("Edit the baskets in the sidebar, set markets, then click Run Pricing Pull.", icon="🛠️")
