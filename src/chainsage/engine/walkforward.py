"""Expanding-window walk-forward validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from chainsage.engine.backtest import load_market_csv, run_backtest_period


def walk_forward_analysis(
    df: pd.DataFrame,
    asset: str,
    *,
    mode: str = "conservative",
    train_months: int = 6,
    test_months: int = 3,
    max_windows: int = 12,
    warmup: int = 35,
    period_start: str | None = None,
    period_end: str | None = None,
) -> dict[str, Any]:
    """
    Expanding-window validation — train on [start:t], test on [t+1:t+test].

    Each window expands the training horizon by ``test_months`` while holding
    a fixed ``test_months`` OOS slice. Strategy parameters are not re-fit per
    window (structure is fixed); this measures regime-timing robustness.
    """
    ts = pd.to_datetime(df["timestamp"])
    df = df.copy()
    df["timestamp"] = ts

    if period_start:
        df = df[df["timestamp"] >= pd.Timestamp(period_start)]
    if period_end:
        df = df[df["timestamp"] <= pd.Timestamp(period_end)]

    origin = df["timestamp"].min()
    end_limit = df["timestamp"].max()

    windows: list[dict[str, Any]] = []
    for w in range(max_windows):
        train_end = origin + pd.DateOffset(months=train_months + w * test_months)
        test_start = train_end + pd.DateOffset(days=1)
        test_end = test_start + pd.DateOffset(months=test_months) - pd.DateOffset(days=1)
        if test_end > end_limit:
            break

        test_start_s = test_start.strftime("%Y-%m-%d")
        test_end_s = test_end.strftime("%Y-%m-%d")
        test_slice = df[(df["timestamp"] >= test_start) & (df["timestamp"] <= test_end)]
        if len(test_slice) <= warmup + 5:
            continue

        try:
            bt = run_backtest_period(
                df,
                test_start_s,
                test_end_s,
                asset=asset,
                mode=mode,
                warmup=warmup,
            )
        except (ValueError, AssertionError):
            continue

        windows.append(
            {
                "window": w + 1,
                "train_end": train_end.strftime("%Y-%m-%d"),
                "test_start": test_start_s,
                "test_end": test_end_s,
                "sharpe": bt["metrics"]["sharpe_ratio"],
                "return": bt["metrics"]["total_return"],
            }
        )

    sharpes = [w["sharpe"] for w in windows]
    return {
        "asset": asset,
        "mode": mode,
        "train_months": train_months,
        "test_months": test_months,
        "n_windows": len(windows),
        "windows": windows,
        "mean_sharpe": round(float(np.mean(sharpes)), 2) if sharpes else 0.0,
        "std_sharpe": round(float(np.std(sharpes)), 2) if sharpes else 0.0,
        "wf_sharpe_label": (
            f"{round(float(np.mean(sharpes)), 2):.2f} ± {round(float(np.std(sharpes)), 2):.2f}"
            if sharpes
            else "—"
        ),
    }


def walk_forward_from_csv(
    path: str | Path,
    asset: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience wrapper loading a committed daily CSV."""
    df = load_market_csv(Path(path))
    return walk_forward_analysis(df, asset, **kwargs)
