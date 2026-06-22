# src/data/fetcher.py
"""
Data fetching layer. Returns MOCK data so the whole pipeline
(fetch -> model -> UI) can be wired up without writing logic yet.
Swap _sample_series() for a real yfinance/requests call later.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd


def _sample_series(symbol: str, days: int = 30) -> pd.DataFrame:
    """Deterministic fake OHLCV so the pipeline can be wired up."""
    # TODO (you, later): replace with real API call. Mock only.
    today = datetime.utcnow().date()
    idx = [today - timedelta(days=d) for d in range(days)][::-1]
    base = abs(hash(symbol)) % 200 + 50
    rows = []
    for i, d in enumerate(idx):
        close = base + (i % 7) - 3
        rows.append({
            "date": d,
            "open": close - 1, "high": close + 2,
            "low": close - 2, "close": close,
            "volume": 1_000_000 + i,
        })
    return pd.DataFrame(rows).set_index("date")


def fetch_price_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    """Historical OHLCV. TODO: real fetching."""
    days = {"1mo": 30, "3mo": 90, "1y": 365}.get(period, 30)
    return _sample_series(symbol, days=days)


def fetch_latest_price(symbol: str) -> float:
    """Most recent close. TODO: real fetching."""
    return float(_sample_series(symbol, days=1)["close"].iloc[-1])
