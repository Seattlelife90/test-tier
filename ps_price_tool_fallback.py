
# ps_price_tool_fallback.py
import re
import json
from urllib.parse import urljoin
import requests
import pandas as pd
import streamlit as st

try:
    from bs4 import BeautifulSoup  # type: ignore
    HAS_BS4 = True
except Exception:
    HAS_BS4 = False

APP_TITLE = "PlayStation Price Puller (Concept GraphQL, no-lxml)"
GRAPHQL = "https://web.np.playstation.com/api/graphql/v1/op"
HASH_CONCEPT = "eab9d873f90d4ad98fd55f07b6a0a606e6b3925f2d03b70477234b79c1df30b5"

def make_session(locale: str):
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": locale + ",en;q=0.8",
        "Origin": "https://store.playstation.com",
        "x-psn-store-locale": locale,
        "x-psn-store-locale-override": locale,
    })
    return s

def extract_links(html_text: str, base_url: str) -> list[str]:
    links = []
    if HAS_BS4:
        soup = BeautifulSoup(html_text, "html.parser")
        for a in soup.find_all("a", href=True):
            links.append(urljoin(base_url, a["href"]))
    else:
        for href in re.findall(r'href=["\'](.*?)["\']', html_text, flags=re.I):
            links.append(urljoin(base_url, href))
    seen = set()
    out = []
    for u in links:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def clean_url(u: str) -> str:
    if not u:
        return u
    u = u.strip()
    if u.startswith("//"):
        u = "https:" + u
    return u

def first_store_link(marketing_url: str, session: requests.Session) -> str | None:
    r = session.get(marketing_url, timeout=20)
    r.raise_for_status()
    links = extract_links(r.text, marketing_url)
    store_links = [u for u in links if "store.playstation.com" in u]
    for u in store_links:
        if "/concept/" in u:
            return u.split("?")[0]
    return store_links[0] if store_links else None

def concept_from_store_url(store_url: str, session: requests.Session) -> str | None:
    m = re.search(r"/concept/(\d+)", store_url)
    if m:
        return m.group(1)
    r = session.get(store_url, timeout=20)
    r.raise_for_status()
    links = extract_links(r.text, store_url)
    for href in links:
        if "/concept/" in href:
            m = re.search(r"/concept/(\d+)", href)
            if m:
                return m.group(1)
    return None

def concept_from_any(url: str, session: requests.Session) -> tuple[str | None, str | None]:
    url = clean_url(url)
    if not url:
        return None, None
    if "store.playstation.com" in url:
        cid = concept_from_store_url(url, session)
        if cid:
            m = re.search(r"store\.playstation\.com/(\w{2}-\w{2})/", url)
            locale = m.group(1) if m else "en-US"
            return cid, f"https://store.playstation.com/{locale}/concept/{cid}"
        return None, None
    store = first_store_link(url, session)
    if not store:
        return None, None
    cid = concept_from_store_url(store, session)
    if not cid:
        return None, None
    m = re.search(r"store\.playstation\.com/(\w{2}-\w{2})/", store)
    locale = m.group(1) if m else "en-US"
    return cid, f"https://store.playstation.com/{locale}/concept/{cid}"

def prime_cookies(concept_url: str, session: requests.Session):
    try:
        session.get(concept_url, timeout=20)
    except Exception:
        pass

def fetch_prices_by_concept(concept_id: str, concept_url: str, session: requests.Session) -> dict:
    params = {
        "operationName": "conceptRetrieveForCtasWithPrice",
        "variables": json.dumps({"conceptId": concept_id}),
        "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": HASH_CONCEPT}}),
    }
    headers = {"Referer": concept_url}
    r = session.get(GRAPHQL, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def extract_title_and_price(data: dict) -> tuple[str | None, dict | None]:
    if not data or "data" not in data:
        return None, None
    payload = data.get("data", {}).get("conceptRetrieveForCtasWithPrice") or {}
    title = payload.get("name") or (payload.get("concept") or {}).get("name")
    products = payload.get("products") or []
    price = None

    def as_str(d, key):
        v = d.get(key)
        return str(v) if v is not None else None

    for p in products:
        if any(k in p for k in ("currencyCode","basePrice","discountedPrice")):
            price = {
                "currencyCode": as_str(p, "currencyCode"),
                "basePrice": as_str(p, "basePrice"),
                "discountedPrice": as_str(p, "discountedPrice"),
                "discountText": as_str(p, "discountText"),
                "endDate": as_str(p, "endDate") or as_str(p, "discountEndDate")
            }
            title = title or p.get("name")
            break
        for cta in (p.get("webctas") or p.get("webCTAs") or []):
            pr = cta.get("price") or {}
            if pr.get("currencyCode"):
                price = {
                    "currencyCode": as_str(pr, "currencyCode"),
                    "basePrice": as_str(pr, "basePrice"),
                    "discountedPrice": as_str(pr, "discountedPrice"),
                    "discountText": as_str(pr, "discountText"),
                    "endDate": as_str(pr, "endDate") or as_str(pr, "discountEndDate")
                }
                title = title or p.get("name")
                break
        if price:
            break
    if not price and products:
        pr = (products[0].get("price") or {})
        if pr:
            price = {
                "currencyCode": as_str(pr, "currencyCode"),
                "basePrice": as_str(pr, "basePrice"),
                "discountedPrice": as_str(pr, "discountedPrice"),
                "discountText": as_str(pr, "discountText"),
                "endDate": as_str(pr, "endDate") or as_str(pr, "discountEndDate")
            }
            title = title or products[0].get("name")
    return title, price

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption("Paste ANY PlayStation URL (marketing or store). The app resolves the concept page and calls the GraphQL pricing API for the selected region. (No lxml dependency)")

locales = [
    "en-US","en-CA","fr-CA","en-GB","en-AU","en-NZ","en-ZA",
    "ja-JP","es-ES","de-DE","fr-FR","it-IT","pt-BR","es-MX","ko-KR"
]
col_loc, _ = st.columns([1,3])
with col_loc:
    locale = st.selectbox("Region/Locale", locales, index=0)

default1 = "https://store.playstation.com/en-us/concept/10014149"
default2 = "https://www.playstation.com/en-us/games/call-of-duty-black-ops-6/"

with st.form("inputs"):
    c1, c2 = st.columns(2)
    with c1:
        url1 = st.text_input("Game URL #1", value=default1)
        name1 = st.text_input("Optional Name #1 (override)", value="")
    with c2:
        url2 = st.text_input("Game URL #2", value=default2)
        name2 = st.text_input("Optional Name #2 (override)", value="")
    run = st.form_submit_button("Pull Prices")

@st.cache_data(show_spinner=False)
def resolve_and_fetch(url: str, override_name: str, locale: str):
    if not url:
        return None
    session = make_session(locale)
    cid, concept_url = concept_from_any(url, session)
    if not cid:
        return {"input_url": url, "error": "Could not resolve conceptId from URL."}
    prime_cookies(concept_url, session)
    try:
        data = fetch_prices_by_concept(cid, concept_url, session)
    except Exception as e:
        return {"input_url": url, "concept_url": concept_url, "concept_id": cid, "error": str(e)}
    title, price = extract_title_and_price(data)
    if override_name:
        title = override_name
    row = {
        "input_url": url,
        "concept_url": concept_url,
        "concept_id": cid,
        "title": title or "",
    }
    if price:
        row.update(price)
    else:
        row["error"] = "Price not found in response."
    return row

if run:
    rows = []
    for u, n in [(url1, name1), (url2, name2)]:
        if u.strip():
            rows.append(resolve_and_fetch(u.strip(), n.strip(), locale))
    if rows:
        df = pd.DataFrame(rows)
        cols_order = ["title","currencyCode","basePrice","discountedPrice","discountText","endDate","concept_id","concept_url","input_url","error"]
        for c in cols_order:
            if c not in df.columns:
                df[c] = ""
        df = df[cols_order]
        st.subheader("Results")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Enter at least one URL and press Pull Prices.")

with st.expander("Notes / Troubleshooting"):
    st.markdown(
        "- If a URL opens a marketing page (`playstation.com/games/...`), the app resolves the corresponding Store concept page automatically.\n"
        "- Locale drives currency (e.g., `en-CA` → CAD). If results look US-based, try again with the correct locale or switch between `en-CA` and `fr-CA`.\n"
        "- Some titles have multiple editions; this app returns the first full-game style product it finds.\n"
        "- Concept IDs are stable and reusable across locales."
    )
