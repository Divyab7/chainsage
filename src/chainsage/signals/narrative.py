"""Score narrative layer: sector rank + Fear & Greed."""

from __future__ import annotations

import pandas as pd

from chainsage.signals.thresholds import (
    FNG_MILD_BEAR,
    FNG_MILD_BULL,
    FNG_RISK_OFF,
    FNG_STRONG_BULL,
    SECTOR_RANK_MILD_BEAR,
    SECTOR_RANK_MILD_BULL,
    SECTOR_RANK_STRONG_BEAR,
    SECTOR_RANK_STRONG_BULL,
)


def _sector_rank(row: pd.Series) -> int:
    if "sector_rank" in row and pd.notna(row["sector_rank"]):
        return int(row["sector_rank"])
    narrative = float(row.get("narrative_score", 0.0))
    if narrative > 0.5:
        return 5
    if narrative > 0.2:
        return 15
    if narrative < -0.2:
        return 55
    return 30


def score_narrative(row: pd.Series, history: pd.DataFrame) -> tuple[float, list[str]]:
    fg = float(row.get("fear_greed", 50.0))
    rank = _sector_rank(row)

    if rank <= SECTOR_RANK_STRONG_BULL and fg >= FNG_STRONG_BULL:
        score, label = 1.0, f"sector_rank {rank} <= 5 AND fng {fg:.0f} >= 50 → +1.0"
    elif rank <= SECTOR_RANK_MILD_BULL and fg >= FNG_MILD_BULL:
        score, label = 0.5, f"sector_rank {rank} <= 10 AND fng {fg:.0f} >= 40 → +0.5"
    elif fg < FNG_RISK_OFF or rank > SECTOR_RANK_STRONG_BEAR:
        score, label = -1.0, f"fng < 15 OR sector_rank {rank} > 50 → -1.0"
    elif fg < FNG_MILD_BEAR or rank > SECTOR_RANK_MILD_BEAR:
        score, label = -0.5, f"fng < 30 OR sector_rank {rank} > 40 → -0.5"
    else:
        score, label = 0.0, f"sector_rank {rank}, fng {fg:.0f} → 0.0"

    return score, [label]
