"""Local technical indicators when CMC REST TA endpoint unavailable."""

from __future__ import annotations

import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / (loss + 1e-9)
    val = 100 - (100 / (1 + rs.iloc[-1]))
    return float(val) if pd.notna(val) else 50.0


def macd_histogram(series: pd.Series) -> float:
    e12 = ema(series, 12)
    e26 = ema(series, 26)
    macd = e12 - e26
    signal = ema(macd, 9)
    hist = macd - signal
    return float(hist.iloc[-1]) if len(hist) > 0 else 0.0


def atr_pct(closes: pd.Series, period: int = 14) -> float:
    """ATR as fraction of price (close-to-close TR proxy when OHLC unavailable)."""
    if len(closes) < period + 1:
        return 0.0
    tr = closes.diff().abs()
    atr = tr.rolling(period).mean().iloc[-1]
    price = float(closes.iloc[-1])
    if price <= 0 or pd.isna(atr):
        return 0.0
    return float(atr / price)


def compute_ta(closes: pd.Series) -> dict[str, float]:
    if len(closes) < 30:
        return {"rsi14": 50.0, "macd_histogram": 0.0, "ema21": float(closes.iloc[-1]), "atr14_pct": 0.0}
    return {
        "rsi14": rsi(closes),
        "macd_histogram": macd_histogram(closes),
        "ema21": float(ema(closes, 21).iloc[-1]),
        "atr14_pct": atr_pct(closes, 14),
    }
