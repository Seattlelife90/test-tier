
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Game Pricing – Silos", layout="wide")
st.title("🎮 Game Pricing – vSilos (Xbox • Steam • PlayStation)")

with st.sidebar:
    st.header("Controls")
    quick = st.toggle("Quick run (first 10 markets)", value=True)
    prefer_msrp = st.toggle("Prefer MSRP (ignore discounts)", value=True)

    st.subheader("PlayStation basket")
    ps_items = st.text_area("One PS product URL or ID per line (standard/cross-gen):",
                            "https://store.playstation.com/en-us/product/UP1001-PPSA01494_00-0000000000000AK2")
    ps_markets_input = st.text_input("PS countries (comma ISO2) — leave blank to auto-use PS-supported",
                                     "")

st.caption("This build wires **PlayStation** via its own silo. Steam/Xbox placeholders remain to keep your working logic unchanged.")

# --- PlayStation run ---
from silos.ps_fetcher_v2 import fetch_ps_prices
from silos.ps_market_silo_v1 import PS_SUPPORTED

ps_list = [s.strip() for s in ps_items.splitlines() if s.strip()]
if ps_markets_input.strip():
    ps_markets_all = [c.strip().upper() for c in ps_markets_input.split(",") if c.strip()]
    ps_markets = [c for c in ps_markets_all if c in PS_SUPPORTED]
else:
    ps_markets = sorted(list(PS_SUPPORTED))

if quick:
    ps_markets = ps_markets[:10]

st.subheader("PlayStation – Raw fetch")
ps_rows = []
prog = st.progress(0.0, text="Fetching PlayStation prices...")
for i, ref in enumerate(ps_list, 1):
    rows = fetch_ps_prices(ref, ps_markets, prefer_msrp=prefer_msrp, edition_hint="standard")
    ps_rows.extend(rows)
    prog.progress(i/len(ps_list))

ps_df = pd.DataFrame(ps_rows)
st.dataframe(ps_df, use_container_width=True)

# --- Diagnostics ---
st.subheader("Diagnostics (PlayStation)")
diag = ps_df[ps_df["price"].isna()].groupby(["country","reason"], dropna=False).size().reset_index(name="count")
st.dataframe(diag, use_container_width=True)

st.download_button("Download PlayStation raw CSV", ps_df.to_csv(index=False).encode("utf-8"),
                   file_name="ps_raw.csv", mime="text/csv")

st.info("Hook your existing Steam/Xbox modules here to keep those paths unchanged. This app focuses on the PS silo wiring.")
