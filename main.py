# main.py
"""FinanceOS entry point — dispatches to CLI or dashboard."""
from __future__ import annotations
import sys

from src.config_loader import load_config
from src.data.fetcher import fetch_latest_price


def main() -> int:
    config = load_config()
    print(f"Welcome to {config['app']['name']} v{config['app']['version']}")
    for symbol in config["watchlist"]["symbols"]:
        price = fetch_latest_price(symbol)
        print(f"  {symbol}: {price:.2f} (mock)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
