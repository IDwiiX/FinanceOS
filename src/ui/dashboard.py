# src/ui/dashboard.py
"""
Streamlit dashboard for FinanceOS.

Run with:
    streamlit run src/ui/dashboard.py --server.address 0.0.0.0 --server.port 8501

Panels:
  - Price chart with SMA(50) / SMA(200) overlay (plotly)
  - Option pricer (call/put + implied vol)
  - Risk metrics card (VaR, ES, Sharpe, Max Drawdown)
  - SMA crossover signal
Data is cached with st.cache_data to avoid re-fetching on every widget change.
"""
from __future__ import annotations


import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config_loader import load_config
from src.data.fetcher import compute_returns, fetch_latest_price, fetch_price_history
from src.models import pricing

cfg = load_config()


# --------------------------------------------------------------------------- #
#  Caching wrappers
#  (TTL comes from config; st.cache_data persists across reruns.)
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=cfg["data"]["cache_ttl_seconds"], show_spinner=False)
def _cached_history(symbol: str, period: str) -> pd.DataFrame:
    return fetch_price_history(symbol, period=period)


@st.cache_data(ttl=cfg["data"]["cache_ttl_seconds"], show_spinner=False)
def _cached_price(symbol: str) -> float:
    return fetch_latest_price(symbol)


# --------------------------------------------------------------------------- #
#  Page setup
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="FinanceOS", page_icon="📈", layout="wide")
st.title("FinanceOS Dashboard")

symbols = cfg["watchlist"]["symbols"]
default_sym = symbols[0]
sel = st.sidebar.selectbox("Symbol", symbols, index=0)
period = st.sidebar.selectbox("History", ["3mo", "6mo", "1y", "2y", "5y"],
                              index=2 if "1y" in cfg["watchlist"]["history_period"] else 3)


# --------------------------------------------------------------------------- #
#  1. Price chart with SMA overlay
# --------------------------------------------------------------------------- #
st.header(f"Price — {sel}")
df = _cached_history(sel, period)
if df.empty:
    st.error(f"No data for {sel}")
    st.stop()

short_w = cfg["signal"]["short_window"]
long_w = cfg["signal"]["long_window"]
df = df.copy()
df[f"SMA{short_w}"] = df["Close"].rolling(short_w).mean()
df[f"SMA{long_w}"] = df["Close"].rolling(long_w).mean()

fig = go.Figure()
fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode="lines",
                         name="Close", line=dict(color="#1f77b4", width=2)))
fig.add_trace(go.Scatter(x=df.index, y=df[f"SMA{short_w}"], mode="lines",
                         name=f"SMA{short_w}", line=dict(color="#ff7f0e", width=1.3)))
fig.add_trace(go.Scatter(x=df.index, y=df[f"SMA{long_w}"], mode="lines",
                         name=f"SMA{long_w}", line=dict(color="#2ca02c", width=1.3)))
fig.update_layout(height=480, xaxis_title="Date", yaxis_title="Price (USD)",
                  hovermode="x unified", margin=dict(l=10, r=10, t=20, b=10))
st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------- #
#  2. Risk metrics
# --------------------------------------------------------------------------- #
st.header("Risk Metrics")
risk_col1, risk_col2, risk_col3, risk_col4 = st.columns(4)

period_days = {"3mo": 63, "6mo": 126, "1y": 252, "2y": 504, "5y": 1260}.get(period, 252)
rets = compute_returns(df).tail(period_days)
prices = df["Close"].tail(period_days)
conf = cfg["risk"]["var_confidence"]
rf = cfg["risk"]["risk_free_rate"]

var_h = pricing.value_at_risk(rets, conf, "historical")
es_h = pricing.expected_shortfall(rets, conf, "historical")
sharpe = pricing.sharpe_ratio(rets, rf)
mdd, peak_dt, trough_dt = pricing.max_drawdown(prices)

risk_col1.metric(f"VaR ({conf:.0%})", f"{var_h:+.2%}",
                 help="Historical simulation: loss not exceeded with this confidence.")
risk_col2.metric(f"ES / CVaR ({conf:.0%})", f"{es_h:+.2%}",
                 help="Average loss in the worst tail.")
risk_col3.metric("Sharpe (ann.)", f"{sharpe:+.2f}",
                 help="Annualised risk-adjusted return.")
risk_col4.metric("Max Drawdown", f"{mdd:+.2%}",
                 help=f"Peak {peak_dt} -> Trough {trough_dt}")

with st.expander("Parametric (variance-covariance) view"):
    var_p = pricing.value_at_risk(rets, conf, "parametric")
    es_p = pricing.expected_shortfall(rets, conf, "parametric")
    pcol1, pcol2 = st.columns(2)
    pcol1.metric(f"VaR ({conf:.0%}, parametric)", f"{var_p:+.2%}")
    pcol2.metric(f"ES ({conf:.0%}, parametric)", f"{es_p:+.2%}")


# --------------------------------------------------------------------------- #
#  3. Trading signal
# --------------------------------------------------------------------------- #
st.header("Trading Signal")
sig = pricing.sma_crossover_signal(df["Close"], short_w, long_w)
colour = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}[sig.recommendation]
scol1, scol2, scol3, scol4 = st.columns(4)
scol1.metric("Recommendation", f"{colour} {sig.recommendation}")
scol2.metric("Last Close", f"${sig.last_close:,.2f}")
scol3.metric(f"SMA{sig.short_window}", f"{sig.short_sma:,.2f}")
scol4.metric(f"SMA{sig.long_window}", f"{sig.long_sma:,.2f}")


# --------------------------------------------------------------------------- #
#  4. Option pricer
# --------------------------------------------------------------------------- #
st.header("Option Pricer (Black-Scholes)")
spot = _cached_price(sel)

with st.form("option_form"):
    ocol1, ocol2, ocol3, ocol4, ocol5 = st.columns(5)
    strike = ocol1.number_input("Strike", min_value=0.01,
                                value=round(spot * 1.1, 2), step=0.5)
    maturity = ocol2.number_input("Maturity (yrs)", min_value=0.01,
                                  value=1.0, step=0.1)
    vol = ocol3.number_input("Volatility", min_value=0.001,
                             value=0.20, step=0.01, format="%.3f")
    rate = ocol4.number_input("Risk-free rate", min_value=-0.10,
                              value=rf, step=0.005, format="%.3f")
    otype = ocol5.selectbox("Type", ["call", "put"])
    submitted = st.form_submit_button("Price")

if submitted:
    call = pricing.black_scholes_price(spot, strike, maturity, rate, vol, "call")
    put = pricing.black_scholes_price(spot, strike, maturity, rate, vol, "put")
    chosen = call if otype == "call" else put
    iv = pricing.implied_volatility(chosen, spot, strike, maturity, rate, otype)

    res1, res2, res3, res4 = st.columns(4)
    res1.metric("Spot", f"${spot:,.2f}")
    res2.metric(f"{otype.title()} price", f"${chosen:,.4f}")
    res3.metric("Implied vol", f"{iv:.4%}" if iv == iv else "n/a")
    res4.metric("Vega", f"{pricing.bs_vega(spot, strike, maturity, rate, vol):.4f}")

st.caption(f"FinanceOS v{cfg['app']['version']} — data via yfinance")
