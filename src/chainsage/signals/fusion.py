"""Conviction gate: only trade when independent layers align."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from chainsage.signals import thresholds as t
from chainsage.signals.derivatives import score_derivatives
from chainsage.signals.narrative import score_narrative
from chainsage.signals.onchain import score_onchain


def compute_conviction(layer_scores: list[float]) -> float:
    """conviction = (sum(layer_scores) + 3) / 6, clamped to [0, 1]."""
    raw = sum(layer_scores)
    normalized = (raw + 3.0) / 6.0
    return round(min(1.0, max(0.0, normalized)), 3)


def compute_target_exposure(conviction: float, signal: str) -> float:
    if signal != "long":
        return 0.0
    return round(conviction * t.MAX_POSITION_SIZE, 3)


@dataclass
class LayerResult:
    name: str
    score: float
    reasons: list[str]


@dataclass
class Decision:
    timestamp: str
    asset: str
    signal: str
    conviction: float
    target_exposure: float
    regime: str
    layers: dict[str, dict[str, Any]]
    falsifiers: list[str]
    falsifier_warnings: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    sub_strategy: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "timestamp": self.timestamp,
            "asset": self.asset,
            "signal": self.signal,
            "conviction": round(self.conviction, 3),
            "target_exposure": round(self.target_exposure, 3),
            "regime": self.regime,
            "layers": self.layers,
            "falsifiers": self.falsifiers,
            "falsifier_warnings": self.falsifier_warnings,
            "reasons": self.reasons,
        }
        if self.sub_strategy:
            out["sub_strategy"] = self.sub_strategy
        return out


def _layer_dict(layer: LayerResult) -> dict[str, Any]:
    return {"score": round(layer.score, 3), "reasons": layer.reasons}


def _check_falsifiers(row: pd.Series) -> tuple[list[str], list[str]]:
    hard: list[str] = []
    soft: list[str] = []

    fg = float(row.get("fear_greed", 50.0))
    funding = float(row.get("funding_rate", 0.0))
    oi_chg = float(row.get("oi_change_24h", 0.0))
    concentration = float(row.get("holder_concentration", 0.0))

    if fg < t.FNG_HARD_STOP:
        hard.append(t.HARD_STOP_FALSIFIERS[0] if t.HARD_STOP_FALSIFIERS else f"fng < {t.FNG_HARD_STOP}")
    if funding > t.FUNDING_HARD_STOP:
        label = (
            t.HARD_STOP_FALSIFIERS[1]
            if len(t.HARD_STOP_FALSIFIERS) > 1
            else f"funding > {t.FUNDING_HARD_STOP:.4%}"
        )
        hard.append(label)
    if oi_chg > t.OI_CHANGE_SOFT:
        soft.append(
            t.SOFT_WARNING_FALSIFIERS[0]
            if t.SOFT_WARNING_FALSIFIERS
            else f"oi_change_24h > {t.OI_CHANGE_SOFT:.0%}"
        )
    if concentration > t.HOLDER_CONCENTRATION_SOFT:
        soft.append(
            t.SOFT_WARNING_FALSIFIERS[1]
            if len(t.SOFT_WARNING_FALSIFIERS) > 1
            else f"holder_concentration > {t.HOLDER_CONCENTRATION_SOFT}"
        )

    return hard, soft


def evaluate_snapshot(
    df: pd.DataFrame,
    idx: int,
    asset: str = "BNB",
) -> Decision:
    row = df.iloc[idx]
    history = df.iloc[: idx + 1]
    ts = str(row["timestamp"])[:10]

    if not bool(row.get("cmc_data_complete", True)):
        return Decision(
            timestamp=ts,
            asset=asset,
            signal="flat",
            conviction=0.0,
            target_exposure=0.0,
            regime="data-incomplete",
            layers={},
            falsifiers=["CMC MCP data incomplete — do not trade"],
            reasons=["Required CMC tool payload missing for this asset"],
        )

    deriv = LayerResult("derivatives", *score_derivatives(row, history))
    chain = LayerResult("onchain", *score_onchain(row, history))
    narr = LayerResult("narrative", *score_narrative(row, history))
    layers = [deriv, chain, narr]
    layer_scores = [deriv.score, chain.score, narr.score]
    layer_sum = sum(layer_scores)

    hard_stop, soft_warn = _check_falsifiers(row)
    bearish = sum(1 for layer in layers if layer.score <= t.CONFLICT_THRESHOLD)
    bullish = sum(1 for layer in layers if layer.score > 0)
    strong_conflict = bullish >= 1 and bearish >= 1

    layer_dict = {
        "derivatives": _layer_dict(deriv),
        "onchain": _layer_dict(chain),
        "narrative": _layer_dict(narr),
    }

    if hard_stop:
        return Decision(
            timestamp=ts,
            asset=asset,
            signal="flat",
            conviction=0.0,
            target_exposure=0.0,
            regime="risk-off" if any("fng" in h for h in hard_stop) else "divergent",
            layers=layer_dict,
            falsifiers=hard_stop,
            falsifier_warnings=soft_warn,
            reasons=["hard_stop falsifier — immediate flat, conviction = 0"],
            sub_strategy="momentum_gates",
        )

    if strong_conflict:
        return Decision(
            timestamp=ts,
            asset=asset,
            signal="flat",
            conviction=0.0,
            target_exposure=0.0,
            regime="divergent",
            layers=layer_dict,
            falsifiers=[],
            falsifier_warnings=soft_warn,
            reasons=["layers disagree — default flat"],
            sub_strategy="momentum_gates",
        )

    if layer_sum >= t.GATE_THRESHOLD and bearish == 0:
        if t.MIN_LAYER_SCORE > 0 and any(layer.score < t.MIN_LAYER_SCORE for layer in layers):
            pass  # fall through to flat
        else:
            conviction = compute_conviction(layer_scores)
            target = compute_target_exposure(conviction, "long")
            return Decision(
                timestamp=ts,
                asset=asset,
                signal="long",
                conviction=conviction,
                target_exposure=target,
                regime="aligned",
                layers=layer_dict,
                falsifiers=[],
                falsifier_warnings=soft_warn,
                reasons=[
                    f"layer sum {layer_sum:.2f} >= {t.GATE_THRESHOLD}",
                    f"all layers >= {t.MIN_LAYER_SCORE}" if t.MIN_LAYER_SCORE > 0 else f"no layer <= {t.CONFLICT_THRESHOLD}",
                ],
                sub_strategy="momentum_gates",
            )

    return Decision(
        timestamp=ts,
        asset=asset,
        signal="flat",
        conviction=0.0,
        target_exposure=0.0,
        regime="divergent",
        layers=layer_dict,
        falsifiers=[],
        falsifier_warnings=soft_warn,
        reasons=["insufficient alignment — default flat"],
        sub_strategy="momentum_gates",
    )
