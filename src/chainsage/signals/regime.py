"""Volatility regime detection for ensemble strategy selection."""

from __future__ import annotations

import pandas as pd

from chainsage.adapters.indicators import atr_pct

ATR_HIGH_VOL = 0.05  # 5% over 14 days
ATR_LOW_VOL = 0.03  # 3%
ATR_PERIOD = 14


def detect_volatility_regime(df: pd.DataFrame, idx: int) -> tuple[str, float]:
    """
    Returns (regime, atr_pct) where regime is 'high', 'low', or 'normal'.
    High vol → mean reversion; low/normal → momentum gates.
    """
    history = df.iloc[: idx + 1]
    closes = history["close"]
    atr = atr_pct(closes, ATR_PERIOD)
    if atr > ATR_HIGH_VOL:
        return "high", atr
    if atr < ATR_LOW_VOL:
        return "low", atr
    return "normal", atr
