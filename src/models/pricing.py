# src/models/pricing.py
"""
YOUR playground. Empty stubs on purpose — implement these yourself
to learn the actual finance.
"""
from __future__ import annotations

import pandas as pd


def price_option(
    spot: float, strike: float, maturity: float,
    rate: float, volatility: float, option_type: str = "call",
) -> float:
    """Price a European option. TODO: implement your model here."""
    raise NotImplementedError("Implement your pricing model here.")


def value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
    """Value-at-Risk from a returns series. TODO: implement your model here."""
    raise NotImplementedError("Implement your risk model here.")
