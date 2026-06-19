"""Regime-adaptive ensemble: mean reversion in high vol, momentum gates otherwise."""

from __future__ import annotations

from typing import Callable

import pandas as pd

from chainsage.signals.fusion import Decision, evaluate_snapshot
from chainsage.signals.mean_reversion import FundingMeanReversion
from chainsage.signals.regime import detect_volatility_regime

DecisionFn = Callable[[pd.DataFrame, int, str], Decision]


class MomentumGates:
    """Current conviction-gated multi-layer strategy."""

    name = "momentum_gates"

    def evaluate(self, df: pd.DataFrame, idx: int, asset: str = "BNB") -> Decision:
        decision = evaluate_snapshot(df, idx, asset=asset)
        decision.sub_strategy = self.name
        if decision.regime == "aligned":
            decision.regime = "low-vol-momentum"
        return decision


def select_strategy(volatility_regime: str) -> FundingMeanReversion | MomentumGates:
    """Use mean reversion in high vol, momentum in low/normal vol."""
    if volatility_regime == "high":
        return FundingMeanReversion()
    return MomentumGates()


def evaluate_snapshot_ensemble(
    df: pd.DataFrame,
    idx: int,
    asset: str = "BNB",
) -> Decision:
    vol_regime, atr = detect_volatility_regime(df, idx)

    if vol_regime == "high":
        mr = FundingMeanReversion()
        decision = mr.evaluate(df, idx, asset=asset, volatility_regime=vol_regime)
        if decision.signal == "long":
            decision.sub_strategy = mr.name
            decision.layers.setdefault(
                "ensemble",
                {
                    "score": 1.0,
                    "reasons": [
                        f"volatility_regime={vol_regime}",
                        f"atr14_pct={atr:.2%}",
                        f"sub_strategy={mr.name}",
                    ],
                },
            )
            return decision
        # No MR edge — fall back to momentum in high vol
        vol_regime = "normal"

    strategy = MomentumGates()
    decision = strategy.evaluate(df, idx, asset=asset)
    decision.sub_strategy = strategy.name
    decision.layers.setdefault(
        "ensemble",
        {
            "score": 1.0 if decision.signal == "long" else 0.0,
            "reasons": [
                f"volatility_regime={vol_regime}",
                f"atr14_pct={atr:.2%}",
                f"sub_strategy={strategy.name}",
            ],
        },
    )
    return decision


def get_decision_fn(mode: str) -> DecisionFn:
    modes: dict[str, DecisionFn] = {
        "aggressive": evaluate_snapshot,
        "ensemble": evaluate_snapshot_ensemble,
        "conservative": evaluate_snapshot,
    }
    if mode not in modes:
        raise ValueError(f"Unknown strategy mode: {mode}. Choose: {', '.join(modes)}")
    return modes[mode]
