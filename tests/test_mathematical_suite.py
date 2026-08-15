import numpy as np
import pandas as pd

from src.models.pricing import (
    black_scholes_price,
    implied_volatility,
    value_at_risk,
    expected_shortfall,
    sharpe_ratio,
    max_drawdown,
    sma_crossover_signal,
)


print("=" * 64)
print("                 FINANCEOS")
print("            MATHEMATICAL TEST SUITE")
print("=" * 64)


# ================================================================
# 1. BLACK-SCHOLES
# ================================================================

print("\n[1/8] BLACK-SCHOLES")

S = 100.0
K = 100.0
T = 1.0
r = 0.05
sigma = 0.20

call = black_scholes_price(S, K, T, r, sigma, "call")
put = black_scholes_price(S, K, T, r, sigma, "put")

expected_call = 10.4505835722
expected_put = 5.5735260223

print(f"  Call:              {call:.6f}")
print(f"  Expected:          {expected_call:.6f}")
print(f"  Put:               {put:.6f}")
print(f"  Expected:          {expected_put:.6f}")

assert abs(call - expected_call) < 1e-4
assert abs(put - expected_put) < 1e-4

print("  ✓ PASS")


# ================================================================
# 2. PUT-CALL PARITY
# ================================================================

print("\n[2/8] PUT-CALL PARITY")

lhs = call - put
rhs = S - K * np.exp(-r * T)

print(f"  C - P:             {lhs:.10f}")
print(f"  S - K·exp(-rT):    {rhs:.10f}")

assert abs(lhs - rhs) < 1e-8

print("  ✓ PASS")


# ================================================================
# 3. IMPLIED VOLATILITY
# ================================================================

print("\n[3/8] IMPLIED VOLATILITY")

recovered_sigma = implied_volatility(
    market_price=call,
    spot=S,
    strike=K,
    maturity=T,
    rate=r,
    option_type="call",
)

print(f"  Original sigma:    {sigma:.8f}")
print(f"  Recovered IV:      {recovered_sigma:.8f}")

assert abs(recovered_sigma - sigma) < 1e-6

print("  ✓ PASS")


# ================================================================
# 4. VALUE AT RISK
# ================================================================

print("\n[4/8] VALUE AT RISK")

returns = pd.Series([
    -0.050, -0.040, -0.030, -0.020, -0.010,
     0.000,  0.010,  0.020,  0.030,  0.040,
     0.050,
])

historical_var = value_at_risk(
    returns,
    confidence=0.95,
    method="historical",
)

parametric_var = value_at_risk(
    returns,
    confidence=0.95,
    method="parametric",
)

print(f"  Historical VaR95: {historical_var:.8f}")
print(f"  Parametric VaR95: {parametric_var:.8f}")

assert historical_var >= 0
assert parametric_var >= 0

print("  ✓ PASS")


# ================================================================
# 5. EXPECTED SHORTFALL
# ================================================================

print("\n[5/8] EXPECTED SHORTFALL")

historical_es = expected_shortfall(
    returns,
    confidence=0.95,
    method="historical",
)

parametric_es = expected_shortfall(
    returns,
    confidence=0.95,
    method="parametric",
)

print(f"  Historical ES95:  {historical_es:.8f}")
print(f"  Parametric ES95:  {parametric_es:.8f}")

assert historical_es >= historical_var
assert parametric_es >= parametric_var

print("  ✓ PASS")


# ================================================================
# 6. SHARPE RATIO
# ================================================================

print("\n[6/8] SHARPE RATIO")

sharpe_returns = pd.Series([
    0.010,
    0.012,
    0.008,
    0.011,
    0.009,
    0.013,
    0.007,
    0.010,
    0.011,
    0.009,
])

sharpe = sharpe_ratio(
    sharpe_returns,
    risk_free_rate=0.04,
    periods_per_year=252,
)

print(f"  Annualized Sharpe: {sharpe:.8f}")

assert np.isfinite(sharpe)

print("  ✓ PASS")


# ================================================================
# 7. MAXIMUM DRAWDOWN
# ================================================================

print("\n[7/8] MAXIMUM DRAWDOWN")

prices = pd.Series(
    [100, 120, 110, 90, 80, 100, 95],
    index=pd.date_range("2026-01-01", periods=7),
)

drawdown, peak_date, trough_date = max_drawdown(prices)

print(f"  Maximum drawdown:  {drawdown:.8f}")
print(f"  Expected:          {0.3333333333:.8f}")
print(f"  Peak date:         {peak_date}")
print(f"  Trough date:       {trough_date}")

assert abs(drawdown - (1 - 80 / 120)) < 1e-8

print("  ✓ PASS")


# ================================================================
# 8. SMA SIGNAL
# ================================================================

print("\n[8/8] SMA SIGNAL")

uptrend = pd.Series(np.linspace(100, 150, 250))
downtrend = pd.Series(np.linspace(150, 100, 250))

buy_signal = sma_crossover_signal(
    uptrend,
    short_window=50,
    long_window=200,
)

sell_signal = sma_crossover_signal(
    downtrend,
    short_window=50,
    long_window=200,
)

print(f"  Uptrend signal:    {buy_signal.recommendation}")
print(f"  Short SMA:         {buy_signal.short_sma:.4f}")
print(f"  Long SMA:          {buy_signal.long_sma:.4f}")

print(f"  Downtrend signal:  {sell_signal.recommendation}")
print(f"  Short SMA:         {sell_signal.short_sma:.4f}")
print(f"  Long SMA:          {sell_signal.long_sma:.4f}")

assert buy_signal.recommendation == "BUY"
assert sell_signal.recommendation == "SELL"

print("  ✓ PASS")


# ================================================================
# FINAL RESULT
# ================================================================

print("\n" + "=" * 64)
print("                  ALL TESTS PASSED")
print("=" * 64)
print()
print("  ✓ Black-Scholes")
print("  ✓ Put-Call Parity")
print("  ✓ Implied Volatility")
print("  ✓ Value at Risk (VaR)")
print("  ✓ Expected Shortfall (ES)")
print("  ✓ Sharpe Ratio")
print("  ✓ Maximum Drawdown")
print("  ✓ SMA Trading Signal")
print()
print("FinanceOS mathematical validation: SUCCESS")
print("=" * 64)
