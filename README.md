
# Game Pricing – Combined (Xbox • Steam • PlayStation), Silo architecture

This package separates platforms into **independent silos**:
- **Steam** and **Xbox** use your existing, proven logic (keep your current modules).
- **PlayStation** uses a dedicated silo with its own market/currency/locale map and fetcher.
  PlayStation logic **must not** share country/locale lists with other platforms.

## Quick start

1. Add your working Steam/Xbox modules (or keep them in this repo if you already have them):
   - `steam_fetcher.py` (or similar)
   - `xbox_fetcher.py`  (or similar)

2. Run the app:
   ```bash
   pip install -r requirements.txt
   streamlit run streamlit_app_combined_silos.py
   ```

3. In the UI:
   - Enter markets. Steam/Xbox use their own lists. PlayStation uses its own built-in map.
   - For PlayStation, provide **product URLs** (preferred) or product IDs. The app will localize
     the URL per-country using the PS locale map and pull **MSRP** (basePrice), ignoring discounts.

### PlayStation silo files

- `silos/ps_market_silo_v1.py` → **Only** the PS market map (country → locale, currency).
- `silos/ps_fetcher_v2.py`      → Fetches PS prices, prefers basePrice (MSRP).

> To override the market map without changing code, drop a `ps_market_map_override.csv`
> (columns: `country,locale,currency,name`) next to the app. It will be loaded automatically.

## Notes
- The PS fetcher is resilient but expects **standard/cross-gen** product pages for edition correctness.
- If you point at a **concept** page, the Standard edition might need selection; provide product URLs to be safe.
