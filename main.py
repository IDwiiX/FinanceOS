#!/usr/bin/env python3
# main.py
"""FinanceOS entry point.

Usage:
    python main.py                      # show watchlist prices
    python main.py --price AAPL         # latest price + signal
    python main.py --menu               # interactive CLI menu
    python main.py --signal AAPL        # SMA crossover signal
    python main.py --option AAPL --strike 200 --maturity 1 --vol 0.2 --rate 0.05
    python main.py --risk AAPL          # VaR / ES / Sharpe / MDD
    python main.py --dashboard          # launch the Streamlit dashboard
"""
from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.panel import Panel

from src.config_loader import load_config
from src.data.fetcher import fetch_latest_price, fetch_price_history, compute_returns
from src.models import pricing

console = Console()


def _print_prices(symbols: list[str]) -> None:
    from rich.table import Table
    table = Table(title="Watchlist Prices")
    table.add_column("Symbol", style="cyan bold")
    table.add_column("Last Close", justify="right", style="green")
    for sym in symbols:
        try:
            price = fetch_latest_price(sym)
            table.add_row(sym, f"${price:,.2f}")
        except Exception as exc:  # noqa: BLE001
            table.add_row(sym, f"[red]error: {exc}[/red]")
    console.print(table)


def _signal_panel(symbol: str) -> None:
    cfg = load_config()
    sw, lw = cfg["signal"]["short_window"], cfg["signal"]["long_window"]
    df = fetch_price_history(symbol)
    sig = pricing.sma_crossover_signal(df["Close"], sw, lw)
    colour = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[sig.recommendation]
    body = (
        f"Last close:     ${sig.last_close:,.2f}\n"
        f"SMA({sig.short_window}):       {sig.short_sma:,.2f}\n"
        f"SMA({sig.long_window}):      {sig.long_sma:,.2f}\n"
        f"Recommendation: [{colour} bold]{sig.recommendation}[/{colour} bold]"
    )
    console.print(Panel(body, title=f"Signal — {symbol}", border_style="blue", expand=False))


def _option_panel(symbol: str, strike: float, maturity: float, rate: float, vol: float) -> None:
    spot = fetch_latest_price(symbol)
    call = pricing.black_scholes_price(spot, strike, maturity, rate, vol, "call")
    put = pricing.black_scholes_price(spot, strike, maturity, rate, vol, "put")
    iv_call = pricing.implied_volatility(call, spot, strike, maturity, rate, "call")
    body = (
        f"[cyan]Spot[/cyan]                ${spot:,.2f}\n"
        f"[cyan]Strike[/cyan]              ${strike:,.2f}\n"
        f"[cyan]Maturity (yrs)[/cyan]      {maturity:.3f}\n"
        f"[cyan]Rate (annual)[/cyan]       {rate:.2%}\n"
        f"[cyan]Volatility (annual)[/cyan] {vol:.2%}\n"
        f"\n[green bold]Call price[/green bold]        ${call:,.4f}\n"
        f"[red bold]Put price[/red bold]          ${put:,.4f}\n"
        f"[yellow]Implied vol (call)[/yellow]     {iv_call:.4%}"
    )
    console.print(Panel(body, title=f"Option Pricing — {symbol}",
                        border_style="magenta", expand=False))


def _risk_panel(symbol: str, period: int) -> None:
    from rich.table import Table
    cfg = load_config()
    rf = cfg["risk"]["risk_free_rate"]
    conf = cfg["risk"]["var_confidence"]
    df = fetch_price_history(symbol)
    rets = compute_returns(df).tail(period)
    prices = df["Close"].tail(period)

    var_h = pricing.value_at_risk(rets, conf, "historical")
    var_p = pricing.value_at_risk(rets, conf, "parametric")
    es_h = pricing.expected_shortfall(rets, conf, "historical")
    es_p = pricing.expected_shortfall(rets, conf, "parametric")
    sharpe = pricing.sharpe_ratio(rets, rf)
    mdd, peak, trough = pricing.max_drawdown(prices)

    table = Table(title=f"Risk Metrics — {symbol} (last {len(rets)} days)")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="yellow")
    table.add_row(f"VaR {conf:.0%} (historical)", f"{var_h:+.4%}")
    table.add_row(f"VaR {conf:.0%} (parametric)", f"{var_p:+.4%}")
    table.add_row(f"ES  {conf:.0%} (historical)", f"{es_h:+.4%}")
    table.add_row(f"ES  {conf:.0%} (parametric)", f"{es_p:+.4%}")
    table.add_row("Sharpe ratio (annualised)", f"{sharpe:+.4f}")
    table.add_row("Max drawdown", f"{mdd:+.4%}")
    console.print(table)


def _launch_dashboard() -> int:
    """Start the Streamlit dashboard as a foreground process."""
    import os
    import subprocess
    cfg = load_config()
    port = cfg["dashboard"]["port"]
    host = cfg["dashboard"]["host"]
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        "src/ui/dashboard.py",
        f"--server.address={host}",
        f"--server.port={port}",
        "--server.headless=true",
    ]
    console.print(f"[bold green]Starting dashboard on http://{host}:{port}[/bold green]")
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        console.print("\n[dim]dashboard stopped.[/dim]")
        return 0


def main() -> int:
    cfg = load_config()
    parser = argparse.ArgumentParser(
        prog="financeos",
        description=f"{cfg['app']['name']} v{cfg['app']['version']}",
    )
    parser.add_argument("--price", metavar="SYM", help="Latest price for a ticker")
    parser.add_argument("--signal", metavar="SYM", help="SMA crossover signal for a ticker")
    parser.add_argument("--option", metavar="SYM", help="Price an option (Black-Scholes)")
    parser.add_argument("--strike", type=float, default=None, help="Strike (default: spot*1.1)")
    parser.add_argument("--maturity", type=float, default=1.0, help="Maturity in years")
    parser.add_argument("--vol", type=float, default=0.20, help="Annualised volatility")
    parser.add_argument("--rate", type=float, default=None, help="Risk-free rate")
    parser.add_argument("--risk", metavar="SYM", help="Risk metrics for a ticker")
    parser.add_argument("--period", type=int, default=None, help="Lookback in trading days")
    parser.add_argument("--menu", action="store_true", help="Launch interactive CLI menu")
    parser.add_argument("--dashboard", action="store_true", help="Launch Streamlit dashboard")
    args = parser.parse_args()

    # --- dispatch ---
    if args.dashboard:
        return _launch_dashboard()

    if args.menu:
        from src.ui.cli import menu
        menu()
        return 0

    if args.price:
        p = fetch_latest_price(args.price.upper())
        console.print(f"[cyan bold]{args.price.upper()}[/cyan bold]  [green]${p:,.2f}[/green]")
        return 0

    if args.signal:
        _signal_panel(args.signal.upper())
        return 0

    if args.option:
        sym = args.option.upper()
        spot = fetch_latest_price(sym)
        rate = args.rate if args.rate is not None else cfg["risk"]["risk_free_rate"]
        strike = args.strike if args.strike is not None else round(spot * 1.1, 2)
        _option_panel(sym, strike, args.maturity, rate, args.vol)
        return 0

    if args.risk:
        period = args.period or cfg["risk"]["periods"]["long"]
        _risk_panel(args.risk.upper(), period)
        return 0

    # --- default: show watchlist prices ---
    console.print(Panel(
        f"[bold magenta]Welcome to {cfg['app']['name']} v{cfg['app']['version']}[/bold magenta]",
        border_style="magenta", expand=False))
    _print_prices(cfg["watchlist"]["symbols"])
    console.print("\n[dim]Try: --price AAPL, --signal AAPL, --option AAPL, --risk AAPL, --menu, --dashboard[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
