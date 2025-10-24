
# v3.4a — Fix: pass FX rates to v2_5.process_results; Clean UX, autorun
import sys
import streamlit as real_st  # type: ignore

# ---- Import v2_5 behind a minimal shim so its UI doesn't render at import ----
class _DummyCtx:
    def __enter__(self): return self
    def __exit__(self, *exc): return False
    def __getattr__(self, name): return self
    def __call__(self, *a, **k): return None
    def columns(self, *a, **k): return [self, self]
    def progress(self, *a, **k): return self
    def empty(self, *a, **k): return self
    def update(self, *a, **k): return None
    def write(self, *a, **k): return None
    def text(self, *a, **k): return None
    def markdown(self, *a, **k): return None
    def dataframe(self, *a, **k): return None
    def caption(self, *a, **k): return None
    def info(self, *a, **k): return None
    def warning(self, *a, **k): return None
    def error(self, *a, **k): return None
    def success(self, *a, **k): return None
    def button(self, *a, **k): return False
    def text_input(self, *a, **k): return ""
    def text_area(self, *a, **k): return ""
    def selectbox(self, *a, **k): return ""
    def multiselect(self, *a, **k): return []
    def toggle(self, *a, **k): return False
    def download_button(self, *a, **k): return None

class _Shim(_DummyCtx):
    def __init__(self):
        self.session_state = {}
        self.sidebar = _DummyCtx()
    def set_page_config(self, *a, **k): return None

shim = _Shim()
sys.modules['streamlit'] = shim
import multiplatform_pricing_tool_v2_5 as v25  # noqa: E402
sys.modules['streamlit'] = real_st
v25.st = real_st
st = real_st

# ---- App code ----
import pandas as pd
from collections import Counter

st.set_page_config(page_title="Game Pricing — v3.4a (Clean UX, Autorun)", page_icon="🎮", layout="wide")

PRELOAD_STEAM = [
    "https://store.steampowered.com/app/1449110/The_Outer_Worlds_2/",
    "https://store.steampowered.com/app/3230400/EA_SPORTS_Madden_NFL_26/",
    "https://store.steampowered.com/app/2933620/Call_of_Duty_Black_Ops_6/",
    "https://store.steampowered.com/app/1285190/Borderlands_4/",
    "https://store.steampowered.com/app/3472040/NBA_2K26/",
]
PRELOAD_XBOX = [
    "https://www.xbox.com/en-US/games/store/p/9NSPRSXXZZLG/0017",
    "https://www.xbox.com/en-us/games/store/ea-sports-madden-nfl-26/9nvd16np4j8t",
    "https://www.xbox.com/en-us/games/store/call-of-duty-black-ops-6-cross-gen-bundle/9pf528m6crhq",
    "https://www.xbox.com/en-us/games/store/borderlands-4/9mx6hkf5647g",
    "https://www.xbox.com/en-us/games/store/nba-2k26-standard-edition/9pj2rvrc0l1x",
]
PRELOAD_PS = [
    "https://store.playstation.com/en-us/product/UP6312-PPSA24588_00-0872768154966924",
    "https://store.playstation.com/en-us/product/UP0006-PPSA26127_00-MADDENNFL26GAME0",
    "https://store.playstation.com/en-us/product/UP0002-PPSA01649_00-CODBO6CROSSGEN01",
    "https://store.playstation.com/en-us/product/UP1001-PPSA01494_00-000000000000OAK2",
    "https://store.playstation.com/en-us/product/UP1001-PPSA28420_00-NBA2K26000000000",
]

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

def parse_list(urls, platform_filter):
    items = []
    for ln in urls:
        plat, pid = detect_platform_and_id(ln)
        if plat == platform_filter and pid:
            items.append((pid, title_from_url(ln)))
    return items

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
        from collections import Counter
        counts = Counter(round(x, 2) for x in usd_vals)
        max_freq = max(counts.values())
        candidates = [v for v, cnt in counts.items() if cnt == max_freq]
        mode_val = min(candidates, key=lambda x: abs(x - mean_val))
        rows.append({"Platform": plat, "Country": ctry, "Mean (USD)": mean_val, "Mode (USD)": mode_val})
    return pd.DataFrame(rows).sort_values(["Platform","Country"])

st.title("Game Pricing Recommendation Tool — v3.4a (Xbox · Steam · PlayStation)")
st.caption("Autoruns all three platforms. Paste URLs only if you want to override the defaults. All platform markets & currencies are siloed from v2.5 (no cross-talk).")

cols = st.columns(3)
steam_urls = cols[0].text_area("Steam URLs", height=140, value="\n".join(PRELOAD_STEAM))
xbox_urls  = cols[1].text_area("Xbox URLs", height=140, value="\n".join(PRELOAD_XBOX))
ps_urls    = cols[2].text_area("PlayStation URLs", height=140, value="\n".join(PRELOAD_PS))

btn_row = st.columns([1,1,1,3])
run_steam = btn_row[0].button("Run Steam")
run_xbox  = btn_row[1].button("Run Xbox")
run_ps    = btn_row[2].button("Run PlayStation")
show_diag = btn_row[3].checkbox("Show diagnostics", value=False)

steam_list = parse_list([x.strip() for x in steam_urls.splitlines() if x.strip()], "steam")
xbox_list  = parse_list([x.strip() for x in xbox_urls.splitlines() if x.strip()], "xbox")
ps_list    = parse_list([x.strip() for x in ps_urls.splitlines() if x.strip()], "ps")

def run_fetch(which: str):
    s = steam_list if which in ("steam","all") else []
    x = xbox_list  if which in ("xbox","all") else []
    p = ps_list    if which in ("ps","all")    else []
    steam_res, xbox_res, ps_res = v25.pull_all_prices(s, x, p, max_workers=8)
    all_results = list(steam_res) + list(xbox_res) + list(ps_res)
    # ✅ FIX: fetch FX rates and pass them into process_results
    rates = v25.fetch_exchange_rates()
    df = v25.process_results(all_results, rates)
    return df

# Autorun all three on load
df_all = run_fetch("all")

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

st.caption("Siloed per-platform markets & currencies via v2.5. Autorun is enabled.")
