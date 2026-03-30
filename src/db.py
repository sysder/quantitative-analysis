"""
db.py — DuckDB connection and schema initialisation.

Usage:
    from src.db import get_connection

    con = get_connection()
    con.execute("SELECT * FROM raw_prices LIMIT 5")
"""

import logging
from pathlib import Path

import duckdb

from config.settings import DB_PATH

logger = logging.getLogger(__name__)

# Module-level connection cache (one connection per process)
_connection: duckdb.DuckDBPyConnection | None = None


def get_connection(db_path: str | Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    """
    Return a DuckDB connection, creating and initialising the schema on first call.

    The connection is cached at module level so all callers share one handle.
    Pass db_path=':memory:' for in-memory databases (useful in tests).
    """
    global _connection

    if _connection is not None:
        return _connection

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Opening DuckDB at %s", db_path)
    _connection = duckdb.connect(str(db_path))
    _init_schema(_connection)
    return _connection


def _init_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create all tables defined in docs/schema.md if they do not yet exist."""

    con.execute("""
        CREATE TABLE IF NOT EXISTS raw_prices (
            ticker       VARCHAR,
            market       VARCHAR,
            date         DATE,
            open         DOUBLE,
            high         DOUBLE,
            low          DOUBLE,
            close        DOUBLE,
            volume       BIGINT,
            PRIMARY KEY (ticker, date)
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS raw_oil_prices (
            date         DATE,
            wti          DOUBLE,
            brent        DOUBLE,
            PRIMARY KEY (date)
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS sector_indices (
            date         DATE,
            market       VARCHAR,
            sector       VARCHAR,
            index_value  DOUBLE,
            source       VARCHAR,
            PRIMARY KEY (market, sector, date)
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS universe (
            ticker       VARCHAR,
            market       VARCHAR,
            name         VARCHAR,
            sector       VARCHAR,
            index_name   VARCHAR,
            PRIMARY KEY (ticker)
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS indicators (
            ticker       VARCHAR,
            date         DATE,
            ma5          DOUBLE,
            ma20         DOUBLE,
            ma50         DOUBLE,
            ma200        DOUBLE,
            rsi14        DOUBLE,
            macd         DOUBLE,
            macd_signal  DOUBLE,
            bb_upper     DOUBLE,
            bb_lower     DOUBLE,
            volume_ratio DOUBLE,
            PRIMARY KEY (ticker, date)
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS sector_sensitivity (
            market       VARCHAR,
            sector       VARCHAR,
            event        VARCHAR,
            correlation  DOUBLE,
            beta         DOUBLE,
            PRIMARY KEY (market, sector, event)
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            ticker           VARCHAR,
            date             DATE,
            technical_score  DOUBLE,
            sentiment_score  DOUBLE,
            final_score      DOUBLE,
            signal           VARCHAR,
            PRIMARY KEY (ticker, date)
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS news_events (
            id           VARCHAR,
            published    TIMESTAMP,
            source       VARCHAR,
            title        VARCHAR,
            sentiment    DOUBLE,
            keywords     VARCHAR[],
            PRIMARY KEY (id)
        )
    """)

    logger.info("DuckDB schema initialised")


def write_dataframe(
    con: duckdb.DuckDBPyConnection,
    df,
    table: str,
    mode: str = "insert_or_replace",
) -> None:
    """
    Write a Polars DataFrame to a DuckDB table.

    mode options:
      'insert_or_replace' — upsert (default); requires a PRIMARY KEY
      'append'            — plain INSERT INTO ... SELECT
    """

    if df.is_empty():
        logger.debug("Skipping write to %s: empty DataFrame", table)
        return

    # Register the Polars DataFrame as a DuckDB relation named '__df_tmp'
    # duckdb can query Polars DataFrames directly via the Arrow interface.
    if mode == "insert_or_replace":
        con.execute(f"INSERT OR REPLACE INTO {table} SELECT * FROM df")
    else:
        con.execute(f"INSERT INTO {table} SELECT * FROM df")

    logger.debug("Wrote %d rows to %s", len(df), table)
