"""OOS sensitivity / robustness analysis (±10% threshold perturbation)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from chainsage.engine.backtest import filter_period, run_backtest
from chainsage.signals.threshold_overrides import apply_threshold_scale
from chainsage.signals.thresholds import OOS_PERIOD_END, OOS_PERIOD_START


def _oos_sharpe(df: pd.DataFrame, asset: str, warmup: int = 35) -> float:
    window = filter_period(df, OOS_PERIOD_START, OOS_PERIOD_END)
    if len(window) <= warmup:
        return 0.0
    result = run_backtest(
        window,
        asset=asset,
        warmup=warmup,
        period_start=OOS_PERIOD_START,
        period_end=OOS_PERIOD_END,
    )
    return float(result["metrics"]["sharpe_ratio"])


def run_sensitivity_analysis(df: pd.DataFrame, asset: str = "BNB") -> dict[str, Any]:
    """Perturb thresholds ±10%; flag if OOS Sharpe drops below 1.0."""
    scenarios = [
        ("Base case", {}),
        ("Funding threshold +10%", {"funding": 1.10}),
        ("Holder threshold -10%", {"holder": 0.90}),
        ("All gates +10%", {"funding": 1.10, "holder": 1.10, "narrative": 1.10, "gates": 1.10}),
    ]

    rows: list[dict[str, Any]] = []
    base_sharpe: float | None = None

    for label, kwargs in scenarios:
        with apply_threshold_scale(**kwargs):
            sharpe = _oos_sharpe(df, asset)
        if base_sharpe is None:
            base_sharpe = sharpe
            impact = "—"
        else:
            if base_sharpe != 0:
                pct = (sharpe - base_sharpe) / abs(base_sharpe) * 100
                impact = f"{pct:+.0f}%"
            else:
                impact = "n/a"
        rows.append(
            {
                "scenario": label,
                "oos_sharpe": round(sharpe, 2),
                "impact": impact,
            }
        )

    fragile = any(r["oos_sharpe"] < 1.0 for r in rows)
    robust = not fragile and all(
        r["oos_sharpe"] >= (base_sharpe or 0) * 0.85 for r in rows[1:]
    )

    return {
        "asset": asset,
        "oos_period": f"{OOS_PERIOD_START} to {OOS_PERIOD_END}",
        "base_oos_sharpe": base_sharpe,
        "rows": rows,
        "fragile": fragile,
        "robust": robust,
        "conclusion": (
            "Strategy is fragile to threshold perturbation (OOS Sharpe < 1.0)."
            if fragile
            else "Strategy is robust to single-parameter perturbation."
        ),
    }


def render_robustness_section(analysis: dict[str, Any]) -> str:
    lines = [
        "## Robustness Check",
        "",
        f"OOS window: {analysis['oos_period']} · Asset: {analysis['asset']}",
        "",
        "| Parameter Change | OOS Sharpe | Impact |",
        "|------------------|----------:|--------|",
    ]
    for row in analysis["rows"]:
        lines.append(
            f"| {row['scenario']} | {row['oos_sharpe']:.2f} | {row['impact']} |"
        )
    lines.extend(["", analysis["conclusion"], ""])
    return "\n".join(lines)
