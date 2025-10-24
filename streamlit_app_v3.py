
import re
import json
import io
from collections import Counter, defaultdict
from typing import List, Dict, Tuple

import streamlit as st
import pandas as pd

# Import the stable, siloed logic from your Claude-backed v2.5 module
import multiplatform_pricing_tool_v2_5 as v25

st.set_page_config(page_title="Game Pricing — v3 (Siloed Steam/Xbox/PS)", page_icon="🎮", layout="wide")

# =========================
# Helpers: ID extraction by URL (delegate to v2_5 where possible)
# =========================
def detect_platform_and_id(url: str) -> Tuple[str, str]:
    url = url.strip()
    if not url:
        return ("", "")
    # Steam
    if "store.steampowered.com/app/" in url:
        appid = v25.extract_steam_appid(url)
        return ("steam", appid or "")
    # Xbox
    if "xbox.com" in url and "/games/store/" in url:
        sid = v25.extract_xbox_store_id(url)
        return ("xbox", sid or "")
    # PlayStation
    if "store.playstation.com" in url and "/product/" in url:
        pid = v25.extract_ps_product_id(url)
        return ("ps", pid or "")
    return ("", "")

def pretty_country(code: str) -> str:
    return v25.COUNTRY_NAMES.get(code, code)

# =========================
# Competitive-set manager
# =========================
st.sidebar.header("Competitive Set")
st.sidebar.caption("Paste **URLs only** (Steam/Xbox/PS). One per line. We'll auto-detect platform, extract IDs, and fetch titles.")

default_urls = [
    # Steam
    "https://store.steampowered.com/app/1449110/The_Outer_Worlds_2/",
    "https://store.steampowered.com/app/3230400/EA_SPORTS_Madden_NFL_26/",
    "https://store.steampowered.com/app/2933620/Call_of_Duty_Black_Ops_6/",
    "https://store.steampowered.com/app/1285190/Borderlands_4/",
    "https://store.steampowered.com/app/3472040/NBA_2K26/",
    # Xbox
    "https://www.xbox.com/en-US/games/store/p/9NSPRSXXZZLG/0017",
    "https://www.xbox.com/en-us/games/store/ea-sports-madden-nfl-26/9nvd16np4j8t",
    "https://www.xbox.com/en-us/games/store/call-of-duty-black-ops-6-cross-gen-bundle/9pf528m6crhq",
    "https://www.xbox.com/en-us/games/store/borderlands-4/9mx6hkf5647g",
    "https://www.xbox.com/en-us/games/store/nba-2k26-standard-edition/9pj2rvrc0l1x",
    # PlayStation
    "https://store.playstation.com/en-us/product/UP6312-PPSA24588_00-0872768154966924",
    "https://store.playstation.com/en-us/product/UP0006-PPSA26127_00-MADDENNFL26GAME0",
    "https://store.playstation.com/en-us/product/UP0002-PPSA01649_00-CODBO6CROSSGEN01",
    "https://store.playstation.com/en-us/product/UP1001-PPSA01494_00-000000000000OAK2",
    "https://store.playstation.com/en-us/product/UP1001-PPSA28420_00-NBA2K26000000000",
]

urls_text = st.sidebar.text_area("URLs", value="\n".join(default_urls), height=260)

col_s1, col_s2, col_s3 = st.sidebar.columns([1,1,1])
with col_s1:
    clear_btn = st.button("Clear")
with col_s2:
    load_btn = st.file_uploader("Upload JSON", type=["json"], label_visibility="collapsed")
with col_s3:
    # We'll populate this via a download button later
    pass

if clear_btn:
    urls_text = ""
    st.experimental_rerun()

# Parse URLs into platform-specific ID lists
steam_games: List[Tuple[str, str]] = []
xbox_games: List[Tuple[str, str]] = []
ps_games: List[Tuple[str, str]] = []

def title_from_url(url: str) -> str:
    # Fallback title label from URL path if we can't fetch it
    try:
        if "steampowered.com/app/" in url:
            t = url.split("/app/")[1].split("/", 1)[1]
        elif "xbox.com" in url:
            t = url.split("/games/store/")[1].split("/")[0]
        elif "store.playstation.com" in url:
            t = url.split("/product/")[1]
        else:
            return "Game"
        return t.replace("-", " ").replace("_", " ").strip()[:60]
    except Exception:
        return "Game"

url_lines = [ln.strip() for ln in urls_text.splitlines() if ln.strip()]
for url in url_lines:
    platform, pid = detect_platform_and_id(url)
    label = title_from_url(url)
    if platform == "steam" and pid:
        steam_games.append((pid, label))
    elif platform == "xbox" and pid:
        xbox_games.append((pid, label))
    elif platform == "ps" and pid:
        ps_games.append((pid, label))

# Offer JSON download of the current comp list
export_payload = {
    "steam": [{"url": u, "id": detect_platform_and_id(u)[1]} for u in url_lines if "steampowered" in u],
    "xbox":  [{"url": u, "id": detect_platform_and_id(u)[1]} for u in url_lines if "xbox.com" in u],
    "ps":    [{"url": u, "id": detect_platform_and_id(u)[1]} for u in url_lines if "playstation.com" in u],
}
export_bytes = io.BytesIO(json.dumps(export_payload, indent=2).encode("utf-8"))
st.sidebar.download_button("Download JSON", data=export_bytes, file_name="comp_set.json", mime="application/json")

# Load JSON if provided
if load_btn is not None:
    try:
        content = json.load(load_btn)
        urls = []
        for key in ["steam","xbox","ps"]:
            for item in content.get(key, []):
                if isinstance(item, dict) and "url" in item:
                    urls.append(item["url"])
                elif isinstance(item, str):
                    urls.append(item)
        if urls:
            st.session_state["urls_override"] = "\n".join(urls)
            st.success("Loaded comp set from JSON.")
            st.experimental_rerun()
    except Exception as e:
        st.error(f"Failed to load JSON: {e}")

if "urls_override" in st.session_state:
    urls_text = st.session_state.pop("urls_override")

# =========================
# Markets controls — siloed per platform (from v2_5)
# =========================
st.sidebar.subheader("Markets")
steam_markets_all = sorted(list(v25.STEAM_MARKETS.keys()))
xbox_markets_all  = sorted(list(v25.XBOX_MARKETS.keys()))
ps_markets_all    = sorted(list(v25.PS_MARKETS.keys()))

steam_markets = st.sidebar.multiselect("Steam Markets", options=steam_markets_all, default=steam_markets_all)
xbox_markets  = st.sidebar.multiselect("Xbox Markets", options=xbox_markets_all, default=xbox_markets_all)
ps_markets    = st.sidebar.multiselect("PlayStation Markets", options=ps_markets_all, default=ps_markets_all)

show_diag = st.sidebar.toggle("Show diagnostics", value=False)

# =========================
# Main layout
# =========================
st.title("Unified Game Pricing — v3")
st.caption("Steam, Xbox, and PlayStation price pulls are **fully siloed**. Mean & Mode recommendations included.")

rcol1, rcol2 = st.columns([1,1])
with rcol1:
    run_steam = st.button("Run Steam")
with rcol2:
    run_all = st.button("Run All (Steam/Xbox/PS)")

run_xbox = st.button("Run Xbox")
run_ps   = st.button("Run PlayStation")

# =========================
# Execution
# =========================
def run_fetch(adapter: str):
    results = []

    if adapter in ("steam", "all") and steam_games and steam_markets:
        # Build list of tuples (appid, title) but title is passed through — v2.5 signatures expect (appid, country, title)
        for appid, title in steam_games:
            for country in steam_markets:
                results.append(("steam", appid, country, title))

    if adapter in ("xbox", "all") and xbox_games and xbox_markets:
        for store_id, title in xbox_games:
            for country in xbox_markets:
                results.append(("xbox", store_id, country, title))

    if adapter in ("ps", "all") and ps_games and ps_markets:
        for product_id, title in ps_games:
            for country in ps_markets:
                results.append(("ps", product_id, country, title))

    # Parallelism and progress are handled inside v2_5.pull_all_prices, but we can also batch by platform.
    steam_list = [(appid, title) for appid, title in steam_games]
    xbox_list  = [(sid, title) for sid, title in xbox_games]
    ps_list    = [(pid, title) for pid, title in ps_games]

    if adapter == "steam":
        xbox_list = []
        ps_list = []
    elif adapter == "xbox":
        steam_list = []
        ps_list = []
    elif adapter == "ps":
        steam_list = []
        xbox_list = []

    # Temporarily narrow markets inside v25 by monkey-patching maps?
    # Better: v2_5.pull_all_prices uses internal maps; we expose selected markets via globals.
    # We'll save originals, replace with filtered, call, then restore.
    orig_steam = dict(v25.STEAM_MARKETS)
    orig_xbox = dict(v25.XBOX_MARKETS)
    orig_ps = dict(v25.PS_MARKETS)
    try:
        v25.STEAM_MARKETS = {k: v for k, v in v25.STEAM_MARKETS.items() if k in set(steam_markets)}
        v25.XBOX_MARKETS  = {k: v for k, v in v25.XBOX_MARKETS.items()  if k in set(xbox_markets)}
        v25.PS_MARKETS    = {k: v for k, v in v25.PS_MARKETS.items()    if k in set(ps_markets)}
        steam_res, xbox_res, ps_res = v25.pull_all_prices(steam_list, xbox_list, ps_list, max_workers=8)
    finally:
        v25.STEAM_MARKETS = orig_steam
        v25.XBOX_MARKETS  = orig_xbox
        v25.PS_MARKETS    = orig_ps

    # v2_5 returns lists of PriceData
    results = []
    results.extend(steam_res)
    results.extend(xbox_res)
    results.extend(ps_res)
    return results, steam_res, xbox_res, ps_res

def to_df(results):
    # v2_5 has process_results to compute USD, US deltas, etc.
    df = v25.process_results(results)
    return df

def recommendations_mean_mode(df: pd.DataFrame) -> pd.DataFrame:
    # Expect columns: Platform, Title, Country, Currency, Local Price, USD, % vs. US, Type, Source, Debug (maybe)
    # Compute per Country & Platform: mean USD and mode USD across titles.
    if df.empty:
        return df
    # Normalize column names
    cols = {c.lower(): c for c in df.columns}
    usd_col = cols.get("usd") or cols.get("price_usd") or "USD"
    country_col = cols.get("country") or "Country"
    platform_col = cols.get("platform") or "Platform"

    rec_rows = []
    for (plat, ctry), grp in df.groupby([platform_col, country_col]):
        usd_vals = [v for v in grp[usd_col].tolist() if isinstance(v, (float, int))]
        if not usd_vals:
            continue
        mean_val = round(sum(usd_vals) / len(usd_vals), 2)
        # Mode: most common, break ties by highest frequency then nearest to mean
        counts = Counter(round(x, 2) for x in usd_vals)
        max_freq = max(counts.values())
        candidates = [val for val, cnt in counts.items() if cnt == max_freq]
        # choose candidate closest to mean
        mode_val = min(candidates, key=lambda x: abs(x - mean_val))
        rec_rows.append({
            "Platform": plat,
            "Country": ctry,
            "Mean (USD)": mean_val,
            "Mode (USD)": mode_val,
        })
    rec_df = pd.DataFrame(rec_rows).sort_values(["Platform", "Country"])
    return rec_df

# Containers for output
steam_container = st.container()
xbox_container  = st.container()
ps_container    = st.container()
recos_container = st.container()

if run_steam or run_all or run_xbox or run_ps:
    adapter = "all" if run_all else ("steam" if run_steam else ("xbox" if run_xbox else "ps"))
    results, steam_res, xbox_res, ps_res = run_fetch(adapter)
    df_all = to_df(results)

    # Split by platform for display
    with steam_container:
        sdf = df_all[df_all["Platform"] == "Steam"] if not df_all.empty else pd.DataFrame()
        st.subheader("Steam Results")
        st.dataframe(sdf, use_container_width=True)
        if not sdf.empty:
            st.download_button("Download Steam CSV", data=sdf.to_csv(index=False).encode("utf-8"), file_name="steam_prices.csv", mime="text/csv")

    with xbox_container:
        xdf = df_all[df_all["Platform"] == "Xbox"] if not df_all.empty else pd.DataFrame()
        st.subheader("Xbox Results")
        st.dataframe(xdf, use_container_width=True)
        if not xdf.empty:
            st.download_button("Download Xbox CSV", data=xdf.to_csv(index=False).encode("utf-8"), file_name="xbox_prices.csv", mime="text/csv")

    with ps_container:
        pdf = df_all[df_all["Platform"] == "PlayStation"] if not df_all.empty else pd.DataFrame()
        st.subheader("PlayStation Results")
        st.dataframe(pdf, use_container_width=True)
        if not pdf.empty:
            st.download_button("Download PlayStation CSV", data=pdf.to_csv(index=False).encode("utf-8"), file_name="ps_prices.csv", mime="text/csv")

    # Recommendations (Mean & Mode)
    rec_df = recommendations_mean_mode(df_all)
    with recos_container:
        st.subheader("Recommendations (Mean & Mode per Platform/Country)")
        st.dataframe(rec_df, use_container_width=True)
        if not rec_df.empty:
            st.download_button("Download Recommendations CSV", data=rec_df.to_csv(index=False).encode("utf-8"), file_name="recommendations_mean_mode.csv", mime="text/csv")

    # Diagnostics
    if show_diag and not df_all.empty:
        # If v2_5 includes a Debug column
        dbg_cols = [c for c in df_all.columns if "debug" in c.lower() or "source" in c.lower() or "Type" in c]
        if dbg_cols:
            st.subheader("Diagnostics")
            st.dataframe(df_all[["Platform","Title","Country"] + dbg_cols], use_container_width=True)
else:
    st.info("Paste URLs on the left, select markets, then click a Run button.")
