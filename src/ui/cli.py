# src/ui/cli.py
"""
Interactive CLI for FinanceOS (typer + rich).

Commands:
    python -m src.ui.cli menu        # interactive menu
    python -m src.ui.cli price AAPL  # latest price + signal
    python -m src.ui.cli signal AAPL # SMA crossover signal
    python -m src.ui.cli option AAPL --strike 200 --maturity 1 --vol 0.2 --rate 0.05
    python -m src.ui.cli risk AAPL --period 252
"""
from __future__ import annotations

import sys

import pandas as pd
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from src.config_loader import load_config
from src.data.fetcher import fetch_latest_price, fetch_price_history, compute_returns
from src.models import pricing

app = typer.Typer(help="FinanceOS command-line interface.")
console = Console()


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _print_prices(symbols: list[str]) -> None:
    table = Table(title="Watchlist Prices", show_lines=False)
    table.add_column("Symbol", style="cyan bold")
    table.add_column("Last Close", justify="right", style="green")
    for sym in symbols:
        try:
            price = fetch_latest_price(sym)
            table.add_row(sym, f"${price:,.2f}")
        except Exception as exc:  # noqa: BLE001
            table.add_row(sym, f"[red]error: {exc}[/red]")
    console.print(table)


def _option_panel(symbol: str, strike: float, maturity: float,
                  rate: float, vol: float) -> None:
    spot = fetch_latest_price(symbol)
    call = pricing.black_scholes_price(spot, strike, maturity, rate, vol, "call")
    put = pricing.black_scholes_price(spot, strike, maturity, rate, vol, "put")
    iv_call = pricing.implied_volatility(call, spot, strike, maturity, rate, "call")

    body = (
        f"[cyan]Spot[/cyan]              ${spot:,.2f}\n"
        f"[cyan]Strike[/cyan]            ${strike:,.2f}\n"
        f"[cyan]Maturity (yrs)[/cyan]    {maturity:.3f}\n"
        f"[cyan]Rate (annual)[/cyan]     {rate:.2%}\n"
        f"[cyan]Volatility (annual)[/cyan] {vol:.2%}\n"
        f"\n[green bold]Call price[/green bold]      ${call:,.4f}\n"
        f"[red bold]Put price[/red bold]        ${put:,.4f}\n"
        f"[yellow]Implied vol (call)[/yellow]   {iv_call:.4%}"
    )
    console.print(Panel(body, title=f"Option Pricing — {symbol}",
                        border_style="magenta", expand=False))


def _risk_table(symbol: str, period: int) -> None:
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

    table = Table(title=f"Risk Metrics — {symbol} (last {len(rets)} days)",
                  show_lines=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="yellow")
    table.add_row(f"VaR {conf:.0%} (historical)", f"{var_h:+.4%}")
    table.add_row(f"VaR {conf:.0%} (parametric)", f"{var_p:+.4%}")
    table.add_row(f"ES  {conf:.0%} (historical)", f"{es_h:+.4%}")
    table.add_row(f"ES  {conf:.0%} (parametric)", f"{es_p:+.4%}")
    table.add_row("Sharpe ratio (annualised)", f"{sharpe:+.4f}")
    table.add_row("Max drawdown", f"{mdd:+.4%}")
    table.add_row("Drawdown peak", str(peak))
    table.add_row("Drawdown trough", str(trough))
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
    console.print(Panel(body, title=f"Signal — {symbol} (SMA crossover)",
                        border_style="blue", expand=False))


# --------------------------------------------------------------------------- #
#  Commands
# --------------------------------------------------------------------------- #
@app.command()
def price(symbol: str) -> None:
    """Show the latest price for a ticker."""
    p = fetch_latest_price(symbol.upper())
    console.print(f"[cyan bold]{symbol.upper()}[/cyan bold]  "
                  f"[green]${p:,.2f}[/green]")


@app.command()
def signal(symbol: str) -> None:
    """Show the SMA crossover signal for a ticker."""
    _signal_panel(symbol.upper())


@app.command()
def option(
    symbol: str,
    strike: float = typer.Option(None, help="Strike; default = spot * 1.1"),
    maturity: float = typer.Option(1.0, help="Time to maturity in years"),
    vol: float = typer.Option(0.20, help="Annualised volatility (0.20 = 20%)"),
    rate: float = typer.Option(None, help="Risk-free rate; default = config"),
) -> None:
    """Price a European option with Black-Scholes."""
    cfg = load_config()
    rate = rate if rate is not None else cfg["risk"]["risk_free_rate"]
    spot = fetch_latest_price(symbol.upper())
    strike = strike if strike is not None else round(spot * 1.1, 2)
    _option_panel(symbol.upper(), strike, maturity, rate, vol)


@app.command()
def risk(
    symbol: str,
    period: int = typer.Option(None, help="Lookback in trading days"),
) -> None:
    """Show VaR, ES, Sharpe, and Max Drawdown for a ticker."""
    cfg = load_config()
    period = period if period is not None else cfg["risk"]["periods"]["long"]
    _risk_table(symbol.upper(), period)


# --------------------------------------------------------------------------- #
#  Interactive menu
# --------------------------------------------------------------------------- #
@app.command()
def menu() -> None:
    """Launch the interactive FinanceOS menu."""
    cfg = load_config()
    symbols = cfg["watchlist"]["symbols"]

    while True:
        console.print(Panel(
            f"[bold magenta]FinanceOS v{cfg['app']['version']}[/bold magenta]\n"
            "Interactive terminal",
            border_style="magenta", expand=False))
        _print_prices(symbols)

        console.print(
            "\n[bold]Options:[/bold]\n"
            "  1) Option pricing\n"
            "  2) Risk metrics\n"
            "  3) Trading signal\n"
            "  q) Quit\n")
        choice = Prompt.ask("Choice", default="q").strip().lower()

        if choice == "q":
            console.print("[dim]bye.[/dim]")
            return
        if choice not in ("1", "2", "3"):
            continue

        sym = Prompt.ask("Symbol", default=symbols[0]).upper()

        if choice == "1":
            spot = fetch_latest_price(sym)
            k = Prompt.ask("Strike", default=f"{spot*1.1:.2f}")
            t = Prompt.ask("Maturity (years)", default="1.0")
            v = Prompt.ask("Volatility (e.g. 0.20)", default="0.20")
            r = Prompt.ask("Risk-free rate", default=str(cfg["risk"]["risk_free_rate"]))
            _option_panel(sym, float(k), float(t), float(r), float(v))

        elif choice == "2":
            p = Prompt.ask("Lookback (days)", default=str(cfg["risk"]["periods"]["long"]))
            _risk_table(sym, int(p))

        elif choice == "3":
            _signal_panel(sym)

        Prompt.ask("\nPress Enter to continue", default="")


if __name__ == "__main__":
    app()
