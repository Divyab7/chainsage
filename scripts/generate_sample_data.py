"""Generate committed sample market data for reproducible backtests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

ASSETS = {
    "BNB": {"start": 220.0, "drift": 0.0004, "vol": 0.025},
    "CAKE": {"start": 2.5, "drift": 0.0002, "vol": 0.035},
    "TWT": {"start": 1.1, "drift": 0.00015, "vol": 0.03},
    "BTC": {"start": 42000.0, "drift": 0.0003, "vol": 0.022},
}


def generate_asset(symbol: str, days: int = 400, seed: int = 42) -> pd.DataFrame:
    cfg = ASSETS[symbol]
    rng = np.random.default_rng(seed + hash(symbol) % 1000)
    dates = pd.date_range("2024-01-01", periods=days, freq="D")
    returns = rng.normal(cfg["drift"], cfg["vol"], days)
    prices = cfg["start"] * np.cumprod(1 + returns)
    volumes = rng.lognormal(mean=18, sigma=0.3, size=days)
    fg = np.clip(50 + np.cumsum(rng.normal(0, 2, days)), 10, 90)
    funding = np.clip(rng.normal(0.0001, 0.0002, days), -0.001, 0.001)
    holder = np.clip(np.cumsum(rng.normal(0, 0.02, days)), -0.5, 0.5)
    narrative = np.clip(np.sin(np.arange(days) / 30) * 0.4 + rng.normal(0, 0.1, days), -0.5, 0.8)

    return pd.DataFrame(
        {
            "timestamp": dates,
            "close": prices,
            "volume_24h": volumes,
            "fear_greed": fg,
            "funding_rate": funding,
            "holder_trend": holder,
            "narrative_score": narrative,
        }
    )


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    for symbol in ASSETS:
        df = generate_asset(symbol)
        path = DATA / f"{symbol.lower()}_daily.csv"
        df.to_csv(path, index=False)
        print(f"Wrote {path} ({len(df)} rows)")


if __name__ == "__main__":
    main()
