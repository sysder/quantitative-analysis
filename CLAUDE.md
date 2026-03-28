# Quantitative Analysis — Design Document

## Product Goal
A quantitative analysis system to identify stocks to buy and sell.

## Core Principles
- **Target Markets:** Japan (TSE) + US (NYSE/NASDAQ)
- **Investment Style:** Short-term trading (days to weeks)
- **Development Approach:** Start with simple screening, expand iteratively
- **Data APIs:** Prefer free tools (yfinance, RSS)

---

## Overall Architecture

```
Phase 1: Data Foundation
  - Fetch oil prices, stock prices, and volume data via yfinance
  - Build target stock universe (Nikkei 225/TOPIX500 + S&P500)
  - Apply liquidity filter

Phase 2: Historical Correlation Analysis
  - Analyze oil price and stock price movement patterns during the 1973 and 1979 oil shocks
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
universe.py     — manage target stock lists
fetcher.py      — fetch data via yfinance
indicators.py   — calculate technical indicators (MA, RSI, MACD, etc.)
screener.py     — filter stocks by signal conditions
scorer.py       — multi-signal scoring
news.py         — RSS fetching, keyword filtering, sentiment analysis
report.py       — output results (CSV or HTML)
```

---

## Tech Stack

| Purpose | Library |
|---|---|
| Stock & oil price data | `yfinance` |
| Data processing | `pandas`, `numpy` |
| Technical indicators | `pandas-ta` or custom implementation |
| RSS feed parsing | `feedparser` |
| Sentiment analysis | `vaderSentiment` |
| Visualization | `matplotlib`, `plotly` |

---

## Background & Design Rationale

### Why reference the oil shocks?
Given the current risk of Hormuz Strait closure affecting oil prices, we use the 1973 and 1979 oil shock patterns to identify sectors sensitive to oil price swings. Sectors historically helped (energy, defense) and hurt (airlines, autos, materials) are quantified from data and used to narrow the stock universe.

### Why RSS over NewsAPI?
Reuters/AP RSS is completely free, real-time, and has no request limits. NewsAPI's free tier has a 24-hour delay and a 100 req/day cap — both unacceptable for short-term trading.

### Limitations of historical patterns
The 1970s economy had far higher oil dependency and no alternative energy. Historical patterns are used only for universe filtering; entry timing is determined by technical analysis.
