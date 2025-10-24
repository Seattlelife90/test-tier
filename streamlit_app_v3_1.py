
import streamlit as st
import pandas as pd
from collections import Counter
from typing import List, Tuple

import multiplatform_pricing_tool_v2_5 as v25

st.set_page_config(page_title="Game Pricing — v3.1 (Clean UX)", page_icon="🎮", layout="wide")

# =========================
# Helpers
# =========================
def detect_platform_and_id(url: str):
    url = url.strip()
    if not url:
        return ("", "")
    if "store.steampowered.com/app/" in url:
        return ("steam", v25.extract_steam_appid(url) or "")
    if "xbox.com" in url and "/games/store/" in url:
        return ("xbox", v25.extract_xbox_store_id(url) or "")
    if "store.playstation.com" in url and "/product/" in url:
        return ("ps", v25.extract_ps_product_id(url) or "")
    return ("", "")

def title_from_url(url: str) -> str:
    try:
        if "steampowered.com/app/" in url:
            t = url.split("/app/")[1].split("/", 1)[1]
        elif "xbox.com" in url and "/games/store/" in url:
            t = url.split("/games/store/")[1].split("/")[0]
        elif "store.playstation.com" in url and "/product/" in url:
            t = url.split("/product/")[1]
        else:
            return "Game"
        return t.replace("-", " ").replace("_", " ").strip()[:60]
    except Exception:
        return "Game"

def recommendations_mean_mode(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Platform","Country","Mean (USD)","Mode (USD)"])
    cols = {c.lower(): c for c in df.columns}
    usd_col = cols.get("usd") or "USD"
    country_col = cols.get("country") or "Country"
    platform_col = cols.get("platform") or "Platform"
    rows = []
    for (plat, ctry), grp in df.groupby([platform_col, country_col]):
        usd_vals = [v for v in grp[usd_col].tolist() if isinstance(v, (float, int))]
        if not usd_vals:
            continue
        mean_val = round(sum(usd_vals) / max(1, len(usd_vals)), 2)
        counts = Counter(round(x, 2) for x in usd_vals)
        max_freq = max(counts.values())
        candidates = [v for v, cnt in counts.items() if cnt == max_freq]
        mode_val = min(candidates, key=lambda x: abs(x - mean_val))
        rows.append({"Platform": plat, "Country": ctry, "Mean (USD)": mean_val, "Mode (USD)": mode_val})
    return pd.DataFrame(rows).sort_values(["Platform","Country"])

# =========================
# UI — Clean, minimal, no side clutter
# =========================
st.title("Unified Game Pricing — v3.1")
st.caption("Paste **URLs only**. Steam, Xbox, and PlayStation are fully siloed with their own markets and currencies from v2.5.")

with st.container():
    st.subheader("Add Games by URL")
    c1, c2, c3 = st.columns(3)
    with c1:
        steam_urls = st.text_area("Steam URLs", height=140, placeholder="https://store.steampowered.com/app/...")
    with c2:
        xbox_urls = st.text_area("Xbox URLs", height=140, placeholder="https://www.xbox.com/en-us/games/store/...")
    with c3:
        ps_urls = st.text_area("PlayStation URLs", height=140, placeholder="https://store.playstation.com/en-us/product/...")

run_all = st.button("Run All", use_container_width=True)
c1, c2, c3, c4 = st.columns([1,1,1,3])
with c1:
    run_steam = st.button("Run Steam")
with c2:
    run_xbox = st.button("Run Xbox")
with c3:
    run_ps = st.button("Run PlayStation")
with c4:
    show_diag = st.toggle("Show diagnostics", value=False, help="Toggle to show parsing sources/debug fields.")

# Parse URLs → (id,title) lists
def parse_list(block: str, platform_filter: str) -> List[Tuple[str, str]]:
    items: List[Tuple[str,str]] = []
    for ln in [x.strip() for x in block.splitlines() if x.strip()]:
        plat, pid = detect_platform_and_id(ln)
        if plat == platform_filter and pid:
            items.append((pid, title_from_url(ln)))
    return items

steam_games = parse_list(steam_urls or "", "steam")
xbox_games  = parse_list(xbox_urls or "", "xbox")
ps_games    = parse_list(ps_urls or "", "ps")

# =========================
# Run
# =========================
def run_fetch(which: str):
    # Use ALL markets from v2_5 (hidden from UI). Do not cross platform maps.
    s = steam_games if which in ("steam","all") else []
    x = xbox_games  if which in ("xbox","all") else []
    p = ps_games    if which in ("ps","all")    else []
    # v2_5 handles threading + progress. We rely on its siloed maps/constants.
    steam_res, xbox_res, ps_res = v25.pull_all_prices(s, x, p, max_workers=8)
    all_results = list(steam_res) + list(xbox_res) + list(ps_res)
    df = v25.process_results(all_results)
    return df

df_all = pd.DataFrame()
if run_all or run_steam or run_xbox or run_ps:
    which = "all" if run_all else ("steam" if run_steam else ("xbox" if run_xbox else "ps"))
    df_all = run_fetch(which)

# =========================
# Display
# =========================
tabs = st.tabs(["Steam", "Xbox", "PlayStation", "Recommendations"])

def platform_df(df: pd.DataFrame, name: str) -> pd.DataFrame:
    if df.empty:
        return df
    return df[df["Platform"] == name]

with tabs[0]:
    st.subheader("Steam")
    sdf = platform_df(df_all, "Steam")
    st.dataframe(sdf, use_container_width=True)
    if not sdf.empty:
        st.download_button("Download CSV", data=sdf.to_csv(index=False).encode("utf-8"), file_name="steam_prices.csv", mime="text/csv")
    if show_diag and not sdf.empty:
        dbg_cols = [c for c in sdf.columns if "debug" in c.lower() or "source" in c.lower() or "Type" in c]
        if dbg_cols:
            st.caption("Diagnostics")
            st.dataframe(sdf[["Platform","Title","Country"] + dbg_cols], use_container_width=True)

with tabs[1]:
    st.subheader("Xbox")
    xdf = platform_df(df_all, "Xbox")
    st.dataframe(xdf, use_container_width=True)
    if not xdf.empty:
        st.download_button("Download CSV", data=xdf.to_csv(index=False).encode("utf-8"), file_name="xbox_prices.csv", mime="text/csv")
    if show_diag and not xdf.empty:
        dbg_cols = [c for c in xdf.columns if "debug" in c.lower() or "source" in c.lower() or "Type" in c]
        if dbg_cols:
            st.caption("Diagnostics")
            st.dataframe(xdf[["Platform","Title","Country"] + dbg_cols], use_container_width=True)

with tabs[2]:
    st.subheader("PlayStation")
    pdf = platform_df(df_all, "PlayStation")
    st.dataframe(pdf, use_container_width=True)
    if not pdf.empty:
        st.download_button("Download CSV", data=pdf.to_csv(index=False).encode("utf-8"), file_name="ps_prices.csv", mime="text/csv")
    if show_diag and not pdf.empty:
        dbg_cols = [c for c in pdf.columns if "debug" in c.lower() or "source" in c.lower() or "Type" in c]
        if dbg_cols:
            st.caption("Diagnostics")
            st.dataframe(pdf[["Platform","Title","Country"] + dbg_cols], use_container_width=True)

with tabs[3]:
    st.subheader("Recommendations (Mean & Mode per Platform/Country)")
    rec_df = recommendations_mean_mode(df_all) if not df_all.empty else pd.DataFrame(columns=["Platform","Country","Mean (USD)","Mode (USD)"])
    st.dataframe(rec_df, use_container_width=True)
    if not rec_df.empty:
        st.download_button("Download Recommendations CSV", data=rec_df.to_csv(index=False).encode("utf-8"), file_name="recommendations_mean_mode.csv", mime="text/csv")

# Footer note (quiet): silo guarantee
st.caption("All platform markets & currencies are siloed internally from v2.5 (no shared country code maps).")
