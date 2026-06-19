"""Event study: forward returns by conviction regime."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from chainsage.signals.fusion import evaluate_snapshot

FORWARD_WINDOWS = (7, 30)


def run_event_study(df: pd.DataFrame, asset: str, warmup: int = 35) -> dict[str, Any]:
    """
    Bucket each day by regime (aligned / divergent / risk-off).
    Measure forward close-to-close returns (no lookahead on signal).
    """
    rows: list[dict[str, Any]] = []

    for i in range(warmup, len(df) - max(FORWARD_WINDOWS)):
        decision = evaluate_snapshot(df, i, asset=asset)
        close = float(df.iloc[i]["close"])
        fwd: dict[str, float] = {}
        for w in FORWARD_WINDOWS:
            if i + w < len(df):
                fwd[f"fwd_{w}d"] = float(df.iloc[i + w]["close"] / close - 1)

        rows.append(
            {
                "timestamp": str(df.iloc[i]["timestamp"])[:10],
                "regime": decision.regime,
                "signal": decision.signal,
                **fwd,
            }
        )

    study = pd.DataFrame(rows)
    if study.empty:
        return {"asset": asset, "buckets": {}, "rows": []}

    buckets: dict[str, dict[str, Any]] = {}
    for regime in ("aligned", "divergent", "risk-off"):
        sub = study[study["regime"] == regime]
        if sub.empty:
            continue
        buckets[regime] = {
            "count": int(len(sub)),
            "fwd_7d_mean": float(sub["fwd_7d"].mean()),
            "fwd_7d_hit_rate": float((sub["fwd_7d"] > 0).mean()),
            "fwd_30d_mean": float(sub["fwd_30d"].mean()),
            "fwd_30d_hit_rate": float((sub["fwd_30d"] > 0).mean()),
        }

    return {"asset": asset, "buckets": buckets, "rows": rows}


def render_event_study_section(results: list[dict[str, Any]]) -> str:
    lines = ["## Event Study (forward returns by regime)", ""]
    lines.append(
        "When layers align (`aligned`), forward returns should beat `divergent` / `risk-off` buckets."
    )
    lines.append("")
    lines.append("| Asset | Regime | Days | 7d mean | 7d hit% | 30d mean | 30d hit% |")
    lines.append("|-------|--------|-----:|--------:|--------:|---------:|---------:|")
    for r in results:
        asset = r["asset"]
        for regime, b in r.get("buckets", {}).items():
            lines.append(
                f"| {asset} | {regime} | {b['count']} | {b['fwd_7d_mean']:.1%} | "
                f"{b['fwd_7d_hit_rate']:.0%} | {b['fwd_30d_mean']:.1%} | {b['fwd_30d_hit_rate']:.0%} |"
            )
    lines.append("")
    return "\n".join(lines)
