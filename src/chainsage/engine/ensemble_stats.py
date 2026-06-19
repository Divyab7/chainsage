"""Ensemble regime statistics for research and SKILL.md headlines."""

from __future__ import annotations

from typing import Any

import pandas as pd

from chainsage.engine.backtest import load_market_csv, run_backtest_period
from chainsage.engine.metrics import sharpe_ratio
from chainsage.signals.mean_reversion import FundingMeanReversion
from chainsage.signals.regime import detect_volatility_regime
from chainsage.signals.thresholds import OOS_PERIOD_END, OOS_PERIOD_START

ROOT_DATA = __import__("pathlib").Path(__file__).resolve().parents[2] / "data"


def ensemble_oos_summary(df: pd.DataFrame, asset: str = "CAKE", warmup: int = 35) -> dict[str, Any]:
    """OOS breakdown: high-vol share and mean-reversion sub-strategy Sharpe."""
    oos = df[(df["timestamp"] >= OOS_PERIOD_START) & (df["timestamp"] <= OOS_PERIOD_END)].copy()
    oos = oos.reset_index(drop=True)
    if len(oos) <= warmup:
        return {}

    mr = FundingMeanReversion()
    regimes: list[str] = []
    mr_returns: list[float] = []
    mr_exposure: list[float] = []

    for i in range(len(oos)):
        if i < warmup:
            continue
        vol_regime, _ = detect_volatility_regime(oos, i)
        regimes.append(vol_regime)
        decision = mr.evaluate(oos, i, asset=asset, volatility_regime=vol_regime)
        exp = decision.target_exposure if decision.signal == "long" else 0.0
        mr_exposure.append(exp)
        ret = float(oos.iloc[i]["close"]) / float(oos.iloc[i - 1]["close"]) - 1.0
        prev_exp = mr_exposure[-2] if len(mr_exposure) > 1 else 0.0
        mr_returns.append(prev_exp * ret)

    n = len(regimes)
    high_pct = regimes.count("high") / n if n else 0.0
    mr_series = pd.Series(mr_returns)
    mr_sharpe = sharpe_ratio(mr_series) if len(mr_series) > 5 else 0.0

    full_oos = run_backtest_period(df, OOS_PERIOD_START, OOS_PERIOD_END, asset=asset, mode="ensemble")

    return {
        "asset": asset,
        "oos_period": f"{OOS_PERIOD_START} to {OOS_PERIOD_END}",
        "high_vol_pct": round(high_pct, 3),
        "mean_reversion_oos_sharpe": round(mr_sharpe, 3),
        "ensemble_oos_sharpe": full_oos["metrics"]["sharpe_ratio"],
        "ensemble_oos_return": full_oos["metrics"]["total_return"],
        "volatility_regime_counts": full_oos.get("volatility_regime_counts", {}),
        "sub_strategy_counts": full_oos.get("sub_strategy_counts", {}),
    }


def write_ensemble_headline(assets: tuple[str, ...] = ("CAKE", "BNB")) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for asset in assets:
        path = ROOT_DATA / f"{asset.lower()}_daily.csv"
        if not path.exists():
            continue
        df = load_market_csv(path)
        out[asset] = ensemble_oos_summary(df, asset=asset)
    return out
