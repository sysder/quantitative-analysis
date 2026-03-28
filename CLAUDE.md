# Quantitative Analysis — Design Document

## Product Goal
A quantitative analysis system to identify stocks to buy and sell.

## Core Principles
- **Target Markets:** Japan (TSE) + US (NYSE/NASDAQ)
- **Investment Style:** Short-term trading (days to weeks)
- **Development Approach:** Start with simple screening, expand iteratively
- **Data APIs:** Prefer free tools (yfinance, RSS, FRED)

---

## Overall Architecture

```
Phase 1: Data Foundation
  - Fetch oil prices, stock prices, and volume data via yfinance / FRED / Stooq
  - Build target stock universe (Nikkei 225/TOPIX500 + S&P500)
  - Apply liquidity filter

Phase 2: Historical Correlation Analysis
  - Analyze oil price and stock price movement patterns during the 1973 and 1979 oil shocks
  - Use sector-level indices (not individual stocks) for 1970s Japan data
  - Build a sector sensitivity map (quantify which sectors rise/fall when oil surges)

Phase 3: Technical Screener
  - Apply technical analysis to sectors with high oil sensitivity (from Phase 2)
  - Signals: momentum, golden cross, volume spike, RSI, Bollinger Bands
  - Rank stocks via multi-signal scoring

Phase 4: News Sentiment
  - Fetch Reuters / AP RSS feeds in real time (feedparser)
  - Keyword filter: Iran, Hormuz, sanctions, oil, OPEC, Trump, etc.
  - Score sentiment with VADER
  - Use sentiment score as a weight on top of the technical score
```

---

## Pipeline Structure

```
universe.py     — manage target stock lists (crawled from Wikipedia / JPX)
fetcher.py      — fetch data via yfinance, FRED API, Stooq crawling, BOJ/JPX CSV
indicators.py   — calculate technical indicators (MA, RSI, MACD, etc.) in Polars
screener.py     — filter stocks by signal conditions
scorer.py       — multi-signal scoring
news.py         — RSS fetching, keyword filtering, sentiment analysis
report.py       — output results (CSV or HTML)
```

---

## Tech Stack

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

---

## Data Sources

| Data | Source | Period | Method |
|---|---|---|---|
| Nikkei 225 index | Stooq | 1970s~ | Crawling |
| TSE sector indices | BOJ / JPX | 1970s~ | CSV download / crawling |
| WTI crude oil price | FRED API | 1970s~ | API |
| US stocks (S&P500) | FRED / yfinance | 1970s~ | API |
| Individual stock prices & volume | yfinance | 1990s~ | API |
| Stock universe (Nikkei 225 / TOPIX500 / S&P500) | Wikipedia / JPX | current | Crawling |
| Reuters / AP news | RSS | real-time | feedparser |

### Crawling targets
- Nikkei 225 constituent list — Wikipedia or Nikkei official
- TOPIX500 constituent list — JPX official site
- S&P500 constituent list — Wikipedia
- Nikkei 225 historical index — Stooq
- TSE sector indices — BOJ / JPX

---

## Architecture: Transformation Layer

```
Polars:  raw data ingestion → technical indicator calculation → write to DuckDB
   ↓
dbt:     SQL transformations on DuckDB (JOINs, aggregations, scoring)
   ↓
Dagster: orchestration of the entire pipeline
```

---

## Background & Design Rationale

### Why reference the oil shocks?
Given the current risk of Hormuz Strait closure affecting oil prices, we use the 1973 and 1979 oil shock patterns to identify sectors sensitive to oil price swings. Sectors historically helped (energy, defense) and hurt (airlines, autos, materials) are quantified from data and used to narrow the stock universe.

### Why sector indices for 1970s Japan data?
Individual stock data for Japanese equities prior to the 1990s is not available via free sources. Sector-level indices from BOJ/JPX and the Nikkei 225 from Stooq are sufficient for Phase 2 historical correlation analysis.

### Why RSS over NewsAPI?
Reuters/AP RSS is completely free, real-time, and has no request limits. NewsAPI's free tier has a 24-hour delay and a 100 req/day cap — both unacceptable for short-term trading.

### Why Polars over pandas?
Faster performance, better memory efficiency, and native DuckDB integration (`duckdb.sql("...").pl()`). Technical indicators are implemented as custom Polars expressions since pandas-ta is not compatible with Polars.

### Why Dagster + dbt?
SQL usage grows significantly in Phase 2-4 (JOINs across oil, sector, and sentiment data). dbt with dbt-duckdb adapter handles SQL transformations cleanly; Dagster orchestrates the full pipeline.

### Limitations of historical patterns
The 1970s economy had far higher oil dependency and no alternative energy. Historical patterns are used only for universe filtering; entry timing is determined by technical analysis.
