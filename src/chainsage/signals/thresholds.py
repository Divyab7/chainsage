"""Quantified scoring thresholds — must match skills/chainsage-conviction-gate/SKILL.md."""

from __future__ import annotations

# Derivatives funding tiers — decimal rate (0.00015 = 0.015%)
DERIVATIVES_TIERS: dict[float, float] = {
    1.0: 0.00015,
    0.5: 0.00008,
    -0.5: -0.00008,
    -1.0: -0.00015,
}

# Any positive funding → +0.5 when tier thresholds rarely fire in historical data
DERIVATIVES_POSITIVE_MILD = True

# On-chain holder_change_7d tiers — decimal (0.03 = 3%)
ONCHAIN_TIERS: dict[float, float] = {
    1.0: 0.03,
    0.5: 0.015,
    -0.5: -0.015,
    -1.0: -0.03,
}

# Narrative tiers
SECTOR_RANK_STRONG_BULL = 5
SECTOR_RANK_MILD_BULL = 10
SECTOR_RANK_MILD_BEAR = 40
SECTOR_RANK_STRONG_BEAR = 50
FNG_STRONG_BULL = 50
FNG_MILD_BULL = 40
FNG_MILD_BEAR = 30
FNG_RISK_OFF = 15

# Gate: sum(layer_scores) >= GATE_THRESHOLD (1.0 for ~25–35% time-in-market; 1.5 = <5% on historical data)
GATE_THRESHOLD = 1.0
MIN_LAYER_SCORE = 0.0  # conservative mode sets 0.5 — all layers must clear this floor
CONFLICT_THRESHOLD = -0.5
ALIGN_THRESHOLD = 0.5  # legacy / diagnostics
MIN_LAYERS_ALIGNED = 2
MAX_POSITION_SIZE = 0.8

# conviction = (sum(layer_scores) + 3) / 6
# target_exposure = conviction * MAX_POSITION_SIZE

# Falsifiers
FNG_HARD_STOP = 15
FUNDING_HARD_STOP = 0.0008  # 0.08%
HARD_STOP_FALSIFIERS = [
    "fng < 15",
    "funding > 0.08%",
]
SOFT_WARNING_FALSIFIERS = [
    "oi_change_24h > 50%",
    "holder_concentration > 0.7",
]
OI_CHANGE_SOFT = 0.50
HOLDER_CONCENTRATION_SOFT = 0.7

# Validation windows
IS_PERIOD_START = "2023-01-01"
IS_PERIOD_END = "2024-06-30"
OOS_PERIOD_START = "2024-07-01"
OOS_PERIOD_END = "2026-06-01"
HELD_OUT_NOTE = "Strategy will be tested on post-June-21 2026 data by judges"

PERFORMANCE_TARGETS = {
    "min_sharpe": 1.2,
    "max_drawdown": 0.20,
    "min_calmar": 1.5,
    "min_win_rate": 0.55,
}

COMMISSION = 0.001
SLIPPAGE = 0.0005
IMPACT_MODEL = "fixed"
ROUND_TRIP_COST = COMMISSION + SLIPPAGE


def tier_score(value: float, tiers: dict[float, float]) -> float:
    """Map a metric to {-1, -0.5, 0, 0.5, 1} using ordered tier thresholds."""
    if value > tiers[1.0]:
        return 1.0
    if value > tiers[0.5]:
        return 0.5
    if value < tiers[-1.0]:
        return -1.0
    if value < tiers[-0.5]:
        return -0.5
    return 0.0
