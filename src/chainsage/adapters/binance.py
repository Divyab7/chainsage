"""Binance public market data — OHLCV and funding rates."""

from __future__ import annotations

from typing import Any

import httpx
import pandas as pd

BINANCE = "https://api.binance.com"
BINANCE_FUTURES = "https://fapi.binance.com"

SYMBOL_MAP = {
    "BNB": "BNBUSDT",
    "CAKE": "CAKEUSDT",
    "TWT": "TWTUSDT",
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
}


def fetch_daily_klines(symbol: str, limit: int = 1000) -> pd.DataFrame:
    pair = SYMBOL_MAP.get(symbol.upper(), f"{symbol.upper()}USDT")
    with httpx.Client(timeout=60.0) as client:
        r = client.get(
            f"{BINANCE}/api/v3/klines",
            params={"symbol": pair, "interval": "1d", "limit": min(limit, 1000)},
        )
        r.raise_for_status()
        rows = r.json()

    df = pd.DataFrame(
        rows,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore",
        ],
    )
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True).dt.tz_localize(None)
    df["close"] = df["close"].astype(float)
    df["volume_24h"] = df["quote_volume"].astype(float)
    return df[["timestamp", "close", "volume_24h"]]


def fetch_funding_history(symbol: str, limit: int = 500) -> pd.DataFrame:
    """8h funding snapshots aggregated to daily mean."""
    pair = SYMBOL_MAP.get(symbol.upper(), f"{symbol.upper()}USDT")
    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.get(
                f"{BINANCE_FUTURES}/fapi/v1/fundingRate",
                params={"symbol": pair, "limit": min(limit, 1000)},
            )
            r.raise_for_status()
            rows = r.json()
    except Exception:
        return pd.DataFrame(columns=["timestamp", "funding_rate"])

    if not rows:
        return pd.DataFrame(columns=["timestamp", "funding_rate"])

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True).dt.tz_localize(None)
    df["funding_rate"] = df["fundingRate"].astype(float)
    daily = df.groupby(df["timestamp"].dt.date)["funding_rate"].mean().reset_index()
    daily.columns = ["timestamp", "funding_rate"]
    daily["timestamp"] = pd.to_datetime(daily["timestamp"])
    return daily
