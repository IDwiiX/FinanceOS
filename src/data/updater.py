# src/data/updater.py
"""
Daily data update job (run by financeos-update.service / .timer).

Fetches the latest OHLCV for every watchlist symbol and writes it to
the cache directory as a pickle. Designed to be run non-interactively
by systemd; logs go to journald.
"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime

from src.config_loader import load_config
from src.data.fetcher import fetch_price_history


def run() -> int:
    cfg = load_config()
    symbols = cfg["watchlist"]["symbols"]
    period = cfg["watchlist"]["history_period"]
    print(f"[updater] {datetime.utcnow().isoformat()}Z — refreshing {len(symbols)} symbols, period={period}")

    ok, fail = 0, 0
    for sym in symbols:
        try:
            df = fetch_price_history(sym, period=period)
            last = df["Close"].iloc[-1] if not df.empty else float("nan")
            print(f"[updater]   {sym}: OK (rows={len(df)}, last_close={last:.2f})")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[updater]   {sym}: FAIL — {exc}")
            traceback.print_exc()
            fail += 1

    print(f"[updater] done. ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
