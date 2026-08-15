# FinanceOS

### Quantitative Finance Engine & Market Analytics Platform

FinanceOS is a modular quantitative-finance platform for market-data ingestion, derivative pricing, portfolio risk analysis, technical signals, and interactive financial visualization.

It combines quantitative models with production-oriented software engineering practices including caching, configuration management, automated updates, CLI tooling, Streamlit visualization, and Linux systemd deployment.

---

## Overview

FinanceOS provides a unified interface for:

- Real-time market prices
- Historical market-data retrieval
- Local data caching
- Black-Scholes option pricing
- Implied volatility estimation
- Historical and parametric Value-at-Risk
- Historical and parametric Expected Shortfall
- Sharpe ratio analysis
- Maximum drawdown analysis
- SMA crossover signals
- Interactive Streamlit dashboards
- Automated Linux data updates

The system currently uses `yfinance` as its market-data provider and supports configurable watchlists.

---

## Architecture

```text
                 ┌─────────────────────┐
                 │     Yahoo Finance   │
                 │      Market Data    │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │    Data Fetcher     │
                 │  Retry + Caching    │
                 └──────────┬──────────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │      FinanceOS Core       │
              │                           │
              │  • Black-Scholes          │
              │  • Implied Volatility     │
              │  • VaR / Expected Shortfall│
              │  • Sharpe Ratio           │
              │  • Maximum Drawdown       │
              │  • SMA Signals            │
              └─────────────┬─────────────┘
                            │
              ┌─────────────┴──────────────┐
              ▼                            ▼
       ┌───────────────┐           ┌────────────────┐
       │      CLI      │           │   Streamlit    │
       │   Interface   │           │    Dashboard   │
       └───────────────┘           └────────────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Linux / systemd     │
                 │ Automated Updates   │
                 └─────────────────────┘
