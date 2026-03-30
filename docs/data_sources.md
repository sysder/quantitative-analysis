# Data Sources

## Overview

| Data | Source | Period | Method |
|---|---|---|---|
| Nikkei 225 index | Stooq | 1970s~ | Crawling |
| TSE sector indices | BOJ / JPX | 1970s~ | CSV download / crawling |
| WTI crude oil price | FRED API | 1970s~ | API |
| US stocks (S&P500) | FRED / yfinance | 1970s~ | API |
| Individual stock prices & volume | yfinance | 1990s~ | API |
| Stock universe (Nikkei 225 / TOPIX500 / S&P500) | Wikipedia / JPX | current | Crawling |
| Reuters / AP news | RSS | real-time | feedparser |

## Crawling Targets

| Target | URL | Purpose |
|---|---|---|
| Nikkei 225 constituents | Wikipedia / Nikkei official | Universe list |
| TOPIX500 constituents | JPX official | Universe list |
| S&P500 constituents | Wikipedia | Universe list |
| Nikkei 225 historical index | Stooq | Phase 2 historical analysis |
| TSE sector indices | BOJ / JPX | Phase 2 historical analysis |

## Notes

- Individual Japanese stock data prior to the 1990s is not available via free sources.
  Sector-level indices (BOJ/JPX) and the Nikkei 225 (Stooq) are used for Phase 2 instead.
- FRED provides free historical data for WTI crude oil and US equities back to the 1970s.
