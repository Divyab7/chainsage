"""Score on-chain layer from get_crypto_metrics holder_change_7d."""

from __future__ import annotations

import pandas as pd

from chainsage.signals.thresholds import ONCHAIN_TIERS, tier_score


def _holder_change_7d(row: pd.Series) -> float:
    if "holder_change_7d" in row and pd.notna(row["holder_change_7d"]):
        return float(row["holder_change_7d"])
    return float(row.get("holder_trend", 0.0)) * 0.1


def score_onchain(row: pd.Series, history: pd.DataFrame) -> tuple[float, list[str]]:
    h = _holder_change_7d(row)
    score = tier_score(h, ONCHAIN_TIERS)
    labels = {
        1.0: f"holder_change_7d {h:.1%} > 3% → +1.0",
        0.5: f"holder_change_7d {h:.1%} > 1.5% → +0.5",
        0.0: "holder_change_7d neutral → 0.0",
        -0.5: f"holder_change_7d {h:.1%} < -1.5% → -0.5",
        -1.0: f"holder_change_7d {h:.1%} < -3% → -1.0",
    }
    return score, [labels[score]]
