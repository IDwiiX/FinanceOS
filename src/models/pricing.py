# src/models/pricing.py
"""
Financial models implemented from scratch.

Everything here is explicit — no QuantLib, no arch, no black-box imports
for the actual finance. We only use numpy (arrays) and scipy.stats.norm
(the cumulative normal distribution function, which is a statistics
primitive, not a finance library).

Models included:
  - black_scholes_price        European call/put
  - implied_volatility         Newton-Raphson (with bisection fallback)
  - value_at_risk              Historical + Parametric (variance-covariance)
  - expected_shortfall         (CVaR) Historical + Parametric
  - sharpe_ratio               annualised risk-adjusted return
  - max_drawdown              worst peak-to-trough loss
  - sma_crossover_signal       BUY / SELL / HOLD based on SMA(50) vs SMA(200)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy.stats import norm

OptionType = Literal["call", "put"]


# --------------------------------------------------------------------------- #
#  Black-Scholes
# --------------------------------------------------------------------------- #
def _d1_d2(spot: float, strike: float, maturity: float,
           rate: float, volatility: float) -> tuple[float, float]:
    """Compute the d1 and d2 terms of the Black-Scholes formula.

    d1 = [ ln(S/K) + (r + 0.5*sigma^2)*T ] / (sigma*sqrt(T))
    d2 = d1 - sigma*sqrt(T)
    """
    if maturity <= 0 or volatility <= 0:
        raise ValueError("maturity and volatility must be > 0")
    sqrtT = math.sqrt(maturity)
    d1 = (math.log(spot / strike) + (rate + 0.5 * volatility ** 2) * maturity) \
         / (volatility * sqrtT)
    d2 = d1 - volatility * sqrtT
    return d1, d2


def black_scholes_price(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    option_type: OptionType = "call",
) -> float:
    """
    Closed-form Black-Scholes price for a European option.

    Call: C = S*N(d1) - K*e^(-rT)*N(d2)
    Put:  P = K*e^(-rT)*N(-d2) - S*N(-d1)

    Args:
        spot:       Current price of the underlying S.
        strike:     Strike price K.
        maturity:   Time to maturity T, in YEARS.
        rate:       Annualised continuously-compounded risk-free rate r.
        volatility: Annualised volatility of the underlying sigma.
        option_type: 'call' or 'put'.
    """
    d1, d2 = _d1_d2(spot, strike, maturity, rate, volatility)
    disc = math.exp(-rate * maturity)  # K*e^(-rT)
    if option_type == "call":
        return spot * norm.cdf(d1) - strike * disc * norm.cdf(d2)
    elif option_type == "put":
        return strike * disc * norm.cdf(-d2) - spot * norm.cdf(-d1)
    raise ValueError(f"option_type must be 'call' or 'put', got {option_type!r}")


def bs_vega(spot: float, strike: float, maturity: float,
            rate: float, volatility: float) -> float:
    """
    Vega: derivative of the BS price w.r.t. sigma.
        vega = S * sqrt(T) * phi(d1)        (phi = standard normal PDF)
    Used by the Newton-Raphson implied-vol solver.
    """
    d1, _ = _d1_d2(spot, strike, maturity, rate, volatility)
    return spot * math.sqrt(maturity) * norm.pdf(d1)


def implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    option_type: OptionType = "call",
    max_iter: int = 100,
    tol: float = 1e-6,
) -> float:
    """
    Back out implied volatility from a market option price.

    Strategy: Newton-Raphson using vega as the gradient. If vega gets
    too small (flat region) or we step out of bounds, fall back to a
    bisection search to guarantee convergence.
    """
    if market_price <= 0:
        return float("nan")

    # Try Newton-Raphson first
    sigma = 0.2  # initial guess: 20% vol
    for _ in range(max_iter):
        price = black_scholes_price(spot, strike, maturity, rate, sigma, option_type)
        diff = price - market_price
        if abs(diff) < tol:
            return sigma
        vega = bs_vega(spot, strike, maturity, rate, sigma)
        if vega < 1e-8:
            break  # flat — bail to bisection
        sigma -= diff / vega
        if sigma <= 0 or sigma > 5:  # went off the rails
            break

    # Fallback: bisection on [1e-4, 5.0]
    lo, hi = 1e-4, 5.0
    f_lo = black_scholes_price(spot, strike, maturity, rate, lo, option_type) - market_price
    f_hi = black_scholes_price(spot, strike, maturity, rate, hi, option_type) - market_price
    if f_lo * f_hi > 0:
        return float("nan")  # no sign change -> no root in this range
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        f_mid = black_scholes_price(spot, strike, maturity, rate, mid, option_type) - market_price
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------- #
#  Risk metrics
# --------------------------------------------------------------------------- #
def value_at_risk(returns: pd.Series, confidence: float = 0.95,
                  method: Literal["historical", "parametric"] = "historical") -> float:
    """
    Value-at-Risk: the loss not exceeded with probability `confidence`.

    Returned as a POSITIVE number representing the loss.
    E.g. VaR_95 = 0.03 means "with 95% confidence, daily loss won't exceed 3%".

    Historical:    empirical percentile of past returns.
    Parametric:    mu - z_alpha * sigma  (assumes normal returns).
    """
    r = returns.dropna()
    if len(r) < 2:
        return float("nan")
    alpha = 1 - confidence
    if method == "historical":
        var = -np.percentile(r, alpha * 100)
    elif method == "parametric":
        z = norm.ppf(alpha)            # negative tail quantile
        var = -(r.mean() + z * r.std(ddof=1))
    else:
        raise ValueError(f"method must be 'historical' or 'parametric', got {method!r}")
    return float(var)


def expected_shortfall(returns: pd.Series, confidence: float = 0.95,
                       method: Literal["historical", "parametric"] = "historical") -> float:
    """
    Expected Shortfall (CVaR): the average loss in the worst (1-c) tail.

    ES = E[ L | L <= VaR ]   — always >= VaR (a larger loss).

    Historical:    mean of the worst (1-c) fraction of returns.
    Parametric:    mu - sigma * phi(z_alpha)/alpha   (closed form for normal).
    """
    r = returns.dropna()
    if len(r) < 2:
        return float("nan")
    alpha = 1 - confidence
    if method == "historical":
        cutoff = np.percentile(r, alpha * 100)
        tail = r[r <= cutoff]
        es = -tail.mean() if len(tail) else float("nan")
    elif method == "parametric":
        z = norm.ppf(alpha)
        es = -(r.mean() - r.std(ddof=1) * norm.pdf(z) / alpha)
    else:
        raise ValueError(f"method must be 'historical' or 'parametric', got {method!r}")
    return float(es)


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.04,
                 periods_per_year: int = 252) -> float:
    """
    Annualised Sharpe ratio.

    Sharpe = (mean(r) * N - rf) / (std(r) * sqrt(N))

    Args:
        returns:          Daily (or periodic) simple returns.
        risk_free_rate:   Annualised risk-free rate (e.g. 0.04 = 4%).
        periods_per_year: 252 for daily, 12 for monthly, etc.
    """
    r = returns.dropna()
    if len(r) < 2:
        return float("nan")
    excess = r.mean() * periods_per_year - risk_free_rate
    vol = r.std(ddof=1) * math.sqrt(periods_per_year)
    if vol == 0:
        return float("nan")
    return float(excess / vol)


def max_drawdown(prices: pd.Series) -> tuple[float, pd.Timestamp, pd.Timestamp]:
    """
    Maximum drawdown of a price/NAV series.

    Returns (mdd_value, peak_date, trough_date) where mdd_value is the
    peak-to-trough decline as a POSITIVE fraction (e.g. 0.35 = -35%).

    Drawdown at time t = Price[t] / RunningMax[t] - 1
    Max drawdown   = min over t of Drawdown[t]
    """
    p = prices.dropna()
    if len(p) < 2:
        return float("nan"), pd.NaT, pd.NaT
    running_max = p.cummax()
    drawdown = p / running_max - 1.0
    trough_idx = drawdown.idxmin()
    mdd = drawdown.loc[trough_idx]
    # peak is the running max just before the trough
    peak_idx = p.loc[:trough_idx].idxmax()
    return float(-mdd), peak_idx, trough_idx


# --------------------------------------------------------------------------- #
#  Trading signal
# --------------------------------------------------------------------------- #
@dataclass
class Signal:
    """Result of a crossover signal computation."""
    recommendation: str   # "BUY" | "SELL" | "HOLD"
    short_sma: float
    long_sma: float
    last_close: float
    short_window: int
    long_window: int


def sma_crossover_signal(prices: pd.Series,
                         short_window: int = 50,
                         long_window: int = 200) -> Signal:
    """
    Simple Moving Average crossover signal.

    Rule:
        If SMA(short) > SMA(long):  BUY   (golden-cross / uptrend)
        If SMA(short) < SMA(long):  SELL  (death-cross / downtrend)
        If within a 1% band:        HOLD  (avoid whipsaws near the crossover)
    """
    if len(prices) < long_window:
        return Signal(
            "HOLD",
            float("nan"),
            float("nan"),
            float(prices.iloc[-1]),
            short_window,
            long_window,
        )   

    short_sma = prices.rolling(short_window).mean().iloc[-1]
    long_sma = prices.rolling(long_window).mean().iloc[-1]
    last_close = float(prices.iloc[-1])

    if math.isnan(short_sma) or math.isnan(long_sma):
        return Signal("HOLD", float("nan"), float("nan"), last_close,
                      short_window, long_window)

    ratio = short_sma / long_sma
    if ratio > 1.01:
        rec = "BUY"
    elif ratio < 0.99:
        rec = "SELL"
    else:
        rec = "HOLD"
    return Signal(rec, float(short_sma), float(long_sma), last_close,
                  short_window, long_window)


# --------------------------------------------------------------------------- #
#  Self-test
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    # Sanity checks against known values
    print("=== Black-Scholes self-test ===")
    # Classic textbook check: ATM call with no variance should = intrinsic
    p = black_scholes_price(spot=100, strike=100, maturity=1.0, rate=0.05, volatility=0.2, option_type="call")
    print(f"BS call (S=100,K=100,T=1,r=5%,sigma=20%): {p:.4f}  (expected ~10.4506)")

    iv = implied_volatility(market_price=p, spot=100, strike=100, maturity=1.0,
                            rate=0.05, option_type="call")
    print(f"Implied vol round-trip: {iv:.4f}  (should be ~0.2000)")

    print("\n=== Risk self-test ===")
    rng = np.random.default_rng(42)
    rets = pd.Series(rng.normal(0.0005, 0.01, 1000))
    print(f"Historical VaR95:  {value_at_risk(rets, 0.95, 'historical'):.4f}")
    print(f"Parametric VaR95:  {value_at_risk(rets, 0.95, 'parametric'):.4f}")
    print(f"Historical ES95:   {expected_shortfall(rets, 0.95, 'historical'):.4f}")
    print(f"Parametric ES95:   {expected_shortfall(rets, 0.95, 'parametric'):.4f}")
    print(f"Sharpe (rf=4%):    {sharpe_ratio(rets, 0.04):.4f}")

    prices = pd.Series(np.cumprod(1 + rets) * 100, name="Close")
    mdd, pk, tr = max_drawdown(prices)
    print(f"Max drawdown:      {mdd:.4f}  (peak {pk}, trough {tr})")

    print("\n=== Signal self-test ===")
    uptrend = pd.Series(np.linspace(100, 150, 250))
    print("Uptrend ->", sma_crossover_signal(uptrend).recommendation)
    downtrend = pd.Series(np.linspace(150, 100, 250))
    print("Downtrend ->", sma_crossover_signal(downtrend).recommendation)
