# src/data/fetcher.py
"""
Data fetching layer.

Fetches real OHLCV data from yfinance with:
  - on-disk pickle cache keyed by (symbol, period) with a TTL
  - timeout + exponential-backoff retries
  - graceful fallback to mock data when offline or rate-limited
"""
from __future__ import annotations

import hashlib
import pickle
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

from src.config_loader import load_config, project_root


# --------------------------------------------------------------------------- #
#  Internal helpers
# --------------------------------------------------------------------------- #
def _cache_paths(symbol: str, period: str) -> tuple[Path, Path]:
    """Return (df_path, meta_path) for a cached entry."""
    cfg = load_config()
    cache_dir = project_root() / cfg["data"]["cache_dir"]
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(f"{symbol}_{period}".encode()).hexdigest()[:12]
    return cache_dir / f"{symbol}_{period}_{key}.pkl", cache_dir / f"{symbol}_{period}_{key}.meta"


def _cache_valid(meta_path: Path) -> bool:
    """True if a cache entry exists and is younger than TTL."""
    if not meta_path.exists():
        return False
    try:
        meta = pickle.loads(meta_path.read_bytes())
    except Exception:
        return False
    ttl = load_config()["data"]["cache_ttl_seconds"]
    return (datetime.utcnow() - meta["cached_at"]).total_seconds() < ttl


def _read_cache(df_path: Path) -> pd.DataFrame:
    return pd.read_pickle(df_path)


def _write_cache(df: pd.DataFrame, df_path: Path, meta_path: Path) -> None:
    df.to_pickle(df_path)
    meta_path.write_bytes(pickle.dumps({"cached_at": datetime.utcnow()}))


def _yf_download(symbol: str, period: str) -> pd.DataFrame:
    """Call yfinance with retry + backoff. Raises on persistent failure."""
    cfg = load_config()["data"]
    timeout = cfg.get("request_timeout", 10)
    retries = cfg.get("request_retries", 3)
    backoff = cfg.get("retry_backoff", 1.5)

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            df = yf.download(
                symbol,
                period=period,
                interval="1d",
                progress=False,
                timeout=timeout,
                auto_adjust=True,
                threads=False,
            )
            if df is not None and not df.empty:
                # Normalise columns: yfinance may return MultiIndex when
                # a single ticker is requested.
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.index = pd.to_datetime(df.index).date
                df.index.name = "date"
                return df
            # empty result — treat as soft failure and retry
            last_err = RuntimeError(f"yfinance returned empty frame for {symbol}")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        time.sleep(backoff ** attempt)
    raise RuntimeError(f"yfinance failed for {symbol} after {retries} attempts: {last_err}")


def _sample_series(symbol: str, days: int = 365) -> pd.DataFrame:
    """Deterministic mock OHLCV — used only when the network is unavailable."""
    today = datetime.utcnow().date()
    idx = [today - timedelta(days=d) for d in range(days)][::-1]
    base = abs(hash(symbol)) % 200 + 50
    rows = []
    for i, d in enumerate(idx):
        close = base + (i % 7) - 3 + 0.5 * i / 30
        rows.append({
            "Open": close - 1, "High": close + 2,
            "Low": close - 2, "Close": close,
            "Volume": 1_000_000 + i,
        })
    df = pd.DataFrame(rows, index=pd.Index(idx, name="date"))
    return df


# --------------------------------------------------------------------------- #
#  Public API
# --------------------------------------------------------------------------- #
def fetch_price_history(symbol: str, period: str | None = None) -> pd.DataFrame:
    """
    Fetch historical OHLCV for a symbol.

    Uses cache when fresh; otherwise hits yfinance. Falls back to mock
    data if the network is unavailable so the rest of the pipeline still
    works offline.

    Returns a DataFrame indexed by date with columns
    [Open, High, Low, Close, Volume].
    """
    cfg = load_config()
    period = period or cfg["watchlist"]["history_period"]

    df_path, meta_path = _cache_paths(symbol, period)
    if _cache_valid(meta_path):
        return _read_cache(df_path)

    try:
        df = _yf_download(symbol, period)
        _write_cache(df, df_path, meta_path)
        return df
    except Exception as exc:  # noqa: BLE001
        print(f"[fetcher] WARNING: using mock data for {symbol} ({exc})")
        days = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825}.get(period, 365)
        df = _sample_series(symbol, days=days)
        return df


def fetch_latest_price(symbol: str) -> float:
    """Return the most recent close price for a symbol."""
    df = fetch_price_history(symbol, period="5d")
    return float(df["Close"].iloc[-1])


def fetch_snapshot(symbols: list[str]) -> dict[str, float]:
    """Return {symbol: latest_close} for a list of tickers."""
    return {s: fetch_latest_price(s) for s in symbols}


def compute_returns(df: pd.DataFrame) -> pd.Series:
    """Daily simple returns from a price DataFrame (Close column)."""
    return df["Close"].pct_change().dropna()


def compute_log_returns(df: pd.DataFrame) -> pd.Series:
    """Daily log returns from a price DataFrame."""
    import numpy as np
    return np.log(df["Close"] / df["Close"].shift(1)).dropna()


if __name__ == "__main__":
    # Quick smoke test
    for sym in load_config()["watchlist"]["symbols"]:
        print(f"{sym}: ${fetch_latest_price(sym):.2f}")
