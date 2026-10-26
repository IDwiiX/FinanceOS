# FinanceOS

### Quantitative Finance & Market Analytics Platform

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-2.x-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-3.x-150458?style=for-the-badge&logo=pandas&logoColor=white)
![SciPy](https://img.shields.io/badge/SciPy-1.x-8CAAE6?style=for-the-badge&logo=scipy&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-systemd-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

A modular quantitative research platform: market data, option pricing, risk analytics, systematic signals, an interactive dashboard, and automated Linux deployment — built as a complete system rather than a set of isolated finance scripts.

**Core capabilities:** market data retrieval & caching · Black-Scholes pricing · implied volatility · historical & parametric VaR/ES · Sharpe ratio · max drawdown · SMA crossover signals · CLI + Streamlit dashboard · systemd automation · mathematical validation suite.

---

## Architecture

```text
                     FinanceOS — Quant Finance Engine
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
   Data Layer                 Quant Layer                 UI Layer
   yfinance                   Black-Scholes                CLI
   Caching                    VaR / ES                     Streamlit
   Updater                    Sharpe / Drawdown
                               SMA Signals
        └──────────────────────────┼──────────────────────────┘
                                    ▼
                     Configuration (YAML + env)
```


---

## Quantitative Models

**Black-Scholes.** European call/put pricing:

$$C = S_0 N(d_1) - Ke^{-rT}N(d_2), \qquad P = Ke^{-rT}N(-d_2) - S_0N(-d_1)$$

$$d_1 = \frac{\ln(S_0/K) + (r+\sigma^2/2)T}{\sigma\sqrt{T}}, \qquad d_2 = d_1 - \sigma\sqrt{T}$$

Validated against the textbook case (S=K=100, T=1, r=5%, σ=20% → Call ≈ 10.450584, Put ≈ 5.573526) and against put-call parity, $C - P = S_0 - Ke^{-rT}$.

**Implied volatility.** Numerical root-finder recovers σ from an observed price; validated via round-trip (known σ → BS price → solved σ).

**Value-at-Risk.** Historical: $VaR_\alpha = -Q_{1-\alpha}(R)$. Parametric (normal): $VaR_\alpha = -(\mu + z_{1-\alpha}\sigma)$.

**Expected Shortfall.** Historical: $ES_\alpha = -E[R \mid R \leq Q_{1-\alpha}(R)]$. Parametric: $ES_\alpha = -\left(\mu - \sigma\frac{\phi(z_{1-\alpha})}{1-\alpha}\right)$. Tested to confirm ES is consistently more severe than VaR.

**Sharpe ratio (annualized):** $\dfrac{\mu_R N - r_f}{\sigma_R\sqrt{N}}$, default $r_f = 4\%$.

**Maximum drawdown:** $DD_t = \dfrac{P_t}{\max_{u\leq t}P_u} - 1$, $MDD = -\min_t(DD_t)$, reported with peak/trough dates.

**SMA crossover signal** (defaults: 50/200-day windows, 1% neutral band):

```text
Short SMA > Long SMA × 1.01  → BUY
Short SMA < Long SMA × 0.99  → SELL
Otherwise                    → HOLD
```

All models are validated in `tests/test_mathematical_suite.py` against known analytical values, not just execution success.

---

## Command-Line Interface

<p align="center">
  <img src="assets/cli.png" alt="FinanceOS CLI" width="850">
</p>

---

## Market Data

Provider: `yfinance`. Default watchlist: AAPL, MSFT, GOOGL, TSLA, NVDA (2y daily history, OHLCV). Local caching (1hr TTL by default) avoids redundant requests; cache is git-ignored.

---

## Usage

```bash
# Setup
git clone git@github.com:IDwiiX/FinanceOS.git && cd FinanceOS
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config/.env.example config/.env

# CLI
python main.py --price AAPL
python main.py --signal AAPL
python main.py --option AAPL --strike 300 --maturity 1 --vol 0.25 --rate 0.04
python main.py --risk AAPL --period 252
python main.py --menu          # interactive CLI
python main.py --dashboard     # Streamlit, http://localhost:8501

# Tests
PYTHONPATH=. .venv/bin/python tests/test_mathematical_suite.py

# Deploy as systemd services
chmod +x deploy.sh && ./deploy.sh
```

Configuration is centralized in `config/settings.yaml` (watchlist, cache, risk confidence levels, SMA windows, dashboard host/port) — no hard-coded constants scattered through the codebase.

