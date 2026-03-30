"""
universe.py — Build and maintain the target stock universe.

Fetches constituent lists for:
  - Nikkei 225  (Wikipedia)
  - TOPIX 500   (JPX Excel download)
  - S&P 500     (Wikipedia)

Returns a Polars DataFrame with columns:
  ticker, market, name, sector, index_name
"""

import io
import logging
import re

import polars as pl
import requests

from config.settings import (
    INDEX_NIKKEI225,
    INDEX_SP500,
    INDEX_TOPIX500,
    JPX_TSE_LISTED_URL,
    MARKET_JP,
    MARKET_US,
    WIKIPEDIA_NIKKEI225_URL,
    WIKIPEDIA_SP500_URL,
)

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 30  # seconds


def _get(url: str) -> requests.Response:
    """HTTP GET with a standard browser User-Agent (some sites block bots)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; quant-analysis-bot/1.0; "
            "+https://github.com/sysder/quantitative-analysis)"
        )
    }
    resp = requests.get(url, headers=headers, timeout=_REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp


# ── Nikkei 225 ────────────────────────────────────────────────────────────────


def fetch_nikkei225() -> pl.DataFrame:
    """
    Scrape Nikkei 225 constituents from the Japanese Wikipedia page.

    The English Wikipedia page no longer contains a structured constituent
    table; the Japanese page (ja.wikipedia.org) has one wikitable per sector,
    each with columns 証券コード (4-digit TSE code) and 銘柄 (name).
    The sector name is taken from the nearest preceding heading.

    yfinance expects Japanese tickers in the form '1234.T'.
    """
    try:
        resp = _get(WIKIPEDIA_NIKKEI225_URL)
    except Exception as exc:
        logger.error("Failed to fetch Nikkei 225 from Wikipedia: %s", exc)
        return pl.DataFrame(schema=_universe_schema())

    try:
        from bs4 import BeautifulSoup  # html parsing to correlate tables with headings
    except ImportError as exc:
        logger.error("beautifulsoup4 is required for Nikkei 225 parsing: %s", exc)
        return pl.DataFrame(schema=_universe_schema())

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        logger.error("Failed to parse Nikkei 225 HTML: %s", exc)
        return pl.DataFrame(schema=_universe_schema())

    rows = []
    seen_codes: set = set()

    for table in soup.find_all("table", class_="wikitable"):
        # Derive sector from the nearest preceding heading (h2/h3/h4).
        # Headings on the JP page look like "食品（10銘柄）"; strip the count.
        sector = ""
        prev_heading = table.find_previous(["h2", "h3", "h4"])
        if prev_heading:
            raw = prev_heading.get_text(strip=True)
            # Remove edit links like "[編集]" and trailing counts like "（N銘柄）"
            raw = re.sub(r"\[.*?\]", "", raw)
            raw = re.sub(r"[（(]\d+銘柄[）)]", "", raw).strip()
            sector = raw

        tbody = table.find("tbody") or table
        for tr in tbody.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            code = cells[0].get_text(strip=True)
            if not re.match(r"^\d{4}$", code):
                continue
            if code in seen_codes:
                continue
            seen_codes.add(code)
            name = cells[1].get_text(strip=True)
            rows.append(
                {
                    "ticker": f"{code}.T",
                    "market": MARKET_JP,
                    "name": name,
                    "sector": sector,
                    "index_name": INDEX_NIKKEI225,
                }
            )

    if not rows:
        logger.warning("No valid Nikkei 225 constituents parsed from Wikipedia")
        return pl.DataFrame(schema=_universe_schema())

    logger.info("Fetched %d Nikkei 225 constituents", len(rows))
    return pl.DataFrame(rows, schema=_universe_schema())


# ── TOPIX 500 ─────────────────────────────────────────────────────────────────


def fetch_topix500() -> pl.DataFrame:
    """
    Download TOPIX 500 constituents from the JPX TSE-listed-issues file.

    JPX publishes a monthly .xls file of all TSE-listed stocks with a
    '規模コード' (size-tier code) column.  TOPIX500 = the top 500 Prime-market
    stocks by market cap, spanning three tiers:
      規模コード=1  TOPIX Core30  (≈30 stocks)
      規模コード=2  TOPIX Large70 (≈70 stocks)
      規模コード=4  TOPIX Mid400  (≈400 stocks)

    Relevant columns:
      コード    — 4-digit TSE code
      銘柄名    — company name
      33業種区分 — 33-sector classification (used as sector)
    """
    try:
        resp = _get(JPX_TSE_LISTED_URL)
    except Exception as exc:
        logger.error("Failed to fetch TSE listed-issues file from JPX: %s", exc)
        return pl.DataFrame(schema=_universe_schema())

    try:
        import pandas as pd

        xls = pd.read_excel(io.BytesIO(resp.content), header=0)
    except Exception as exc:
        logger.error("Failed to parse JPX listed-issues Excel file: %s", exc)
        return pl.DataFrame(schema=_universe_schema())

    # TOPIX500 tiers: Core30=1, Large70=2, Mid400=4
    _TOPIX500_SIZE_CODES = {1, 2, 4}
    topix500 = xls[xls["規模コード"].isin(_TOPIX500_SIZE_CODES)].copy()

    rows = []
    for _, row in topix500.iterrows():
        code = str(row.get("コード", "")).strip()
        if not re.match(r"^\d{4}$", code):
            continue
        name = str(row.get("銘柄名", "")).strip()
        if name in ("nan", "None", "NaN"):
            name = ""
        sector = str(row.get("33業種区分", "")).strip()
        if sector in ("nan", "None", "NaN", "-"):
            sector = ""
        rows.append(
            {
                "ticker": f"{code}.T",
                "market": MARKET_JP,
                "name": name,
                "sector": sector,
                "index_name": INDEX_TOPIX500,
            }
        )

    if not rows:
        logger.warning("No valid TOPIX500 constituents parsed")
        return pl.DataFrame(schema=_universe_schema())

    logger.info("Fetched %d TOPIX500 constituents", len(rows))
    return pl.DataFrame(rows, schema=_universe_schema())


# ── S&P 500 ───────────────────────────────────────────────────────────────────


def fetch_sp500() -> pl.DataFrame:
    """
    Scrape S&P 500 constituents from Wikipedia.

    The Wikipedia page has a table with columns:
    'Symbol', 'Security', 'GICS Sector', 'GICS Sub-Industry', etc.
    """
    try:
        resp = _get(WIKIPEDIA_SP500_URL)
    except Exception as exc:
        logger.error("Failed to fetch S&P 500 from Wikipedia: %s", exc)
        return pl.DataFrame(schema=_universe_schema())

    try:
        import pandas as pd

        tables = pd.read_html(io.StringIO(resp.text), attrs={"id": "constituents"})
        df_raw = tables[0]
    except Exception as exc:
        logger.error("Failed to parse S&P 500 HTML table: %s", exc)
        return pl.DataFrame(schema=_universe_schema())

    df_raw.columns = [str(c).lower().replace(" ", "_") for c in df_raw.columns]

    rows = []
    for _, row in df_raw.iterrows():
        ticker = str(row.get("symbol", "")).strip().replace(".", "-")
        if not ticker:
            continue
        name = str(row.get("security", "")).strip()
        sector = str(row.get("gics_sector", "")).strip()
        rows.append(
            {
                "ticker": ticker,
                "market": MARKET_US,
                "name": name,
                "sector": sector,
                "index_name": INDEX_SP500,
            }
        )

    if not rows:
        logger.warning("No valid S&P 500 constituents parsed")
        return pl.DataFrame(schema=_universe_schema())

    return pl.DataFrame(rows, schema=_universe_schema())


# ── Combined universe ─────────────────────────────────────────────────────────


def build_universe() -> pl.DataFrame:
    """
    Fetch all three indices and return a combined, deduplicated universe.

    Returns a Polars DataFrame with columns:
        ticker (str), market (str), name (str), sector (str), index_name (str)
    """
    nikkei = fetch_nikkei225()
    topix = fetch_topix500()
    sp500 = fetch_sp500()

    combined = pl.concat([nikkei, topix, sp500], how="diagonal_relaxed")

    # Deduplicate: keep the first occurrence per ticker
    # (a stock may appear in both Nikkei 225 and TOPIX 500)
    combined = combined.unique(subset=["ticker"], keep="first")

    logger.info(
        "Universe built: %d tickers (%d JP, %d US)",
        len(combined),
        combined.filter(pl.col("market") == MARKET_JP).height,
        combined.filter(pl.col("market") == MARKET_US).height,
    )
    return combined


# ── Helpers ───────────────────────────────────────────────────────────────────


def _universe_schema() -> dict:
    return {
        "ticker": pl.Utf8,
        "market": pl.Utf8,
        "name": pl.Utf8,
        "sector": pl.Utf8,
        "index_name": pl.Utf8,
    }
