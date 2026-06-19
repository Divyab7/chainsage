"""Score derivatives layer from get_global_crypto_derivatives_metrics funding rate."""

from __future__ import annotations

import pandas as pd

from chainsage.signals.thresholds import DERIVATIVES_POSITIVE_MILD, DERIVATIVES_TIERS, tier_score


def score_derivatives(row: pd.Series, history: pd.DataFrame) -> tuple[float, list[str]]:
    funding = float(row.get("funding_rate", 0.0))
    score = tier_score(funding, DERIVATIVES_TIERS)
    if score == 0.0 and DERIVATIVES_POSITIVE_MILD and funding > 0:
        return 0.5, ["funding > 0 → +0.5 (positive carry)"]
    labels = {
        1.0: "funding > 0.015% → +1.0",
        0.5: "funding > 0.008% → +0.5",
        0.0: "funding neutral → 0.0",
        -0.5: "funding < -0.008% → -0.5",
        -1.0: "funding < -0.015% → -1.0",
    }
    return score, [labels[score]]
