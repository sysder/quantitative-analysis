"""
fetcher.py — Fetch market data from external sources.

Functions:
  fetch_stock_prices(tickers, start, end)  → Polars DataFrame (raw_prices schema)
  fetch_oil_prices(start, end)             → Polars DataFrame (raw_oil_prices schema)
  fetch_nikkei_index(start, end)           → Polars DataFrame (sector_indices schema)
  fetch_tse_sector_indices()               → Polars DataFrame (sector_indices schema)

All functions return Polars DataFrames.  Network errors are logged and an
empty DataFrame with the correct schema is returned rather than raising.
"""

import io
import logging
from datetime import date
from typing import Optional

import polars as pl
import requests

from config.settings import (
    FRED_API_KEY,
    FRED_BASE_URL,
    FRED_BRENT_SERIES,
    FRED_WTI_SERIES,
    HISTORY_START_OIL,
    HISTORY_START_STOCKS,
    JPX_SECTOR_INDEX_URL,
    MARKET_JP,
    MARKET_US,
    YFINANCE_BATCH_SIZE,
    YFINANCE_INTERVAL,
)

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 30


# ── Internal helpers ──────────────────────────────────────────────────────────


def _today() -> str:
    return date.today().isoformat()


def _default_start(history_start: str) -> str:
    """Return history_start when doing a full backfill; useful as a default."""
    return history_start


def _get(url: str, params: Optional[dict] = None) -> requests.Response:
    headers = {"User-Agent": ("Mozilla/5.0 (compatible; quant-analysis-bot/1.0)")}
    resp = requests.get(url, headers=headers, params=params, timeout=_REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp


# ── Stock prices via yfinance ─────────────────────────────────────────────────


def fetch_stock_prices(
    tickers: list[str],
    start: str = HISTORY_START_STOCKS,
    end: Optional[str] = None,
) -> pl.DataFrame:
    """
    Fetch OHLCV data for a list of tickers using yfinance.

    Japanese tickers must include the '.T' suffix (e.g. '7203.T').
    Returns a Polars DataFrame matching the raw_prices schema.
    """
    if end is None:
        end = _today()

    if not tickers:
        logger.warning("fetch_stock_prices called with empty ticker list")
        return pl.DataFrame(schema=_raw_prices_schema())

    import yfinance as yf

    all_frames: list[pl.DataFrame] = []

    # yfinance performs best when fetching in batches
    for i in range(0, len(tickers), YFINANCE_BATCH_SIZE):
        batch = tickers[i : i + YFINANCE_BATCH_SIZE]
        try:
            raw = yf.download(
                batch,
                start=start,
                end=end,
                interval=YFINANCE_INTERVAL,
                auto_adjust=True,
                progress=False,
                group_by="ticker",
            )
        except Exception as exc:
            logger.error("yfinance download failed for batch %s: %s", batch, exc)
            continue

        if raw.empty:
            continue

        # yfinance returns a MultiIndex DataFrame when multiple tickers are requested.
        # Normalise to (ticker, date, open, high, low, close, volume).
        try:
            import pandas as pd

            if isinstance(raw.columns, pd.MultiIndex):
                for ticker in batch:
                    try:
                        df_t = raw[ticker].copy()
                    except KeyError:
                        continue
                    df_t = df_t.reset_index()
                    df_t.columns = [c.lower() for c in df_t.columns]
                    df_t.insert(0, "ticker", ticker)
                    all_frames.append(_normalise_ohlcv(df_t, ticker))
            else:
                # Single ticker — flat columns
                raw = raw.reset_index()
                raw.columns = [c.lower() for c in raw.columns]
                ticker = batch[0]
                raw.insert(0, "ticker", ticker)
                all_frames.append(_normalise_ohlcv(raw, ticker))
        except Exception as exc:
            logger.error("Error normalising yfinance data for batch: %s", exc)

    if not all_frames:
        return pl.DataFrame(schema=_raw_prices_schema())

    return pl.concat(all_frames, how="diagonal_relaxed")


def _normalise_ohlcv(df_pd, ticker: str) -> pl.DataFrame:
    """Convert a pandas OHLCV DataFrame (single ticker) to the raw_prices Polars schema."""
    import pandas as pd

    # Ensure required columns exist; fill missing with None
    for col in ("open", "high", "low", "close", "volume"):
        if col not in df_pd.columns:
            df_pd[col] = None

    # Determine market from ticker suffix
    market = MARKET_JP if ticker.endswith(".T") else MARKET_US

    df_pd = df_pd[["ticker", "date", "open", "high", "low", "close", "volume"]].copy()
    df_pd["market"] = market
    df_pd["date"] = pd.to_datetime(df_pd["date"]).dt.date

    # Drop rows with no close price
    df_pd = df_pd.dropna(subset=["close"])

    # Convert via dict to avoid requiring pyarrow
    return pl.DataFrame(df_pd.to_dict(orient="list")).select(
        [
            pl.col("ticker").cast(pl.Utf8),
            pl.col("market").cast(pl.Utf8),
            pl.col("date").cast(pl.Date),
            pl.col("open").cast(pl.Float64),
            pl.col("high").cast(pl.Float64),
            pl.col("low").cast(pl.Float64),
            pl.col("close").cast(pl.Float64),
            pl.col("volume").cast(pl.Int64),
        ]
    )


# ── Oil prices via FRED ───────────────────────────────────────────────────────


def fetch_oil_prices(
    start: str = HISTORY_START_OIL,
    end: Optional[str] = None,
) -> pl.DataFrame:
    """
    Fetch WTI and Brent crude oil spot prices from FRED.

    FRED returns data as JSON.  No API key is required for public series,
    but FRED_API_KEY in settings.py can be set for higher rate limits.
    Returns a Polars DataFrame matching the raw_oil_prices schema.
    """
    if end is None:
        end = _today()

    wti = _fetch_fred_series(FRED_WTI_SERIES, start, end)
    brent = _fetch_fred_series(FRED_BRENT_SERIES, start, end)

    if wti.is_empty() and brent.is_empty():
        return pl.DataFrame(schema=_raw_oil_prices_schema())

    if wti.is_empty():
        wti = brent.select(pl.col("date")).with_columns(pl.lit(None).cast(pl.Float64).alias("wti"))

    if brent.is_empty():
        brent = wti.select(pl.col("date")).with_columns(
            pl.lit(None).cast(pl.Float64).alias("brent")
        )

    # Join on date; outer join so we keep all dates from either series
    combined = wti.join(brent, on="date", how="full", coalesce=True).sort("date")
    return combined


def _fetch_fred_series(series_id: str, start: str, end: str) -> pl.DataFrame:
    """Fetch a single FRED series and return a two-column DataFrame: date, <series_id>."""
    params: dict = {
        "series_id": series_id,
        "observation_start": start,
        "observation_end": end,
        "file_type": "json",
        "units": "lin",
        "frequency": "d",
    }
    if FRED_API_KEY:
        params["api_key"] = FRED_API_KEY
    else:
        # FRED allows unauthenticated requests but recommends registering
        params["api_key"] = "abcdefghijklmnopqrstuvwxyz123456"  # public demo key fallback

    try:
        resp = _get(FRED_BASE_URL, params=params)
        data = resp.json()
    except Exception as exc:
        logger.error("FRED API request failed for series %s: %s", series_id, exc)
        return pl.DataFrame({"date": [], series_id.lower(): []}).with_columns(
            pl.col("date").cast(pl.Date),
            pl.col(series_id.lower()).cast(pl.Float64),
        )

    observations = data.get("observations", [])
    if not observations:
        logger.warning("No observations returned from FRED for series %s", series_id)
        return pl.DataFrame({"date": [], series_id.lower(): []}).with_columns(
            pl.col("date").cast(pl.Date),
            pl.col(series_id.lower()).cast(pl.Float64),
        )

    col_name = "wti" if series_id == FRED_WTI_SERIES else "brent"

    rows = []
    for obs in observations:
        value_str = obs.get("value", ".")
        if value_str == ".":
            # FRED uses '.' for missing values
            value = None
        else:
            try:
                value = float(value_str)
            except ValueError:
                value = None
        rows.append({"date": obs["date"], col_name: value})

    return pl.DataFrame(rows).with_columns(
        pl.col("date").str.strptime(pl.Date, "%Y-%m-%d"),
        pl.col(col_name).cast(pl.Float64),
    )


# ── Nikkei 225 index via yfinance ────────────────────────────────────────────


def fetch_nikkei_index(
    start: str = "1970-01-01",
    end: Optional[str] = None,
) -> pl.DataFrame:
    """
    Fetch Nikkei 225 daily historical index via yfinance (ticker: ^N225).

    Returns a Polars DataFrame matching the sector_indices schema
    with market='JP', sector='Nikkei225', source='yfinance'.

    Stooq was the original source but blocks requests from container
    environments.  The Stooq implementation is preserved below as a
    commented-out fallback in case yfinance becomes unavailable.
    """
    if end is None:
        end = _today()

    import pandas as pd
    import yfinance as yf

    try:
        df = yf.download(
            "^N225",
            start=start,
            end=end,
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
    except Exception as exc:
        logger.error("yfinance download failed for ^N225: %s", exc)
        return pl.DataFrame(schema=_sector_indices_schema())

    if df.empty:
        logger.warning("yfinance returned empty data for ^N225")
        return pl.DataFrame(schema=_sector_indices_schema())

    # Flatten MultiIndex columns if present (yfinance >= 0.2 may return them)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0].lower() for col in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]

    df = df.reset_index()
    # Rename 'date' column — yfinance uses 'Date' (capital) which becomes 'date' after lower()
    df.columns = [c.lower() for c in df.columns]

    if "close" not in df.columns or "date" not in df.columns:
        logger.warning("Unexpected yfinance columns for ^N225: %s", list(df.columns))
        return pl.DataFrame(schema=_sector_indices_schema())

    df = df[["date", "close"]].dropna(subset=["close"])
    df["date"] = pd.to_datetime(df["date"]).dt.date

    # Convert via dict to avoid requiring pyarrow (same method as _normalise_ohlcv)
    result = pl.DataFrame(df.to_dict(orient="list")).select(
        pl.col("date").cast(pl.Date).alias("date"),
        pl.lit(MARKET_JP).alias("market"),
        pl.lit("Nikkei225").alias("sector"),
        pl.col("close").cast(pl.Float64).alias("index_value"),
        pl.lit("yfinance").alias("source"),
    )
    return result

    # ── Stooq fallback (blocked in container environments) ──────────────────
    # url = STOOQ_CSV_URL.format(ticker=STOOQ_NIKKEI225_TICKER)
    # params = {"d1": start.replace("-", ""), "d2": end.replace("-", "")}
    # try:
    #     resp = _get(url, params=params)
    #     text = resp.text
    # except Exception as exc:
    #     logger.error("Failed to fetch Nikkei 225 from Stooq: %s", exc)
    #     return pl.DataFrame(schema=_sector_indices_schema())
    # if not text or not text.strip():
    #     logger.warning(
    #         "Stooq returned empty response for Nikkei 225 (possible rate-limit or bot-block)"
    #     )
    #     return pl.DataFrame(schema=_sector_indices_schema())
    # try:
    #     df_stooq = pl.read_csv(io.StringIO(text))
    # except Exception as exc:
    #     logger.error("Failed to parse Stooq CSV: %s", exc)
    #     return pl.DataFrame(schema=_sector_indices_schema())
    # if df_stooq.is_empty():
    #     logger.warning("Stooq returned empty data for Nikkei 225")
    #     return pl.DataFrame(schema=_sector_indices_schema())
    # df_stooq = df_stooq.rename({c: c.lower() for c in df_stooq.columns})
    # if "close" not in df_stooq.columns or "date" not in df_stooq.columns:
    #     logger.warning("Unexpected Stooq CSV columns: %s", df_stooq.columns)
    #     return pl.DataFrame(schema=_sector_indices_schema())
    # return df_stooq.select(
    #     pl.col("date").str.strptime(pl.Date, "%Y-%m-%d").alias("date"),
    #     pl.lit(MARKET_JP).alias("market"),
    #     pl.lit("Nikkei225").alias("sector"),
    #     pl.col("close").cast(pl.Float64).alias("index_value"),
    #     pl.lit("Stooq").alias("source"),
    # )


# ── TSE sector indices via JPX ────────────────────────────────────────────────


def fetch_tse_sector_indices() -> pl.DataFrame:
    """
    Download TOPIX-17 sector index weights from JPX.

    JPX publishes constituent weights as an Excel file.  This function
    downloads the file, extracts sector names and latest index data,
    and returns a Polars DataFrame matching the sector_indices schema.

    Note: JPX does not publish a free historical time-series for sector
    indices via a direct download URL.  This function returns the latest
    constituent weight data annotated with today's date as a reference
    snapshot.  Phase 2 historical analysis will use BOJ statistical data
    separately.
    """
    try:
        resp = _get(JPX_SECTOR_INDEX_URL)
    except Exception as exc:
        logger.error("Failed to fetch JPX sector index file: %s", exc)
        return pl.DataFrame(schema=_sector_indices_schema())

    try:
        import pandas as pd

        xls = pd.read_excel(io.BytesIO(resp.content), header=None)
    except Exception as exc:
        logger.error("Failed to parse JPX sector Excel file: %s", exc)
        return pl.DataFrame(schema=_sector_indices_schema())

    # The Excel has sector names in the first meaningful column and numeric
    # weights in subsequent columns.  We extract the sector names and use
    # the aggregate weight as a proxy index value for the snapshot.
    rows = []
    today_str = _today()

    for _, row in xls.iterrows():
        first_cell = str(row.iloc[0]).strip() if len(row) > 0 else ""
        # Skip header rows, empty rows, and numeric-only rows
        if not first_cell or first_cell in ("nan", "None") or first_cell.replace(".", "").isdigit():
            continue
        # Try to find a numeric value in the row (weight / index value)
        index_val = None
        for cell in row.iloc[1:]:
            try:
                val = float(str(cell).strip())
                if val > 0:
                    index_val = val
                    break
            except (ValueError, TypeError):
                continue

        if index_val is None:
            continue

        rows.append(
            {
                "date": today_str,
                "market": MARKET_JP,
                "sector": first_cell,
                "index_value": index_val,
                "source": "JPX",
            }
        )

    if not rows:
        logger.warning("No sector data extracted from JPX Excel file")
        return pl.DataFrame(schema=_sector_indices_schema())

    return pl.DataFrame(rows).with_columns(
        pl.col("date").str.strptime(pl.Date, "%Y-%m-%d"),
        pl.col("market").cast(pl.Utf8),
        pl.col("sector").cast(pl.Utf8),
        pl.col("index_value").cast(pl.Float64),
        pl.col("source").cast(pl.Utf8),
    )


# ── Schema helpers ────────────────────────────────────────────────────────────


def _raw_prices_schema() -> dict:
    return {
        "ticker": pl.Utf8,
        "market": pl.Utf8,
        "date": pl.Date,
        "open": pl.Float64,
        "high": pl.Float64,
        "low": pl.Float64,
        "close": pl.Float64,
        "volume": pl.Int64,
    }


def _raw_oil_prices_schema() -> dict:
    return {
        "date": pl.Date,
        "wti": pl.Float64,
        "brent": pl.Float64,
    }


def _sector_indices_schema() -> dict:
    return {
        "date": pl.Date,
        "market": pl.Utf8,
        "sector": pl.Utf8,
        "index_value": pl.Float64,
        "source": pl.Utf8,
    }
