
"""
PlayStation Market Silo (v1)

This module is an **exclusive mapping for PlayStation**. It must not be used
for Steam or Xbox. Import this in your app and filter PlayStation pulls to
PS_SUPPORTED only; obtain the PS locale via `ps_locale(cc)`.

If you want to override or extend this mapping without editing code,
drop a CSV named `ps_market_map_override.csv` next to your app with columns:
country,locale,currency,name (currency is optional). When present, overrides
or adds to PS_MARKETS at import time.
"""
from __future__ import annotations
import csv, os
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass(frozen=True)
class PSMarket:
    code: str
    name: str
    locale: str
    currency: Optional[str] = None

# --- Seed map (safe defaults). Currency is optional; locale is required. ---
# This list is conservative and can be extended; it intentionally avoids
# markets known to be Xbox-only.
PS_MARKETS: Dict[str, PSMarket] = {
    # North America
    "US": PSMarket("US", "United States", "en-us", "USD"),
    "CA": PSMarket("CA", "Canada", "en-ca", "CAD"),
    "MX": PSMarket("MX", "Mexico", "es-mx"),

    # LATAM (PS supported)
    "AR": PSMarket("AR", "Argentina", "es-ar"),
    "BR": PSMarket("BR", "Brazil", "pt-br", "BRL"),
    "CL": PSMarket("CL", "Chile", "es-cl"),
    "CO": PSMarket("CO", "Colombia", "es-co"),
    "PE": PSMarket("PE", "Peru", "es-pe"),
    "CR": PSMarket("CR", "Costa Rica", "es-cr"),
    "GT": PSMarket("GT", "Guatemala", "es-gt"),
    "HN": PSMarket("HN", "Honduras", "es-hn"),
    "NI": PSMarket("NI", "Nicaragua", "es-ni"),
    "PA": PSMarket("PA", "Panama", "es-pa"),
    "PY": PSMarket("PY", "Paraguay", "es-py"),
    "SV": PSMarket("SV", "El Salvador", "es-sv"),
    "DO": PSMarket("DO", "Dominican Republic", "es-do"),
    "BO": PSMarket("BO", "Bolivia", "es-bo"),

    # Western Europe
    "GB": PSMarket("GB", "United Kingdom", "en-gb", "GBP"),
    "IE": PSMarket("IE", "Ireland", "en-ie", "EUR"),
    "FR": PSMarket("FR", "France", "fr-fr", "EUR"),
    "DE": PSMarket("DE", "Germany", "de-de", "EUR"),
    "ES": PSMarket("ES", "Spain", "es-es", "EUR"),
    "IT": PSMarket("IT", "Italy", "it-it", "EUR"),
    "PT": PSMarket("PT", "Portugal", "pt-pt", "EUR"),
    "NL": PSMarket("NL", "Netherlands", "nl-nl", "EUR"),
    "BE": PSMarket("BE", "Belgium", "fr-fr", "EUR"),
    "AT": PSMarket("AT", "Austria", "de-at", "EUR"),
    "CH": PSMarket("CH", "Switzerland", "de-ch", "CHF"),
    "LU": PSMarket("LU", "Luxembourg", "fr-lu", "EUR"),
    "GR": PSMarket("GR", "Greece", "el-gr", "EUR"),

    # CEE + Nordics
    "PL": PSMarket("PL", "Poland", "pl-pl", "PLN"),
    "CZ": PSMarket("CZ", "Czech Republic", "cs-cz", "CZK"),
    "SK": PSMarket("SK", "Slovakia", "sk-sk"),  # PS availability varies
    "HU": PSMarket("HU", "Hungary", "hu-hu", "HUF"),
    "RO": PSMarket("RO", "Romania", "ro-ro", "RON"),
    "BG": PSMarket("BG", "Bulgaria", "bg-bg", "BGN"),
    "SI": PSMarket("SI", "Slovenia", "sl-si", "EUR"),
    "HR": PSMarket("HR", "Croatia", "hr-hr", "EUR"),
    "CY": PSMarket("CY", "Cyprus", "en-cy", "EUR"),
    "IS": PSMarket("IS", "Iceland", "is-is", "ISK"),
    "SE": PSMarket("SE", "Sweden", "sv-se", "SEK"),
    "DK": PSMarket("DK", "Denmark", "da-dk", "DKK"),
    "NO": PSMarket("NO", "Norway", "no-no", "NOK"),
    "FI": PSMarket("FI", "Finland", "fi-fi", "EUR"),
    "UA": PSMarket("UA", "Ukraine", "uk-ua", "UAH"),

    # APAC
    "AU": PSMarket("AU", "Australia", "en-au", "AUD"),
    "NZ": PSMarket("NZ", "New Zealand", "en-nz", "NZD"),
    "JP": PSMarket("JP", "Japan", "ja-jp", "JPY"),
    "KR": PSMarket("KR", "Korea", "ko-kr", "KRW"),
    "SG": PSMarket("SG", "Singapore", "en-sg", "SGD"),
    "MY": PSMarket("MY", "Malaysia", "en-my", "MYR"),
    "TH": PSMarket("TH", "Thailand", "th-th", "THB"),
    "ID": PSMarket("ID", "Indonesia", "id-id", "IDR"),
    "TW": PSMarket("TW", "Taiwan", "zh-tw", "TWD"),
    "HK": PSMarket("HK", "Hong Kong", "en-hk", "HKD"),
    "IN": PSMarket("IN", "India", "en-in", "INR"),

    # Middle East & Africa
    "TR": PSMarket("TR", "Türkiye", "tr-tr", "TRY"),
    "IL": PSMarket("IL", "Israel", "en-il", "ILS"),
    "SA": PSMarket("SA", "Saudi Arabia", "ar-sa", "SAR"),
    "AE": PSMarket("AE", "United Arab Emirates", "en-ae", "AED"),
    "QA": PSMarket("QA", "Qatar", "ar-qa"),  # currency optional
    "KW": PSMarket("KW", "Kuwait", "ar-kw"),
    "ZA": PSMarket("ZA", "South Africa", "en-za", "ZAR"),
    "BH": PSMarket("BH", "Bahrain", "ar-bh"),
    "OM": PSMarket("OM", "Oman", "en-om"),
}

# Build supported set
PS_SUPPORTED = set(PS_MARKETS.keys())

def _apply_override_csv(path: str = "ps_market_map_override.csv") -> None:
    """Allow an external CSV to override or extend the mapping without code edits."""
    if not os.path.exists(path):
        return
    try:
        with open(path, newline="", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                cc = (row.get("country") or "").strip().upper()
                loc = (row.get("locale") or "").strip()
                cur = (row.get("currency") or "").strip().upper() or None
                nm  = (row.get("name") or "").strip() or cc
                if not cc or not loc:
                    continue
                PS_MARKETS[cc] = PSMarket(cc, nm, loc, cur)
        PS_SUPPORTED.clear()
        PS_SUPPORTED.update(PS_MARKETS.keys())
    except Exception:
        # Silent fail to avoid import errors; callers can still use defaults.
        pass

# Apply user override on import if present
_apply_override_csv()

def ps_supported(cc: str) -> bool:
    return str(cc).upper() in PS_SUPPORTED

def ps_locale(cc: str) -> str:
    """Return PlayStation locale (e.g., 'fr-fr'). Defaults to 'en-us' if unknown."""
    cc = str(cc).upper()
    return PS_MARKETS.get(cc, PSMarket(cc, cc, "en-us")).locale

def ps_currency(cc: str) -> str | None:
    """Return static currency for the market, if we have one. Parsers can
    still prefer currency parsed from page when present."""
    cc = str(cc).upper()
    return PS_MARKETS.get(cc, PSMarket(cc, cc, "en-us")).currency
