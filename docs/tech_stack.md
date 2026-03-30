# Tech Stack

## Libraries & Tools

| Purpose | Library / Tool |
|---|---|
| Stock & oil price data (1990s~) | `yfinance` |
| Oil price & US stocks (1970s~) | FRED API |
| Nikkei 225 index (1970s~) | Stooq (crawling) |
| TSE sector indices (1970s~) | BOJ / JPX (CSV download / crawling) |
| Stock universe lists | Wikipedia / JPX (crawling) |
| Data processing | `polars` |
| Technical indicators | Custom implementation in Polars expressions |
| DB | DuckDB |
| Orchestration | Dagster |
| SQL transformation | dbt (dbt-duckdb adapter) |
| RSS feed parsing | `feedparser` |
| Sentiment analysis | `vaderSentiment` |
| Visualization | `plotly` |

## Rationale

### Polars over pandas
Faster performance, better memory efficiency, and native DuckDB integration
(`duckdb.sql("...").pl()`). Technical indicators are implemented as custom Polars
expressions since pandas-ta is not compatible with Polars.

### Custom technical indicators
`pandas-ta` is pandas-only. Since we use Polars, indicators (MA, RSI, MACD, Bollinger
Bands) are implemented directly using Polars rolling expressions.

### Dagster + dbt
SQL usage grows significantly in Phase 2–4 (JOINs across oil, sector, and sentiment
data). dbt with the dbt-duckdb adapter handles SQL transformations cleanly; Dagster
orchestrates the full pipeline with asset-based dependency tracking.

### RSS over NewsAPI
Reuters/AP RSS is completely free, real-time, and has no request limits. NewsAPI's
free tier has a 24-hour delay and a 100 req/day cap — both unacceptable for
short-term trading.

### DuckDB
Embedded columnar database — no server required. Ideal for analytical queries on
time-series financial data. Natively integrates with Polars and dbt.
