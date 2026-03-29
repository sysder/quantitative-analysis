# Quantitative Analysis

## Product Goal
A quantitative analysis system to identify stocks to buy and sell.

## Core Principles
- **Target Markets:** Japan (TSE) + US (NYSE/NASDAQ)
- **Investment Style:** Short-term trading (days to weeks)
- **Development Approach:** Start with simple screening, expand iteratively
- **Data APIs:** Prefer free tools (yfinance, FRED, RSS)

## Background
Given the current risk of Hormuz Strait closure affecting oil prices, the system uses
1973 and 1979 oil shock patterns to identify oil-sensitive sectors, then applies
technical screening and real-time news sentiment to generate buy/sell signals.

## Extensibility Principles
MCP, Skills, Subagents, Agent Teams, Hooks, and Plugins are not used in the current
implementation, but the project is designed to support them in the future:

- **Clear module boundaries** — each module (`fetcher.py`, `indicators.py`, etc.) has a
  well-defined interface so individual components can be exposed as MCP servers or
  delegated to Subagents without restructuring.
- **Externalized configuration** — stock universe, schedules, and signal thresholds are
  managed in config files, not hardcoded, making Hook and schedule integration straightforward.
- **Dagster asset-based design** — defining pipeline steps as Dagster assets keeps
  dependencies explicit and makes it easy to hand off sub-pipelines to agents later.

## Agent Team Design (Future)

The system is designed to be operated by a team of 8 agents in two layers:

### Research Team (experimental, iterative loop)
- **Researcher** — reads papers, technical indicator docs (PDFs/Markdown), proposes strategies → outputs `strategy_proposal.md`
- **Backtester** — implements proposed strategies in Python (Polars/numpy), runs backtests → outputs `backtest_results.md`
- **Reviewer** — validates results, flags overfitting/lookahead bias, feeds back to Researcher or approves → outputs `review.md`

Approved strategies are handed off to the Implementation Team.

### Implementation Team (production modules)
- **Tech Lead** — overall integration, cross-team coordination, final review
- **Data Engineer** — `fetcher.py`, `universe.py`, DuckDB schema, Dagster assets
- **Quant Researcher** — `indicators.py`, oil shock correlation analysis; consumes approved strategies from Research Team
- **Signal Engineer** — `screener.py`, `scorer.py`, multi-signal scoring
- **NLP Engineer** — `news.py`, RSS pipeline, VADER sentiment integration

### Information Flow
```
External knowledge (papers/docs)
  → Researcher  → strategy_proposal.md
  → Backtester  → backtest_results.md
  → Reviewer    → review.md (approved)
  → Quant Researcher → indicators.py
  → Signal Engineer  → screener.py / scorer.py
  → NLP Engineer     → news.py
  → Data Engineer    → fetcher.py / DuckDB
  → Tech Lead        → final integration
```

## Documentation
- [Architecture](docs/architecture.md) — pipeline phases, transformation layer, module structure
- [Data Sources](docs/data_sources.md) — ingestion methods, crawling targets
- [Schema](docs/schema.md) — DuckDB table definitions
- [Tech Stack](docs/tech_stack.md) — libraries, tools, and rationale
