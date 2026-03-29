# Architecture

## Pipeline

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

## Transformation Layer

```
Polars:  raw data ingestion → technical indicator calculation → write to DuckDB
   ↓
dbt:     SQL transformations on DuckDB (JOINs, aggregations, scoring)
   ↓
Dagster: orchestration of the entire pipeline
```

## Module Structure

```
universe.py     — manage target stock lists (crawled from Wikipedia / JPX)
fetcher.py      — fetch data via yfinance, FRED API, Stooq crawling, BOJ/JPX CSV
indicators.py   — calculate technical indicators (MA, RSI, MACD, etc.) in Polars
screener.py     — filter stocks by signal conditions
scorer.py       — multi-signal scoring
news.py         — RSS fetching, keyword filtering, sentiment analysis
report.py       — output results (CSV or HTML)
```
