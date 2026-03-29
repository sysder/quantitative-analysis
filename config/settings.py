"""
Externalized configuration for the quantitative analysis pipeline.
All tickers, date ranges, API series IDs, and URLs are defined here.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Project root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH = PROJECT_ROOT / "artifacts" / "quant.duckdb"

# ── FRED API ──────────────────────────────────────────────────────────────────
# Free API — no key required for most series; set FRED_API_KEY for higher limits
FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# FRED series identifiers
FRED_WTI_SERIES = "DCOILWTICO"        # WTI crude oil spot price (USD/barrel)
FRED_BRENT_SERIES = "DCOILBRENTEU"    # Brent crude oil spot price (USD/barrel)

# ── Date ranges ───────────────────────────────────────────────────────────────
# Historical data start dates per use-case
HISTORY_START_OIL = "1970-01-01"      # WTI available from 1986; FRED goes back further for Brent
HISTORY_START_STOCKS = "1990-01-01"   # yfinance practical start for Japanese stocks
HISTORY_START_INDEX = "1970-01-01"    # Nikkei 225 via Stooq

# Default lookback for recent price fetches (days)
DEFAULT_LOOKBACK_DAYS = 365

# ── Universe crawling URLs ────────────────────────────────────────────────────
WIKIPEDIA_NIKKEI225_URL = "https://ja.wikipedia.org/wiki/%E6%97%A5%E7%B5%8C%E5%B9%B3%E5%9D%87%E6%A0%AA%E4%BE%A1"
WIKIPEDIA_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# JPX publishes the full list of TSE-listed issues as an .xls file updated monthly.
# TOPIX500 = Core30 (規模コード=1) + Large70 (規模コード=2) + Mid400 (規模コード=4).
# The old topixweight_j.xlsx URL returned 404; this endpoint is the current source.
JPX_TSE_LISTED_URL = (
    "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
)
# Keep old name as an alias so any external code referencing it still imports cleanly.
JPX_TOPIX500_URL = JPX_TSE_LISTED_URL

# ── Stooq ─────────────────────────────────────────────────────────────────────
# Stooq CSV download endpoint (replace {ticker} at call site)
STOOQ_CSV_URL = "https://stooq.com/q/d/l/?s={ticker}&i=d"

# Nikkei 225 ticker on Stooq
STOOQ_NIKKEI225_TICKER = "^n225"

# ── BOJ/JPX sector indices ────────────────────────────────────────────────────
# The BOJ provides sector-level stock price indices as downloadable CSV.
# Actual endpoint requires navigation; the URL below is the statistics portal.
BOJ_STATS_BASE_URL = "https://www.stat-search.boj.or.jp"

# JPX sector index download (TOPIX-17 series, latest weights)
JPX_SECTOR_INDEX_URL = (
    "https://www.jpx.co.jp/markets/indices/topix/files/TOPIX17_weight.xlsx"
)

# ── yfinance settings ─────────────────────────────────────────────────────────
# Maximum tickers to fetch in a single yfinance.download() call
YFINANCE_BATCH_SIZE = 50

# Interval for price data
YFINANCE_INTERVAL = "1d"

# ── Sector mapping for TSE (TOPIX-17 sectors) ─────────────────────────────────
TSE_SECTORS = [
    "foods",
    "energy_resources",
    "construction_materials",
    "raw_materials_chemicals",
    "pharmaceutical",
    "automobiles_transportation",
    "steel_nonferrous",
    "machinery",
    "electric_appliances_precision",
    "it_services",
    "electric_power_gas",
    "transportation_logistics",
    "commercial_wholesale",
    "retail",
    "banks",
    "financials_ex_banks",
    "real_estate",
]

# ── Market identifiers ────────────────────────────────────────────────────────
MARKET_JP = "JP"
MARKET_US = "US"

# ── Index names (used in the `universe` table) ────────────────────────────────
INDEX_NIKKEI225 = "Nikkei225"
INDEX_TOPIX500 = "TOPIX500"
INDEX_SP500 = "SP500"
