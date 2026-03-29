"""
phase1.py — Dagster assets for Phase 1: Data Foundation.

Assets:
  stock_universe      — Fetch and persist the target stock universe
  oil_prices          — Fetch WTI/Brent crude oil prices from FRED
  stock_prices        — Fetch individual stock OHLCV data via yfinance
  nikkei_index        — Fetch Nikkei 225 historical index from Stooq
  tse_sector_indices  — Fetch TSE sector index snapshot from JPX
"""

import logging

import polars as pl
from dagster import asset, get_dagster_logger

from config.settings import HISTORY_START_OIL, HISTORY_START_STOCKS
from src.db import get_connection, write_dataframe
from src.fetcher import (
    fetch_nikkei_index,
    fetch_oil_prices,
    fetch_stock_prices,
    fetch_tse_sector_indices,
)
from src.universe import build_universe

logger = logging.getLogger(__name__)


# ── stock_universe ─────────────────────────────────────────────────────────────

@asset(
    group_name="phase1",
    description="Fetch Nikkei 225, TOPIX 500, and S&P 500 constituent lists.",
)
def stock_universe() -> pl.DataFrame:
    """
    Crawl Wikipedia and JPX to build the target stock universe.

    Returns a Polars DataFrame with columns:
        ticker, market, name, sector, index_name
    Persists to the DuckDB `universe` table.
    """
    log = get_dagster_logger()
    log.info("Building stock universe...")

    df = build_universe()
    log.info("Universe: %d tickers", len(df))

    con = get_connection()
    write_dataframe(con, df, "universe")
    return df


# ── oil_prices ────────────────────────────────────────────────────────────────

@asset(
    group_name="phase1",
    description="Fetch WTI and Brent crude oil prices from FRED.",
)
def oil_prices() -> pl.DataFrame:
    """
    Fetch daily WTI and Brent crude oil prices from the FRED API.

    Returns a Polars DataFrame with columns: date, wti, brent.
    Persists to the DuckDB `raw_oil_prices` table.
    """
    log = get_dagster_logger()
    log.info("Fetching oil prices from FRED (start=%s)...", HISTORY_START_OIL)

    df = fetch_oil_prices(start=HISTORY_START_OIL)
    log.info("Oil prices: %d rows", len(df))

    con = get_connection()
    write_dataframe(con, df, "raw_oil_prices")
    return df


# ── stock_prices ──────────────────────────────────────────────────────────────

@asset(
    group_name="phase1",
    description="Fetch individual stock OHLCV data via yfinance.",
    deps=[stock_universe],
)
def stock_prices(stock_universe: pl.DataFrame) -> pl.DataFrame:
    """
    Fetch daily OHLCV prices for all tickers in the universe via yfinance.

    Depends on stock_universe to obtain the list of tickers.
    Returns a Polars DataFrame matching the raw_prices schema.
    Persists to the DuckDB `raw_prices` table.
    """
    log = get_dagster_logger()

    tickers = stock_universe["ticker"].to_list()
    log.info("Fetching stock prices for %d tickers (start=%s)...", len(tickers), HISTORY_START_STOCKS)

    df = fetch_stock_prices(tickers, start=HISTORY_START_STOCKS)
    log.info("Stock prices: %d rows across %d tickers", len(df), df["ticker"].n_unique() if not df.is_empty() else 0)

    con = get_connection()
    write_dataframe(con, df, "raw_prices")
    return df


# ── nikkei_index ──────────────────────────────────────────────────────────────

@asset(
    group_name="phase1",
    description="Fetch Nikkei 225 historical index from Stooq.",
)
def nikkei_index() -> pl.DataFrame:
    """
    Fetch Nikkei 225 daily closing values from Stooq going back to the 1970s.

    Returns a Polars DataFrame matching the sector_indices schema.
    Persists to the DuckDB `sector_indices` table.
    """
    log = get_dagster_logger()
    log.info("Fetching Nikkei 225 index from Stooq...")

    df = fetch_nikkei_index()
    log.info("Nikkei 225: %d rows", len(df))

    con = get_connection()
    write_dataframe(con, df, "sector_indices")
    return df


# ── tse_sector_indices ────────────────────────────────────────────────────────

@asset(
    group_name="phase1",
    description="Fetch TSE TOPIX-17 sector index snapshot from JPX.",
)
def tse_sector_indices() -> pl.DataFrame:
    """
    Download the current TOPIX-17 sector index weights from JPX.

    Returns a Polars DataFrame matching the sector_indices schema.
    Persists to the DuckDB `sector_indices` table.
    """
    log = get_dagster_logger()
    log.info("Fetching TSE sector indices from JPX...")

    df = fetch_tse_sector_indices()
    log.info("TSE sector indices: %d sectors", len(df))

    con = get_connection()
    write_dataframe(con, df, "sector_indices")
    return df
