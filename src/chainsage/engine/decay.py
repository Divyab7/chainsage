"""IS-to-OOS strategy decay analysis."""

from __future__ import annotations

from typing import Any


def analyze_decay(is_results: dict[str, Any], oos_results: dict[str, Any]) -> dict[str, Any]:
    """
    Measure in-sample to out-of-sample Sharpe decay.

    ``decay_ratio`` = OOS Sharpe / IS Sharpe (0 when IS Sharpe is zero).
    ``decay_pct`` = percent erosion from IS to OOS.
    """
    is_sr = float(is_results.get("metrics", {}).get("sharpe_ratio", 0.0))
    oos_sr = float(oos_results.get("metrics", {}).get("sharpe_ratio", 0.0))

    if abs(is_sr) < 1e-9:
        decay_ratio = 0.0
    else:
        decay_ratio = round(oos_sr / is_sr, 2)

    decay_pct = round((1.0 - decay_ratio) * 100.0, 1) if is_sr != 0 else 100.0

    if decay_ratio >= 0.8:
        interpretation = "edge_preserved"
    elif decay_ratio >= 0.5:
        interpretation = "partial_decay"
    elif decay_ratio > 0.0:
        interpretation = "significant_decay"
    else:
        interpretation = "regime_mismatch"

    return {
        "is_sharpe": round(is_sr, 2),
        "oos_sharpe": round(oos_sr, 2),
        "decay_ratio": decay_ratio,
        "decay_pct": decay_pct,
        "interpretation": interpretation,
        "conclusion": (
            "Edge not preserved in OOS regime"
            if decay_ratio < 0.5
            else "Partial edge retention across regimes"
        ),
    }
