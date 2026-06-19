"""Institutional risk diagnostics — DSR, PBO, walk-forward, decay."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from chainsage.engine.backtest import run_backtest_period, run_is_oos_headline
from chainsage.engine.decay import analyze_decay
from chainsage.engine.metrics import deflated_sharpe, deflated_sharpe_probability
from chainsage.engine.validation import probability_of_overfitting
from chainsage.engine.walkforward import walk_forward_analysis
from chainsage.signals.thresholds import IS_PERIOD_END, IS_PERIOD_START

N_STRATEGY_VARIANTS = 3  # Conservative, Ensemble, Aggressive


def _strategy_returns_from_equity(equity_curve: list[dict]) -> pd.Series:
    eq = pd.Series([p["strategy"] for p in equity_curve])
    return eq.pct_change().dropna()


def run_institutional_diagnostics(
    df: pd.DataFrame,
    asset: str = "CAKE",
    mode: str = "conservative",
) -> dict[str, Any]:
    """Compute DSR, PBO, walk-forward, and decay for headline conservative CAKE."""
    headline = run_is_oos_headline(df, asset=asset, mode=mode)
    is_block = headline["in_sample"]
    oos_block = headline["out_of_sample"]

    is_sr = float(is_block["metrics"]["sharpe_ratio"])
    n_obs = max(len(is_block.get("equity_curve", [])) - 1, 30)

    is_returns = _strategy_returns_from_equity(is_block["equity_curve"])
    skew = float(is_returns.skew()) if len(is_returns) > 3 else 0.0
    kurt = float(is_returns.kurtosis()) + 3.0 if len(is_returns) > 3 else 3.0

    trial_returns: list[pd.Series] = []
    for trial_mode in ("conservative", "ensemble", "aggressive"):
        trial_is = run_backtest_period(
            df, IS_PERIOD_START, IS_PERIOD_END, asset=asset, mode=trial_mode
        )
        trial_returns.append(_strategy_returns_from_equity(trial_is["equity_curve"]))

    dsr = deflated_sharpe(
        is_sr,
        n_trials=N_STRATEGY_VARIANTS,
        n_observations=n_obs,
        skew=skew,
        kurtosis=kurt,
    )
    dsr_prob = deflated_sharpe_probability(
        is_sr,
        n_trials=N_STRATEGY_VARIANTS,
        n_observations=n_obs,
        skew=skew,
        kurtosis=kurt,
    )
    pbo = probability_of_overfitting(is_returns, n_partitions=10, trial_returns=trial_returns)
    wf = walk_forward_analysis(
        df,
        asset,
        mode=mode,
        train_months=6,
        test_months=3,
        max_windows=12,
    )
    decay = analyze_decay(is_block, oos_block)

    return {
        "asset": asset,
        "mode": mode,
        "is_period": f"{IS_PERIOD_START} → {IS_PERIOD_END}",
        "standard_sharpe_is": round(is_sr, 2),
        "deflated_sharpe": dsr,
        "deflated_sharpe_probability": dsr_prob,
        "n_trials": N_STRATEGY_VARIANTS,
        "n_observations": n_obs,
        "pbo": pbo,
        "walk_forward": {
            "n_windows": wf["n_windows"],
            "mean_sharpe": wf["mean_sharpe"],
            "std_sharpe": wf["std_sharpe"],
            "wf_sharpe_label": wf.get("wf_sharpe_label", "—"),
            "train_months": wf["train_months"],
            "test_months": wf["test_months"],
        },
        "decay": decay,
    }


def write_institutional_risk_report(
    df: pd.DataFrame,
    asset: str = "CAKE",
    mode: str = "conservative",
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    """Write ``reports/institutional_risk.json`` and return diagnostics."""
    out = run_institutional_diagnostics(df, asset=asset, mode=mode)
    root = Path(__file__).resolve().parents[3]
    dest = reports_dir or root / "reports"
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "institutional_risk.json"
    import json

    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out
